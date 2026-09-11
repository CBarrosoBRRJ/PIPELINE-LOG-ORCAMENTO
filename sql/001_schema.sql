-- Generated from shared metadata. Additive DDL only.

CREATE SCHEMA IF NOT EXISTS sladb;


CREATE TABLE IF NOT EXISTS sladb.dim_board (
	board_id BIGSERIAL NOT NULL,
	board_name TEXT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	board_sk TEXT NOT NULL,
	PRIMARY KEY (board_id),
	CONSTRAINT uq_dim_board_surrogate UNIQUE (board_sk),
	CONSTRAINT uq_dim_board_identity UNIQUE (board_id, board_sk)
)

;


CREATE TABLE IF NOT EXISTS sladb.dim_person (
	person_id TEXT NOT NULL,
	person_name TEXT NOT NULL,
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
	snapshot_at TIMESTAMP WITH TIME ZONE NOT NULL,
	raw_data JSONB NOT NULL,
	mapping JSONB NOT NULL,
	PRIMARY KEY (board_id, snapshot_date),
	CONSTRAINT fk_bronze_monday_board_sc_6408c39c FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED
)

;


CREATE TABLE IF NOT EXISTS sladb.dim_status (
	status_id TEXT NOT NULL,
	board_id BIGINT NOT NULL,
	status_label TEXT NOT NULL,
	status_label_norm TEXT NOT NULL,
	status_order INTEGER,
	status_column_id TEXT NOT NULL,
	status_color TEXT,
	is_terminal BOOLEAN NOT NULL,
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
	board_id BIGINT NOT NULL,
	mode TEXT NOT NULL,
	start_at TIMESTAMP WITH TIME ZONE NOT NULL,
	end_at TIMESTAMP WITH TIME ZONE NOT NULL,
	status TEXT NOT NULL,
	metrics JSONB NOT NULL,
	PRIMARY KEY (run_id),
	CONSTRAINT fk_etl_run_06572f90 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED
)

;


CREATE TABLE IF NOT EXISTS sladb.etl_watermark (
	pipeline_name TEXT NOT NULL,
	board_id BIGINT NOT NULL,
	last_run_utc TIMESTAMP WITH TIME ZONE NOT NULL,
	last_log_event_id TEXT,
	last_item_page_cursor TEXT,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (pipeline_name),
	CONSTRAINT fk_etl_watermark_5c17326e FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED
)

;


CREATE TABLE IF NOT EXISTS sladb.meta_column_mapping (
	board_id BIGINT NOT NULL,
	column_id TEXT NOT NULL,
	column_title TEXT NOT NULL,
	column_type TEXT NOT NULL,
	analytical_attribute TEXT,
	is_extracted BOOLEAN NOT NULL,
	is_modeled BOOLEAN NOT NULL,
	is_present BOOLEAN NOT NULL,
	discovered_at TIMESTAMP WITH TIME ZONE NOT NULL,
	board_sk TEXT,
	PRIMARY KEY (board_id, column_id),
	CONSTRAINT fk_meta_column_mapping_0a689ea5 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED,
	CONSTRAINT fk_sk_meta_column_mapping_e946c5b7 FOREIGN KEY(board_id, board_sk) REFERENCES sladb.dim_board (board_id, board_sk) DEFERRABLE INITIALLY DEFERRED
)

;


CREATE TABLE IF NOT EXISTS sladb.meta_entity_mapping (
	board_id BIGINT NOT NULL,
	entity_type TEXT NOT NULL,
	source_key TEXT NOT NULL,
	source_text TEXT NOT NULL,
	canonical_id TEXT,
	canonical_name TEXT,
	entity_kind TEXT NOT NULL,
	review_status TEXT NOT NULL,
	reviewed_by TEXT,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (board_id, entity_type, source_key),
	CONSTRAINT fk_meta_entity_mapping_c3348c56 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED
)

;


CREATE TABLE IF NOT EXISTS sladb.meta_gold_rule_snapshot (
	versao_regras TEXT NOT NULL,
	board_id BIGINT NOT NULL,
	conteudo JSONB NOT NULL,
	registrado_em TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (versao_regras),
	CONSTRAINT fk_meta_gold_rule_snapsho_54d2df14 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED
)

;


CREATE TABLE IF NOT EXISTS sladb.dim_item (
	item_id BIGSERIAL NOT NULL,
	board_id BIGINT NOT NULL,
	item_name TEXT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE,
	updated_at TIMESTAMP WITH TIME ZONE,
	current_status_id TEXT NOT NULL,
	is_active BOOLEAN NOT NULL,
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
	board_id BIGINT NOT NULL,
	person_id TEXT NOT NULL,
	role TEXT NOT NULL,
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
	board_id BIGINT NOT NULL,
	item_id BIGINT NOT NULL,
	event TEXT NOT NULL,
	event_at_utc TIMESTAMP WITH TIME ZONE NOT NULL,
	created_at_raw TEXT,
	status_from_text TEXT,
	status_to_text TEXT,
	status_from_index INTEGER,
	status_to_index INTEGER,
	column_id TEXT NOT NULL,
	column_title TEXT,
	group_id TEXT,
	raw_data JSONB NOT NULL,
	timestamp_source TEXT NOT NULL,
	ingested_at TIMESTAMP WITH TIME ZONE NOT NULL,
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
	snapshot_at TIMESTAMP WITH TIME ZONE NOT NULL,
	snapshot_date DATE NOT NULL,
	current_status_id TEXT NOT NULL,
	status_text TEXT,
	status_index INTEGER,
	is_active BOOLEAN NOT NULL,
	raw_data JSONB NOT NULL,
	PRIMARY KEY (item_id, board_id, snapshot_date),
	CONSTRAINT fk_bronze_monday_item_sna_24cd51e8 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED,
	CONSTRAINT fk_bronze_monday_item_sna_d0aabd55 FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED,
	CONSTRAINT fk_bronze_monday_item_sna_a359096f FOREIGN KEY(current_status_id) REFERENCES sladb.dim_status (status_id) DEFERRABLE INITIALLY DEFERRED
)

;

CREATE INDEX IF NOT EXISTS ix_bronze_monday_item_snapshot_raw ON sladb.bronze_monday_item_snapshot_raw (board_id, snapshot_at);


CREATE TABLE IF NOT EXISTS sladb.data_quality_issue (
	issue_id TEXT NOT NULL,
	board_id BIGINT NOT NULL,
	item_id BIGINT NOT NULL,
	code TEXT NOT NULL,
	detail TEXT NOT NULL,
	detected_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (issue_id),
	CONSTRAINT fk_data_quality_issue_703437c1 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED,
	CONSTRAINT fk_data_quality_issue_046237d0 FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED
)

;


CREATE TABLE IF NOT EXISTS sladb.fct_item_sla_summary (
	item_id BIGINT NOT NULL,
	board_id BIGINT NOT NULL,
	status_atual TEXT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE,
	first_status_at TIMESTAMP WITH TIME ZONE,
	finalizado_em TIMESTAMP WITH TIME ZONE,
	lead_time_total_min FLOAT,
	sla_status_atual_min FLOAT,
	open_interval BOOLEAN NOT NULL,
	is_active BOOLEAN NOT NULL,
	history_quality TEXT NOT NULL,
	sla_start_utc TIMESTAMP WITH TIME ZONE,
	sla_start_quality TEXT NOT NULL,
	atualizado_em TIMESTAMP WITH TIME ZONE NOT NULL,
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
	minutes_in_status FLOAT NOT NULL,
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
	board_id BIGINT NOT NULL,
	item_id BIGINT NOT NULL,
	status_id TEXT NOT NULL,
	status_from TEXT,
	status_to TEXT NOT NULL,
	status_start_utc TIMESTAMP WITH TIME ZONE NOT NULL,
	status_end_utc TIMESTAMP WITH TIME ZONE NOT NULL,
	duration_minutes FLOAT NOT NULL,
	duration_hours FLOAT NOT NULL,
	is_open_interval BOOLEAN NOT NULL,
	event_start_id TEXT,
	event_end_id TEXT,
	item_name TEXT,
	marca TEXT,
	cliente TEXT,
	talento TEXT,
	intervenciencia TEXT,
	pessoas_json JSONB,
	snapshot_date DATE,
	attribute_source TEXT NOT NULL,
	history_quality TEXT NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
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
	board_id BIGINT NOT NULL,
	item_id BIGINT NOT NULL,
	status_id TEXT NOT NULL,
	status_from TEXT,
	status_to TEXT,
	event_at_utc TIMESTAMP WITH TIME ZONE NOT NULL,
	timestamp_source TEXT NOT NULL,
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


CREATE TABLE IF NOT EXISTS sladb.gold_projeto_status (
	interval_id TEXT NOT NULL,
	board_id BIGINT NOT NULL,
	item_id BIGINT NOT NULL,
	status_id TEXT NOT NULL,
	projeto_nome TEXT NOT NULL,
	status_nome TEXT NOT NULL,
	ordem_status_quadro INTEGER,
	status_final BOOLEAN NOT NULL,
	ordem_etapa INTEGER NOT NULL,
	passagem_numero_no_status INTEGER NOT NULL,
	eh_retorno BOOLEAN NOT NULL,
	eh_primeiro_registro BOOLEAN NOT NULL,
	eh_ultimo_registro BOOLEAN NOT NULL,
	entrada_status_utc TIMESTAMP WITH TIME ZONE NOT NULL,
	saida_status_utc TIMESTAMP WITH TIME ZONE,
	entrada_status_local TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	saida_status_local TIMESTAMP WITHOUT TIME ZONE,
	corte_utc TIMESTAMP WITH TIME ZONE NOT NULL,
	corte_local TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	duracao_minutos FLOAT NOT NULL,
	duracao_horas FLOAT NOT NULL,
	intervalo_aberto BOOLEAN NOT NULL,
	qualidade_historico TEXT NOT NULL,
	elegivel_comparacao BOOLEAN NOT NULL,
	horas_observadas_encerradas FLOAT,
	status_atual_id TEXT NOT NULL,
	status_atual_nome TEXT NOT NULL,
	projeto_ativo BOOLEAN NOT NULL,
	projeto_na_fila BOOLEAN NOT NULL,
	status_atual_divergente BOOLEAN NOT NULL,
	entrada_comprovada_utc TIMESTAMP WITH TIME ZONE,
	finalizado_em_utc TIMESTAMP WITH TIME ZONE,
	tempo_desde_entrada_horas FLOAT,
	tempo_status_atual_horas FLOAT,
	marca_chave TEXT,
	marca_nome TEXT,
	marca_situacao TEXT NOT NULL,
	talento_chave TEXT,
	talento_nome TEXT,
	talento_origem TEXT,
	talento_situacao TEXT NOT NULL,
	responsavel_orcamento TEXT,
	responsaveis_orcamento_json JSONB NOT NULL,
	quantidade_responsaveis_orcamento INTEGER NOT NULL,
	responsavel_situacao TEXT NOT NULL,
	talent_manager TEXT,
	gp TEXT,
	audiencia TEXT,
	conteudo TEXT,
	producao TEXT,
	pessoas_referencia_json JSONB NOT NULL,
	cadastro_referencia_utc TIMESTAMP WITH TIME ZONE,
	versao_regras TEXT NOT NULL,
	board_sk TEXT NOT NULL,
	item_sk TEXT NOT NULL,
	status_sk TEXT NOT NULL,
	PRIMARY KEY (interval_id),
	CONSTRAINT fk_gold_projeto_status_3e6fde19 FOREIGN KEY(board_id) REFERENCES sladb.dim_board (board_id) DEFERRABLE INITIALLY DEFERRED,
	CONSTRAINT fk_gold_projeto_status_d612ad30 FOREIGN KEY(item_id) REFERENCES sladb.dim_item (item_id) DEFERRABLE INITIALLY DEFERRED,
	CONSTRAINT fk_gold_projeto_status_a35625af FOREIGN KEY(status_id) REFERENCES sladb.dim_status (status_id) DEFERRABLE INITIALLY DEFERRED,
	CONSTRAINT fk_gold_projeto_status_fec14abf FOREIGN KEY(versao_regras) REFERENCES sladb.meta_gold_rule_snapshot (versao_regras) DEFERRABLE INITIALLY DEFERRED,
	CONSTRAINT fk_gold_projeto_status_f2b260a7 FOREIGN KEY(interval_id) REFERENCES sladb.fct_item_status_interval (interval_id) DEFERRABLE INITIALLY DEFERRED,
	CONSTRAINT fk_gold_projeto_status_15cb5839 FOREIGN KEY(status_atual_id) REFERENCES sladb.dim_status (status_id) DEFERRABLE INITIALLY DEFERRED,
	CONSTRAINT fk_sk_gold_projeto_status_6758164f FOREIGN KEY(board_id, board_sk) REFERENCES sladb.dim_board (board_id, board_sk) DEFERRABLE INITIALLY DEFERRED,
	CONSTRAINT fk_sk_gold_projeto_status_2e6468b2 FOREIGN KEY(item_id, item_sk) REFERENCES sladb.dim_item (item_id, item_sk) DEFERRABLE INITIALLY DEFERRED,
	CONSTRAINT fk_sk_gold_projeto_status_60f72d33 FOREIGN KEY(status_id, status_sk) REFERENCES sladb.dim_status (status_id, status_sk) DEFERRABLE INITIALLY DEFERRED
)

;

CREATE INDEX IF NOT EXISTS ix_gold_projeto_status ON sladb.gold_projeto_status (board_id, item_id, ordem_etapa);
