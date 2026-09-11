"""Private review artifacts, outside the PostgreSQL consumption database."""

import csv
import json
from datetime import datetime
from pathlib import Path


def export_review(store, settings):
    data = store.read_many(["quarentena_projeto", "meta_entity_mapping"], settings.monday_board_id)
    folder = settings.runtime_dir / "review"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "catalogo_identidades.json").write_text(
        json.dumps(data["meta_entity_mapping"], ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    rows = data["quarentena_projeto"]
    from ..models.schemas import DEFINITIONS

    fields = [f.split(":")[0] for f in DEFINITIONS["quarentena_projeto"][1].split()]
    with (folder / "projetos_quarentena.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "motivos": json.dumps(row["motivos"], ensure_ascii=False)})
    return {
        "quarantined_projects": len(rows),
        "catalog_entries": len(data["meta_entity_mapping"]),
        "directory": str(folder),
    }


def import_review(store, settings, path):
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
