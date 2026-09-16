"""Read-only migration tests; real PostgreSQL is opt-in and loopback-only."""

import copy
import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import closing

import pytest
from conftest import FakeMonday, at
from test_gcp_store import cloud

from sls_orcamento_ppd.db.checkpoint import encode, fingerprint
from sls_orcamento_ppd.migration.readers import load_checkpoint, postgres_snapshot, reconcile_source
from sls_orcamento_ppd.models.consumption import GOLD, PUBLIC_FIELDS, publication
from sls_orcamento_ppd.models.schemas import DEFINITIONS
from sls_orcamento_ppd.pipelines.runner import run

_migration_cloud = pytest.fixture(name="migration_cloud")(cloud.__wrapped__)


def save_test_checkpoint(path, data, generation="confirmed"):
    raw = encode(data)
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("CREATE TABLE checkpoint (slot TEXT, generation TEXT, digest TEXT, data BLOB)")
        conn.execute(
            "INSERT INTO checkpoint VALUES (?,?,?,?)",
            (
                "active",
                generation,
                hashlib.sha256(raw).hexdigest(),
                raw,
            ),
        )


@pytest.fixture
def migration_data(migration_cloud, board):
    cfg, _, new = migration_cloud
    run(cfg, "backfill", client=FakeMonday(board), store=new(), at=at())
    return cfg, new().read_many(DEFINITIONS)


def test_checkpoint_reads_exact_generation_without_modifying_file(tmp_path, migration_data):
    _, data = migration_data
    path = tmp_path / "checkpoint with # and spaces.sqlite3"
    save_test_checkpoint(path, data)
    original = path.read_bytes()
    assert fingerprint(load_checkpoint(path, "confirmed")) == fingerprint(data)
    assert path.read_bytes() == original
    with pytest.raises(RuntimeError, match="corrompido"):
        load_checkpoint(path, "not-the-receipt")
    assert path.read_bytes() == original


def test_missing_checkpoint_never_creates_file(tmp_path):
    path = tmp_path / "missing.sqlite3"
    with pytest.raises(RuntimeError, match="ausente"):
        load_checkpoint(path, "generation")
    assert not path.exists()


def test_bad_checksum_blocks_checkpoint(tmp_path):
    path = tmp_path / "corrupt.sqlite3"
    save_test_checkpoint(path, {name: [] for name in DEFINITIONS})
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("UPDATE checkpoint SET digest='invalid'")
    with pytest.raises(RuntimeError, match="corrompido"):
        load_checkpoint(path, "confirmed")


def test_source_reconciliation_rejects_manual_edits(migration_data):
    cfg, data = migration_data
    actual = publication(data, cfg.preferred_timezone)
    reconcile_source(data, actual, cfg.monday_board_id, cfg.preferred_timezone)
    changed = copy.deepcopy(actual)
    changed[GOLD][0]["projeto_nome"] = "manual change"
    with pytest.raises(RuntimeError, match="diverge"):
        reconcile_source(data, changed, cfg.monday_board_id, cfg.preferred_timezone)
    with pytest.raises(RuntimeError, match="Inventário"):
        reconcile_source(data, {}, cfg.monday_board_id, cfg.preferred_timezone)


@pytest.fixture
def local_source(migration_data, tmp_path):
    if os.environ.get("RUN_MIGRATION_TESTS") != "1":
        pytest.skip("Local PostgreSQL migration integration is opt-in")
    psycopg = pytest.importorskip("psycopg")
    from psycopg import sql

    cfg, data = migration_data
    schema = "migration_test_" + uuid.uuid4().hex[:12]
    cfg = cfg.model_copy(
        update={
            "pg_dsn": type(cfg.pg_dsn)(""),
            "pg_host": "127.0.0.1",
            "pg_port": int(os.environ.get("MIGRATION_TEST_PORT", "55439")),
            "pg_db": "migration_test",
            "pg_user": "migration_test",
            "pg_password": type(cfg.pg_password)("local-test-only"),
            "pg_sslmode": "disable",
            "pg_schema": schema,
            "runtime_dir": tmp_path,
        }
    )
    path = tmp_path / f"pipeline_state_{schema}_{cfg.monday_board_id}.sqlite3"
    save_test_checkpoint(path, data)
    types = {
        "text": "TEXT",
        "id": "BIGINT",
        "int": "BIGINT",
        "bool": "BOOLEAN",
        "time": "TIMESTAMPTZ",
        "localtime": "TIMESTAMP",
        "num": "DOUBLE PRECISION",
    }
    kwargs = dict(
        host="127.0.0.1",
        port=cfg.pg_port,
        dbname="migration_test",
        user="migration_test",
        password="local-test-only",
    )
    with psycopg.connect(**kwargs, autocommit=True) as setup:
        setup.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            projected = publication(data, cfg.preferred_timezone)
            for name, fields in PUBLIC_FIELDS.items():
                columns = [f.split(":") for f in fields.split()]
                definitions = sql.SQL(", ").join(
                    sql.SQL("{} {}").format(sql.Identifier(k), sql.SQL(types[t]))
                    for k, t in columns
                )
                table = sql.Identifier(schema, name)
                setup.execute(sql.SQL("CREATE TABLE {} ({})").format(table, definitions))
                for row in projected[name]:
                    setup.execute(
                        sql.SQL("INSERT INTO {} VALUES ({})").format(
                            table,
                            sql.SQL(", ").join(sql.Placeholder() for _ in columns),
                        ),
                        [row[k] for k, _ in columns],
                    )
            receipt = json.dumps(
                {"storage": 4, "pipeline": cfg.pipeline_name, "generation": "confirmed"}
            )
            setup.execute(
                sql.SQL("COMMENT ON TABLE {} IS {}").format(
                    sql.Identifier(schema, GOLD),
                    sql.Literal(receipt),
                )
            )
            yield cfg, data, setup
        finally:
            # Only this randomly named test schema, on a forced loopback test database.
            assert schema.startswith("migration_test_") and len(schema) == 27
            setup.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_real_source_read_only_and_same_legacy_lock(local_source):
    cfg, expected, setup = local_source
    original = (
        cfg.runtime_dir / f"pipeline_state_{cfg.pg_schema}_{cfg.monday_board_id}.sqlite3"
    ).read_bytes()
    lock_id = int.from_bytes(
        hashlib.sha256(f"sls_orcamento_pdd:{cfg.monday_board_id}".encode()).digest()[:8],
        "big",
        signed=True,
    )
    with postgres_snapshot(cfg) as data:
        assert fingerprint(data) == fingerprint(expected)
        assert not setup.execute("SELECT pg_try_advisory_lock(%s)", (lock_id,)).fetchone()[0]
    assert setup.execute("SELECT pg_try_advisory_lock(%s)", (lock_id,)).fetchone()[0]
    setup.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))
    assert (
        cfg.runtime_dir / f"pipeline_state_{cfg.pg_schema}_{cfg.monday_board_id}.sqlite3"
    ).read_bytes() == original


def test_real_source_rejects_foreign_receipt(local_source):
    from psycopg import sql

    cfg, _, setup = local_source
    setup.execute(
        sql.SQL("COMMENT ON TABLE {} IS NULL").format(sql.Identifier(cfg.pg_schema, GOLD))
    )
    with pytest.raises(RuntimeError, match="Recibo"), postgres_snapshot(cfg):
        pass


def test_real_source_rejects_changed_publication(local_source):
    from psycopg import sql

    cfg, _, setup = local_source
    setup.execute(
        sql.SQL("UPDATE {} SET projeto_nome='modified'").format(sql.Identifier(cfg.pg_schema, GOLD))
    )
    with pytest.raises(RuntimeError, match="diverge"), postgres_snapshot(cfg):
        pass
