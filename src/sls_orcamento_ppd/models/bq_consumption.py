"""GCP physical contract v5: all joins and working-hour calculations in Python."""

import hashlib
from collections import defaultdict
from datetime import UTC

from ..db.checkpoint import canonical_json
from ..rules.business_time import POLICY, BusinessCalendar
from .consumption import GOLD, PUBLIC_FIELDS, PUBLIC_REQUIRED, publication
from .contracts import valid_type

FIELDS = PUBLIC_FIELDS[GOLD] + (
    " duracao_horas_uteis:num horas_uteis_observadas_encerradas:num"
    " tempo_status_atual_horas_uteis:num tempo_desde_entrada_horas_uteis:num"
    " expediente:text versao_calendario:text"
)
REQUIRED = PUBLIC_REQUIRED[GOLD] | {"expediente", "versao_calendario"}


def project(data, settings):
    calendar = BusinessCalendar(settings.preferred_timezone, settings.business_holidays)
    result = publication(data, settings.preferred_timezone)
    latest = {r["item_id"]: r for r in data[GOLD] if r["eh_ultimo_registro"]}
    # Compute project-level metrics once, not once per historical passage.
    metrics = {}
    for item, last in latest.items():
        current = (
            calendar.hours(last["entrada_status_utc"], last["corte_utc"])
            if (
                last["qualidade_historico"] == "observed"
                and last["tempo_status_atual_horas"] is not None
            )
            else None
        )
        total = (
            calendar.hours(
                last["entrada_comprovada_utc"], last["finalizado_em_utc"] or last["corte_utc"]
            )
            if (last["tempo_desde_entrada_horas"] is not None)
            else None
        )
        metrics[item] = current, total
    for row in result[GOLD]:
        hours = calendar.hours(
            row["entrada_status_utc"], row["saida_status_utc"] or row["corte_utc"]
        )
        current, total = metrics[row["item_id"]]
        row.update(
            duracao_horas_uteis=hours,
            horas_uteis_observadas_encerradas=hours if row["elegivel_comparacao"] else None,
            tempo_status_atual_horas_uteis=current,
            tempo_desde_entrada_horas_uteis=total,
            expediente=POLICY,
            versao_calendario=calendar.version,
        )
    # Validate full precision before rounding the public copy only.
    validate_public(result[GOLD], settings.monday_board_id)
    hour_fields = [field.split(":")[0] for field in FIELDS.split() if field.endswith(":num")]
    for row in result[GOLD]:
        for field in hour_fields:
            if row[field] is not None:
                row[field] = round(row[field], 3)
    validate_public(result[GOLD], settings.monday_board_id)
    result["calendar"] = calendar.snapshot()
    return result


def validate_public(rows, board_id):
    fields = dict(f.split(":") for f in FIELDS.split())
    seen, groups = set(), defaultdict(list)
    for row in rows:
        if set(row) != fields.keys():
            raise ValueError("Contrato sla_orcamento: campos incompatíveis")
        for column, kind in fields.items():
            value = row[column]
            if (value is None and column in REQUIRED) or (
                value is not None and not valid_type(kind, value)
            ):
                raise ValueError(f"Contrato sla_orcamento.{column}: tipo/nulabilidade inválidos")
            if column in REQUIRED and kind == "text" and not value.strip():
                raise ValueError(f"Contrato sla_orcamento.{column}: texto obrigatório vazio")
        if row["board_id"] != board_id or row["interval_id"] in seen:
            raise ValueError("Contrato sla_orcamento: escopo/chave inválidos")
        seen.add(row["interval_id"])
        groups[row["item_id"]].append(row)
        observed = row["qualidade_historico"] == "observed"
        if any(
            (row[c] is not None) != observed
            for c in (
                "entrada_status_utc",
                "entrada_status_local",
                "duracao_horas",
                "duracao_horas_uteis",
            )
        ):
            raise ValueError("Contrato sla_orcamento: duração sem evidência")
        if observed and row["duracao_horas_uteis"] > row["duracao_horas"] + 1e-8:
            raise ValueError("Contrato sla_orcamento: horas úteis excedem horas corridas")
    for group in groups.values():
        ordered = sorted(group, key=lambda r: r["ordem_etapa"])
        if [r["ordem_etapa"] for r in ordered] != list(range(1, len(group) + 1)):
            raise ValueError("Contrato sla_orcamento: sequência inválida")
        if [r["intervalo_aberto"] for r in ordered] != [False] * (len(group) - 1) + [True]:
            raise ValueError("Contrato sla_orcamento: última passagem inválida")


def digest(rows):
    fields = dict(f.split(":") for f in FIELDS.split())
    values = [
        {
            k: r.get(k).astimezone(UTC) if kind == "time" and r.get(k) is not None else r.get(k)
            for k, kind in fields.items()
        }
        for r in rows
    ]
    values.sort(key=lambda r: r["interval_id"])
    return hashlib.sha256(canonical_json(values)).hexdigest()
