"""Reviewed aliases; cosmetic normalization never proves identity."""

from uuid import NAMESPACE_URL, uuid5

from ..models.contracts import validate_table
from ..services.clean import clean_text


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
                "review_reason": None,
                "updated_at": self.at,
            }
        return self.rows[key]

    def resolve(self, entity_type, value, *, exclusive=False):
        row = self.get(entity_type, value)
        if row is None:
            return None, None, "ausente"
        if row["review_status"] == "quarantined":
            return None, None, "quarentena"
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
