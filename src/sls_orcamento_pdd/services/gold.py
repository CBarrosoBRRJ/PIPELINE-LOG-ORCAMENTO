"""One row per status passage; no source mutation or external identity inference."""

import hashlib
import json
import re
from collections import Counter, defaultdict
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from ..models.contracts import validate_table
from ..models.keys import with_surrogates
from .clean import clean_text
from .extract import norm, obj

RULE_VERSION = "2.0.0"
COLLECTIVES = {"bruno e marrone", "manual do mundo", "podpah"}
ROLE_TITLES = {
    "responsavel_orcamento": "orcamento",
    "talent_manager": "talent manager",
    "gp": "gp",
    "audiencia": "audiencia",
    "conteudo": "conteudo",
    "producao": "producao",
}


def source_key(value):
    """Cosmetic matching only: keep accents, punctuation and identity ambiguity."""
    return (clean_text(value) or "").casefold()


def entity_key(board_id, entity_type, value):
    return str(uuid5(NAMESPACE_URL, f"sls_orcamento_pdd:entity:{board_id}:{entity_type}:{value}"))


class Catalog:
    def __init__(self, rows, board_id, at):
        validate_table("meta_entity_mapping", rows, board_id)
        self.rows = {(r["entity_type"], r["source_key"]): dict(r) for r in rows}
        self.original_keys = set(self.rows)
        self.board_id, self.at = board_id, at
        identities = {}
        for row in rows:
            if source_key(row["source_key"]) != row["source_key"]:
                raise ValueError("Catálogo: source_key não normalizada")
            if row["review_status"] == "approved":
                if (
                    not all(
                        clean_text(row.get(k))
                        for k in ("canonical_id", "canonical_name", "reviewed_by")
                    )
                    or row["entity_kind"] == "unknown"
                ):
                    raise ValueError("Catálogo: aprovação sem identidade, tipo ou revisor")
                identity = (row["entity_type"], row["canonical_id"])
                definition = (row["canonical_name"], row["entity_kind"])
                if identity in identities and identities[identity] != definition:
                    raise ValueError("Catálogo: identidade canônica conflitante")
                identities[identity] = definition

    def get(self, entity_type, value):
        label = clean_text(value)
        if not label:
            return None
        key = (entity_type, source_key(label))
        if key not in self.rows:
            self.rows[key] = {
                "board_id": self.board_id,
                "entity_type": entity_type,
                "source_key": key[1],
                "source_text": label,
                "canonical_id": None,
                "canonical_name": None,
                "entity_kind": "unknown",
                "review_status": "pending",
                "reviewed_by": None,
                "updated_at": self.at,
            }
        return self.rows[key]

    def resolve(self, entity_type, value, *, exclusive=False):
        row = self.get(entity_type, value)
        if row is None:
            return None, None, "ausente"
        if row["review_status"] == "approved":
            if entity_type == "talento" and row["entity_kind"] != "person":
                return None, None, "nao_individual"
            return row["canonical_id"], row["canonical_name"], "aprovado"
        if entity_type == "talento" and not exclusive:
            return None, None, "pendente_revisao"
        return (
            entity_key(self.board_id, entity_type, row["source_key"]),
            row["source_text"],
            "cadastro_exclusivo" if exclusive else "texto_normalizado",
        )


def talent_decision(snapshot, mapping, catalog):
    talent, inter = (clean_text(snapshot.get(k)) for k in ("talento", "intervenciencia"))
    # Keep both source values available for review, even on excluded projects.
    for value in (talent, inter):
        catalog.get("talento", value)
    reasons = set()
    if talent and inter:
        reasons.add("talento_ambas_colunas")
    values = {v["id"]: v for v in snapshot.get("raw_data", {}).get("column_values", [])}
    structured = obj(values.get(mapping.get("talento"), {}).get("value"))
    ids = structured.get("ids", [])
    if len(set(ids)) > 1:
        reasons.add("talento_multiplo")
    for original in (snapshot.get("talento"), snapshot.get("intervenciencia")):
        value = clean_text(original)
        if not value:
            continue
        normalized = norm(value)
        row = catalog.get("talento", value)
        if re.search(r"\bsquad\s+(?:de\s+)?talentos\b", normalized):
            reasons.add("talento_squad")
        if normalized in COLLECTIVES or (
            row["review_status"] == "approved" and row["entity_kind"] != "person"
        ):
            reasons.add("talento_nao_individual")
        # Approved individual identities may contain punctuation; structured
        # multiple selection and both-columns exclusions always take precedence.
        approved_person = row["review_status"] == "approved" and row["entity_kind"] == "person"
        if not approved_person and re.search(r"[,;\n\r+]|\s[&/]\s", original):
            reasons.add("talento_multiplo")
    origin = "talento" if talent else "intervenciencia" if inter else None
    identity = catalog.resolve("talento", talent or inter, exclusive=bool(talent))
    return sorted(reasons), origin, identity


def people_fields(snapshot, board, people):
    raw_values = {v["id"]: v for v in snapshot.get("raw_data", {}).get("column_values", [])}
    memberships = defaultdict(set)
    for p in snapshot.get("pessoas_json", []):
        memberships[p["source_column_id"]].add((p["kind"], str(p["id"])))
    columns = {}
    for field, title in ROLE_TITLES.items():
        matches = [
            c["id"] for c in board["columns"] if c["type"] == "people" and norm(c["title"]) == title
        ]
        if len(matches) > 1:
            raise ValueError("Gold: coluna de pessoas ambígua")
        columns[field] = matches[0] if matches else None
    if not columns["responsavel_orcamento"]:
        raise ValueError("Gold: coluna Orçamento do tipo pessoas ausente")
    distinct = {}
    for p in snapshot.get("pessoas_json", []):
        key = (p["source_column_id"], p["kind"], str(p["id"]))
        known = people.get(str(p["id"]), {}) if p["kind"] == "person" else {}
        name = clean_text(known.get("person_name") or p.get("name"))
        if name == f"Pessoa {p['id']}":
            name = None  # Existing technical placeholder is not a resolved name.
        name_source = "cadastro_pessoa" if name else "indisponivel"
        column_text = clean_text(raw_values.get(p["source_column_id"], {}).get("text"))
        if (
            not name
            and column_text
            and len(memberships[p["source_column_id"]]) == 1
            and p["kind"] == "person"
        ):
            name, name_source = column_text, "texto_snapshot_unica_pessoa"
        distinct[key] = {
            "id": str(p["id"]),
            "tipo": p["kind"],
            "nome": name,
            "coluna_id": p["source_column_id"],
            "nome_origem": name_source,
        }
    all_people = [distinct[k] for k in sorted(distinct)]
    result = {
        field: " | ".join(p["nome"] for p in all_people if p["coluna_id"] == col and p["nome"])
        or None
        for field, col in columns.items()
    }
    owners = [p for p in all_people if p["coluna_id"] == columns["responsavel_orcamento"]]
    # Multiple unresolved IDs retain source display text, never a guessed pairing.
    for field, column_id in columns.items():
        members = [p for p in all_people if p["coluna_id"] == column_id]
        raw_text = clean_text(raw_values.get(column_id, {}).get("text"))
        if members and any(not p["nome"] for p in members) and raw_text:
            result[field] = raw_text
    situation = (
        "ausente"
        if not owners
        else "equipe"
        if any(p["tipo"] != "person" for p in owners)
        else "nome_indisponivel"
        if any(not p["nome"] for p in owners)
        else "identificado"
    )
    if situation == "nome_indisponivel" and result["responsavel_orcamento"]:
        situation = "texto_snapshot_sem_correspondencia_individual"
    return {
        **result,
        "pessoas_referencia_json": all_people,
        "responsaveis_orcamento_json": owners,
        "quantidade_responsaveis_orcamento": len(owners),
        "responsavel_situacao": situation,
    }


def build_gold(payload, snapshots, board, mapping, catalog_rows, persons, settings, at):
    """Enrich the complete technical history, then exclude whole projects only from Gold."""
    catalog = Catalog(catalog_rows, settings.monday_board_id, at)
    approved = [r for r in catalog_rows if r["review_status"] == "approved"]
    version_input = {
        "board_id": settings.monday_board_id,
        "catalog": sorted(approved, key=lambda r: (r["entity_type"], r["source_key"])),
        "mapping": mapping,
        "columns": [{k: c[k] for k in ("id", "title", "type")} for c in board["columns"]],
        "initial": settings.initial_status_label,
        "final": settings.final_status_labels,
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

    gold = []
    for item in sorted(payload["dim_item"], key=lambda r: r["item_id"]):
        item_id = item["item_id"]
        snap = latest.get(item_id, {})
        reasons, origin, talent = talent_decision(snap, mapping, catalog)
        brand = catalog.resolve("marca", snap.get("marca"))
        if reasons:
            issue(item_id, "gold_projeto_excluido", {"motivos": reasons})
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
    payload["gold_projeto_status"] = gold
    # The pipeline only discovers candidates. Never overwrite human approvals.
    payload["meta_entity_mapping"] = [
        r for key, r in catalog.rows.items() if key not in catalog.original_keys
    ]
    validate_gold(payload)
    return {
        "gold_rows": len(gold),
        "gold_projects": len({r["item_id"] for r in gold}),
        "gold_excluded_projects": sum(
            q["code"] == "gold_projeto_excluido" for q in payload["data_quality_issue"]
        ),
        "gold_rules_version": version,
    }


def validate_gold(payload):
    """Check exact eligible set, source durations, sequence and whole-project exclusion."""
    gold = payload["gold_projeto_status"]
    validate_table("gold_projeto_status", gold)
    excluded = {
        q["item_id"] for q in payload["data_quality_issue"] if q["code"] == "gold_projeto_excluido"
    }
    source = {
        r["interval_id"]: r
        for r in payload["fct_item_status_interval"]
        if r["item_id"] not in excluded
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
            raw["duration_minutes"],
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
