"""Portable private-state collections; never creates database tables."""

from .keys import SURROGATE_COLUMNS

DEFINITIONS = {
    "quarentena_projeto": (
        "board_id,item_id",
        "board_id:id item_id:id projeto_nome:text marca_original:text talento_original:text "
        "interveniencia_original:text motivos:json cadastro_referencia_utc:time "
        "corte_utc:time versao_regras:text atualizado_em:time",
    ),
    "meta_gold_rule_snapshot": (
        "versao_regras",
        "versao_regras:text board_id:id conteudo:json registrado_em:time",
    ),
    "meta_entity_mapping": (
        "board_id,entity_type,source_key",
        "board_id:id entity_type:text source_key:text source_text:text canonical_id:text "
        "canonical_name:text entity_kind:text review_status:text reviewed_by:text review_reason:text updated_at:time",
    ),
    "gold_projeto_status": (
        "interval_id",
        "interval_id:text board_id:id item_id:id status_id:text projeto_nome:text "
        "status_nome:text ordem_status_quadro:int status_final:bool ordem_etapa:int "
        "passagem_numero_no_status:int eh_retorno:bool eh_primeiro_registro:bool eh_ultimo_registro:bool "
        "entrada_status_utc:time saida_status_utc:time entrada_status_local:localtime "
        "saida_status_local:localtime corte_utc:time corte_local:localtime "
        "duracao_minutos:num duracao_horas:num intervalo_aberto:bool qualidade_historico:text "
        "elegivel_comparacao:bool horas_observadas_encerradas:num "
        "status_atual_id:text status_atual_nome:text projeto_ativo:bool projeto_na_fila:bool "
        "status_atual_divergente:bool entrada_comprovada_utc:time finalizado_em_utc:time "
        "tempo_desde_entrada_horas:num tempo_status_atual_horas:num "
        "marca_chave:text marca_nome:text marca_situacao:text "
        "talento_chave:text talento_nome:text talento_origem:text talento_situacao:text "
        "responsavel_orcamento:text responsaveis_orcamento_json:json "
        "quantidade_responsaveis_orcamento:int responsavel_situacao:text "
        "talent_manager:text gp:text audiencia:text conteudo:text producao:text "
        "pessoas_referencia_json:json cadastro_referencia_utc:time versao_regras:text",
    ),
    "dim_board": ("board_id", "board_id:id board_name:text created_at:time updated_at:time"),
    "meta_column_mapping": (
        "board_id,column_id",
        "board_id:id column_id:text column_title:text column_type:text "
        "analytical_attribute:text is_extracted:bool is_modeled:bool is_present:bool discovered_at:time",
    ),
    "bronze_monday_activity_log_raw": (
        "event_id",
        "event_id:text board_id:id item_id:id event:text event_at_utc:time "
        "created_at_raw:text status_from_text:text status_to_text:text status_from_index:int "
        "status_to_index:int column_id:text column_title:text group_id:text raw_data:json "
        "timestamp_source:text ingested_at:time",
    ),
    "bronze_monday_item_snapshot_raw": (
        "board_id,item_id,snapshot_date",
        "item_id:id board_id:id item_name:text group_id:text "
        "created_at:time updated_at:time marca:text cliente:text talento:text intervenciencia:text "
        "pessoas_json:json snapshot_at:time snapshot_date:date current_status_id:text "
        "status_text:text status_index:int is_active:bool raw_data:json",
    ),
    "bronze_monday_board_schema_raw": (
        "board_id,snapshot_date",
        "board_id:id snapshot_date:date snapshot_at:time raw_data:json mapping:json",
    ),
    "silver_monday_status_event_stg": (
        "event_id",
        "event_id:text board_id:id item_id:id status_id:text status_from:text "
        "status_to:text event_at_utc:time timestamp_source:text",
    ),
    "dim_status": (
        "status_id",
        "status_id:text board_id:id status_label:text status_label_norm:text "
        "status_order:int status_column_id:text status_color:text is_terminal:bool",
    ),
    "dim_person": ("person_id", "person_id:text person_name:text email:text"),
    "dim_item": (
        "item_id",
        "item_id:id board_id:id item_name:text created_at:time updated_at:time "
        "current_status_id:text is_active:bool last_seen_at:time",
    ),
    "bridge_item_person": (
        "item_id,person_id,source_column_id,snapshot_date",
        "item_id:id board_id:id person_id:text role:text source_column_id:text snapshot_date:date",
    ),
    "fct_item_status_interval": (
        "interval_id",
        "interval_id:text board_id:id item_id:id status_id:text status_from:text "
        "status_to:text status_start_utc:time status_end_utc:time duration_minutes:num duration_hours:num "
        "is_open_interval:bool event_start_id:text event_end_id:text item_name:text marca:text "
        "cliente:text talento:text intervenciencia:text pessoas_json:json snapshot_date:date "
        "attribute_source:text history_quality:text updated_at:time",
    ),
    "fct_item_status_daily": (
        "board_id,dt,item_id,status_id",
        "board_id:id dt:date item_id:id status_id:text "
        "minutes_in_status:num marca:text cliente:text talento:text intervenciencia:text snapshot_date:date",
    ),
    "fct_item_sla_summary": (
        "item_id",
        "item_id:id board_id:id status_atual:text created_at:time first_status_at:time "
        "finalizado_em:time lead_time_total_min:num sla_status_atual_min:num open_interval:bool "
        "is_active:bool history_quality:text sla_start_utc:time sla_start_quality:text atualizado_em:time",
    ),
    "etl_watermark": (
        "pipeline_name",
        "pipeline_name:text board_id:id last_run_utc:time last_log_event_id:text "
        "last_item_page_cursor:text updated_at:time",
    ),
    "etl_run": (
        "run_id",
        "run_id:text board_id:id mode:text start_at:time end_at:time status:text metrics:json",
    ),
    "data_quality_issue": (
        "issue_id",
        "issue_id:text board_id:id item_id:id code:text detail:text detected_at:time",
    ),
}


for _name, _columns in SURROGATE_COLUMNS.items():
    _keys, _fields = DEFINITIONS[_name]
    DEFINITIONS[_name] = (_keys, _fields + " " + " ".join(f"{c}:text" for c in _columns))


def foreign_keys():
    """Explicit relational contract; Monday item IDs remain unchanged."""
    relationships = []
    for name, (_, fields) in DEFINITIONS.items():
        columns = {f.split(":")[0] for f in fields.split()}
        if "board_id" in columns and name != "dim_board":
            relationships.append((name, "board_id", "dim_board", "board_id"))
        if "item_id" in columns and name != "dim_item":
            relationships.append((name, "item_id", "dim_item", "item_id"))
        if "status_id" in columns and name != "dim_status":
            relationships.append((name, "status_id", "dim_status", "status_id"))
        if "current_status_id" in columns:
            relationships.append((name, "current_status_id", "dim_status", "status_id"))
    relationships.extend(
        [
            ("quarentena_projeto", "versao_regras", "meta_gold_rule_snapshot", "versao_regras"),
            ("gold_projeto_status", "versao_regras", "meta_gold_rule_snapshot", "versao_regras"),
            ("gold_projeto_status", "interval_id", "fct_item_status_interval", "interval_id"),
            ("gold_projeto_status", "status_atual_id", "dim_status", "status_id"),
            ("bridge_item_person", "person_id", "dim_person", "person_id"),
            (
                "silver_monday_status_event_stg",
                "event_id",
                "bronze_monday_activity_log_raw",
                "event_id",
            ),
            (
                "fct_item_status_interval",
                "event_start_id",
                "bronze_monday_activity_log_raw",
                "event_id",
            ),
            (
                "fct_item_status_interval",
                "event_end_id",
                "bronze_monday_activity_log_raw",
                "event_id",
            ),
        ]
    )
    return relationships


REPLACE_TABLES = {
    "quarentena_projeto",
    "gold_projeto_status",
    "silver_monday_status_event_stg",
    "fct_item_status_interval",
    "fct_item_status_daily",
    "fct_item_sla_summary",
    "data_quality_issue",
}
