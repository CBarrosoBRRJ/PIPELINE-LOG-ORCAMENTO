"""Portable checkpoint merging and validation; no database dependencies."""

from ..models.contracts import prepare_payload, validate_table
from ..models.schemas import DEFINITIONS, REPLACE_TABLES, foreign_keys
from ..services.load import merge_rows


def validate_state(data, board_id):
    if set(data) != set(DEFINITIONS):
        raise ValueError("Checkpoint: inventário lógico incompatível")
    for name, rows in data.items():
        validate_table(name, rows, board_id)
    for child, column, parent, target in foreign_keys():
        identities = {r[target] for r in data[parent]}
        if any(r.get(column) is not None and r[column] not in identities for r in data[child]):
            raise ValueError(f"Referência interna órfã: {child}.{column}")


def merge_state(old, payload, board_id, *, reviewed=False):
    payload = prepare_payload(payload, board_id)
    data = dict(old)
    for name, rows in payload.items():
        if name in REPLACE_TABLES:
            data[name] = rows
        elif name == "meta_gold_rule_snapshot" or (name == "meta_entity_mapping" and not reviewed):
            data[name] = merge_rows(rows, old[name], name)
        else:
            if name == "bronze_monday_activity_log_raw":
                ingested = {r["event_id"]: r["ingested_at"] for r in old[name]}
                rows = [
                    {**r, "ingested_at": ingested.get(r["event_id"], r["ingested_at"])}
                    for r in rows
                ]
            data[name] = merge_rows(old[name], rows, name)
    validate_state(data, board_id)
    return data
