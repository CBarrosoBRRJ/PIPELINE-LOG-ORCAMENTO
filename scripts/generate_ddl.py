"""Regenerate checked-in DDL from the canonical relational metadata."""

from pathlib import Path

from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import AddConstraint, CreateIndex, CreateTable

from sls_orcamento_pdd.db.bq import table_ddl
from sls_orcamento_pdd.db.consumer import consumer_tables
from sls_orcamento_pdd.db.postgres import postgres_views
from sls_orcamento_pdd.models.schemas import define_tables


def main():
    root = Path(__file__).resolve().parents[1] / "sql"
    metadata, tables = consumer_tables("orcamento")
    parts = [
        "-- PostgreSQL v3: ONLY the consumption table. Use CLI init-db (new) or migrate-single-table (legacy) to pair executor state.",
        "CREATE SCHEMA IF NOT EXISTS orcamento;",
    ]
    dialect = postgresql.dialect()
    for table in metadata.sorted_tables:
        parts.append(str(CreateTable(table, if_not_exists=True).compile(dialect=dialect)) + ";")
        for index in table.indexes:
            parts.append(str(CreateIndex(index, if_not_exists=True).compile(dialect=dialect)) + ";")
    ddl = "\n\n".join(parts)
    (root / "001_schema.sql").write_text(
        "\n".join(line.rstrip() for line in ddl.splitlines()) + "\n", encoding="utf-8"
    )
    # Kept only as a rollback reference; never executed by initialize().
    (root / "002_gold_views.sql").write_text(
        "-- LEGACY: rollback reference only. Current consumer: gold_projeto_status.\n"
        + ";\n\n".join(postgres_views("sladb", "America/Sao_Paulo"))
        + ";\n",
        encoding="utf-8",
    )
    migration = [
        "-- PostgreSQL v3: reference uniqueness only. Internal references are validated in Python.",
        "-- Legacy migration: sla-pipeline migrate-single-table. Never recreate technical tables.",
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
                AND connamespace='orcamento'::regnamespace) THEN
    {ddl};
  END IF;
END $$;""")
    (root / "005_relational_keys.sql").write_text("\n\n".join(migration), encoding="utf-8")
    bq_ddl = [
        "-- Future BigQuery adapter reference (not deployed); internal logical model, not current PostgreSQL inventory.",
        'CREATE SCHEMA IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}` OPTIONS(location="${BQ_LOCATION}");',
    ]
    metadata, _ = define_tables()
    bq_ddl.extend(
        table_ddl("${BQ_PROJECT}.${BQ_DATASET}", t.name) + ";" for t in metadata.sorted_tables
    )
    (root / "bq" / "001_schema.sql").write_text("\n\n".join(bq_ddl) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
