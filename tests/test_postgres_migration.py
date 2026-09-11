import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.schema import CreateSchema

from sls_orcamento_pdd.config import Settings
from sls_orcamento_pdd.db.postgres import PostgresStore


@pytest.mark.skipif(os.environ.get("RUN_POSTGRES_TESTS") != "1", reason="PostgreSQL opt-in")
def test_initialize_leaves_legacy_view_until_explicit_retirement(tmp_path):
    settings = Settings(pg_schema="sla_test_" + uuid.uuid4().hex[:12], runtime_dir=tmp_path)
    store = PostgresStore(settings)
    table = store.tables["fct_item_status_interval"]
    old_fields = [c.name for c in table.c if not c.name.endswith("_sk")]
    with store.engine.begin() as conn:
        conn.execute(CreateSchema(settings.pg_schema))
        store.metadata.create_all(conn)
        conn.execute(
            text(
                f"CREATE VIEW {settings.pg_schema}.gold_intervals_local AS SELECT "
                + ",".join(old_fields)
                + f",status_start_utc AT TIME ZONE 'America/Sao_Paulo' status_start_local, "
                f"status_end_utc AT TIME ZONE 'America/Sao_Paulo' status_end_local "
                f"FROM {settings.pg_schema}.fct_item_status_interval"
            )
        )
    store.initialize()
    store.initialize()
    with store.engine.connect() as conn:
        columns = (
            conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema=:schema AND table_name='gold_intervals_local' "
                    "ORDER BY ordinal_position"
                ),
                {"schema": settings.pg_schema},
            )
            .scalars()
            .all()
        )
    assert columns[: len(old_fields) + 2] == old_fields + ["status_start_local", "status_end_local"]
    assert "item_sk" not in columns  # No implicit legacy consumer changes.
