# Contrato de campos — referência gerada

Versão 2.2.0. Fonte: `models/schemas.py` e `models/contracts.py`.
Regenerar com `python scripts/generate_contract_docs.py`.

GCP v4 publica somente sla_orcamento no BigQuery. As coleções lógicas abaixo ficam no checkpoint privado GCS; não são tabelas BigQuery. PostgreSQL é legado de migração. Contrato público v5: models/bq_consumption.py. Campos físicos: [OURO_CONSUMO.md](OURO_CONSUMO.md).
Significado de negócio das coleções: [PRD_ELT_REGRAS.md](PRD_ELT_REGRAS.md).
Política de nulos e tratamento: [ARQUITETURA_E_GOVERNANCA.md](ARQUITETURA_E_GOVERNANCA.md).

`id`: inteiro positivo de 64 bits; `text`: texto; `time`: timestamp com fuso;
`date`: data; `num`: número finito não negativo; `bool`: booleano; `json`: objeto/lista.
`localtime`: data/hora local sem fuso, para apresentação; referência temporal continua em UTC.
Campos opcionais aceitam NULL. Campos obrigatórios não aceitam NULL e textos obrigatórios não aceitam vazio.
SKs são calculadas antes da gravação e validadas contra o ID original; referências internas são verificadas em Python.

## `quarentena_projeto`

Chave primária: `board_id,item_id`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `board_id` | id | Sim | dim_board.board_id |
| `item_id` | id | Sim | dim_item.item_id |
| `projeto_nome` | text | Sim | — |
| `marca_original` | text | Não | — |
| `talento_original` | text | Não | — |
| `interveniencia_original` | text | Não | — |
| `motivos` | json | Sim | — |
| `cadastro_referencia_utc` | time | Não | — |
| `corte_utc` | time | Sim | — |
| `versao_regras` | text | Sim | meta_gold_rule_snapshot.versao_regras |
| `atualizado_em` | time | Sim | — |
| `board_sk` | text | Sim | — |
| `item_sk` | text | Sim | — |

## `meta_gold_rule_snapshot`

Chave primária: `versao_regras`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `versao_regras` | text | Sim | — |
| `board_id` | id | Sim | dim_board.board_id |
| `conteudo` | json | Sim | — |
| `registrado_em` | time | Sim | — |

## `meta_entity_mapping`

Chave primária: `board_id,entity_type,source_key`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `board_id` | id | Sim | dim_board.board_id |
| `entity_type` | text | Sim | — |
| `source_key` | text | Sim | — |
| `source_text` | text | Sim | — |
| `canonical_id` | text | Não | — |
| `canonical_name` | text | Não | — |
| `entity_kind` | text | Sim | — |
| `review_status` | text | Sim | — |
| `reviewed_by` | text | Não | — |
| `review_reason` | text | Não | — |
| `updated_at` | time | Sim | — |

## `gold_projeto_status`

Chave primária: `interval_id`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `interval_id` | text | Sim | fct_item_status_interval.interval_id |
| `board_id` | id | Sim | dim_board.board_id |
| `item_id` | id | Sim | dim_item.item_id |
| `status_id` | text | Sim | dim_status.status_id |
| `projeto_nome` | text | Sim | — |
| `status_nome` | text | Sim | — |
| `ordem_status_quadro` | int | Não | — |
| `status_final` | bool | Sim | — |
| `ordem_etapa` | int | Sim | — |
| `passagem_numero_no_status` | int | Sim | — |
| `eh_retorno` | bool | Sim | — |
| `eh_primeiro_registro` | bool | Sim | — |
| `eh_ultimo_registro` | bool | Sim | — |
| `entrada_status_utc` | time | Sim | — |
| `saida_status_utc` | time | Não | — |
| `entrada_status_local` | localtime | Sim | — |
| `saida_status_local` | localtime | Não | — |
| `corte_utc` | time | Sim | — |
| `corte_local` | localtime | Sim | — |
| `duracao_minutos` | num | Sim | — |
| `duracao_horas` | num | Sim | — |
| `intervalo_aberto` | bool | Sim | — |
| `qualidade_historico` | text | Sim | — |
| `elegivel_comparacao` | bool | Sim | — |
| `horas_observadas_encerradas` | num | Não | — |
| `status_atual_id` | text | Sim | dim_status.status_id |
| `status_atual_nome` | text | Sim | — |
| `projeto_ativo` | bool | Sim | — |
| `projeto_na_fila` | bool | Sim | — |
| `status_atual_divergente` | bool | Sim | — |
| `entrada_comprovada_utc` | time | Não | — |
| `finalizado_em_utc` | time | Não | — |
| `tempo_desde_entrada_horas` | num | Não | — |
| `tempo_status_atual_horas` | num | Não | — |
| `marca_chave` | text | Não | — |
| `marca_nome` | text | Não | — |
| `marca_situacao` | text | Sim | — |
| `talento_chave` | text | Não | — |
| `talento_nome` | text | Não | — |
| `talento_origem` | text | Não | — |
| `talento_situacao` | text | Sim | — |
| `responsavel_orcamento` | text | Não | — |
| `responsaveis_orcamento_json` | json | Sim | — |
| `quantidade_responsaveis_orcamento` | int | Sim | — |
| `responsavel_situacao` | text | Sim | — |
| `talent_manager` | text | Não | — |
| `gp` | text | Não | — |
| `audiencia` | text | Não | — |
| `conteudo` | text | Não | — |
| `producao` | text | Não | — |
| `pessoas_referencia_json` | json | Sim | — |
| `cadastro_referencia_utc` | time | Não | — |
| `versao_regras` | text | Sim | meta_gold_rule_snapshot.versao_regras |
| `board_sk` | text | Sim | — |
| `item_sk` | text | Sim | — |
| `status_sk` | text | Sim | — |

## `dim_board`

Chave primária: `board_id`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `board_id` | id | Sim | — |
| `board_name` | text | Sim | — |
| `created_at` | time | Não | — |
| `updated_at` | time | Sim | — |
| `board_sk` | text | Sim | — |

## `meta_column_mapping`

Chave primária: `board_id,column_id`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `board_id` | id | Sim | dim_board.board_id |
| `column_id` | text | Sim | — |
| `column_title` | text | Sim | — |
| `column_type` | text | Sim | — |
| `analytical_attribute` | text | Não | — |
| `is_extracted` | bool | Sim | — |
| `is_modeled` | bool | Sim | — |
| `is_present` | bool | Sim | — |
| `discovered_at` | time | Sim | — |
| `board_sk` | text | Não | — |

## `bronze_monday_activity_log_raw`

Chave primária: `event_id`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `event_id` | text | Sim | — |
| `board_id` | id | Sim | dim_board.board_id |
| `item_id` | id | Sim | dim_item.item_id |
| `event` | text | Sim | — |
| `event_at_utc` | time | Sim | — |
| `created_at_raw` | text | Não | — |
| `status_from_text` | text | Não | — |
| `status_to_text` | text | Não | — |
| `status_from_index` | int | Não | — |
| `status_to_index` | int | Não | — |
| `column_id` | text | Sim | — |
| `column_title` | text | Não | — |
| `group_id` | text | Não | — |
| `raw_data` | json | Sim | — |
| `timestamp_source` | text | Sim | — |
| `ingested_at` | time | Sim | — |

## `bronze_monday_item_snapshot_raw`

Chave primária: `board_id,item_id,snapshot_date`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `item_id` | id | Sim | dim_item.item_id |
| `board_id` | id | Sim | dim_board.board_id |
| `item_name` | text | Não | — |
| `group_id` | text | Não | — |
| `created_at` | time | Não | — |
| `updated_at` | time | Não | — |
| `marca` | text | Não | — |
| `cliente` | text | Não | — |
| `talento` | text | Não | — |
| `intervenciencia` | text | Não | — |
| `pessoas_json` | json | Não | — |
| `snapshot_at` | time | Sim | — |
| `snapshot_date` | date | Sim | — |
| `current_status_id` | text | Sim | dim_status.status_id |
| `status_text` | text | Não | — |
| `status_index` | int | Não | — |
| `is_active` | bool | Sim | — |
| `raw_data` | json | Sim | — |

## `bronze_monday_board_schema_raw`

Chave primária: `board_id,snapshot_date`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `board_id` | id | Sim | dim_board.board_id |
| `snapshot_date` | date | Sim | — |
| `snapshot_at` | time | Sim | — |
| `raw_data` | json | Sim | — |
| `mapping` | json | Sim | — |

## `silver_monday_status_event_stg`

Chave primária: `event_id`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `event_id` | text | Sim | bronze_monday_activity_log_raw.event_id |
| `board_id` | id | Sim | dim_board.board_id |
| `item_id` | id | Sim | dim_item.item_id |
| `status_id` | text | Sim | dim_status.status_id |
| `status_from` | text | Não | — |
| `status_to` | text | Não | — |
| `event_at_utc` | time | Sim | — |
| `timestamp_source` | text | Sim | — |
| `board_sk` | text | Não | — |
| `item_sk` | text | Não | — |
| `status_sk` | text | Não | — |

## `dim_status`

Chave primária: `status_id`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `status_id` | text | Sim | — |
| `board_id` | id | Sim | dim_board.board_id |
| `status_label` | text | Sim | — |
| `status_label_norm` | text | Sim | — |
| `status_order` | int | Não | — |
| `status_column_id` | text | Sim | — |
| `status_color` | text | Não | — |
| `is_terminal` | bool | Sim | — |
| `status_sk` | text | Sim | — |
| `board_sk` | text | Não | — |

## `dim_person`

Chave primária: `person_id`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `person_id` | text | Sim | — |
| `person_name` | text | Sim | — |
| `email` | text | Não | — |
| `person_sk` | text | Sim | — |

## `dim_item`

Chave primária: `item_id`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `item_id` | id | Sim | — |
| `board_id` | id | Sim | dim_board.board_id |
| `item_name` | text | Sim | — |
| `created_at` | time | Não | — |
| `updated_at` | time | Não | — |
| `current_status_id` | text | Sim | dim_status.status_id |
| `is_active` | bool | Sim | — |
| `last_seen_at` | time | Não | — |
| `item_sk` | text | Sim | — |
| `board_sk` | text | Não | — |
| `current_status_sk` | text | Não | — |

## `bridge_item_person`

Chave primária: `item_id,person_id,source_column_id,snapshot_date`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `item_id` | id | Sim | dim_item.item_id |
| `board_id` | id | Sim | dim_board.board_id |
| `person_id` | text | Sim | dim_person.person_id |
| `role` | text | Sim | — |
| `source_column_id` | text | Sim | — |
| `snapshot_date` | date | Sim | — |
| `board_sk` | text | Não | — |
| `item_sk` | text | Não | — |
| `person_sk` | text | Não | — |

## `fct_item_status_interval`

Chave primária: `interval_id`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `interval_id` | text | Sim | — |
| `board_id` | id | Sim | dim_board.board_id |
| `item_id` | id | Sim | dim_item.item_id |
| `status_id` | text | Sim | dim_status.status_id |
| `status_from` | text | Não | — |
| `status_to` | text | Sim | — |
| `status_start_utc` | time | Sim | — |
| `status_end_utc` | time | Sim | — |
| `duration_minutes` | num | Sim | — |
| `duration_hours` | num | Sim | — |
| `is_open_interval` | bool | Sim | — |
| `event_start_id` | text | Não | bronze_monday_activity_log_raw.event_id |
| `event_end_id` | text | Não | bronze_monday_activity_log_raw.event_id |
| `item_name` | text | Não | — |
| `marca` | text | Não | — |
| `cliente` | text | Não | — |
| `talento` | text | Não | — |
| `intervenciencia` | text | Não | — |
| `pessoas_json` | json | Não | — |
| `snapshot_date` | date | Não | — |
| `attribute_source` | text | Sim | — |
| `history_quality` | text | Sim | — |
| `updated_at` | time | Sim | — |
| `board_sk` | text | Não | — |
| `item_sk` | text | Não | — |
| `status_sk` | text | Não | — |

## `fct_item_status_daily`

Chave primária: `board_id,dt,item_id,status_id`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `board_id` | id | Sim | dim_board.board_id |
| `dt` | date | Sim | — |
| `item_id` | id | Sim | dim_item.item_id |
| `status_id` | text | Sim | dim_status.status_id |
| `minutes_in_status` | num | Sim | — |
| `marca` | text | Não | — |
| `cliente` | text | Não | — |
| `talento` | text | Não | — |
| `intervenciencia` | text | Não | — |
| `snapshot_date` | date | Não | — |
| `board_sk` | text | Não | — |
| `item_sk` | text | Não | — |
| `status_sk` | text | Não | — |

## `fct_item_sla_summary`

Chave primária: `item_id`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `item_id` | id | Sim | dim_item.item_id |
| `board_id` | id | Sim | dim_board.board_id |
| `status_atual` | text | Sim | — |
| `created_at` | time | Não | — |
| `first_status_at` | time | Não | — |
| `finalizado_em` | time | Não | — |
| `lead_time_total_min` | num | Não | — |
| `sla_status_atual_min` | num | Não | — |
| `open_interval` | bool | Sim | — |
| `is_active` | bool | Sim | — |
| `history_quality` | text | Sim | — |
| `sla_start_utc` | time | Não | — |
| `sla_start_quality` | text | Sim | — |
| `atualizado_em` | time | Sim | — |
| `board_sk` | text | Não | — |
| `item_sk` | text | Não | — |

## `etl_watermark`

Chave primária: `pipeline_name`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `pipeline_name` | text | Sim | — |
| `board_id` | id | Sim | dim_board.board_id |
| `last_run_utc` | time | Sim | — |
| `last_log_event_id` | text | Não | — |
| `last_item_page_cursor` | text | Não | — |
| `updated_at` | time | Sim | — |

## `etl_run`

Chave primária: `run_id`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `run_id` | text | Sim | — |
| `board_id` | id | Sim | dim_board.board_id |
| `mode` | text | Sim | — |
| `start_at` | time | Sim | — |
| `end_at` | time | Sim | — |
| `status` | text | Sim | — |
| `metrics` | json | Sim | — |

## `data_quality_issue`

Chave primária: `issue_id`.

| Campo | Tipo | Obrigatório | Referência |
|---|---|---|---|
| `issue_id` | text | Sim | — |
| `board_id` | id | Sim | dim_board.board_id |
| `item_id` | id | Sim | dim_item.item_id |
| `code` | text | Sim | — |
| `detail` | text | Sim | — |
| `detected_at` | time | Sim | — |
