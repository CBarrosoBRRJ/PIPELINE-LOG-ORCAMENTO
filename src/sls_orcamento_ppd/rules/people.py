"""Role mapping and accountable attribution, without multiplying passages."""

from collections import defaultdict

from ..services.clean import clean_text
from ..services.extract import norm

ROLE_TITLES = {
    "responsavel_orcamento": "orcamento",
    "talent_manager": "talent manager",
    "gp": "gp",
    "audiencia": "audiencia",
    "conteudo": "conteudo",
    "producao": "producao",
}


def person_name(value, person_id=None):
    """Reject known technical labels without guessing the original person's identity."""
    name = clean_text(value)
    if not name:
        return None
    normalized = norm(name)
    if any(
        label in normalized
        for label in (
            "deleted on invitation cancelation",
            "deleted on invitation cancellation",
        )
    ):
        return None
    if person_id is not None and normalized == norm(f"Pessoa {person_id}"):
        return None
    return name


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
        name = person_name(known.get("person_name"), p["id"]) or person_name(p.get("name"), p["id"])
        name_source = "cadastro_pessoa" if name else "indisponivel"
        column_text = person_name(raw_values.get(p["source_column_id"], {}).get("text"), p["id"])
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
    unmatched_text_fields = set()
    for field, column_id in columns.items():
        members = [p for p in all_people if p["coluna_id"] == column_id]
        raw_text = person_name(
            raw_values.get(column_id, {}).get("text"),
            members[0]["id"] if len(members) == 1 else None,
        )
        if members and any(not p["nome"] for p in members) and raw_text:
            result[field] = raw_text
            unmatched_text_fields.add(field)
    situation = (
        "ausente"
        if not owners
        else "equipe"
        if any(p["tipo"] != "person" for p in owners)
        else "nome_indisponivel"
        if any(not p["nome"] for p in owners)
        else "identificado"
    )
    if situation == "nome_indisponivel" and "responsavel_orcamento" in unmatched_text_fields:
        situation = "texto_snapshot_sem_correspondencia_individual"
    return {
        **result,
        "pessoas_referencia_json": all_people,
        "responsaveis_orcamento_json": owners,
        "quantidade_responsaveis_orcamento": len(owners),
        "responsavel_situacao": situation,
    }
