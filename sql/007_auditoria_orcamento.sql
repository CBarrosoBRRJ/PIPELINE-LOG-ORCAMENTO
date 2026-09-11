-- Leitura apenas. Todos os grupos_duplicados devem ser zero.
SELECT 'dim_board' AS tabela, COUNT(*) AS grupos_duplicados
FROM (SELECT board_id FROM orcamento.dim_board GROUP BY board_id HAVING COUNT(*) > 1) d
UNION ALL
SELECT 'meta_column_mapping' AS tabela, COUNT(*) AS grupos_duplicados
FROM (SELECT board_id,column_id FROM orcamento.meta_column_mapping GROUP BY board_id,column_id HAVING COUNT(*) > 1) d
UNION ALL
SELECT 'bronze_monday_activity_log_raw' AS tabela, COUNT(*) AS grupos_duplicados
FROM (SELECT event_id FROM orcamento.bronze_monday_activity_log_raw GROUP BY event_id HAVING COUNT(*) > 1) d
UNION ALL
SELECT 'bronze_monday_item_snapshot_raw' AS tabela, COUNT(*) AS grupos_duplicados
FROM (SELECT board_id,item_id,snapshot_date FROM orcamento.bronze_monday_item_snapshot_raw GROUP BY board_id,item_id,snapshot_date HAVING COUNT(*) > 1) d
UNION ALL
SELECT 'bronze_monday_board_schema_raw' AS tabela, COUNT(*) AS grupos_duplicados
FROM (SELECT board_id,snapshot_date FROM orcamento.bronze_monday_board_schema_raw GROUP BY board_id,snapshot_date HAVING COUNT(*) > 1) d
UNION ALL
SELECT 'silver_monday_status_event_stg' AS tabela, COUNT(*) AS grupos_duplicados
FROM (SELECT event_id FROM orcamento.silver_monday_status_event_stg GROUP BY event_id HAVING COUNT(*) > 1) d
UNION ALL
SELECT 'dim_status' AS tabela, COUNT(*) AS grupos_duplicados
FROM (SELECT status_id FROM orcamento.dim_status GROUP BY status_id HAVING COUNT(*) > 1) d
UNION ALL
SELECT 'dim_person' AS tabela, COUNT(*) AS grupos_duplicados
FROM (SELECT person_id FROM orcamento.dim_person GROUP BY person_id HAVING COUNT(*) > 1) d
UNION ALL
SELECT 'dim_item' AS tabela, COUNT(*) AS grupos_duplicados
FROM (SELECT item_id FROM orcamento.dim_item GROUP BY item_id HAVING COUNT(*) > 1) d
UNION ALL
SELECT 'bridge_item_person' AS tabela, COUNT(*) AS grupos_duplicados
FROM (SELECT item_id,person_id,source_column_id,snapshot_date FROM orcamento.bridge_item_person GROUP BY item_id,person_id,source_column_id,snapshot_date HAVING COUNT(*) > 1) d
UNION ALL
SELECT 'fct_item_status_interval' AS tabela, COUNT(*) AS grupos_duplicados
FROM (SELECT interval_id FROM orcamento.fct_item_status_interval GROUP BY interval_id HAVING COUNT(*) > 1) d
UNION ALL
SELECT 'fct_item_status_daily' AS tabela, COUNT(*) AS grupos_duplicados
FROM (SELECT board_id,dt,item_id,status_id FROM orcamento.fct_item_status_daily GROUP BY board_id,dt,item_id,status_id HAVING COUNT(*) > 1) d
UNION ALL
SELECT 'fct_item_sla_summary' AS tabela, COUNT(*) AS grupos_duplicados
FROM (SELECT item_id FROM orcamento.fct_item_sla_summary GROUP BY item_id HAVING COUNT(*) > 1) d
UNION ALL
SELECT 'etl_watermark' AS tabela, COUNT(*) AS grupos_duplicados
FROM (SELECT pipeline_name FROM orcamento.etl_watermark GROUP BY pipeline_name HAVING COUNT(*) > 1) d
UNION ALL
SELECT 'etl_run' AS tabela, COUNT(*) AS grupos_duplicados
FROM (SELECT run_id FROM orcamento.etl_run GROUP BY run_id HAVING COUNT(*) > 1) d
UNION ALL
SELECT 'data_quality_issue' AS tabela, COUNT(*) AS grupos_duplicados
FROM (SELECT issue_id FROM orcamento.data_quality_issue GROUP BY issue_id HAVING COUNT(*) > 1) d
ORDER BY tabela;

SELECT code,COUNT(*) AS ocorrencias,COUNT(DISTINCT item_id) AS projetos
FROM orcamento.data_quality_issue GROUP BY code ORDER BY ocorrencias DESC;

SELECT status_label,is_terminal,queue_count,current_item_count
FROM orcamento.gold_status_metrics ORDER BY status_order;

SELECT last_run_utc,updated_at FROM orcamento.etl_watermark;
