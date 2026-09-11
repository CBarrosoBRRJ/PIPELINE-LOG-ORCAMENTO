"""Real PostgreSQL tests. Opt in; each session uses an isolated test schema."""

import copy
import os
import uuid
from datetime import timedelta

import pytest
from conftest import at, raw_event, raw_item
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

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
    invalid_item = {**store.read("dim_item")[0], "current_status_id": "nonexistent"}
    invalid_item.pop("current_status_sk")
    with pytest.raises(IntegrityError):
        store.commit({"fct_item_status_interval": [], "dim_item": [invalid_item]}, 42)
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
    orphan = {**original, "current_status_id": "nonexistent-status"}
    orphan.pop("current_status_sk")
    with pytest.raises(IntegrityError):
        store.commit({"dim_item": [orphan]}, 42)
    assert store.read("dim_item")[0]["current_status_id"] == original["current_status_id"]
    with pytest.raises(IntegrityError), store.engine.begin() as conn:
        # A manual mismatch between natural ID and SK must be rejected too.
        conn.execute(
            text(
                f"UPDATE {pg_settings.pg_schema}.fct_item_status_interval SET item_sk='wrong-entity'"
            )
        )


def test_contract_required_fields_enforced_in_database(pg_settings, board):
    store = PostgresStore(pg_settings)
    run(pg_settings, "backfill", client=FakeMonday(board), store=store, at=at())
    with pytest.raises(IntegrityError), store.engine.begin() as conn:
        conn.execute(text(f"UPDATE {pg_settings.pg_schema}.dim_item SET item_name=NULL"))
    # Unknown Entrada is legitimately nullable and must never be fabricated.
    assert store.read("fct_item_sla_summary")[0]["sla_start_utc"] is None
    store.initialize()
    store.initialize()


def test_dirty_legacy_data_blocks_required_field_migration(pg_settings, board):
    store = PostgresStore(pg_settings)
    run(pg_settings, "backfill", client=FakeMonday(board), store=store, at=at())
    with store.engine.begin() as conn:
        conn.execute(
            text(
                f"ALTER TABLE {pg_settings.pg_schema}.dim_item ALTER COLUMN item_name DROP NOT NULL"
            )
        )
        conn.execute(text(f"UPDATE {pg_settings.pg_schema}.dim_item SET item_name=NULL"))
    with pytest.raises(IntegrityError):
        store.initialize()
    assert store.read("dim_item")[0]["item_name"] is None


def test_gold_exclusion_reinclusion_and_database_uniqueness(pg_settings, board):
    class MutableMonday(FakeMonday):
        talent = None

        def item_pages(self):
            self.pages_items += 1
            item = raw_item()
            item["column_values"].append({"id": "talent_x", "text": self.talent, "value": None})
            yield [item]

    store = PostgresStore(pg_settings)
    client = MutableMonday(board)
    run(pg_settings, client=client, store=store, at=at())
    gold = store.read("gold_projeto_status")
    assert len(gold) == 2
    assert gold[0]["responsavel_orcamento"] == "Pessoa teste"
    with pytest.raises(IntegrityError), store.engine.begin() as conn:
        conn.execute(
            text(
                f"INSERT INTO {pg_settings.pg_schema}.gold_projeto_status SELECT * FROM {pg_settings.pg_schema}.gold_projeto_status"
            )
        )
    client.talent = "Squad de Talentos"
    run(pg_settings, client=client, store=store, at=at() + timedelta(hours=1))
    assert store.read("gold_projeto_status") == []
    assert len(store.read("fct_item_status_interval")) == 2
    assert any(q["code"] == "gold_projeto_excluido" for q in store.read("data_quality_issue"))
    client.talent = "Pessoa individual"
    run(pg_settings, client=client, store=store, at=at() + timedelta(hours=2))
    assert len(store.read("gold_projeto_status")) == 2
    assert {r["interval_id"] for r in store.read("gold_projeto_status")} == {
        r["interval_id"] for r in gold
    }
    assert not any(q["code"] == "gold_projeto_excluido" for q in store.read("data_quality_issue"))


def test_catalog_manual_approval_not_overwritten(pg_settings, board):
    store = PostgresStore(pg_settings)
    run(pg_settings, client=FakeMonday(board), store=store, at=at())
    pending = store.read("meta_entity_mapping")[0]
    with store.engine.begin() as conn:
        conn.execute(
            text(
                f"UPDATE {pg_settings.pg_schema}.meta_entity_mapping SET canonical_id='brand-test',canonical_name='Marca Revisada',entity_kind='organization',review_status='approved',reviewed_by='test'"
            )
        )
    store.commit({"meta_entity_mapping": [pending]}, 42)
    assert store.read("meta_entity_mapping")[0]["review_status"] == "approved"
    run(pg_settings, client=FakeMonday(board), store=store, at=at())
    assert store.read("gold_projeto_status")[0]["marca_nome"] == "Marca Revisada"
    assert len(store.read("meta_gold_rule_snapshot")) == 2
