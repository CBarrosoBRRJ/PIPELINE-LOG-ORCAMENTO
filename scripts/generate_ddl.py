"""Generate only the current BigQuery public table contract."""

from pathlib import Path

from sls_orcamento_ppd.db.bq import table_ddl


def main():
    target = Path(__file__).resolve().parents[1] / "sql" / "bq" / "001_schema.sql"
    target.write_text(
        "-- GCP v4: exactly one public table; dataset provisioned separately. State stays in GCS.\n\n"
        + table_ddl("${BQ_PROJECT}.${BQ_DATASET}", "${BQ_TABLE}")
        + ";\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
