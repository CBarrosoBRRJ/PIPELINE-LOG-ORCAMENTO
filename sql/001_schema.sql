-- PostgreSQL 3.1: Gold + project review queue only. Use CLI init-db (new) or migrate-consumption (upgrade).

CREATE SCHEMA IF NOT EXISTS orcamento;


CREATE TABLE IF NOT EXISTS orcamento.gold_projeto_status (
	ordem_etapa INTEGER NOT NULL,
	projeto_nome TEXT NOT NULL,
	status_nome TEXT NOT NULL,
	entrada_status_local TIMESTAMP WITHOUT TIME ZONE,
	saida_status_local TIMESTAMP WITHOUT TIME ZONE,
	duracao_horas FLOAT,
	marca_nome TEXT,
	talento_nome TEXT,
	responsavel_orcamento TEXT,
	eh_retorno BOOLEAN NOT NULL,
	item_id BIGINT NOT NULL,
	board_id BIGINT NOT NULL,
	interval_id TEXT NOT NULL,
	qualidade_historico TEXT NOT NULL,
	intervalo_aberto BOOLEAN NOT NULL,
	status_final BOOLEAN NOT NULL,
	corte_local TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	elegivel_comparacao BOOLEAN NOT NULL,
	horas_observadas_encerradas FLOAT,
	status_atual_nome TEXT NOT NULL,
	projeto_na_fila BOOLEAN NOT NULL,
	tempo_desde_entrada_horas FLOAT,
	tempo_status_atual_horas FLOAT,
	responsavel_situacao TEXT NOT NULL,
	cadastro_referencia_utc TIMESTAMP WITH TIME ZONE,
	versao_regras TEXT NOT NULL,
	item_sk TEXT NOT NULL,
	board_sk TEXT NOT NULL,
	status_id TEXT NOT NULL,
	status_sk TEXT NOT NULL,
	entrada_status_utc TIMESTAMP WITH TIME ZONE,
	saida_status_utc TIMESTAMP WITH TIME ZONE,
	corte_utc TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (interval_id),
	CONSTRAINT uq_gold_projeto_ordem UNIQUE (board_id, item_id, ordem_etapa),
	CONSTRAINT ck_gold_ordem CHECK (ordem_etapa >= 1),
	CONSTRAINT ck_gold_evidencia CHECK ((qualidade_historico = 'observed' AND entrada_status_utc IS NOT NULL AND entrada_status_local IS NOT NULL AND duracao_horas IS NOT NULL) OR (qualidade_historico IN ('initial_inferred','no_history_inferred') AND entrada_status_utc IS NULL AND entrada_status_local IS NULL AND duracao_horas IS NULL)),
	CONSTRAINT ck_gold_fechamento CHECK (intervalo_aberto = (saida_status_utc IS NULL) AND (entrada_status_utc IS NULL OR entrada_status_utc < corte_utc) AND (saida_status_utc IS NULL OR (saida_status_utc <= corte_utc AND (entrada_status_utc IS NULL OR saida_status_utc >= entrada_status_utc)))),
	CONSTRAINT ck_gold_duracao CHECK (duracao_horas IS NULL OR (duracao_horas >= 0 AND abs(duracao_horas - extract(epoch FROM (coalesce(saida_status_utc,corte_utc)-entrada_status_utc))/3600) < 0.00001))
)

;

CREATE INDEX IF NOT EXISTS ix_gold_projeto_status ON orcamento.gold_projeto_status (board_id, item_id, ordem_etapa);

CREATE UNIQUE INDEX IF NOT EXISTS uq_gold_ultima_passagem ON orcamento.gold_projeto_status (board_id, item_id) WHERE intervalo_aberto;


CREATE TABLE IF NOT EXISTS orcamento.pendencias_projeto (
	item_id BIGINT NOT NULL,
	board_id BIGINT NOT NULL,
	projeto_nome TEXT NOT NULL,
	excluido_da_analise BOOLEAN NOT NULL,
	motivos TEXT NOT NULL,
	como_corrigir TEXT NOT NULL,
	marca_original TEXT,
	talento_original TEXT,
	interveniencia_original TEXT,
	responsavel_orcamento_original TEXT,
	codigos TEXT NOT NULL,
	cadastro_referencia_utc TIMESTAMP WITH TIME ZONE,
	corte_local TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	versao_regras TEXT NOT NULL,
	item_sk TEXT NOT NULL,
	PRIMARY KEY (item_id, board_id)
)

;
