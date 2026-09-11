"""Real PostgreSQL tests. Opt in; each session uses an isolated test schema."""

import copy
import os
import uuid
from datetime import timedelta

import pytest
from conftest import at, raw_event, raw_item
from sqlalchemy import text
from sqlalchemy.exc import DataError, IntegrityError

from sls_orcamento_pdd.config import Settings
from sls_orcamento_pdd.db.postgres import PostgresStore
from sls_orcamento_pdd.pipelines.runner import run

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_TESTS") != "1", reason="PostgreSQL opt-in"
)


@pytest.fixture
def pg_settings(tmp_path):
    return Settings(
        MONDAY_BOARD_ID=42,
        MONDAY_STATUS_COLUMN_ID="status_19",
        pg_schema="sla_test_" + uuid.uuid4().hex[:12],
        runtime_dir=tmp_path,
        backfill_from="2026-01-01T00:00:00Z",
    )


class FakeMonday:
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


def test_real_postgres_idempotence_incremental_and_failure(pg_settings, board):
    store = PostgresStore(pg_settings)
    first = run(pg_settings, "backfill", client=FakeMonday(board), store=store, at=at())
    second = run(pg_settings, "daily", client=FakeMonday(board), store=store, at=at())
    assert first["new_events"] == 1
    assert second["new_events"] == second["new_intervals"] == 0
    assert len(store.read("bronze_monday_activity_log_raw")) == 1
    assert len(store.read("bronze_monday_item_snapshot_raw")) == 1
    before = store.read("etl_watermark")
    with pytest.raises(RuntimeError, match="simulada"):
        run(
            pg_settings,
            client=FakeMonday(board, fail=True),
            store=store,
            at=at() + timedelta(hours=1),
        )
    assert store.read("etl_watermark") == before
    assert len(store.read("fct_item_status_interval")) == 2
    with store.engine.connect() as conn:
        result = conn.execute(
            text(
                f"SELECT SUM(accumulated_minutes) FROM {pg_settings.pg_schema}.gold_status_metrics"
            )
        ).scalar()
        assert result == 600


def test_transaction_rollback_and_advisory_lock(pg_settings, board):
    store = PostgresStore(pg_settings)
    run(pg_settings, "backfill", client=FakeMonday(board), store=store, at=at())
    before = copy.deepcopy(store.read("fct_item_status_interval"))
    with pytest.raises(DataError):
        store.commit(
            {"fct_item_status_interval": [], "dim_item": [{"item_id": "invalid-bigint"}]}, 42
        )
    assert store.read("fct_item_status_interval") == before
    with store.lock(), pytest.raises(RuntimeError, match="ativa"), store.lock():
        pass


def test_board_count_mismatch_preserves_watermark(pg_settings, board):
    store = PostgresStore(pg_settings)
    board["items_count"] = 2
    with pytest.raises(ValueError, match="extração"):
        run(pg_settings, client=FakeMonday(board), store=store, at=at())
    assert store.read("etl_watermark") == []


def test_foreign_keys_reject_orphan_and_original_item_id_is_preserved(pg_settings, board):
    store = PostgresStore(pg_settings)
    run(pg_settings, "backfill", client=FakeMonday(board), store=store, at=at())
    assert store.read("dim_item")[0]["item_id"] == 123
    assert (
        store.read("dim_item")[0]["item_sk"] == store.read("fct_item_status_interval")[0]["item_sk"]
    )
    assert store.read("dim_board")[0]["board_id"] == 42
    catalog = store.read("meta_column_mapping")
    assert (
        next(c for c in catalog if c["column_id"] == "brand_x")["analytical_attribute"] == "marca"
    )
    original = store.read("dim_item")[0]
    with pytest.raises(IntegrityError):
        store.commit({"dim_item": [{**original, "current_status_id": "nonexistent-status"}]}, 42)
    assert store.read("dim_item")[0]["current_status_id"] == original["current_status_id"]
    with pytest.raises(IntegrityError), store.engine.begin() as conn:
        # A manual mismatch between natural ID and SK must be rejected too.
        conn.execute(
            text(
                f"UPDATE {pg_settings.pg_schema}.fct_item_status_interval SET item_sk='wrong-entity'"
            )
        )
