-- Replace placeholders with .env values.

CREATE SCHEMA IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}` OPTIONS(location="${BQ_LOCATION}");

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (
  `board_id` INT64 NOT NULL,
  `board_name` STRING NOT NULL,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL,
  `board_sk` STRING,
  PRIMARY KEY (`board_id`) NOT ENFORCED
)
CLUSTER BY board_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.dim_person` (
  `person_id` STRING NOT NULL,
  `person_name` STRING NOT NULL,
  `email` STRING,
  `person_sk` STRING,
  PRIMARY KEY (`person_id`) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.bronze_monday_board_schema_raw` (
  `board_id` INT64 NOT NULL,
  `snapshot_date` DATE NOT NULL,
  `snapshot_at` TIMESTAMP NOT NULL,
  `raw_data` JSON NOT NULL,
  `mapping` JSON NOT NULL,
  PRIMARY KEY (`board_id`, `snapshot_date`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED
)
PARTITION BY snapshot_date
CLUSTER BY board_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.dim_status` (
  `status_id` STRING NOT NULL,
  `board_id` INT64 NOT NULL,
  `status_label` STRING NOT NULL,
  `status_label_norm` STRING NOT NULL,
  `status_order` INT64,
  `status_column_id` STRING NOT NULL,
  `status_color` STRING,
  `is_terminal` BOOL NOT NULL,
  `status_sk` STRING,
  `board_sk` STRING,
  PRIMARY KEY (`status_id`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED
)
CLUSTER BY board_id, status_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.etl_run` (
  `run_id` STRING NOT NULL,
  `board_id` INT64 NOT NULL,
  `mode` STRING NOT NULL,
  `start_at` TIMESTAMP NOT NULL,
  `end_at` TIMESTAMP NOT NULL,
  `status` STRING NOT NULL,
  `metrics` JSON NOT NULL,
  PRIMARY KEY (`run_id`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED
)
PARTITION BY DATE(start_at)
CLUSTER BY board_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.etl_watermark` (
  `pipeline_name` STRING NOT NULL,
  `board_id` INT64 NOT NULL,
  `last_run_utc` TIMESTAMP NOT NULL,
  `last_log_event_id` STRING,
  `last_item_page_cursor` STRING,
  `updated_at` TIMESTAMP NOT NULL,
  PRIMARY KEY (`pipeline_name`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED
)
CLUSTER BY board_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.meta_column_mapping` (
  `board_id` INT64 NOT NULL,
  `column_id` STRING NOT NULL,
  `column_title` STRING NOT NULL,
  `column_type` STRING NOT NULL,
  `analytical_attribute` STRING,
  `is_extracted` BOOL NOT NULL,
  `is_modeled` BOOL NOT NULL,
  `is_present` BOOL NOT NULL,
  `discovered_at` TIMESTAMP NOT NULL,
  `board_sk` STRING,
  PRIMARY KEY (`board_id`, `column_id`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED
)
CLUSTER BY board_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.meta_entity_mapping` (
  `board_id` INT64 NOT NULL,
  `entity_type` STRING NOT NULL,
  `source_key` STRING NOT NULL,
  `source_text` STRING NOT NULL,
  `canonical_id` STRING,
  `canonical_name` STRING,
  `entity_kind` STRING NOT NULL,
  `review_status` STRING NOT NULL,
  `reviewed_by` STRING,
  `review_reason` STRING,
  `updated_at` TIMESTAMP NOT NULL,
  PRIMARY KEY (`board_id`, `entity_type`, `source_key`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED
)
CLUSTER BY board_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.meta_gold_rule_snapshot` (
  `versao_regras` STRING NOT NULL,
  `board_id` INT64 NOT NULL,
  `conteudo` JSON NOT NULL,
  `registrado_em` TIMESTAMP NOT NULL,
  PRIMARY KEY (`versao_regras`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED
)
CLUSTER BY board_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.dim_item` (
  `item_id` INT64 NOT NULL,
  `board_id` INT64 NOT NULL,
  `item_name` STRING NOT NULL,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `current_status_id` STRING NOT NULL,
  `is_active` BOOL NOT NULL,
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
  `item_id` INT64 NOT NULL,
  `board_id` INT64 NOT NULL,
  `person_id` STRING NOT NULL,
  `role` STRING NOT NULL,
  `source_column_id` STRING NOT NULL,
  `snapshot_date` DATE NOT NULL,
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
  `event_id` STRING NOT NULL,
  `board_id` INT64 NOT NULL,
  `item_id` INT64 NOT NULL,
  `event` STRING NOT NULL,
  `event_at_utc` TIMESTAMP NOT NULL,
  `created_at_raw` STRING,
  `status_from_text` STRING,
  `status_to_text` STRING,
  `status_from_index` INT64,
  `status_to_index` INT64,
  `column_id` STRING NOT NULL,
  `column_title` STRING,
  `group_id` STRING,
  `raw_data` JSON NOT NULL,
  `timestamp_source` STRING NOT NULL,
  `ingested_at` TIMESTAMP NOT NULL,
  PRIMARY KEY (`event_id`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED,
  FOREIGN KEY (`item_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_item` (`item_id`) NOT ENFORCED
)
PARTITION BY DATE(event_at_utc)
CLUSTER BY board_id, item_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.bronze_monday_item_snapshot_raw` (
  `item_id` INT64 NOT NULL,
  `board_id` INT64 NOT NULL,
  `item_name` STRING,
  `group_id` STRING,
  `created_at` TIMESTAMP,
  `updated_at` TIMESTAMP,
  `marca` STRING,
  `cliente` STRING,
  `talento` STRING,
  `intervenciencia` STRING,
  `pessoas_json` JSON,
  `snapshot_at` TIMESTAMP NOT NULL,
  `snapshot_date` DATE NOT NULL,
  `current_status_id` STRING NOT NULL,
  `status_text` STRING,
  `status_index` INT64,
  `is_active` BOOL NOT NULL,
  `raw_data` JSON NOT NULL,
  PRIMARY KEY (`board_id`, `item_id`, `snapshot_date`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED,
  FOREIGN KEY (`item_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_item` (`item_id`) NOT ENFORCED,
  FOREIGN KEY (`current_status_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_status` (`status_id`) NOT ENFORCED
)
PARTITION BY snapshot_date
CLUSTER BY board_id, item_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.data_quality_issue` (
  `issue_id` STRING NOT NULL,
  `board_id` INT64 NOT NULL,
  `item_id` INT64 NOT NULL,
  `code` STRING NOT NULL,
  `detail` STRING NOT NULL,
  `detected_at` TIMESTAMP NOT NULL,
  PRIMARY KEY (`issue_id`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED,
  FOREIGN KEY (`item_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_item` (`item_id`) NOT ENFORCED
)
CLUSTER BY board_id, item_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.fct_item_sla_summary` (
  `item_id` INT64 NOT NULL,
  `board_id` INT64 NOT NULL,
  `status_atual` STRING NOT NULL,
  `created_at` TIMESTAMP,
  `first_status_at` TIMESTAMP,
  `finalizado_em` TIMESTAMP,
  `lead_time_total_min` FLOAT64,
  `sla_status_atual_min` FLOAT64,
  `open_interval` BOOL NOT NULL,
  `is_active` BOOL NOT NULL,
  `history_quality` STRING NOT NULL,
  `sla_start_utc` TIMESTAMP,
  `sla_start_quality` STRING NOT NULL,
  `atualizado_em` TIMESTAMP NOT NULL,
  `board_sk` STRING,
  `item_sk` STRING,
  PRIMARY KEY (`item_id`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED,
  FOREIGN KEY (`item_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_item` (`item_id`) NOT ENFORCED
)
CLUSTER BY board_id, item_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.fct_item_status_daily` (
  `board_id` INT64 NOT NULL,
  `dt` DATE NOT NULL,
  `item_id` INT64 NOT NULL,
  `status_id` STRING NOT NULL,
  `minutes_in_status` FLOAT64 NOT NULL,
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

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.quarentena_projeto` (
  `board_id` INT64 NOT NULL,
  `item_id` INT64 NOT NULL,
  `projeto_nome` STRING NOT NULL,
  `marca_original` STRING,
  `talento_original` STRING,
  `interveniencia_original` STRING,
  `motivos` JSON NOT NULL,
  `cadastro_referencia_utc` TIMESTAMP,
  `corte_utc` TIMESTAMP NOT NULL,
  `versao_regras` STRING NOT NULL,
  `atualizado_em` TIMESTAMP NOT NULL,
  `board_sk` STRING NOT NULL,
  `item_sk` STRING NOT NULL,
  PRIMARY KEY (`board_id`, `item_id`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED,
  FOREIGN KEY (`item_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_item` (`item_id`) NOT ENFORCED,
  FOREIGN KEY (`versao_regras`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.meta_gold_rule_snapshot` (`versao_regras`) NOT ENFORCED
)
CLUSTER BY board_id, item_id;

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.fct_item_status_interval` (
  `interval_id` STRING NOT NULL,
  `board_id` INT64 NOT NULL,
  `item_id` INT64 NOT NULL,
  `status_id` STRING NOT NULL,
  `status_from` STRING,
  `status_to` STRING NOT NULL,
  `status_start_utc` TIMESTAMP NOT NULL,
  `status_end_utc` TIMESTAMP NOT NULL,
  `duration_minutes` FLOAT64 NOT NULL,
  `duration_hours` FLOAT64 NOT NULL,
  `is_open_interval` BOOL NOT NULL,
  `event_start_id` STRING,
  `event_end_id` STRING,
  `item_name` STRING,
  `marca` STRING,
  `cliente` STRING,
  `talento` STRING,
  `intervenciencia` STRING,
  `pessoas_json` JSON,
  `snapshot_date` DATE,
  `attribute_source` STRING NOT NULL,
  `history_quality` STRING NOT NULL,
  `updated_at` TIMESTAMP NOT NULL,
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
  `event_id` STRING NOT NULL,
  `board_id` INT64 NOT NULL,
  `item_id` INT64 NOT NULL,
  `status_id` STRING NOT NULL,
  `status_from` STRING,
  `status_to` STRING,
  `event_at_utc` TIMESTAMP NOT NULL,
  `timestamp_source` STRING NOT NULL,
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

CREATE TABLE IF NOT EXISTS `${BQ_PROJECT}.${BQ_DATASET}.gold_projeto_status` (
  `interval_id` STRING NOT NULL,
  `board_id` INT64 NOT NULL,
  `item_id` INT64 NOT NULL,
  `status_id` STRING NOT NULL,
  `projeto_nome` STRING NOT NULL,
  `status_nome` STRING NOT NULL,
  `ordem_status_quadro` INT64,
  `status_final` BOOL NOT NULL,
  `ordem_etapa` INT64 NOT NULL,
  `passagem_numero_no_status` INT64 NOT NULL,
  `eh_retorno` BOOL NOT NULL,
  `eh_primeiro_registro` BOOL NOT NULL,
  `eh_ultimo_registro` BOOL NOT NULL,
  `entrada_status_utc` TIMESTAMP NOT NULL,
  `saida_status_utc` TIMESTAMP,
  `entrada_status_local` DATETIME NOT NULL,
  `saida_status_local` DATETIME,
  `corte_utc` TIMESTAMP NOT NULL,
  `corte_local` DATETIME NOT NULL,
  `duracao_minutos` FLOAT64 NOT NULL,
  `duracao_horas` FLOAT64 NOT NULL,
  `intervalo_aberto` BOOL NOT NULL,
  `qualidade_historico` STRING NOT NULL,
  `elegivel_comparacao` BOOL NOT NULL,
  `horas_observadas_encerradas` FLOAT64,
  `status_atual_id` STRING NOT NULL,
  `status_atual_nome` STRING NOT NULL,
  `projeto_ativo` BOOL NOT NULL,
  `projeto_na_fila` BOOL NOT NULL,
  `status_atual_divergente` BOOL NOT NULL,
  `entrada_comprovada_utc` TIMESTAMP,
  `finalizado_em_utc` TIMESTAMP,
  `tempo_desde_entrada_horas` FLOAT64,
  `tempo_status_atual_horas` FLOAT64,
  `marca_chave` STRING,
  `marca_nome` STRING,
  `marca_situacao` STRING NOT NULL,
  `talento_chave` STRING,
  `talento_nome` STRING,
  `talento_origem` STRING,
  `talento_situacao` STRING NOT NULL,
  `responsavel_orcamento` STRING,
  `responsaveis_orcamento_json` JSON NOT NULL,
  `quantidade_responsaveis_orcamento` INT64 NOT NULL,
  `responsavel_situacao` STRING NOT NULL,
  `talent_manager` STRING,
  `gp` STRING,
  `audiencia` STRING,
  `conteudo` STRING,
  `producao` STRING,
  `pessoas_referencia_json` JSON NOT NULL,
  `cadastro_referencia_utc` TIMESTAMP,
  `versao_regras` STRING NOT NULL,
  `board_sk` STRING NOT NULL,
  `item_sk` STRING NOT NULL,
  `status_sk` STRING NOT NULL,
  PRIMARY KEY (`interval_id`) NOT ENFORCED,
  FOREIGN KEY (`board_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_board` (`board_id`) NOT ENFORCED,
  FOREIGN KEY (`item_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_item` (`item_id`) NOT ENFORCED,
  FOREIGN KEY (`status_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_status` (`status_id`) NOT ENFORCED,
  FOREIGN KEY (`versao_regras`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.meta_gold_rule_snapshot` (`versao_regras`) NOT ENFORCED,
  FOREIGN KEY (`interval_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.fct_item_status_interval` (`interval_id`) NOT ENFORCED,
  FOREIGN KEY (`status_atual_id`) REFERENCES `${BQ_PROJECT}.${BQ_DATASET}.dim_status` (`status_id`) NOT ENFORCED
)
PARTITION BY DATE(entrada_status_utc)
CLUSTER BY board_id, item_id, status_id;
