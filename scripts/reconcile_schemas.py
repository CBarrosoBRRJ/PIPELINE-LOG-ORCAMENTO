"""Reconcile missing historical rows and rebuild target at its existing cut.

Same PostgreSQL database, two schemas. Source stays intact. Default is dry run.
"""

import argparse
import hashlib
import json

from sls_orcamento_pdd.config import Settings, load_settings
from sls_orcamento_pdd.db.postgres import PostgresStore
from sls_orcamento_pdd.models.contracts import prepare_payload
from sls_orcamento_pdd.models.schemas import DEFINITIONS
from sls_orcamento_pdd.pipelines.runner import column_catalog
from sls_orcamento_pdd.services.extract import discover
from sls_orcamento_pdd.services.load import merge_rows
from sls_orcamento_pdd.services.state import watermark
from sls_orcamento_pdd.services.transform import transform


def digest(rows):
    return hashlib.sha256(
        "\n".join(sorted(json.dumps(r, sort_keys=True, default=str) for r in rows)).encode()
    ).hexdigest()


def reconcile(settings, source_schema, target_schema, apply=False):
    source_schema = Settings.identifier(source_schema)
    target_schema = Settings.identifier(target_schema)
    if source_schema == target_schema:
        raise ValueError("Origem e destino devem ser schemas diferentes")
    settings = settings.model_copy(update={"pg_schema": target_schema})
    source = PostgresStore(settings.model_copy(update={"pg_schema": source_schema}))
    target = PostgresStore(settings)
    names = [
        "bronze_monday_activity_log_raw",
        "bronze_monday_item_snapshot_raw",
        "bronze_monday_board_schema_raw",
        "dim_person",
        "etl_run",
    ]
    # PostgreSQL advisory lock is database/board-wide, covering both schemas.
    with target.lock():
        board = settings.monday_board_id
        checkpoint = target.read("etl_watermark", board)
        target_cut = watermark(checkpoint, settings.pipeline_name)
        source_cut = watermark(source.read("etl_watermark", board), settings.pipeline_name)
        if not target_cut or not source_cut:
            raise ValueError("Os dois schemas precisam ter uma carga concluída")
        at = target_cut["last_run_utc"]
        if source_cut["last_run_utc"] > at:
            raise ValueError(
                "Origem tem corte mais recente; atualizar destino antes de reconciliar"
            )
        merged, missing, source_hashes = {}, {}, {}
        for name in names:
            old, current = source.read(name, board), target.read(name, board)
            source_hashes[name] = digest(old)
            keys = DEFINITIONS[name][0].split(",")
            identities = {tuple(row[k] for k in keys) for row in current}
            missing[name] = [row for row in old if tuple(row[k] for k in keys) not in identities]
            merged[name] = merge_rows(old, current, name)  # Existing target wins on collisions.
        raw_before = digest(target.read("fct_item_status_interval", board))
        schema = max(
            (r for r in merged["bronze_monday_board_schema_raw"] if r["snapshot_at"] <= at),
            key=lambda r: r["snapshot_at"],
        )
        mapping, statuses, _ = discover(schema["raw_data"], settings)
        snapshots = merged["bronze_monday_item_snapshot_raw"]
        active = {r["item_id"] for r in snapshots if r["snapshot_at"] == at and r["is_active"]}
        if not active:
            raise ValueError("Snapshot do corte não encontrado; não é seguro reconstruir a fila")
        payload = transform(
            merged["bronze_monday_activity_log_raw"], snapshots, statuses, settings, at, active
        )
        payload.update(missing)
        payload["meta_column_mapping"] = column_catalog(
            schema["raw_data"], mapping, at, target.read("meta_column_mapping", board)
        )
        prepare_payload(payload, board)
        report = {
            "source_schema": source_schema,
            "target_schema": target_schema,
            "cut_utc": str(at),
            "missing_rows": {k: len(v) for k, v in missing.items()},
            "active_items": len(active),
            "terminal_statuses": sum(s["is_terminal"] for s in payload["dim_status"]),
            "applied": apply,
        }
        if apply:
            target.commit(payload, board)
            if target.read("etl_watermark", board) != checkpoint:
                raise ValueError("Watermark alterado inesperadamente")
            if any(digest(source.read(n, board)) != source_hashes[n] for n in names):
                raise ValueError("Origem alterada durante reconciliação")
            report["source_unchanged"] = True
            report["watermark_unchanged"] = True
            report["intervals_changed"] = raw_before != digest(
                target.read("fct_item_status_interval", board)
            )
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source_schema")
    parser.add_argument("target_schema")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                reconcile(load_settings(), args.source_schema, args.target_schema, args.apply),
                indent=2,
            )
        )
    except Exception as error:
        print(json.dumps({"status": "failed", "error_type": type(error).__name__}))
        raise SystemExit(1) from None
