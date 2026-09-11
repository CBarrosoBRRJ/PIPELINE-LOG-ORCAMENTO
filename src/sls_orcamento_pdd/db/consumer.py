"""One physical PostgreSQL table; private processing state in runtime SQLite.

The PostgreSQL table comment is the atomic publication receipt. A checkpoint is
fsynced first; after COMMIT it is promoted. Recovery follows the receipt, never
an uncommitted watermark. A missing volume fails closed instead of losing history.
"""

import copy
import json
import uuid
from contextlib import contextmanager

from sqlalchemy import (
    CheckConstraint,
    Column,
    Index,
    MetaData,
    Table,
    UniqueConstraint,
    select,
    text,
)
from sqlalchemy.schema import AddConstraint, CreateSchema

from ..models.contracts import prepare_payload, required_columns, validate_table
from ..models.schemas import DEFINITIONS, REPLACE_TABLES, TYPES, foreign_keys
from ..services.load import merge_rows
from .checkpoint import Checkpoint, fingerprint
from .postgres import PostgresStore

GOLD = "gold_projeto_status"


def consumer_tables(schema):
    metadata = MetaData(schema=schema)
    keys, fields = DEFINITIONS[GOLD]
    table = Table(
        GOLD,
        metadata,
        *[
            Column(
                name,
                TYPES[kind],
                primary_key=name in keys.split(","),
                nullable=name not in required_columns(GOLD),
            )
            for name, kind in (f.split(":") for f in fields.split())
        ],
    )
    table.append_constraint(
        UniqueConstraint("board_id", "item_id", "ordem_etapa", name="uq_gold_projeto_ordem")
    )
    Index("ix_gold_projeto_status", table.c.board_id, table.c.item_id, table.c.ordem_etapa)
    Index(
        "uq_gold_ultima_passagem",
        table.c.board_id,
        table.c.item_id,
        unique=True,
        postgresql_where=table.c.intervalo_aberto,
    )
    for name, expression in {
        "ck_gold_ordem": "ordem_etapa >= 1 AND passagem_numero_no_status >= 1",
        "ck_gold_marcadores": "eh_primeiro_registro = (ordem_etapa=1) AND eh_retorno = (passagem_numero_no_status>1) AND intervalo_aberto=eh_ultimo_registro",
        "ck_gold_fechamento": "intervalo_aberto = (saida_status_utc IS NULL) AND entrada_status_utc < corte_utc AND (saida_status_utc IS NULL OR saida_status_utc BETWEEN entrada_status_utc AND corte_utc)",
        "ck_gold_duracao": "duracao_minutos >= 0 AND abs(duracao_minutos - extract(epoch FROM (coalesce(saida_status_utc,corte_utc)-entrada_status_utc))/60) < 0.00001 AND abs(duracao_horas*60-duracao_minutos) < 0.00001",
    }.items():
        table.append_constraint(CheckConstraint(expression, name=name))
    return metadata, {GOLD: table}


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
        if marker.get("storage") != 3 or marker.get("pipeline") != self.settings.pipeline_name:
            raise RuntimeError("Publicação pertence a outro checkpoint/pipeline")
        return marker["generation"]

    def _mark(self, conn, generation):
        marker = json.dumps(
            {"storage": 3, "pipeline": self.settings.pipeline_name, "generation": generation}
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
            if names - {GOLD}:
                raise RuntimeError(
                    "Tabelas legadas presentes: execute migrate-single-table antes da próxima carga"
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
            result = {}
            for name in names:
                rows = data[name]
                if name == GOLD:
                    rows = [dict(r) for r in conn.execute(select(self.tables[GOLD])).mappings()]
                    if fingerprint({GOLD: rows}) != fingerprint({GOLD: data[GOLD]}):
                        raise RuntimeError(
                            "Gold alterada fora do pipeline: publicação diverge do checkpoint"
                        )
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
                    table = self.tables[GOLD]
                    conn.execute(table.delete().where(table.c.board_id == board_id))
                    for offset in range(0, len(payload[GOLD]), 500):
                        conn.execute(table.insert(), payload[GOLD][offset : offset + 500])
                self._mark(conn, generation)
            self.checkpoint.promote(generation)
            self._generation, self._cache = generation, data

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
            if names == {GOLD}:
                self.initialize()
                return {"tables": [GOLD], "already_migrated": True}
            if names != set(DEFINITIONS):
                raise ValueError(
                    "Migração requer inventário legado exato; nenhum objeto foi excluído"
                )
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
            backup = self.checkpoint.path.with_suffix(".before_migration.sqlite3")
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
                for name in DEFINITIONS:
                    rows = [dict(r) for r in conn.execute(select(legacy.tables[name])).mappings()]
                    if fingerprint({name: rows}) != fingerprint({name: data[name]}):
                        raise RuntimeError(
                            "Origem mudou durante migração; tente novamente, nada excluído"
                        )
                constraints = (
                    conn.execute(
                        text(
                            "SELECT conname FROM pg_constraint WHERE conrelid=to_regclass(:t) AND contype='f'"
                        ),
                        {"t": f"{self.settings.pg_schema}.{GOLD}"},
                    )
                    .scalars()
                    .all()
                )
                for name in constraints:
                    conn.execute(text(f"ALTER TABLE {schema}.{GOLD} DROP CONSTRAINT {quote(name)}"))
                self._constraints(conn)
                # No CASCADE: unknown external dependencies abort the transaction.
                conn.execute(
                    text(
                        "DROP TABLE "
                        + ",".join(f"{schema}.{quote(n)}" for n in sorted(names - {GOLD}))
                    )
                )
                self._mark(conn, generation)
                if self._names(conn) != {GOLD}:
                    raise RuntimeError("Inventário final divergente")
            self.checkpoint.promote(generation)
            return {
                "tables": [GOLD],
                "removed_tables": len(names) - 1,
                "rows": len(data[GOLD]),
                "checkpoint_verified": True,
                "gold_fingerprint": fingerprint({GOLD: data[GOLD]}),
            }
