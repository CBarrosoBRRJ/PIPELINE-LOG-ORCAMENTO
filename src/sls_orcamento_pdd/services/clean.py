"""Normalize analytical text on copies; never overwrite source JSON/evidence."""

import unicodedata

from .extract import ALIASES, norm


def clean_text(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Tratamento de texto: tipo incompatível; valor omitido")
    return " ".join(unicodedata.normalize("NFC", value).split()) or None


def clean_inputs(events, snapshots, statuses):
    events = [
        {**row, **{k: clean_text(row.get(k)) for k in ("status_from_text", "status_to_text")}}
        for row in events
    ]
    snapshots = [
        {
            **row,
            **{k: clean_text(row.get(k)) for k in ALIASES},
            "item_name": clean_text(row.get("item_name")) or f"Item {row['item_id']}",
            "status_text": clean_text(row.get("status_text")) or "Sem status",
        }
        for row in snapshots
    ]
    statuses = [
        {
            **row,
            "status_label": clean_text(row.get("status_label")) or "Sem status",
            "status_label_norm": norm(clean_text(row.get("status_label")) or "Sem status"),
        }
        for row in statuses
    ]
    return events, snapshots, statuses
