"""Python projection: business passages and private project-level correction queue.

Internal evidence stays unchanged. Unknown dates/durations are NULL in the public
table, never an estimate presented as a measured SLA.
"""

import hashlib
import json
from collections import defaultdict
from datetime import UTC

from ..rules.eligibility import EXCLUSION_REASONS
from ..rules.people import person_name

GOLD = "gold_projeto_status"
PENDING = "pendencias_projeto"
PUBLIC_FIELDS = {
    GOLD: (
        "ordem_etapa:int projeto_nome:text status_nome:text entrada_status_local:localtime "
        "saida_status_local:localtime duracao_horas:num marca_nome:text talento_nome:text "
        "responsavel_orcamento:text eh_retorno:bool item_id:id board_id:id interval_id:text "
        "qualidade_historico:text intervalo_aberto:bool status_final:bool corte_local:localtime "
        "elegivel_comparacao:bool horas_observadas_encerradas:num status_atual_nome:text "
        "projeto_na_fila:bool tempo_desde_entrada_horas:num tempo_status_atual_horas:num "
        "responsavel_situacao:text cadastro_referencia_utc:time versao_regras:text "
        "item_sk:text board_sk:text status_id:text status_sk:text "
        "entrada_status_utc:time saida_status_utc:time corte_utc:time"
    ),
    PENDING: (
        "item_id:id board_id:id projeto_nome:text excluido_da_analise:bool "
        "motivos:text como_corrigir:text marca_original:text talento_original:text "
        "interveniencia_original:text responsavel_orcamento_original:text codigos:text "
        "cadastro_referencia_utc:time corte_local:localtime versao_regras:text item_sk:text"
    ),
}
PUBLIC_KEYS = {GOLD: ("interval_id",), PENDING: ("board_id", "item_id")}
PUBLIC_REQUIRED = {
    GOLD: {
        "ordem_etapa",
        "projeto_nome",
        "status_nome",
        "eh_retorno",
        "item_id",
        "board_id",
        "interval_id",
        "qualidade_historico",
        "intervalo_aberto",
        "status_final",
        "corte_local",
        "elegivel_comparacao",
        "status_atual_nome",
        "projeto_na_fila",
        "responsavel_situacao",
        "versao_regras",
        "item_sk",
        "board_sk",
        "status_id",
        "status_sk",
        "corte_utc",
    },
    PENDING: {
        "item_id",
        "board_id",
        "projeto_nome",
        "excluido_da_analise",
        "motivos",
        "como_corrigir",
        "codigos",
        "corte_local",
        "versao_regras",
        "item_sk",
    },
}


def public_gold(rows):
    fields = [f.split(":")[0] for f in PUBLIC_FIELDS[GOLD].split()]
    last_observed = {
        r["item_id"]: r["qualidade_historico"] == "observed"
        for r in rows
        if r["eh_ultimo_registro"]
    }
    result = []
    for source in rows:
        row = {name: source.get(name) for name in fields}
        if row["qualidade_historico"] != "observed":
            for name in ("entrada_status_utc", "entrada_status_local", "duracao_horas"):
                row[name] = None
        if not last_observed.get(row["item_id"]):
            row["tempo_status_atual_horas"] = None
        if row["responsavel_orcamento"] and not person_name(row["responsavel_orcamento"]):
            row["responsavel_orcamento"] = None
            row["responsavel_situacao"] = "nome_indisponivel"
        result.append(row)
    return result


def pending_projects(data, timezone="America/Sao_Paulo"):
    """One current row per project; source corrections remove resolved reasons on replay/load."""
    latest = {}
    for snapshot in sorted(data["bronze_monday_item_snapshot_raw"], key=lambda r: r["snapshot_at"]):
        latest[snapshot["item_id"]] = snapshot
    histories = defaultdict(list)
    for row in data[GOLD]:
        histories[row["item_id"]].append(row)
    quarantine = {row["item_id"]: row for row in data["quarentena_projeto"]}
    result = []
    for item_id in sorted(set(histories) | set(quarantine)):
        passages = sorted(histories[item_id], key=lambda r: r["ordem_etapa"])
        q = quarantine.get(item_id)
        snap = latest.get(item_id, {})
        source = q or passages[-1]
        codes = set(q["motivos"] if q else [])
        if passages:
            if all(r["qualidade_historico"] == "no_history_inferred" for r in passages):
                codes.add("historico_sem_transicoes")
            elif any(r["qualidade_historico"] != "observed" for r in passages):
                codes.add("historico_inicial_nao_comprovado")
            if not passages[-1]["entrada_comprovada_utc"]:
                codes.add("inicio_entrada_nao_comprovado")
            if passages[-1]["status_atual_divergente"]:
                codes.add("status_atual_divergente")
            situation = public_gold([passages[-1]])[0]["responsavel_situacao"]
            if situation != "identificado":
                codes.add("responsavel_" + situation)
        if not codes:
            continue
        labels = dict(EXCLUSION_REASONS)
        labels.update(
            {
                "historico_sem_transicoes": "Histórico sem transições comprovadas; duração desconhecida",
                "historico_inicial_nao_comprovado": "Início do primeiro trecho não comprovado",
                "inicio_entrada_nao_comprovado": "Entrada inicial do processo não comprovada",
                "status_atual_divergente": "Status do cadastro diverge da última transição",
                "responsavel_ausente": "Responsável Orçamento não preenchido",
                "responsavel_nome_indisponivel": "ID de responsável sem nome válido disponível",
                "responsavel_equipe": "Equipe atribuída sem responsável individual",
                "responsavel_texto_snapshot_sem_correspondencia_individual": "Nomes de responsáveis sem correspondência individual segura aos IDs",
            }
        )
        actions = []
        if q:
            actions.append(
                "Revisar Talento/Interveniência e Marca no Monday; manter uma única pessoa individual em uma única coluna. Grafias e identidades ambíguas exigem revisão do catálogo, sem junção automática por similaridade."
            )
        if any(c.startswith("historico_") or c == "inicio_entrada_nao_comprovado" for c in codes):
            actions.append(
                "Verificar se existe histórico anterior exportável. Não inventar datas nem mover o status para simular o passado; novas transições serão capturadas nas próximas cargas."
            )
        if any(c.startswith("responsavel_") for c in codes):
            actions.append(
                "Conferir a pessoa na coluna Orçamento do Monday; substituir referências excluídas e conferir permissão de leitura de usuários."
            )
        if "status_atual_divergente" in codes:
            actions.append(
                "Conferir a atividade do item e o status atual no Monday; se a divergência persistir após a próxima carga, revisar os eventos disponíveis."
            )
        raw = next(
            (
                v.get("text")
                for v in snap.get("raw_data", {}).get("column_values", [])
                if v.get("id") == "person"
            ),
            None,
        )
        # Discover the responsible source column, instead of coupling new boards to 'person'.
        schemas = data["bronze_monday_board_schema_raw"]
        if schemas:
            from ..services.extract import norm

            board = max(schemas, key=lambda r: r["snapshot_at"])["raw_data"]
            owner_ids = {
                c["id"]
                for c in board["columns"]
                if c["type"] == "people" and norm(c["title"]) == "orcamento"
            }
            raw = (
                " | ".join(
                    v["text"]
                    for v in snap.get("raw_data", {}).get("column_values", [])
                    if v.get("id") in owner_ids and v.get("text")
                )
                or None
            )
        if q:
            from zoneinfo import ZoneInfo

            # Same local cut as Gold; no wall-clock timestamp mixed into the published batch.
            local_cut = passages[0]["corte_local"] if passages else None
            if local_cut is None:
                local_cut = q["corte_utc"].astimezone(ZoneInfo(timezone)).replace(tzinfo=None)
        else:
            local_cut = source["corte_local"]
        result.append(
            {
                "item_id": item_id,
                "board_id": source["board_id"],
                "projeto_nome": source["projeto_nome"],
                "excluido_da_analise": q is not None,
                "motivos": " | ".join(labels.get(c, c) for c in sorted(codes)),
                "como_corrigir": " ".join(actions),
                "codigos": " | ".join(sorted(codes)),
                "marca_original": snap.get("marca"),
                "talento_original": snap.get("talento"),
                "interveniencia_original": snap.get("intervenciencia"),
                "responsavel_orcamento_original": raw,
                "cadastro_referencia_utc": source.get("cadastro_referencia_utc"),
                "corte_local": local_cut,
                "versao_regras": source["versao_regras"],
                "item_sk": source["item_sk"],
            }
        )
    return result


def publication(data, timezone="America/Sao_Paulo"):
    result = {GOLD: public_gold(data[GOLD]), PENDING: pending_projects(data, timezone)}
    for name, rows in result.items():
        keys = PUBLIC_KEYS[name]
        if len(rows) != len({tuple(r[k] for k in keys) for r in rows}):
            raise ValueError(f"Consumo: chave duplicada em {name}")
        if any(r.get(k) is None for r in rows for k in PUBLIC_REQUIRED[name]):
            raise ValueError(f"Consumo: campo obrigatório ausente em {name}")
    gold_ids = {(r["board_id"], r["item_id"]) for r in result[GOLD]}
    if any(
        (r["board_id"], r["item_id"]) in gold_ids
        for r in result[PENDING]
        if r["excluido_da_analise"]
    ):
        raise ValueError("Consumo: projeto excluído presente na análise")
    return result


def public_fingerprint(name, rows):
    fields = dict(f.split(":") for f in PUBLIC_FIELDS[name].split())
    values = [
        {
            k: r.get(k).astimezone(UTC)
            if fields[k] == "time" and r.get(k) is not None
            else r.get(k)
            for k in fields
        }
        for r in rows
    ]
    values.sort(key=lambda r: tuple(str(r[k]) for k in PUBLIC_KEYS[name]))
    raw = json.dumps(
        values,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=lambda v: v.isoformat(),
    )
    return hashlib.sha256(raw.encode()).hexdigest()
