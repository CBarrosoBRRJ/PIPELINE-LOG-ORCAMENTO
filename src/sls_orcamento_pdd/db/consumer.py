"""Two business PostgreSQL tables; private processing state in runtime SQLite.

The PostgreSQL table comment is the atomic publication receipt. A checkpoint is
fsynced first; after COMMIT it is promoted. Recovery follows the receipt, never
an uncommitted watermark. A missing volume fails closed instead of losing history.
"""

import copy
import json
import uuid
from contextlib import contextmanager

from sqlalchemy import CheckConstraint, UniqueConstraint, select, text
from sqlalchemy.schema import AddConstraint, CreateSchema

from ..models.consumption import (
    GOLD,
    PENDING,
    PUBLIC_FIELDS,
    consumer_tables,
    public_fingerprint,
    publication,
)
from ..models.contracts import prepare_payload, validate_table
from ..models.schemas import DEFINITIONS, REPLACE_TABLES, foreign_keys
from ..services.load import merge_rows
from .checkpoint import Checkpoint, fingerprint
from .postgres import PostgresStore


def validate_state(data):
    for name, rows in data.items():
        validate_table(name, rows)
    for child, column, parent, target in foreign_keys():
        identities = {r[target] for r in data[parent]}
        if any(r.get(column) is not None and r[column] not in identities for r in data[child]):
            raise ValueError(f"Referência interna órfã: {child}.{column}")


class ConsumerStore(PostgresStore):
    def __init__(self, settings):
        super().__init__(settings)
        self.metadata, self.tables = consumer_tables(settings.pg_schema)
        self.checkpoint = Checkpoint(
            settings.runtime_dir
            / f"pipeline_state_{settings.pg_schema}_{settings.monday_board_id}.sqlite3"
        )
        self._depth = 0
        self._cache = None
        self._generation = None

    @contextmanager
    def lock(self):
        if self._depth:
            yield
            return
        with super().lock():
            self._depth += 1
            try:
                yield
            finally:
                self._depth -= 1

    def _names(self, conn):
        return set(
            conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema=:s"),
                {"s": self.settings.pg_schema},
            ).scalars()
        )

    def _receipt(self, conn):
        value = conn.scalar(
            text("SELECT obj_description(to_regclass(:t),'pg_class')"),
            {"t": f"{self.settings.pg_schema}.{GOLD}"},
        )
        if value is None:
            raise RuntimeError(
                "Migração pendente: execute migrate-single-table no executor com volume persistente"
            )
        marker = json.loads(value)
        if marker.get("storage") != 4 or marker.get("pipeline") != self.settings.pipeline_name:
            raise RuntimeError(
                "Contrato de consumo pendente: execute migrate-consumption no executor"
            )
        return marker["generation"]

    def _mark(self, conn, generation):
        marker = json.dumps(
            {"storage": 4, "pipeline": self.settings.pipeline_name, "generation": generation}
        )
        literal = marker.replace("'", "''")
        conn.execute(text(f"COMMENT ON TABLE {self.settings.pg_schema}.{GOLD} IS '{literal}'"))

    def _constraints(self, conn):
        existing = set(
            conn.execute(
                text("SELECT conname FROM pg_constraint WHERE conrelid=to_regclass(:t)"),
                {"t": f"{self.settings.pg_schema}.{GOLD}"},
            ).scalars()
        )
        for constraint in self.tables[GOLD].constraints:
            if (
                isinstance(constraint, (CheckConstraint, UniqueConstraint))
                and constraint.name not in existing
            ):
                conn.execute(AddConstraint(constraint))
        for index in self.tables[GOLD].indexes:
            index.create(conn, checkfirst=True)

    def _load(self, conn):
        generation = self._receipt(conn)
        if generation != self._generation:
            self._cache = self.checkpoint.load(generation)
            self._generation = generation
        # Even a cached process must notice a lost persistent volume.
        if not self.checkpoint.path.is_file():
            raise RuntimeError("Checkpoint ausente: restaure o volume runtime")
        return generation, self._cache

    def initialize(self):
        with self.lock(), self.engine.begin() as conn:
            names = self._names(conn)
            if names and names != set(PUBLIC_FIELDS):
                raise RuntimeError(
                    "Tabelas legadas presentes: execute migrate-consumption antes da próxima carga"
                )
            if GOLD in names:
                generation, _ = self._load(conn)
                self._constraints(conn)
                self.checkpoint.promote(generation)
                return
            if self.checkpoint.path.exists():
                raise RuntimeError(
                    "Banco vazio com checkpoint existente: restaure o banco correspondente"
                )
            generation = str(uuid.uuid4())
            self.checkpoint.stage(generation, {name: [] for name in DEFINITIONS})
            conn.execute(CreateSchema(self.settings.pg_schema, if_not_exists=True))
            self.metadata.create_all(conn)
            self._mark(conn, generation)
        self.checkpoint.promote(generation)

    def read_many(self, names, board_id=None):
        with self.engine.connect() as conn:
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            _, data = self._load(conn)
            expected = {}
            if GOLD in names or PENDING in names:
                expected = publication(data, self.settings.preferred_timezone)
                for name, projected in expected.items():
                    actual = [dict(r) for r in conn.execute(select(self.tables[name])).mappings()]
                    if public_fingerprint(name, actual) != public_fingerprint(name, projected):
                        raise RuntimeError(
                            "Consumo alterado fora do pipeline: publicação diverge do checkpoint"
                        )
            result = {}
            for name in names:
                rows = expected[PENDING] if name == PENDING else data[name]
                result[name] = copy.deepcopy(
                    [
                        r
                        for r in rows
                        if board_id is None or "board_id" not in r or r["board_id"] == board_id
                    ]
                )
            return result

    def read(self, table, board_id=None):
        return self.read_many([table], board_id)[table]

    def _validate_gold(self, data):
        from ..rules.cutoff import closed_day_cut
        from ..services.gold import validate_gold
        from ..services.state import watermark

        previous = watermark(data["etl_watermark"], self.settings.pipeline_name)
        cutoff = (
            closed_day_cut(previous["last_run_utc"], self.settings.preferred_timezone)
            if previous
            else None
        )
        validate_gold(data, cutoff=cutoff)

    def commit(self, payload, board_id, *, reviewed=False):
        payload = prepare_payload(payload, board_id)
        with self.lock():
            with self.engine.connect() as conn:
                generation, old = self._load(conn)
            self.read_many([GOLD])  # Reject manual edits before replacing a published batch.
            self.checkpoint.promote(generation)
            data = dict(old)
            for name, rows in payload.items():
                if name in REPLACE_TABLES:
                    data[name] = [r for r in old[name] if r.get("board_id") != board_id] + rows
                elif name == "meta_gold_rule_snapshot" or (
                    name == "meta_entity_mapping" and not reviewed
                ):
                    data[name] = merge_rows(rows, old[name], name)
                else:
                    if name == "bronze_monday_activity_log_raw":
                        ingested = {r["event_id"]: r["ingested_at"] for r in old[name]}
                        rows = [
                            {**r, "ingested_at": ingested.get(r["event_id"], r["ingested_at"])}
                            for r in rows
                        ]
                    data[name] = merge_rows(old[name], rows, name)
            validate_state(data)
            if GOLD in payload:
                self._validate_gold(data)
            generation = str(uuid.uuid4())
            self.checkpoint.stage(generation, data)
            with self.engine.begin() as conn:
                if GOLD in payload:
                    self._publish(conn, data, board_id)
                self._mark(conn, generation)
            self.checkpoint.promote(generation)
            self._generation, self._cache = generation, data

    def _publish(self, conn, data, board_id):
        for name, rows in publication(data, self.settings.preferred_timezone).items():
            table = self.tables[name]
            selected = [r for r in rows if r["board_id"] == board_id]
            if name == GOLD:
                selected.sort(key=lambda r: (r["item_id"], r["ordem_etapa"]))
            conn.execute(table.delete().where(table.c.board_id == board_id))
            for offset in range(0, len(selected), 500):
                conn.execute(table.insert(), selected[offset : offset + 500])

    def claim_daily(self, row):
        with self.lock():
            if any(r["run_id"] == row["run_id"] for r in self.read("etl_run")):
                return False
            self.commit({"etl_run": [row]}, self.settings.monday_board_id)
            return True

    def migrate(self):
        """Explicit authorized cutover; never called by initialize or scheduler."""
        with self.lock():
            legacy = PostgresStore(self.settings)
            with self.engine.connect() as conn:
                names = self._names(conn)
            if names == set(PUBLIC_FIELDS):
                self.initialize()
                return {"tables": sorted(PUBLIC_FIELDS), "already_migrated": True}
            if names not in ({GOLD}, set(DEFINITIONS)):
                raise ValueError(
                    "Migração requer inventário legado exato; nenhum objeto foi excluído"
                )
            if names == {GOLD}:
                with self.engine.connect() as conn:
                    marker = json.loads(
                        conn.scalar(
                            text("SELECT obj_description(to_regclass(:t),'pg_class')"),
                            {"t": f"{self.settings.pg_schema}.{GOLD}"},
                        )
                    )
                if (
                    marker.get("storage") != 3
                    or marker.get("pipeline") != self.settings.pipeline_name
                ):
                    raise ValueError("Migração: origem não reconhecida")
                data = self.checkpoint.load(marker["generation"])
            else:
                data = legacy.read_many(DEFINITIONS)
            if {r["board_id"] for r in data["dim_board"]} != {self.settings.monday_board_id}:
                raise ValueError("Migração bloqueada: escopo contém outros quadros")
            validate_state(data)
            self._validate_gold(data)
            generation = str(uuid.uuid4())
            self.checkpoint.stage(generation, data)
            saved = self.checkpoint.load(generation)
            if fingerprint(saved) != fingerprint(data):
                raise RuntimeError("Reconciliação do checkpoint falhou; nada excluído")
            backup = self.checkpoint.path.with_suffix(".before_consumption_v4.sqlite3")
            self.checkpoint.backup(backup)
            quote = self.engine.dialect.identifier_preparer.quote
            schema = quote(self.settings.pg_schema)
            with self.engine.begin() as conn:
                conn.execute(text("SET LOCAL lock_timeout='15s'"))
                conn.execute(
                    text(
                        "LOCK TABLE "
                        + ",".join(f"{schema}.{quote(n)}" for n in sorted(names))
                        + " IN ACCESS EXCLUSIVE MODE"
                    )
                )
                # Reject out-of-band writes between snapshot and exclusive lock.
                for name in names:
                    rows = [dict(r) for r in conn.execute(select(legacy.tables[name])).mappings()]
                    if fingerprint({name: rows}) != fingerprint({name: data[name]}):
                        raise RuntimeError(
                            "Origem mudou durante migração; tente novamente, nada excluído"
                        )
                grants = (
                    conn.execute(
                        text(
                            "SELECT grantee,privilege_type,is_grantable FROM information_schema.role_table_grants "
                            "WHERE table_schema=:s AND table_name=:t"
                        ),
                        {"s": self.settings.pg_schema, "t": GOLD},
                    )
                    .mappings()
                    .all()
                )
                owner = conn.scalar(
                    text(
                        "SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid=to_regclass(:t)"
                    ),
                    {"t": f"{self.settings.pg_schema}.{GOLD}"},
                )
                # No CASCADE: unknown external dependencies abort the transaction.
                conn.execute(
                    text("DROP TABLE " + ",".join(f"{schema}.{quote(n)}" for n in sorted(names)))
                )
                self.metadata.create_all(conn)
                self._publish(conn, data, self.settings.monday_board_id)
                self._mark(conn, generation)
                for name in PUBLIC_FIELDS:
                    conn.execute(
                        text(f"ALTER TABLE {schema}.{quote(name)} OWNER TO {quote(owner)}")
                    )
                for grant in grants:
                    privilege = grant["privilege_type"]
                    if privilege not in {
                        "SELECT",
                        "INSERT",
                        "UPDATE",
                        "DELETE",
                        "TRUNCATE",
                        "REFERENCES",
                        "TRIGGER",
                        "MAINTAIN",
                    }:
                        raise ValueError("Migração: privilégio não reconhecido")
                    role = "PUBLIC" if grant["grantee"] == "PUBLIC" else quote(grant["grantee"])
                    option = " WITH GRANT OPTION" if grant["is_grantable"] == "YES" else ""
                    conn.execute(text(f"GRANT {privilege} ON {schema}.{GOLD} TO {role}{option}"))
                    if privilege == "SELECT":
                        conn.execute(text(f"GRANT SELECT ON {schema}.{PENDING} TO {role}{option}"))
                if self._names(conn) != set(PUBLIC_FIELDS):
                    raise RuntimeError("Inventário final divergente")
            self.checkpoint.promote(generation)
            return {
                "tables": sorted(PUBLIC_FIELDS),
                "removed_tables": len(names) - 1,
                "rows": len(data[GOLD]),
                "checkpoint_verified": True,
                "gold_fingerprint": fingerprint({GOLD: data[GOLD]}),
                "pending_projects": len(publication(data, self.settings.preferred_timezone)[PENDING]),
            }
