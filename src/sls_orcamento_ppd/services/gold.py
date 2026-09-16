"""One row per status passage; no source mutation or external identity inference."""

import hashlib
import json
from collections import Counter, defaultdict
from zoneinfo import ZoneInfo

from ..models.contracts import validate_table
from ..models.keys import with_surrogates
from ..rules import RULE_VERSION
from ..rules.cutoff import close_gold_day
from ..rules.eligibility import talent_decision
from ..rules.identities import Catalog
from ..rules.people import people_fields
from .clean import clean_text


def build_gold(
    payload, snapshots, board, mapping, catalog_rows, persons, settings, at, *, cutoff=None
):
    """Enrich the complete technical history, then exclude whole projects only from Gold."""
    catalog = Catalog(catalog_rows, settings.monday_board_id, at)
    approved = [r for r in catalog_rows if r["review_status"] in {"approved", "quarantined"}]
    version_input = {
        "board_id": settings.monday_board_id,
        "catalog": sorted(approved, key=lambda r: (r["entity_type"], r["source_key"])),
        "mapping": mapping,
        "columns": [{k: c[k] for k in ("id", "title", "type")} for c in board["columns"]],
        "initial": settings.initial_status_label,
        "final": settings.final_status_labels,
        "cut_policy": "closed_day" if cutoff is not None else "ingestion_start",
    }
    digest = hashlib.sha256(
        json.dumps(version_input, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    version = f"{RULE_VERSION}:{digest}"
    payload["meta_gold_rule_snapshot"] = [
        {
            "versao_regras": version,
            "board_id": settings.monday_board_id,
            "conteudo": json.loads(json.dumps(version_input, default=str)),
            "registrado_em": at,
        }
    ]
    latest = {}
    for snapshot in sorted(snapshots, key=lambda r: (r["snapshot_at"], r["item_id"])):
        if snapshot["snapshot_at"] <= at:
            latest[snapshot["item_id"]] = snapshot
    statuses = {r["status_id"]: r for r in payload["dim_status"]}
    summaries = {r["item_id"]: r for r in payload["fct_item_sla_summary"]}
    people = {str(r["person_id"]): r for r in persons}
    grouped, issues = defaultdict(list), defaultdict(set)
    for row in payload["fct_item_status_interval"]:
        grouped[row["item_id"]].append(row)  # Preserve transform's native event tie order.
    for row in payload["data_quality_issue"]:
        issues[row["item_id"]].add(row["code"])
    zone = ZoneInfo(settings.preferred_timezone)

    def local(timestamp):
        return timestamp.astimezone(zone).replace(tzinfo=None) if timestamp else None

    def issue(item_id, code, detail):
        payload["data_quality_issue"].append(
            {
                "issue_id": hashlib.sha256(
                    f"{settings.monday_board_id}|{item_id}|{code}".encode()
                ).hexdigest(),
                "board_id": settings.monday_board_id,
                "item_id": item_id,
                "code": code,
                "detail": json.dumps({"versao_regras": version, **detail}, ensure_ascii=False),
                "detected_at": at,
            }
        )

    gold, quarantine = [], []
    for item in sorted(payload["dim_item"], key=lambda r: r["item_id"]):
        item_id = item["item_id"]
        snap = latest.get(item_id, {})
        reasons, origin, talent = talent_decision(snap, mapping, catalog)
        brand = catalog.resolve("marca", snap.get("marca"))
        if brand[2] == "quarentena":
            reasons = sorted(set(reasons) | {"marca_revisao_manual"})
        if reasons:
            issue(item_id, "gold_projeto_excluido", {"motivos": reasons})
            quarantine.append(
                with_surrogates(
                    "quarentena_projeto",
                    {
                        "board_id": item["board_id"],
                        "item_id": item_id,
                        "projeto_nome": clean_text(item["item_name"]),
                        "marca_original": snap.get("marca"),
                        "talento_original": snap.get("talento"),
                        "interveniencia_original": snap.get("intervenciencia"),
                        "motivos": reasons,
                        "cadastro_referencia_utc": snap.get("snapshot_at"),
                        "corte_utc": cutoff or at,
                        "versao_regras": version,
                        "atualizado_em": at,
                    },
                )
            )
            continue
        if talent[2] == "pendente_revisao":
            issue(item_id, "gold_identidade_pendente", {"entidade": "talento"})
        summary = summaries[item_id]
        current = statuses[item["current_status_id"]]
        attrs = people_fields(snap, board, people)
        intervals = grouped[item_id]
        counts = Counter()
        inconsistent = bool(
            issues[item_id] & {"cadeia_status_inconsistente", "snapshot_status_divergente"}
        )
        for order, row in enumerate(intervals, 1):
            counts[row["status_id"]] += 1
            status = statuses[row["status_id"]]
            closed_observed = (
                row["history_quality"] == "observed"
                and not row["is_open_interval"]
                and not inconsistent
            )
            end = None if row["is_open_interval"] else row["status_end_utc"]
            gold.append(
                with_surrogates(
                    "gold_projeto_status",
                    {
                        "interval_id": row["interval_id"],
                        "board_id": item["board_id"],
                        "item_id": item_id,
                        "status_id": row["status_id"],
                        "projeto_nome": clean_text(item["item_name"]),
                        "status_nome": status["status_label"],
                        "ordem_status_quadro": status["status_order"],
                        "status_final": status["is_terminal"],
                        "ordem_etapa": order,
                        "passagem_numero_no_status": counts[row["status_id"]],
                        "eh_retorno": counts[row["status_id"]] > 1,
                        "eh_primeiro_registro": order == 1,
                        "eh_ultimo_registro": order == len(intervals),
                        "entrada_status_utc": row["status_start_utc"],
                        "saida_status_utc": end,
                        "entrada_status_local": local(row["status_start_utc"]),
                        "saida_status_local": local(end),
                        "corte_utc": at,
                        "corte_local": local(at),
                        "duracao_minutos": row["duration_minutes"],
                        "duracao_horas": row["duration_hours"],
                        "intervalo_aberto": row["is_open_interval"],
                        "qualidade_historico": row["history_quality"],
                        "elegivel_comparacao": closed_observed,
                        "horas_observadas_encerradas": row["duration_hours"]
                        if closed_observed
                        else None,
                        "status_atual_id": item["current_status_id"],
                        "status_atual_nome": current["status_label"],
                        "projeto_ativo": item["is_active"],
                        "projeto_na_fila": item["is_active"] and not current["is_terminal"],
                        "status_atual_divergente": "snapshot_status_divergente" in issues[item_id],
                        "entrada_comprovada_utc": summary["sla_start_utc"],
                        "finalizado_em_utc": summary["finalizado_em"],
                        "tempo_desde_entrada_horas": summary["lead_time_total_min"] / 60
                        if summary["lead_time_total_min"] is not None
                        else None,
                        "tempo_status_atual_horas": summary["sla_status_atual_min"] / 60
                        if summary["sla_status_atual_min"] is not None
                        else None,
                        "marca_chave": brand[0],
                        "marca_nome": brand[1],
                        "marca_situacao": brand[2],
                        "talento_chave": talent[0],
                        "talento_nome": talent[1],
                        "talento_situacao": talent[2],
                        "talento_origem": origin,
                        "cadastro_referencia_utc": snap.get("snapshot_at"),
                        "versao_regras": version,
                        **attrs,
                    },
                )
            )
    if cutoff is not None:
        if cutoff > at:
            raise ValueError("Gold: corte posterior à extração")
        gold = close_gold_day(gold, cutoff, settings.preferred_timezone)
    payload["gold_projeto_status"] = gold
    payload["quarentena_projeto"] = quarantine
    # The pipeline only discovers candidates. Never overwrite human approvals.
    payload["meta_entity_mapping"] = [
        r for key, r in catalog.rows.items() if key not in catalog.original_keys
    ]
    validate_gold(payload, cutoff=cutoff)
    return {
        "gold_rows": len(gold),
        "gold_projects": len({r["item_id"] for r in gold}),
        "gold_excluded_projects": sum(
            q["code"] == "gold_projeto_excluido" for q in payload["data_quality_issue"]
        ),
        "gold_rules_version": version,
        "gold_cut_utc": (cutoff or at).isoformat(),
    }


def validate_gold(payload, *, cutoff=None):
    """Check exact eligible set, source durations, sequence and whole-project exclusion."""
    gold = payload["gold_projeto_status"]
    validate_table("gold_projeto_status", gold)
    cuts = {r["corte_utc"] for r in gold}
    if len(cuts) > 1 or (cutoff is not None and cuts and cuts != {cutoff}):
        raise ValueError("Gold: cortes misturados")
    cutoff = cutoff or next(iter(cuts), None)
    excluded = {
        q["item_id"] for q in payload["data_quality_issue"] if q["code"] == "gold_projeto_excluido"
    }
    if "quarentena_projeto" in payload:
        validate_table("quarentena_projeto", payload["quarentena_projeto"])
        if {r["item_id"] for r in payload["quarentena_projeto"]} != excluded:
            raise ValueError("Quarentena: projetos não reconciliados com as exclusões")
    source = {
        r["interval_id"]: r
        for r in payload["fct_item_status_interval"]
        if r["item_id"] not in excluded and (cutoff is None or r["status_start_utc"] < cutoff)
    }
    if set(source) != {r["interval_id"] for r in gold}:
        raise ValueError("Gold: conjunto de passagens não reconciliado")
    by_item = defaultdict(list)
    for row in gold:
        raw = source[row["interval_id"]]
        if (
            row["item_id"],
            row["status_id"],
            row["entrada_status_utc"],
            row["duracao_minutos"],
            row["qualidade_historico"],
        ) != (
            raw["item_id"],
            raw["status_id"],
            raw["status_start_utc"],
            (min(raw["status_end_utc"], cutoff) - raw["status_start_utc"]).total_seconds() / 60
            if cutoff is not None
            else raw["duration_minutes"],
            raw["history_quality"],
        ):
            raise ValueError("Gold: identidade, duração ou histórico divergente")
        by_item[row["item_id"]].append(row)
    for rows in by_item.values():
        counts = Counter()
        ordered = sorted(rows, key=lambda r: r["ordem_etapa"])
        for order, row in enumerate(ordered, 1):
            counts[row["status_id"]] += 1
            if (
                row["ordem_etapa"] != order
                or row["passagem_numero_no_status"] != counts[row["status_id"]]
                or row["eh_retorno"] != (counts[row["status_id"]] > 1)
                or row["eh_primeiro_registro"] != (order == 1)
                or row["eh_ultimo_registro"] != (order == len(rows))
            ):
                raise ValueError("Gold: sequência ou retorno inválido")
            if order > 1 and ordered[order - 2]["saida_status_utc"] != row["entrada_status_utc"]:
                raise ValueError("Gold: descontinuidade entre passagens")
            if row["intervalo_aberto"] != (order == len(rows)):
                raise ValueError("Gold: apenas a última passagem pode estar aberta")
