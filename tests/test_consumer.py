"""Cutover and recovery against isolated LOCAL PostgreSQL schemas only."""

import os
import uuid
from datetime import timedelta

import pytest
from conftest import at
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from test_postgres import FakeMonday

from sls_orcamento_pdd.config import Settings
from sls_orcamento_pdd.db.checkpoint import fingerprint
from sls_orcamento_pdd.db.consumer import GOLD, ConsumerStore
from sls_orcamento_pdd.db.postgres import PostgresStore
from sls_orcamento_pdd.models.consumption import PENDING, public_gold
from sls_orcamento_pdd.models.schemas import DEFINITIONS
from sls_orcamento_pdd.pipelines.runner import run

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_TESTS") != "1", reason="PostgreSQL opt-in"
)


@pytest.fixture
def cfg(tmp_path):
    settings = Settings(
        MONDAY_BOARD_ID=42,
        MONDAY_STATUS_COLUMN_ID="status_19",
        pg_schema="consumer_test_" + uuid.uuid4().hex[:12],
        runtime_dir=tmp_path,
        backfill_from="2026-01-01T00:00:00Z",
    )
    assert settings.pg_host in {"localhost", "127.0.0.1"} and settings.pg_port == 55432
    return settings


def test_cutover_preserves_every_record_and_never_recreates_tables(cfg, board):
    legacy = PostgresStore(cfg)
    run(cfg, "backfill", client=FakeMonday(board), store=legacy, at=at())
    before = legacy.read_many(DEFINITIONS)
    store = ConsumerStore(cfg)
    with pytest.raises(RuntimeError, match="legadas"):
        store.initialize()
    result = store.migrate()
    assert result["removed_tables"] == 19
    assert fingerprint(store.read_many(DEFINITIONS)) == fingerprint(before)
    for _ in range(2):
        store = ConsumerStore(cfg)
        store.initialize()
        assert store.check_connection()["tables"] == [GOLD, PENDING]
    run(cfg, client=FakeMonday(board), store=store, at=at())
    assert fingerprint({GOLD: store.read(GOLD)}) == fingerprint({GOLD: before[GOLD]})
    assert store.check_connection()["tables"] == [GOLD, PENDING]
    assert store.migrate()["already_migrated"]
    with pytest.raises(RuntimeError, match="convertido para consumo"):
        legacy.initialize()


def test_single_table_new_install_claims_failures_and_original_ids(cfg, board):
    store = ConsumerStore(cfg)
    run(cfg, "backfill", client=FakeMonday(board), store=store, at=at())
    first = run(cfg, client=FakeMonday(board), store=store, at=at(), scheduled_for=at())
    assert first["status"] == "success"
    store = ConsumerStore(cfg)
    failed_client = FakeMonday(board, fail=True)
    assert (
        run(cfg, client=failed_client, store=store, at=at(), scheduled_for=at())["status"]
        == "skipped"
    )
    assert failed_client.pages_items == 0
    watermark = store.read("etl_watermark")
    tomorrow = at() + timedelta(days=1)
    with pytest.raises(RuntimeError, match="simulada"):
        run(
            cfg,
            client=FakeMonday(board, fail=True),
            store=store,
            at=tomorrow,
            scheduled_for=tomorrow,
        )
    store = ConsumerStore(cfg)
    assert store.read("etl_watermark") == watermark
    assert (
        run(cfg, client=FakeMonday(board), store=store, at=tomorrow, scheduled_for=tomorrow)[
            "status"
        ]
        == "skipped"
    )
    assert store.check_connection()["tables"] == [GOLD, PENDING]
    assert store.read(GOLD)[0]["item_id"] == 123
    with pytest.raises(IntegrityError), store.engine.begin() as conn:
        row = {**public_gold(store.read(GOLD))[0], "interval_id": "duplicate-business-order"}
        conn.execute(store.tables[GOLD].insert().values(row))


def test_pending_commit_recovers_and_missing_volume_blocks(cfg, board, monkeypatch):
    store = ConsumerStore(cfg)
    run(cfg, "backfill", client=FakeMonday(board), store=store, at=at())
    before = store.read("etl_run")
    row = {**before[0], "run_id": str(uuid.uuid4())}
    original = store.checkpoint.promote
    calls = 0

    def crash(generation):
        nonlocal calls
        calls += 1
        if calls == 2:  # PostgreSQL committed but local promotion not completed.
            raise OSError("crash after commit")
        return original(generation)

    monkeypatch.setattr(store.checkpoint, "promote", crash)
    with pytest.raises(OSError, match="crash"):
        store.commit({"etl_run": [row]}, 42)
    restarted = ConsumerStore(cfg)
    restarted.initialize()
    assert len(restarted.read("etl_run")) == len(before) + 1
    gold_before = restarted.read(GOLD)
    restarted.checkpoint.path.rename(restarted.checkpoint.path.with_suffix(".moved"))
    with pytest.raises(RuntimeError, match="ausente"):
        ConsumerStore(cfg).initialize()
    with restarted.engine.connect() as conn:
        assert conn.scalar(text(f"SELECT count(*) FROM {cfg.pg_schema}.{GOLD}")) == len(gold_before)


def test_rollback_keeps_watermark_and_orphans_block_publication(cfg, board, monkeypatch):
    store = ConsumerStore(cfg)
    run(cfg, "backfill", client=FakeMonday(board), store=store, at=at())
    before = store.read_many(DEFINITIONS)
    item = {**store.read("dim_item")[0], "current_status_id": "missing"}
    item.pop("current_status_sk")
    with pytest.raises(ValueError, match="órfã"):
        store.commit({"dim_item": [item]}, 42)
    original = store._mark

    def failure(conn, generation):
        original(conn, generation)
        raise RuntimeError("transaction rollback")

    monkeypatch.setattr(store, "_mark", failure)
    with pytest.raises(RuntimeError, match="rollback"):
        store.commit({"gold_projeto_status": store.read(GOLD)}, 42)
    restarted = ConsumerStore(cfg)
    restarted.initialize()
    assert fingerprint(restarted.read_many(DEFINITIONS)) == fingerprint(before)


def test_external_dependency_aborts_drop_without_data_loss(cfg, board):
    legacy = PostgresStore(cfg)
    run(cfg, "backfill", client=FakeMonday(board), store=legacy, at=at())
    with legacy.engine.begin() as conn:
        conn.execute(
            text(
                f"CREATE VIEW public.test_dependency_{cfg.pg_schema} AS SELECT item_id FROM {cfg.pg_schema}.dim_item"
            )
        )
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError):
        ConsumerStore(cfg).migrate()
    assert len(legacy.check_connection()["tables"]) == 20
    assert len(legacy.read(GOLD)) == 1
    with legacy.engine.begin() as conn:
        conn.execute(text(f"DROP VIEW public.test_dependency_{cfg.pg_schema}"))


def test_review_import_export_and_out_of_band_gold_detection(cfg, board, monkeypatch):
    import json

    from sls_orcamento_pdd.pipelines import runner
    from sls_orcamento_pdd.services.review import export_review, import_review

    store = ConsumerStore(cfg)
    run(cfg, "backfill", client=FakeMonday(board), store=store, at=at())
    row = store.read("meta_entity_mapping")[0]
    row.update(
        canonical_id="approved-brand",
        canonical_name="Marca Revisada",
        review_status="approved",
        reviewed_by="test",
        entity_kind="organization",
    )
    path = cfg.runtime_dir / "reviewed.json"
    path.write_text(json.dumps([row], default=str), encoding="utf-8")
    assert import_review(store, cfg, path)["reviewed_rows"] == 1
    monkeypatch.setattr(runner, "get_store", lambda settings: store)
    runner.replay(cfg)
    assert store.read(GOLD)[0]["marca_nome"] == "Marca Revisada"
    assert export_review(store, cfg)["quarantined_projects"] == 0
    assert (cfg.runtime_dir / "review" / "projetos_quarentena.csv").exists()
    with store.engine.begin() as conn:
        conn.execute(text(f"UPDATE {cfg.pg_schema}.{GOLD} SET marca_nome='outside-edit'"))
    with pytest.raises(RuntimeError, match="fora do pipeline"):
        ConsumerStore(cfg).read(GOLD)
    with pytest.raises(RuntimeError, match="fora do pipeline"):
        ConsumerStore(cfg).commit({GOLD: store._cache[GOLD]}, 42)


def test_version3_upgrade_keeps_ids_and_hides_inferred_times(cfg, board):
    import json

    legacy = PostgresStore(cfg)
    run(cfg, "backfill", client=FakeMonday(board), store=legacy, at=at())
    before = legacy.read_many(DEFINITIONS)
    store = ConsumerStore(cfg)
    generation = str(uuid.uuid4())
    store.checkpoint.stage(generation, before)
    store.checkpoint.promote(generation)
    with legacy.engine.begin() as conn:
        foreign = (
            conn.execute(
                text(
                    "SELECT conname FROM pg_constraint WHERE conrelid=to_regclass(:t) AND contype='f'"
                ),
                {"t": f"{cfg.pg_schema}.{GOLD}"},
            )
            .scalars()
            .all()
        )
        for name in foreign:
            conn.execute(text(f'ALTER TABLE {cfg.pg_schema}.{GOLD} DROP CONSTRAINT "{name}"'))
        conn.execute(
            text("DROP TABLE " + ",".join(f"{cfg.pg_schema}.{n}" for n in DEFINITIONS if n != GOLD))
        )
        marker = json.dumps({"storage": 3, "pipeline": cfg.pipeline_name, "generation": generation})
        conn.execute(text(f"COMMENT ON TABLE {cfg.pg_schema}.{GOLD} IS '{marker}'"))
    with pytest.raises(RuntimeError, match="legadas"):
        store.initialize()
    assert store.migrate()["tables"] == [GOLD, PENDING]
    assert fingerprint(store.read_many(DEFINITIONS)) == fingerprint(before)
    with store.engine.connect() as conn:
        rows = list(conn.execute(store.tables[GOLD].select()).mappings())
        assert len(rows) == len(before[GOLD])
        assert rows[0]["interval_id"] == before[GOLD][0]["interval_id"]
        assert rows[0]["duracao_horas"] is None
        assert rows[0]["entrada_status_local"] is None
        assert conn.scalar(text(f"SELECT count(*) FROM {cfg.pg_schema}.{PENDING}")) == 1
    assert store.migrate()["already_migrated"]


def test_health_uses_publication_but_does_not_hide_failed_attempt(cfg, board):
    import json

    from sls_orcamento_pdd.services.health import BUSY, check_health

    store = ConsumerStore(cfg)
    run(cfg, "backfill", client=FakeMonday(board), store=store, at=at())
    last = store.read("etl_run")[0]
    status = {
        "status": "failed",
        "end_at": (last["end_at"] + timedelta(minutes=1)).isoformat(),
        "error": BUSY,
        "scheduled_date": None,
    }
    path = cfg.runtime_dir / "status_42.json"
    path.write_text(json.dumps(status), encoding="utf-8")
    result = check_health(store, cfg, now=at() + timedelta(hours=1))
    assert result["warnings"] == ["concurrent_attempt_rejected"]
    assert json.loads(path.read_text())["status"] == "failed"  # Never rewrite old evidence.
    status["error"] = "API failure"
    path.write_text(json.dumps(status), encoding="utf-8")
    with pytest.raises(ValueError, match="falhou"):
        check_health(store, cfg, now=at() + timedelta(hours=1))
