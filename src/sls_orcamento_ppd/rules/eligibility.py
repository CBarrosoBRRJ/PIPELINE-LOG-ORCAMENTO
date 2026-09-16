"""Whole-project exclusions. Codes are the stable audit interface."""

import re

from ..services.clean import clean_text
from ..services.extract import norm, obj

COLLECTIVES = {"bruno e marrone", "manual do mundo", "podpah"}

EXCLUSION_REASONS = {
    "talento_ambas_colunas": "Talento e Interveniência preenchidos",
    "talento_multiplo": "Mais de um talento no projeto",
    "talento_squad": "Squad de Talentos",
    "talento_nao_individual": "Coletivo ou organização identificados",
    "talento_identidade_pendente": "Interveniência sem identidade individual revisada",
    "talento_revisao_manual": "Grafia ou identidade de talento em quarentena manual",
    "marca_revisao_manual": "Grafia ou identidade de Marca em quarentena manual",
}


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
        if row["review_status"] == "quarantined":
            reasons.add("talento_revisao_manual")
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
    if identity[2] == "pendente_revisao":
        reasons.add("talento_identidade_pendente")
    return sorted(reasons), origin, identity
