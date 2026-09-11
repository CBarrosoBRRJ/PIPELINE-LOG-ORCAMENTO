"""Regenerate checked-in DDL from the canonical relational metadata."""

from pathlib import Path

from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import AddConstraint, CreateIndex, CreateTable

from sls_orcamento_pdd.db.bq import table_ddl
from sls_orcamento_pdd.db.postgres import postgres_views
from sls_orcamento_pdd.models.schemas import define_tables


def main():
    root = Path(__file__).resolve().parents[1] / "sql"
    metadata, tables = define_tables()
    parts = [
        "-- Generated from shared metadata. Additive DDL only.",
        "CREATE SCHEMA IF NOT EXISTS sladb;",
    ]
    dialect = postgresql.dialect()
    for table in metadata.sorted_tables:
        parts.append(str(CreateTable(table, if_not_exists=True).compile(dialect=dialect)) + ";")
        for index in table.indexes:
            parts.append(str(CreateIndex(index, if_not_exists=True).compile(dialect=dialect)) + ";")
    (root / "001_schema.sql").write_text("\n\n".join(parts), encoding="utf-8")
    (root / "002_gold_views.sql").write_text(
        ";\n\n".join(postgres_views("sladb", "America/Sao_Paulo")) + ";\n", encoding="utf-8"
    )
    migration = [
        "-- Existing databases: run sla-pipeline init-db first. It adds/backfills UUIDv5 SKs transactionally without extensions.",
        "-- Reference DDL for constraints after columns and UUIDv5 data migration. No tables are dropped.",
    ]
    constraints = []
    for table in tables.values():
        constraints.extend(
            sorted(
                (c for c in table.constraints if isinstance(c, UniqueConstraint)),
                key=lambda c: c.name,
            )
        )
    for table in tables.values():
        constraints.extend(sorted(table.foreign_key_constraints, key=lambda c: c.name))
    for constraint in constraints:
        ddl = str(AddConstraint(constraint).compile(dialect=dialect))
        migration.append(f"""DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='{constraint.name}'
                AND connamespace='sladb'::regnamespace) THEN
    {ddl};
  END IF;
END $$;""")
    (root / "005_relational_keys.sql").write_text("\n\n".join(migration), encoding="utf-8")
    bq_ddl = [
        "-- Replace placeholders with .env values.",
        'CREATE SCHEMA IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}` OPTIONS(location="${BQ_LOCATION}");',
    ]
    bq_ddl.extend(
        table_ddl("${BQ_PROJECT}.${BQ_DATASET}", t.name) + ";" for t in metadata.sorted_tables
    )
    (root / "bq" / "001_schema.sql").write_text("\n\n".join(bq_ddl) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
