# Databricks notebook source
# Configure widgets/secret scope no workspace; nunca registre credenciais em saída.
dbutils.widgets.text("secret_scope", "sla-pipeline")  # noqa: F821
dbutils.widgets.text("pg_host", "")  # noqa: F821
dbutils.widgets.text("pg_port", "5432")  # noqa: F821
dbutils.widgets.text("pg_database", "sla_workflow")  # noqa: F821
dbutils.widgets.text("pg_schema", "sladb")  # noqa: F821
scope = dbutils.widgets.get("secret_scope")  # noqa: F821
host = dbutils.widgets.get("pg_host")  # noqa: F821
port = dbutils.widgets.get("pg_port")  # noqa: F821
database = dbutils.widgets.get("pg_database")  # noqa: F821
schema = dbutils.widgets.get("pg_schema")  # noqa: F821
url = f"jdbc:postgresql://{host}:{port}/{database}"
properties = {
    "user": dbutils.secrets.get(scope, "pg-user"),  # noqa: F821
    "password": dbutils.secrets.get(scope, "pg-password"),  # noqa: F821
    "driver": "org.postgresql.Driver",
    "sslmode": "require",
}
intervals = spark.read.jdbc(  # noqa: F821
    url=url, table=f"{schema}.fct_item_status_interval", properties=properties
)
intervals.createOrReplaceTempView("sla_status_intervals")
