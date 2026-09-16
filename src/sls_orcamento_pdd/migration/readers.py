"""Import only reconciled legacy evidence; never write to PostgreSQL or SQLite."""

import hashlib
import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from ..db.checkpoint import decode
from ..db.state_payload import validate_state
from ..models.consumption import GOLD, PUBLIC_FIELDS, public_fingerprint, publication


def load_checkpoint(path, generation):
    path = Path(path).resolve()
    if not path.is_file():
        raise RuntimeError("Checkpoint ausente; restaure a cópia correspondente ao banco")
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
        rows = conn.execute(
            "SELECT digest,data FROM checkpoint WHERE generation=?", (generation,)
        ).fetchall()
    if len(rows) != 1 or hashlib.sha256(rows[0][1]).hexdigest() != rows[0][0]:
        raise RuntimeError("Checkpoint incompatível/corrompido; confira a geração do recibo")
    return decode(rows[0][1])


def reconcile_source(data, actual, board_id, timezone):
    """Fail before import if any source table differs from its private checkpoint."""
    validate_state(data, board_id)
    if set(actual) != set(PUBLIC_FIELDS):
        raise RuntimeError("Inventário legado incompatível: esperadas Gold e pendências")
    for name, expected in publication(data, timezone).items():
        if public_fingerprint(name, actual[name]) != public_fingerprint(name, expected):
            raise RuntimeError("Publicação PostgreSQL diverge do checkpoint; migração bloqueada")


@contextmanager
def postgres_snapshot(settings):
    try:
        import psycopg
        from psycopg import sql
        from psycopg.rows import dict_row
    except ImportError:
        raise RuntimeError("Instale o extra de migração: pip install '.[migration]'") from None

    dsn = settings.pg_dsn.get_secret_value()
    kwargs = {"connect_timeout": 15}
    if dsn:
        dsn = dsn.replace("postgresql+psycopg://", "postgresql://", 1)
    else:
        kwargs.update(
            host=settings.pg_host,
            port=settings.pg_port,
            dbname=settings.pg_db,
            user=settings.pg_user,
            password=settings.pg_password.get_secret_value(),
            sslmode=settings.pg_sslmode,
        )
    lock_id = int.from_bytes(
        hashlib.sha256(f"sls_orcamento_pdd:{settings.monday_board_id}".encode()).digest()[:8],
        "big",
        signed=True,
    )
    with psycopg.connect(dsn, **kwargs) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL statement_timeout='30s'")
        if not conn.execute("SELECT pg_try_advisory_xact_lock(%s)", (lock_id,)).fetchone()[0]:
            raise RuntimeError("Já existe uma execução ativa para este board")
        names = {
            r[0]
            for r in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema=%s",
                (settings.pg_schema,),
            )
        }
        if names != set(PUBLIC_FIELDS):
            raise RuntimeError("Origem requer o contrato legado 3.1: Gold e pendências somente")
        relation = sql.Identifier(settings.pg_schema, GOLD).as_string(conn)
        value = conn.execute(
            "SELECT obj_description(to_regclass(%s),'pg_class')",
            (relation,),
        ).fetchone()[0]
        marker = json.loads(value) if value else {}
        if (
            marker.get("storage") != 4
            or marker.get("pipeline") != settings.pipeline_name
            or not isinstance(marker.get("generation"), str)
            or not marker["generation"]
        ):
            raise RuntimeError("Recibo PostgreSQL ausente/incompatível; restaure a origem correta")
        path = settings.runtime_dir / (
            f"pipeline_state_{settings.pg_schema}_{settings.monday_board_id}.sqlite3"
        )
        data = load_checkpoint(path, marker["generation"])
        actual = {}
        with conn.cursor(row_factory=dict_row) as cursor:
            for name in PUBLIC_FIELDS:
                cursor.execute(
                    sql.SQL("SELECT * FROM {}.{}").format(
                        sql.Identifier(settings.pg_schema),
                        sql.Identifier(name),
                    )
                )
                actual[name] = cursor.fetchall()
        reconcile_source(data, actual, settings.monday_board_id, settings.preferred_timezone)
        yield data
