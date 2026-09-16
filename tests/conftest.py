import json
from datetime import UTC, datetime

import pytest

from sls_orcamento_pdd.config import Settings
from sls_orcamento_pdd.services.extract import discover, parse_activity, snapshot


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        MONDAY_BOARD_ID=42,
        MONDAY_STATUS_COLUMN_ID="status_19",
        MONDAY_API_TOKEN="test-only",
        runtime_dir=tmp_path,
        backfill_from="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def board():
    return {
        "id": "42",
        "name": "Test board",
        "items_count": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "columns": [
            {
                "id": "status_19",
                "title": "Status",
                "type": "status",
                "settings_str": json.dumps(
                    {"labels": {"7": "Entrada", "0": "Elaboração", "8": "Encerrado"}}
                ),
            },
            {"id": "brand_x", "title": "Marca", "type": "text"},
            {"id": "talent_x", "title": "Talentos Exclusivos", "type": "dropdown"},
            {"id": "inter_x", "title": "Interveniência", "type": "text"},
            {"id": "owner_x", "title": "Orçamento", "type": "people"},
        ],
    }


def at(hour=12, day=2):
    return datetime(2026, 1, day, hour, tzinfo=UTC)


def raw_event(event_id="1", hour=8, before=7, after=0, changed_at=None):
    labels = {7: "Entrada", 0: "Elaboração", 8: "Encerrado"}
    value = {"label": {"index": after, "text": labels[after]}}
    if changed_at is not None:
        value["changed_at"] = changed_at
    return {
        "id": event_id,
        "event": "update_column_value",
        "created_at": str(int(at(hour).timestamp()) * 10_000_000),
        "data": json.dumps(
            {
                "pulse_id": 123,
                "column_id": "status_19",
                "value": value,
                "previous_value": {"label": {"index": before, "text": labels[before]}},
            }
        ),
    }


def raw_item(status=0):
    return {
        "id": "123",
        "name": "Projeto teste",
        "created_at": "2026-01-02T02:00:00Z",
        "updated_at": "2026-01-02T08:00:00Z",
        "state": "active",
        "group": {"id": "group"},
        "column_values": [
            {"id": "status_19", "text": "", "value": json.dumps({"index": status})},
            {"id": "brand_x", "text": "Marca A", "value": None},
            {
                "id": "owner_x",
                "value": json.dumps({"personsAndTeams": [{"id": 99, "kind": "person"}]}),
            },
        ],
    }


@pytest.fixture
def sample(settings, board):
    mapping, statuses, labels = discover(board, settings)
    return (
        [parse_activity(raw_event(), settings, at())],
        [snapshot(raw_item(), mapping, labels, settings, at())],
        statuses,
    )


class FakeMonday:
    """Deterministic Monday double shared by cloud and migration tests."""

    def __init__(self, board, fail=False):
        self.schema = board
        self.pages_items = self.pages_logs = self.calls = 0
        self.fail = fail

    def board(self):
        return self.schema

    def item_pages(self):
        self.pages_items += 1
        yield [raw_item()]

    def users(self, ids):
        return [{"id": "99", "name": "Pessoa teste", "email": None}]

    def activity_page(self, page, start, end):
        if self.fail:
            raise RuntimeError("Falha de extração simulada")
        self.pages_logs += 1
        return [raw_event()] if page == 1 else []
