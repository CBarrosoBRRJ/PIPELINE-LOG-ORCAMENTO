-- Generated from shared metadata. Additive DDL only.

CREATE SCHEMA IF NOT EXISTS sladb;


CREATE TABLE IF NOT EXISTS sladb.dim_board (
	board_id BIGSERIAL NOT NULL, 
	board_name TEXT, 
	created_at TIMESTAMP WITH TIME ZONE, 
	updated_at TIMESTAMP WITH TIME ZONE, 
	board_sk TEXT NOT NULL, 
	PRIMARY KEY (board_id), 
	CONSTRAINT uq_dim_board_surrogate UNIQUE (board_sk), 
	CONSTRAINT uq_dim_board_identity UNIQUE (board_id, board_sk)
)

;


CREATE TABLE IF NOT EXISTS sladb.dim_person (
	person_id TEXT NOT NULL, 
	person_name TEXT, 
	email TEXT, 
	person_sk TEXT NOT NULL, 
	PRIMARY KEY (person_id), 
	CONSTRAINT uq_dim_person_surrogate UNIQUE (person_sk), 
	CONSTRAINT uq_dim_person_identity UNIQUE (person_id, person_sk)
)

;


CREATE TABLE IF NOT EXISTS sladb.bronze_monday_board_schema_raw (
	board_id BIGINT NOT NULL, 
	snapshot_date DATE NOT NULL, 
	snapshot_at TIMESTAMP WITH TIME ZONE, 
	raw_data JSONB, 
	mapping JSONB, 
	PRIMARY KEY (board_id, snapshot_date), 
	CONSTRAINT fk_bronze_monday_board_sc_6408c39c FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED
)

;


CREATE TABLE IF NOT EXISTS sladb.dim_status (
	status_id TEXT NOT NULL, 
	board_id BIGINT, 
	status_label TEXT, 
	status_label_norm TEXT, 
	status_order INTEGER, 
	status_column_id TEXT, 
	status_color TEXT, 
	is_terminal BOOLEAN, 
	status_sk TEXT NOT NULL, 
	board_sk TEXT, 
	PRIMARY KEY (status_id), 
	CONSTRAINT uq_dim_status_surrogate UNIQUE (status_sk), 
	CONSTRAINT uq_dim_status_identity UNIQUE (status_id, status_sk), 
	CONSTRAINT fk_dim_status_ab14a9c2 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_sk_dim_status_f64c46d4 FOREIGN KEY(board_id, board_sk) REFERENCES sladb.dim_board (board_id, board_sk) DEFERRABLE INITIALLY DEFERRED
)

;


CREATE TABLE IF NOT EXISTS sladb.etl_run (
	run_id TEXT NOT NULL, 
	board_id BIGINT, 
	mode TEXT, 
	start_at TIMESTAMP WITH TIME ZONE, 
	end_at TIMESTAMP WITH TIME ZONE, 
	status TEXT, 
	metrics JSONB, 
	PRIMARY KEY (run_id), 
	CONSTRAINT fk_etl_run_06572f90 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED
)

;


CREATE TABLE IF NOT EXISTS sladb.etl_watermark (
	pipeline_name TEXT NOT NULL, 
	board_id BIGINT, 
	last_run_utc TIMESTAMP WITH TIME ZONE, 
	last_log_event_id TEXT, 
	last_item_page_cursor TEXT, 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (pipeline_name), 
	CONSTRAINT fk_etl_watermark_5c17326e FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED
)

;


CREATE TABLE IF NOT EXISTS sladb.meta_column_mapping (
	board_id BIGINT NOT NULL, 
	column_id TEXT NOT NULL, 
	column_title TEXT, 
	column_type TEXT, 
	analytical_attribute TEXT, 
	is_extracted BOOLEAN, 
	is_modeled BOOLEAN, 
	is_present BOOLEAN, 
	discovered_at TIMESTAMP WITH TIME ZONE, 
	board_sk TEXT, 
	PRIMARY KEY (board_id, column_id), 
	CONSTRAINT fk_meta_column_mapping_0a689ea5 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_sk_meta_column_mapping_e946c5b7 FOREIGN KEY(board_id, board_sk) REFERENCES sladb.dim_board (board_id, board_sk) DEFERRABLE INITIALLY DEFERRED
)

;


CREATE TABLE IF NOT EXISTS sladb.dim_item (
	item_id BIGSERIAL NOT NULL, 
	board_id BIGINT, 
	item_name TEXT, 
	created_at TIMESTAMP WITH TIME ZONE, 
	updated_at TIMESTAMP WITH TIME ZONE, 
	current_status_id TEXT, 
	is_active BOOLEAN, 
	last_seen_at TIMESTAMP WITH TIME ZONE, 
	item_sk TEXT NOT NULL, 
	board_sk TEXT, 
	current_status_sk TEXT, 
	PRIMARY KEY (item_id), 
	CONSTRAINT uq_dim_item_surrogate UNIQUE (item_sk), 
	CONSTRAINT uq_dim_item_identity UNIQUE (item_id, item_sk), 
	CONSTRAINT fk_dim_item_d11a0832 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_dim_item_09337c7f FOREIGN KEY(current_status_id) REFERENCES sladb.dim_status (status_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_sk_dim_item_90ad47c4 FOREIGN KEY(board_id, board_sk) REFERENCES sladb.dim_board (board_id, board_sk) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_sk_dim_item_dd30ed1b FOREIGN KEY(current_status_id, current_status_sk) REFERENCES sladb.dim_status (status_id, status_sk) DEFERRABLE INITIALLY DEFERRED
)

;


CREATE TABLE IF NOT EXISTS sladb.bridge_item_person (
	item_id BIGINT NOT NULL, 
	board_id BIGINT, 
	person_id TEXT NOT NULL, 
	role TEXT, 
	source_column_id TEXT NOT NULL, 
	snapshot_date DATE NOT NULL, 
	board_sk TEXT, 
	item_sk TEXT, 
	person_sk TEXT, 
	PRIMARY KEY (item_id, person_id, source_column_id, snapshot_date), 
	CONSTRAINT fk_bridge_item_person_781d0b8e FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_bridge_item_person_81549e59 FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_bridge_item_person_7129f07e FOREIGN KEY(person_id) REFERENCES sladb.dim_person (person_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_sk_bridge_item_person_12f60f40 FOREIGN KEY(board_id, board_sk) REFERENCES sladb.dim_board (board_id, board_sk) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_sk_bridge_item_person_cbc0d895 FOREIGN KEY(item_id, item_sk) REFERENCES sladb.dim_item (item_id, item_sk) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_sk_bridge_item_person_d42f7eec FOREIGN KEY(person_id, person_sk) REFERENCES sladb.dim_person (person_id, person_sk) DEFERRABLE INITIALLY DEFERRED
)

;


CREATE TABLE IF NOT EXISTS sladb.bronze_monday_activity_log_raw (
	event_id TEXT NOT NULL, 
	board_id BIGINT, 
	item_id BIGINT, 
	event TEXT, 
	event_at_utc TIMESTAMP WITH TIME ZONE, 
	created_at_raw TEXT, 
	status_from_text TEXT, 
	status_to_text TEXT, 
	status_from_index INTEGER, 
	status_to_index INTEGER, 
	column_id TEXT, 
	column_title TEXT, 
	group_id TEXT, 
	raw_data JSONB, 
	timestamp_source TEXT, 
	ingested_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (event_id), 
	CONSTRAINT fk_bronze_monday_activity_3dcc3f5c FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_bronze_monday_activity_b0f7a30e FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED
)

;

CREATE INDEX IF NOT EXISTS ix_bronze_monday_activity_log_raw ON sladb.bronze_monday_activity_log_raw (board_id, item_id, event_at_utc);


CREATE TABLE IF NOT EXISTS sladb.bronze_monday_item_snapshot_raw (
	item_id BIGINT NOT NULL, 
	board_id BIGINT NOT NULL, 
	item_name TEXT, 
	group_id TEXT, 
	created_at TIMESTAMP WITH TIME ZONE, 
	updated_at TIMESTAMP WITH TIME ZONE, 
	marca TEXT, 
	cliente TEXT, 
	talento TEXT, 
	intervenciencia TEXT, 
	pessoas_json JSONB, 
	snapshot_at TIMESTAMP WITH TIME ZONE, 
	snapshot_date DATE NOT NULL, 
	current_status_id TEXT, 
	status_text TEXT, 
	status_index INTEGER, 
	is_active BOOLEAN, 
	raw_data JSONB, 
	PRIMARY KEY (item_id, board_id, snapshot_date), 
	CONSTRAINT fk_bronze_monday_item_sna_24cd51e8 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_bronze_monday_item_sna_d0aabd55 FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_bronze_monday_item_sna_a359096f FOREIGN KEY(current_status_id) REFERENCES sladb.dim_status (status_id) DEFERRABLE INITIALLY DEFERRED
)

;

CREATE INDEX IF NOT EXISTS ix_bronze_monday_item_snapshot_raw ON sladb.bronze_monday_item_snapshot_raw (board_id, snapshot_at);


CREATE TABLE IF NOT EXISTS sladb.data_quality_issue (
	issue_id TEXT NOT NULL, 
	board_id BIGINT, 
	item_id BIGINT, 
	code TEXT, 
	detail TEXT, 
	detected_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (issue_id), 
	CONSTRAINT fk_data_quality_issue_703437c1 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_data_quality_issue_046237d0 FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED
)

;


CREATE TABLE IF NOT EXISTS sladb.fct_item_sla_summary (
	item_id BIGINT NOT NULL, 
	board_id BIGINT, 
	status_atual TEXT, 
	created_at TIMESTAMP WITH TIME ZONE, 
	first_status_at TIMESTAMP WITH TIME ZONE, 
	finalizado_em TIMESTAMP WITH TIME ZONE, 
	lead_time_total_min FLOAT, 
	sla_status_atual_min FLOAT, 
	open_interval BOOLEAN, 
	is_active BOOLEAN, 
	history_quality TEXT, 
	sla_start_utc TIMESTAMP WITH TIME ZONE, 
	sla_start_quality TEXT, 
	atualizado_em TIMESTAMP WITH TIME ZONE, 
	board_sk TEXT, 
	item_sk TEXT, 
	PRIMARY KEY (item_id), 
	CONSTRAINT fk_fct_item_sla_summary_c37db9ad FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_fct_item_sla_summary_4edf7f62 FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_sk_fct_item_sla_summar_4e697322 FOREIGN KEY(board_id, board_sk) REFERENCES sladb.dim_board (board_id, board_sk) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_sk_fct_item_sla_summar_3213dfd6 FOREIGN KEY(item_id, item_sk) REFERENCES sladb.dim_item (item_id, item_sk) DEFERRABLE INITIALLY DEFERRED
)

;


CREATE TABLE IF NOT EXISTS sladb.fct_item_status_daily (
	board_id BIGINT NOT NULL, 
	dt DATE NOT NULL, 
	item_id BIGINT NOT NULL, 
	status_id TEXT NOT NULL, 
	minutes_in_status FLOAT, 
	marca TEXT, 
	cliente TEXT, 
	talento TEXT, 
	intervenciencia TEXT, 
	snapshot_date DATE, 
	board_sk TEXT, 
	item_sk TEXT, 
	status_sk TEXT, 
	PRIMARY KEY (board_id, dt, item_id, status_id), 
	CONSTRAINT fk_fct_item_status_daily_d19775a0 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_fct_item_status_daily_22189c08 FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_fct_item_status_daily_9be8110c FOREIGN KEY(status_id) REFERENCES sladb.dim_status (status_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_sk_fct_item_status_dai_2e645de9 FOREIGN KEY(board_id, board_sk) REFERENCES sladb.dim_board (board_id, board_sk) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_sk_fct_item_status_dai_72627477 FOREIGN KEY(item_id, item_sk) REFERENCES sladb.dim_item (item_id, item_sk) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_sk_fct_item_status_dai_6c37dcfb FOREIGN KEY(status_id, status_sk) REFERENCES sladb.dim_status (status_id, status_sk) DEFERRABLE INITIALLY DEFERRED
)

;

CREATE INDEX IF NOT EXISTS ix_fct_item_status_daily ON sladb.fct_item_status_daily (board_id, dt);


CREATE TABLE IF NOT EXISTS sladb.fct_item_status_interval (
	interval_id TEXT NOT NULL, 
	board_id BIGINT, 
	item_id BIGINT, 
	status_id TEXT, 
	status_from TEXT, 
	status_to TEXT, 
	status_start_utc TIMESTAMP WITH TIME ZONE, 
	status_end_utc TIMESTAMP WITH TIME ZONE, 
	duration_minutes FLOAT, 
	duration_hours FLOAT, 
	is_open_interval BOOLEAN, 
	event_start_id TEXT, 
	event_end_id TEXT, 
	item_name TEXT, 
	marca TEXT, 
	cliente TEXT, 
	talento TEXT, 
	intervenciencia TEXT, 
	pessoas_json JSONB, 
	snapshot_date DATE, 
	attribute_source TEXT, 
	history_quality TEXT, 
	updated_at TIMESTAMP WITH TIME ZONE, 
	board_sk TEXT, 
	item_sk TEXT, 
	status_sk TEXT, 
	PRIMARY KEY (interval_id), 
	CONSTRAINT fk_fct_item_status_interv_607c39b9 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_fct_item_status_interv_972db58d FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_fct_item_status_interv_77e9239a FOREIGN KEY(status_id) REFERENCES sladb.dim_status (status_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_fct_item_status_interv_91c75244 FOREIGN KEY(event_start_id) REFERENCES sladb.bronze_monday_activity_log_raw (event_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_fct_item_status_interv_189ab117 FOREIGN KEY(event_end_id) REFERENCES sladb.bronze_monday_activity_log_raw (event_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_sk_fct_item_status_int_20069069 FOREIGN KEY(board_id, board_sk) REFERENCES sladb.dim_board (board_id, board_sk) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_sk_fct_item_status_int_4139de9f FOREIGN KEY(item_id, item_sk) REFERENCES sladb.dim_item (item_id, item_sk) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_sk_fct_item_status_int_3d0ce0b1 FOREIGN KEY(status_id, status_sk) REFERENCES sladb.dim_status (status_id, status_sk) DEFERRABLE INITIALLY DEFERRED
)

;

CREATE INDEX IF NOT EXISTS ix_fct_item_status_interval ON sladb.fct_item_status_interval (board_id, item_id, status_start_utc);


CREATE TABLE IF NOT EXISTS sladb.silver_monday_status_event_stg (
	event_id TEXT NOT NULL, 
	board_id BIGINT, 
	item_id BIGINT, 
	status_id TEXT, 
	status_from TEXT, 
	status_to TEXT, 
	event_at_utc TIMESTAMP WITH TIME ZONE, 
	timestamp_source TEXT, 
	board_sk TEXT, 
	item_sk TEXT, 
	status_sk TEXT, 
	PRIMARY KEY (event_id), 
	CONSTRAINT fk_silver_monday_status_e_b21a1cfe FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_silver_monday_status_e_d1373af0 FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_silver_monday_status_e_ba5ffa81 FOREIGN KEY(status_id) REFERENCES sladb.dim_status (status_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_silver_monday_status_e_b5769ee2 FOREIGN KEY(event_id) REFERENCES sladb.bronze_monday_activity_log_raw (event_id) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_sk_silver_monday_statu_b0d4ce85 FOREIGN KEY(board_id, board_sk) REFERENCES sladb.dim_board (board_id, board_sk) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_sk_silver_monday_statu_275d8684 FOREIGN KEY(item_id, item_sk) REFERENCES sladb.dim_item (item_id, item_sk) DEFERRABLE INITIALLY DEFERRED, 
	CONSTRAINT fk_sk_silver_monday_statu_1b1d6d34 FOREIGN KEY(status_id, status_sk) REFERENCES sladb.dim_status (status_id, status_sk) DEFERRABLE INITIALLY DEFERRED
)

;