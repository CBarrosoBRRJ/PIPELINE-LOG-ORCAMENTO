import hashlib
from contextlib import contextmanager

from sqlalchemy import UniqueConstraint, bindparam, create_engine, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.schema import AddConstraint, CreateSchema

from ..models.contracts import prepare_payload, required_columns
from ..models.keys import DIMENSION_IDENTITIES, SURROGATE_COLUMNS, with_surrogates
from ..models.schemas import DEFINITIONS, REPLACE_TABLES, define_tables


def postgres_views(schema, timezone):
    tz = timezone.replace("'", "''")
    interval_fields = [f.split(":")[0] for f in DEFINITIONS["fct_item_status_interval"][1].split()]
    interval_projection = ", ".join(c for c in interval_fields if not c.endswith("_sk"))
    surrogate_projection = ", ".join(c for c in interval_fields if c.endswith("_sk"))
    return [
        f"""CREATE OR REPLACE VIEW {schema}.gold_status_metrics AS
      WITH dwell AS (
        SELECT board_id, status_id, COUNT(*) AS interval_count,
          SUM(duration_minutes) AS accumulated_minutes,
          AVG(duration_minutes) AS mean_minutes,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_minutes) AS median_minutes,
          percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_minutes) AS p95_minutes
        FROM {schema}.fct_item_status_interval GROUP BY board_id, status_id
      ), queue AS (
        SELECT board_id, current_status_id AS status_id, COUNT(*) AS current_item_count
        FROM {schema}.dim_item WHERE is_active GROUP BY board_id, current_status_id
      )
      SELECT s.board_id, s.status_id, s.status_label, s.status_order, s.is_terminal,
        COALESCE(d.interval_count,0) AS interval_count, COALESCE(d.accumulated_minutes,0) AS accumulated_minutes,
        d.mean_minutes, d.median_minutes, d.p95_minutes,
        COALESCE(q.current_item_count,0) AS current_item_count,
        CASE WHEN s.is_terminal THEN 0 ELSE COALESCE(q.current_item_count,0) END AS queue_count
      FROM {schema}.dim_status s LEFT JOIN dwell d USING(board_id,status_id)
      LEFT JOIN queue q USING(board_id,status_id)""",
        f"""CREATE OR REPLACE VIEW {schema}.gold_project_status AS
      SELECT board_id, item_id, status_id, SUM(duration_minutes) AS total_minutes,
        SUM(duration_hours) AS total_hours, COUNT(*) AS visit_count
      FROM {schema}.fct_item_status_interval GROUP BY board_id,item_id,status_id""",
        f"""CREATE OR REPLACE VIEW {schema}.gold_status_bottlenecks AS
      SELECT *, dense_rank() OVER(PARTITION BY board_id ORDER BY accumulated_minutes DESC) AS time_rank,
        dense_rank() OVER(PARTITION BY board_id ORDER BY queue_count DESC) AS queue_rank
      FROM {schema}.gold_status_metrics WHERE NOT is_terminal""",
        f"""CREATE OR REPLACE VIEW {schema}.gold_intervals_local AS
      SELECT {interval_projection}, status_start_utc AT TIME ZONE '{tz}' AS status_start_local,
        status_end_utc AT TIME ZONE '{tz}' AS status_end_local, {surrogate_projection}
      FROM {schema}.fct_item_status_interval""",
    ]


class PostgresStore:
    def __init__(self, settings):
        self.settings = settings
        self.engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            connect_args={
                "connect_timeout": 15,
                **(
                    {"sslmode": settings.pg_sslmode}
                    if not settings.pg_dsn.get_secret_value()
                    else {}
                ),
            },
        )
        self.metadata, self.tables = define_tables(settings.pg_schema)

    def check_connection(self):
        """Read-only diagnostics; never include a DSN, password or business rows."""
        with self.engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            conn.execute(text("SET LOCAL statement_timeout='15s'"))
            row = dict(
                conn.execute(
                    text(
                        "SELECT current_database() AS database, current_user AS username, "
                        "current_setting('server_version') AS server_version"
                    )
                )
                .mappings()
                .one()
            )
            row["schema"] = self.settings.pg_schema
            row["tls"] = conn.scalar(text("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()"))
            row["tables"] = (
                conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema=:schema ORDER BY table_name"
                    ),
                    {"schema": self.settings.pg_schema},
                )
                .scalars()
                .all()
            )
            return row

    def initialize(self):
        with self.engine.begin() as conn:
            conn.execute(CreateSchema(self.settings.pg_schema, if_not_exists=True))
            self.metadata.create_all(conn)
            self._migrate_surrogate_columns(conn)
            # Seed newly introduced board dimension from existing raw schema history.
            board_rows = conn.execute(
                text(f"""SELECT DISTINCT ON(board_id) board_id,raw_data->>'name' AS board_name,
                (raw_data->>'created_at')::timestamptz AS created_at,snapshot_at AS updated_at
              FROM {self.settings.pg_schema}.bronze_monday_board_schema_raw
              ORDER BY board_id,snapshot_at DESC""")
            ).mappings()
            for row in board_rows:
                conn.execute(
                    insert(self.tables["dim_board"])
                    .values(with_surrogates("dim_board", row))
                    .on_conflict_do_nothing(index_elements=["board_id"])
                )
            # Additive migration for the explicit business SLA start anchor.
            conn.execute(
                text(
                    f"ALTER TABLE {self.settings.pg_schema}.fct_item_sla_summary "
                    "ADD COLUMN IF NOT EXISTS sla_start_utc TIMESTAMPTZ, "
                    "ADD COLUMN IF NOT EXISTS sla_start_quality TEXT"
                )
            )
            # Promote the required-field contract to PostgreSQL too. No filling
            # unknowns: an incompatible existing row aborts this transaction.
            nullable_columns = set(
                conn.execute(
                    text(
                        "SELECT table_name,column_name FROM information_schema.columns "
                        "WHERE table_schema=:schema AND is_nullable='YES'"
                    ),
                    {"schema": self.settings.pg_schema},
                ).all()
            )
            for name in self.tables:
                changes = [
                    f"ALTER COLUMN {column} SET NOT NULL"
                    for column in sorted(required_columns(name))
                    if (name, column) in nullable_columns
                ]
                if changes:
                    conn.execute(
                        text(f"ALTER TABLE {self.settings.pg_schema}.{name} " + ", ".join(changes))
                    )
            existing = set(
                conn.execute(
                    text("""SELECT c.conname FROM pg_constraint c
              JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname=:schema"""),
                    {"schema": self.settings.pg_schema},
                ).scalars()
            )
            for table in self.tables.values():
                for constraint in table.constraints:
                    if isinstance(constraint, UniqueConstraint) and constraint.name not in existing:
                        conn.execute(AddConstraint(constraint))
            for table in self.tables.values():
                for constraint in table.foreign_key_constraints:
                    if constraint.name not in existing:
                        conn.execute(AddConstraint(constraint))
            for statement in postgres_views(
                self.settings.pg_schema, self.settings.preferred_timezone
            ):
                conn.execute(text(statement))

    def _migrate_surrogate_columns(self, conn):
        for name, columns in SURROGATE_COLUMNS.items():
            target = self.tables[name]
            for column in columns:
                conn.execute(
                    text(
                        f"ALTER TABLE {self.settings.pg_schema}.{name} ADD COLUMN IF NOT EXISTS {column} TEXT"
                    )
                )
            keys = [c.name for c in target.primary_key]
            sources = set(keys) | {source for source, _ in columns.values()}
            # Null source IDs legitimately yield null SKs; do not rewrite those rows every run.
            missing = [
                target.c[column].is_(None) & target.c[source].is_not(None)
                for column, (source, _) in columns.items()
            ]
            rows = list(
                conn.execute(
                    select(*(target.c[c] for c in sources)).where(or_(*missing))
                ).mappings()
            )
            statement = (
                target.update()
                .where(*(target.c[k] == bindparam(f"pk_{k}") for k in keys))
                .values(**{c: bindparam(f"value_{c}") for c in columns})
            )
            for start in range(0, len(rows), 500):
                parameters = []
                for row in rows[start : start + 500]:
                    enriched = with_surrogates(name, row)
                    parameters.append(
                        {
                            **{f"pk_{k}": row[k] for k in keys},
                            **{f"value_{c}": enriched[c] for c in columns},
                        }
                    )
                conn.execute(statement, parameters)
            if name in DIMENSION_IDENTITIES:
                surrogate = DIMENSION_IDENTITIES[name][1]
                conn.execute(
                    text(
                        f"ALTER TABLE {self.settings.pg_schema}.{name} ALTER COLUMN {surrogate} SET NOT NULL"
                    )
                )

    @contextmanager
    def lock(self):
        # Dedicated session prevents stale leases after process termination.
        lock_id = int.from_bytes(
            hashlib.sha256(f"sls_orcamento_pdd:{self.settings.monday_board_id}".encode()).digest()[
                :8
            ],
            "big",
            signed=True,
        )
        with self.engine.connect() as conn:
            acquired = conn.scalar(text("SELECT pg_try_advisory_lock(:id)"), {"id": lock_id})
            conn.commit()
            if not acquired:
                raise RuntimeError("Já existe uma execução ativa para este board")
            try:
                yield
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": lock_id})
                conn.commit()

    def read(self, table, board_id=None):
        target = self.tables[table]
        statement = select(target)
        if board_id is not None and "board_id" in target.c:
            statement = statement.where(target.c.board_id == board_id)
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(statement).mappings()]

    def commit(self, payload, board_id):
        payload = prepare_payload(payload, board_id)
        with self.engine.begin() as conn:
            for name, rows in payload.items():
                table = self.tables[name]
                if name in REPLACE_TABLES:
                    conn.execute(table.delete().where(table.c.board_id == board_id))
                for offset in range(0, len(rows), 500):
                    batch = rows[offset : offset + 500]
                    statement = insert(table).values(batch)
                    keys = [c.name for c in table.primary_key]
                    updates = {
                        c.name: statement.excluded[c.name] for c in table.c if c.name not in keys
                    }
                    if name == "bronze_monday_activity_log_raw":
                        updates.pop("ingested_at", None)
                    conn.execute(statement.on_conflict_do_update(index_elements=keys, set_=updates))
