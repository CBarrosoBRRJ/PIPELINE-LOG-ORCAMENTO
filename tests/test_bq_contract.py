from sls_orcamento_pdd.db.bq import integrity_assertions, table_ddl
from sls_orcamento_pdd.models.schemas import DEFINITIONS, define_tables, foreign_keys


def test_bq_schema_preserves_keys_partitioning_and_relationships():
    sql = table_ddl("project.dataset", "fct_item_status_interval")
    assert "`item_id` INT64" in sql
    assert "PARTITION BY DATE(status_start_utc)" in sql
    assert "REFERENCES `project.dataset.dim_item` (`item_id`) NOT ENFORCED" in sql
    assert "CLUSTER BY board_id, item_id, status_id" in sql


def test_bq_checks_integrity_before_publication():
    statements = integrity_assertions("project.dataset", DEFINITIONS)
    assert len(statements) >= len(DEFINITIONS) + len(foreign_keys())
    assert all(s.startswith("ASSERT") for s in statements)
    assert any("Invalid primary key: bronze_monday_item_snapshot_raw" in s for s in statements)
    assert any("Invalid foreign key: bridge_item_person.person_id" in s for s in statements)


def test_metadata_creation_order_has_parents_before_children():
    metadata, _ = define_tables()
    order = {table.name: i for i, table in enumerate(metadata.sorted_tables)}
    assert all(order[parent] < order[child] for child, _, parent, _ in foreign_keys())
