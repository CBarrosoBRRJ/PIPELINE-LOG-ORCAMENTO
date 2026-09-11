-- Replace placeholders with .env values.

CREATE SCHEMA IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}` OPTIONS(location="${BQ_LOCATION}");

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (
  `board_id` INT64,
  `board_name` STRING,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `board_sk` STRING,
  PRIMARY KEY (`board_id`) NOT ENFORCED
)
CLUSTER BY board_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.dim_person` (
  `person_id` STRING,
  `person_name` STRING,
  `email` STRING,
  `person_sk` STRING,
  PRIMARY KEY (`person_id`) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.bronze_monday_board_schema_raw` (
  `board_id` INT64,
  `snapshot_date` DATE,
  `snapshot_at` TIMESTAMP,
  `raw_data` JSON,
  `mapping` JSON,
  PRIMARY KEY (`board_id`, `snapshot_date`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED
)
PARTITION BY snapshot_date
CLUSTER BY board_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.dim_status` (
  `status_id` STRING,
  `board_id` INT64,
  `status_label` STRING,
  `status_label_norm` STRING,
  `status_order` INT64,
  `status_column_id` STRING,
  `status_color` STRING,
  `is_terminal` BOOL,
  `status_sk` STRING,
  `board_sk` STRING,
  PRIMARY KEY (`status_id`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED
)
CLUSTER BY board_id, status_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.etl_run` (
  `run_id` STRING,
  `board_id` INT64,
  `mode` STRING,
  `start_at` TIMESTAMP,
  `end_at` TIMESTAMP,
  `status` STRING,
  `metrics` JSON,
  PRIMARY KEY (`run_id`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED
)
PARTITION BY DATE(start_at)
CLUSTER BY board_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.etl_watermark` (
  `pipeline_name` STRING,
  `board_id` INT64,
  `last_run_utc` TIMESTAMP,
  `last_log_event_id` STRING,
  `last_item_page_cursor` STRING,
  `updated_at` TIMESTAMP,
  PRIMARY KEY (`pipeline_name`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED
)
CLUSTER BY board_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.meta_column_mapping` (
  `board_id` INT64,
  `column_id` STRING,
  `column_title` STRING,
  `column_type` STRING,
  `analytical_attribute` STRING,
  `is_extracted` BOOL,
  `is_modeled` BOOL,
  `is_present` BOOL,
  `discovered_at` TIMESTAMP,
  `board_sk` STRING,
  PRIMARY KEY (`board_id`, `column_id`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED
)
CLUSTER BY board_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.dim_item` (
  `item_id` INT64,
  `board_id` INT64,
  `item_name` STRING,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `current_status_id` STRING,
  `is_active` BOOL,
  `last_seen_at` TIMESTAMP,
  `item_sk` STRING,
  `board_sk` STRING,
  `current_status_sk` STRING,
  PRIMARY KEY (`item_id`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED,
  FOREIGN KEY (`current_status_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_status` (`status_id`) NOT ENFORCED
)
CLUSTER BY board_id, item_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.bridge_item_person` (
  `item_id` INT64,
  `board_id` INT64,
  `person_id` STRING,
  `role` STRING,
  `source_column_id` STRING,
  `snapshot_date` DATE,
  `board_sk` STRING,
  `item_sk` STRING,
  `person_sk` STRING,
  PRIMARY KEY (`item_id`, `person_id`, `source_column_id`, `snapshot_date`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED,
  FOREIGN KEY (`item_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_item` (`item_id`) NOT ENFORCED,
  FOREIGN KEY (`person_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_person` (`person_id`) NOT ENFORCED
)
CLUSTER BY board_id, item_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.bronze_monday_activity_log_raw` (
  `event_id` STRING,
  `board_id` INT64,
  `item_id` INT64,
  `event` STRING,
  `event_at_utc` TIMESTAMP,
  `created_at_raw` STRING,
  `status_from_text` STRING,
  `status_to_text` STRING,
  `status_from_index` INT64,
  `status_to_index` INT64,
  `column_id` STRING,
  `column_title` STRING,
  `group_id` STRING,
  `raw_data` JSON,
  `timestamp_source` STRING,
  `ingested_at` TIMESTAMP,
  PRIMARY KEY (`event_id`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED,
  FOREIGN KEY (`item_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_item` (`item_id`) NOT ENFORCED
)
PARTITION BY DATE(event_at_utc)
CLUSTER BY board_id, item_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.bronze_monday_item_snapshot_raw` (
  `item_id` INT64,
  `board_id` INT64,
  `item_name` STRING,
  `group_id` STRING,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `marca` STRING,
  `cliente` STRING,
  `talento` STRING,
  `intervenciencia` STRING,
  `pessoas_json` JSON,
  `snapshot_at` TIMESTAMP,
  `snapshot_date` DATE,
  `current_status_id` STRING,
  `status_text` STRING,
  `status_index` INT64,
  `is_active` BOOL,
  `raw_data` JSON,
  PRIMARY KEY (`board_id`, `item_id`, `snapshot_date`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED,
  FOREIGN KEY (`item_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_item` (`item_id`) NOT ENFORCED,
  FOREIGN KEY (`current_status_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_status` (`status_id`) NOT ENFORCED
)
PARTITION BY snapshot_date
CLUSTER BY board_id, item_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.data_quality_issue` (
  `issue_id` STRING,
  `board_id` INT64,
  `item_id` INT64,
  `code` STRING,
  `detail` STRING,
  `detected_at` TIMESTAMP,
  PRIMARY KEY (`issue_id`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED,
  FOREIGN KEY (`item_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_item` (`item_id`) NOT ENFORCED
)
CLUSTER BY board_id, item_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.fct_item_sla_summary` (
  `item_id` INT64,
  `board_id` INT64,
  `status_atual` STRING,
  `created_at` TIMESTAMP,
  `first_status_at` TIMESTAMP,
  `finalizado_em` TIMESTAMP,
  `lead_time_total_min` FLOAT64,
  `sla_status_atual_min` FLOAT64,
  `open_interval` BOOL,
  `is_active` BOOL,
  `history_quality` STRING,
  `sla_start_utc` TIMESTAMP,
  `sla_start_quality` STRING,
  `atualizado_em` TIMESTAMP,
  `board_sk` STRING,
  `item_sk` STRING,
  PRIMARY KEY (`item_id`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED,
  FOREIGN KEY (`item_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_item` (`item_id`) NOT ENFORCED
)
CLUSTER BY board_id, item_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.fct_item_status_daily` (
  `board_id` INT64,
  `dt` DATE,
  `item_id` INT64,
  `status_id` STRING,
  `minutes_in_status` FLOAT64,
  `marca` STRING,
  `cliente` STRING,
  `talento` STRING,
  `intervenciencia` STRING,
  `snapshot_date` DATE,
  `board_sk` STRING,
  `item_sk` STRING,
  `status_sk` STRING,
  PRIMARY KEY (`board_id`, `dt`, `item_id`, `status_id`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED,
  FOREIGN KEY (`item_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_item` (`item_id`) NOT ENFORCED,
  FOREIGN KEY (`status_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_status` (`status_id`) NOT ENFORCED
)
PARTITION BY dt
CLUSTER BY board_id, item_id, status_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.fct_item_status_interval` (
  `interval_id` STRING,
  `board_id` INT64,
  `item_id` INT64,
  `status_id` STRING,
  `status_from` STRING,
  `status_to` STRING,
  `status_start_utc` TIMESTAMP,
  `status_end_utc` TIMESTAMP,
  `duration_minutes` FLOAT64,
  `duration_hours` FLOAT64,
  `is_open_interval` BOOL,
  `event_start_id` STRING,
  `event_end_id` STRING,
  `item_name` STRING,
  `marca` STRING,
  `cliente` STRING,
  `talento` STRING,
  `intervenciencia` STRING,
  `pessoas_json` JSON,
  `snapshot_date` DATE,
  `attribute_source` STRING,
  `history_quality` STRING,
  `updated_at` TIMESTAMP,
  `board_sk` STRING,
  `item_sk` STRING,
  `status_sk` STRING,
  PRIMARY KEY (`interval_id`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED,
  FOREIGN KEY (`item_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_item` (`item_id`) NOT ENFORCED,
  FOREIGN KEY (`status_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_status` (`status_id`) NOT ENFORCED,
  FOREIGN KEY (`event_start_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.bronze_monday_activity_log_raw` (`event_id`) NOT ENFORCED,
  FOREIGN KEY (`event_end_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.bronze_monday_activity_log_raw` (`event_id`) NOT ENFORCED
)
PARTITION BY DATE(status_start_utc)
CLUSTER BY board_id, item_id, status_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.silver_monday_status_event_stg` (
  `event_id` STRING,
  `board_id` INT64,
  `item_id` INT64,
  `status_id` STRING,
  `status_from` STRING,
  `status_to` STRING,
  `event_at_utc` TIMESTAMP,
  `timestamp_source` STRING,
  `board_sk` STRING,
  `item_sk` STRING,
  `status_sk` STRING,
  PRIMARY KEY (`event_id`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED,
  FOREIGN KEY (`item_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_item` (`item_id`) NOT ENFORCED,
  FOREIGN KEY (`status_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_status` (`status_id`) NOT ENFORCED,
  FOREIGN KEY (`event_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.bronze_monday_activity_log_raw` (`event_id`) NOT ENFORCED
)
PARTITION BY DATE(event_at_utc)
CLUSTER BY board_id, item_id, status_id;
