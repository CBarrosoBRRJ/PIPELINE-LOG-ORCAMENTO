from sls_orcamento_ppd.db.bq import public_schema, table_ddl
from sls_orcamento_ppd.models.bq_consumption import FIELDS


def test_only_public_gold_ddl_with_nullable_unknown_times():
    sql = table_ddl("project.dataset")
    assert sql.count("CREATE TABLE") == 1
    assert "project.dataset.sla_orcamento" in sql
    assert "CLUSTER BY board_id, item_id, status_id" in sql
    assert "REFERENCES" not in sql
    assert "entrada_status_utc` TIMESTAMP," in sql
    assert "duracao_horas_uteis` FLOAT64," in sql
    schema = {f.name: f for f in public_schema()}
    assert set(schema) == {f.split(":")[0] for f in FIELDS.split()}
    assert schema["interval_id"].mode == "REQUIRED"
    assert schema["entrada_status_utc"].mode == "NULLABLE"
    assert schema["versao_calendario"].mode == "REQUIRED"
