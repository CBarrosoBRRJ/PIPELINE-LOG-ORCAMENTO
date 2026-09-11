-- Executar após backfill/daily. Detalhes de ingestão em sladb.etl_run.
SELECT board_id, COUNT(*) AS total_dim, COUNT(*) FILTER(WHERE is_active) AS active_items,
       100.0 * COUNT(*) FILTER(WHERE current_status_id IS NULL) / NULLIF(COUNT(*),0)
         AS pct_without_status_key
FROM sladb.dim_item GROUP BY board_id;

-- Uma chave Sem status resolve o join, mas não corrige uma lacuna da fonte.
SELECT i.board_id, COUNT(*) AS source_empty_status_items
FROM sladb.dim_item i JOIN sladb.dim_status s ON s.status_id=i.current_status_id
WHERE i.is_active AND s.status_label_norm='sem status' GROUP BY i.board_id;

-- Resultado esperado: zero linhas (tolerância: 0,00001 minuto).
SELECT board_id,item_id,SUM(duration_minutes) AS total_minutes,
       EXTRACT(EPOCH FROM (MAX(status_end_utc)-MIN(status_start_utc)))/60 AS elapsed_minutes
FROM sladb.fct_item_status_interval GROUP BY board_id,item_id
HAVING ABS(SUM(duration_minutes)-EXTRACT(EPOCH FROM (MAX(status_end_utc)-MIN(status_start_utc)))/60)>0.00001;

WITH intervals AS (
 SELECT board_id,item_id,SUM(duration_minutes) minutes
 FROM sladb.fct_item_status_interval GROUP BY board_id,item_id
), daily AS (
 SELECT board_id,item_id,SUM(minutes_in_status) minutes
 FROM sladb.fct_item_status_daily GROUP BY board_id,item_id
)
SELECT * FROM intervals i FULL JOIN daily d USING(board_id,item_id)
WHERE ABS(COALESCE(i.minutes,0)-COALESCE(d.minutes,0))>0.00001;

SELECT code,COUNT(*) AS items FROM sladb.data_quality_issue GROUP BY code ORDER BY items DESC;
SELECT * FROM sladb.gold_status_bottlenecks ORDER BY time_rank,queue_rank;
