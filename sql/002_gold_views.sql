-- LEGACY: rollback reference only. Current consumer: gold_projeto_status.
CREATE OR REPLACE VIEW sladb.gold_status_metrics AS
      WITH dwell AS (
        SELECT board_id, status_id, COUNT(*) AS interval_count,
          SUM(duration_minutes) AS accumulated_minutes,
          AVG(duration_minutes) AS mean_minutes,
          percentile_cont(0.5) WITHIN GROUP (ORDER BY duration_minutes) AS median_minutes,
          percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_minutes) AS p95_minutes
        FROM sladb.fct_item_status_interval GROUP BY board_id, status_id
      ), queue AS (
        SELECT board_id, current_status_id AS status_id, COUNT(*) AS current_item_count
        FROM sladb.dim_item WHERE is_active GROUP BY board_id, current_status_id
      )
      SELECT s.board_id, s.status_id, s.status_label, s.status_order, s.is_terminal,
        COALESCE(d.interval_count,0) AS interval_count, COALESCE(d.accumulated_minutes,0) AS accumulated_minutes,
        d.mean_minutes, d.median_minutes, d.p95_minutes,
        COALESCE(q.current_item_count,0) AS current_item_count,
        CASE WHEN s.is_terminal THEN 0 ELSE COALESCE(q.current_item_count,0) END AS queue_count
      FROM sladb.dim_status s LEFT JOIN dwell d USING(board_id,status_id)
      LEFT JOIN queue q USING(board_id,status_id);

CREATE OR REPLACE VIEW sladb.gold_project_status AS
      SELECT board_id, item_id, status_id, SUM(duration_minutes) AS total_minutes,
        SUM(duration_hours) AS total_hours, COUNT(*) AS visit_count
      FROM sladb.fct_item_status_interval GROUP BY board_id,item_id,status_id;

CREATE OR REPLACE VIEW sladb.gold_status_bottlenecks AS
      SELECT *, dense_rank() OVER(PARTITION BY board_id ORDER BY accumulated_minutes DESC) AS time_rank,
        dense_rank() OVER(PARTITION BY board_id ORDER BY queue_count DESC) AS queue_rank
      FROM sladb.gold_status_metrics WHERE NOT is_terminal;

CREATE OR REPLACE VIEW sladb.gold_intervals_local AS
      SELECT interval_id, board_id, item_id, status_id, status_from, status_to, status_start_utc, status_end_utc, duration_minutes, duration_hours, is_open_interval, event_start_id, event_end_id, item_name, marca, cliente, talento, intervenciencia, pessoas_json, snapshot_date, attribute_source, history_quality, updated_at, status_start_utc AT TIME ZONE 'America/Sao_Paulo' AS status_start_local,
        status_end_utc AT TIME ZONE 'America/Sao_Paulo' AS status_end_local, board_sk, item_sk, status_sk
      FROM sladb.fct_item_status_interval;
