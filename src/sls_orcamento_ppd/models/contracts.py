"""Versioned, portable publication contracts. Errors contain metadata, never values."""

import math
from datetime import date, datetime

from .keys import SURROGATE_COLUMNS, with_surrogates
from .schemas import DEFINITIONS

CONTRACT_VERSION = "2.2.0"
REQUIRED = {
    "quarentena_projeto": "projeto_nome motivos corte_utc versao_regras atualizado_em board_sk item_sk",
    "meta_gold_rule_snapshot": "board_id conteudo registrado_em",
    "meta_entity_mapping": "source_text entity_kind review_status updated_at",
    "gold_projeto_status": "board_id item_id status_id projeto_nome status_nome status_final ordem_etapa passagem_numero_no_status eh_retorno eh_primeiro_registro eh_ultimo_registro entrada_status_utc entrada_status_local corte_utc corte_local duracao_minutos duracao_horas intervalo_aberto qualidade_historico elegivel_comparacao status_atual_id status_atual_nome projeto_ativo projeto_na_fila status_atual_divergente marca_situacao talento_situacao responsaveis_orcamento_json quantidade_responsaveis_orcamento responsavel_situacao pessoas_referencia_json versao_regras board_sk item_sk status_sk",
    "dim_board": "board_name updated_at",
    "dim_item": "board_id item_name current_status_id is_active",
    "dim_status": "board_id status_label status_label_norm status_column_id is_terminal",
    "dim_person": "person_name",
    "meta_column_mapping": "column_title column_type is_extracted is_modeled is_present discovered_at",
    "bronze_monday_activity_log_raw": "board_id item_id event event_at_utc column_id raw_data ingested_at timestamp_source",
    "bronze_monday_item_snapshot_raw": "snapshot_at current_status_id is_active raw_data",
    "bronze_monday_board_schema_raw": "snapshot_at raw_data mapping",
    "silver_monday_status_event_stg": "board_id item_id status_id event_at_utc timestamp_source",
    "bridge_item_person": "board_id role",
    "fct_item_status_interval": "board_id item_id status_id status_to status_start_utc status_end_utc duration_minutes duration_hours is_open_interval attribute_source history_quality updated_at",
    "fct_item_status_daily": "minutes_in_status",
    "fct_item_sla_summary": "board_id status_atual open_interval is_active history_quality sla_start_quality atualizado_em",
    "etl_watermark": "board_id last_run_utc updated_at",
    "etl_run": "board_id mode start_at end_at status metrics",
    "data_quality_issue": "board_id item_id code detail detected_at",
}
DOMAINS = {
    "qualidade_historico": {"observed", "initial_inferred", "no_history_inferred"},
    "entity_type": {"marca", "talento"},
    "entity_kind": {"person", "organization", "collective", "unknown"},
    "review_status": {"pending", "approved", "quarantined"},
    "history_quality": {"observed", "initial_inferred", "no_history_inferred"},
    "attribute_source": {"as_of_start", "earliest_available", "unavailable"},
    "sla_start_quality": {"observed_event", "unavailable"},
}


def valid_type(kind, value):
    if kind == "text":
        return isinstance(value, str)
    if kind == "id":
        return type(value) is int and 0 < value < 2**63
    if kind == "int":
        return type(value) is int
    if kind == "bool":
        return type(value) is bool
    if kind == "time":
        return isinstance(value, datetime) and value.utcoffset() is not None
    if kind == "localtime":
        return isinstance(value, datetime) and value.tzinfo is None
    if kind == "date":
        return type(value) is date
    if kind == "num":
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    return isinstance(value, (dict, list))


def required_columns(name):
    return set(DEFINITIONS[name][0].split(",")) | set(REQUIRED.get(name, "").split())


def validate_table(name, rows, board_id=None, *, unique=True):
    if name not in DEFINITIONS:
        raise ValueError("Contrato: tabela não cadastrada")
    keys = DEFINITIONS[name][0].split(",")
    if name == "gold_projeto_status":
        orders = [(r.get("board_id"), r.get("item_id"), r.get("ordem_etapa")) for r in rows]
        if len(set(orders)) != len(orders):
            raise ValueError("Contrato: gold_projeto_status ordem duplicada no projeto")
    fields = dict(field.split(":") for field in DEFINITIONS[name][1].split())
    required = required_columns(name)
    seen = set()

    def fail(column, rule):
        # Column names below come from the trusted contract, not source payloads.
        raise ValueError(f"Contrato {CONTRACT_VERSION}: {name}.{column}: {rule}")

    for row in rows:
        if set(row) - fields.keys():
            fail("registro", "campo não cadastrado")
        for column, kind in fields.items():
            value = row.get(column)
            if value is None:
                if column in required:
                    fail(column, "obrigatório ausente")
                continue
            valid = valid_type(kind, value)
            if not valid:
                fail(column, "tipo/domínio inválido")
            if kind == "text" and column in required and not value.strip():
                fail(column, "texto obrigatório vazio")
            if column in DOMAINS and value not in DOMAINS[column]:
                fail(column, "categoria não cadastrada")
        if board_id is not None and "board_id" in fields and row.get("board_id") != board_id:
            fail("board_id", "escopo divergente")
        identity = tuple(row[k] for k in keys)
        if unique and identity in seen:
            fail("chave_primaria", "duplicada no lote")
        seen.add(identity)
        expected = with_surrogates(name, row)
        for sk in SURROGATE_COLUMNS.get(name, {}):
            if sk in row and row[sk] != expected[sk]:
                fail(sk, "inconsistente com ID de origem")
        if name == "gold_projeto_status":
            end = row["saida_status_utc"]
            if row["intervalo_aberto"] != (end is None):
                fail("saida_status_utc", "inconsistente com intervalo aberto")
            minutes = ((end or row["corte_utc"]) - row["entrada_status_utc"]).total_seconds() / 60
            if (
                minutes < 0
                or abs(minutes - row["duracao_minutos"]) > 1e-5
                or abs(minutes / 60 - row["duracao_horas"]) > 1e-5
            ):
                fail("duracao_horas", "não reconciliada com datas")
            if end is not None and end > row["corte_utc"]:
                fail("saida_status_utc", "posterior ao corte")
            if row["elegivel_comparacao"] and (
                row["qualidade_historico"] != "observed"
                or row["intervalo_aberto"]
                or row["status_atual_divergente"]
            ):
                fail("elegivel_comparacao", "histórico incompatível")
            if row["horas_observadas_encerradas"] != (
                row["duracao_horas"] if row["elegivel_comparacao"] else None
            ):
                fail("horas_observadas_encerradas", "valor incompatível com elegibilidade")
            if (
                row["entrada_comprovada_utc"] is None
                and row["tempo_desde_entrada_horas"] is not None
            ):
                fail("tempo_desde_entrada_horas", "total sem Entrada comprovada")
            if min(row["ordem_etapa"], row["passagem_numero_no_status"]) < 1:
                fail("ordem_etapa", "ordem inválida")
        if name == "meta_entity_mapping" and row["review_status"] == "approved":
            if (
                not all(
                    isinstance(row.get(k), str) and row[k].strip()
                    for k in ("canonical_id", "canonical_name", "reviewed_by")
                )
                or row["entity_kind"] == "unknown"
            ):
                fail("review_status", "aprovação incompleta")
        if name == "meta_entity_mapping" and row["review_status"] == "quarantined":
            if not all(
                isinstance(row.get(k), str) and row[k].strip()
                for k in ("reviewed_by", "review_reason")
            ):
                fail("review_status", "quarentena manual sem motivo ou revisor")
        if name == "quarentena_projeto" and (
            not isinstance(row["motivos"], list)
            or not row["motivos"]
            or any(not isinstance(v, str) or not v for v in row["motivos"])
        ):
            fail("motivos", "quarentena sem motivos válidos")
        if name == "fct_item_status_interval":
            minutes = (row["status_end_utc"] - row["status_start_utc"]).total_seconds() / 60
            if minutes < 0 or abs(minutes - row["duration_minutes"]) > 1e-5:
                fail("duration_minutes", "não reconciliado com datas")
            if abs(row["duration_hours"] * 60 - minutes) > 1e-5:
                fail("duration_hours", "não reconciliado com minutos")
            if row["history_quality"] == "observed" and not row.get("event_start_id"):
                fail("event_start_id", "visita observada sem evento inicial")
            if row["is_open_interval"] and row.get("event_end_id") is not None:
                fail("event_end_id", "visita aberta com evento final")
        if name == "fct_item_sla_summary":
            start = row.get("sla_start_utc")
            if (start is None) != (row["sla_start_quality"] == "unavailable"):
                fail("sla_start_quality", "inconsistente com início")
            if start is None and row.get("lead_time_total_min") is not None:
                fail("lead_time_total_min", "total sem Entrada comprovada")


def prepare_payload(payload, board_id):
    prepared = {}
    for name, rows in payload.items():
        validate_table(name, rows, board_id)
        prepared[name] = [with_surrogates(name, row) for row in rows]
    return prepared
