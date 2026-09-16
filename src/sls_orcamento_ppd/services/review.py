"""Private GCS review artifacts and explicitly approved catalog imports."""

import json
from datetime import datetime
from pathlib import Path


def export_review(store, settings):
    data = store.read_many(["quarentena_projeto", "meta_entity_mapping"], settings.monday_board_id)
    data["pendencias_projeto"] = store.read("pendencias_projeto", settings.monday_board_id)
    return {
        "quarantined_projects": len(data["quarentena_projeto"]),
        "catalog_entries": len(data["meta_entity_mapping"]),
        "uri": store.write_artifact("review", data),
    }


def import_review(store, settings, path):
    if str(path).startswith("gs://"):
        from google.cloud import storage

        blob = storage.Blob.from_string(
            str(path), client=storage.Client(project=settings.bq_project)
        )
        rows = json.loads(blob.download_as_bytes())
    else:
        rows = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("Revisão requer lista JSON não vazia")
    for row in rows:
        if row.get("review_status") not in {"approved", "quarantined"}:
            raise ValueError("Importe somente identidades explicitamente revisadas")
        row["updated_at"] = datetime.fromisoformat(row["updated_at"])
    from ..models.contracts import prepare_payload
    from ..rules.identities import Catalog
    from ..utils.time import utcnow
    from .load import merge_rows

    rows = prepare_payload({"meta_entity_mapping": rows}, settings.monday_board_id)[
        "meta_entity_mapping"
    ]
    with store.lock():
        combined = merge_rows(store.read("meta_entity_mapping"), rows, "meta_entity_mapping")
        Catalog(combined, settings.monday_board_id, utcnow())
        store.commit({"meta_entity_mapping": rows}, settings.monday_board_id, reviewed=True)
    return {"reviewed_rows": len(rows), "next_step": "replay ou próxima carga diária"}
