"""Health follows the durable publication, retaining actual failure signals."""

import json

from ..utils.time import parse_timestamp, utcnow
from .state import watermark

BUSY = "Já existe uma execução ativa para este board"


def check_health(store, settings, *, now=None):
    data = store.read_many(
        ["etl_watermark", "etl_run", "gold_projeto_status"], settings.monday_board_id
    )
    previous = watermark(data["etl_watermark"], settings.pipeline_name)
    if not previous:
        raise ValueError("Nenhuma coleta publicada")
    successful = [
        r
        for r in data["etl_run"]
        if r["status"] == "success" and r["start_at"] == previous["last_run_utc"]
    ]
    if not successful:
        raise ValueError("Watermark sem execução bem-sucedida correspondente")
    last = max(successful, key=lambda r: r["end_at"])
    age = ((now or utcnow()) - previous["last_run_utc"]).total_seconds() / 3600
    if age < 0 or age > settings.run_window_hours + 2:
        raise ValueError("Coleta publicada está atrasada ou com data futura")
    if any(
        r["mode"] == "scheduled" and r["status"] != "success" and r["start_at"] >= last["start_at"]
        for r in data["etl_run"]
    ):
        raise ValueError("Tentativa diária falhou ou não terminou; confira logs e reserva")
    warnings = []
    path = settings.runtime_dir / f"status_{settings.monday_board_id}.json"
    if path.exists():
        runtime = json.loads(path.read_text(encoding="utf-8"))
        if runtime["status"] != "success" and parse_timestamp(runtime["end_at"]) > last["end_at"]:
            if runtime.get("error") == BUSY and not runtime.get("scheduled_date"):
                warnings.append("concurrent_attempt_rejected")
            else:
                raise ValueError("Última tentativa registrada falhou; confira logs")
    return {
        "age_hours": round(age, 2),
        "source": "durable_publication",
        "warnings": warnings,
        "gold_rows": len(data["gold_projeto_status"]),
    }
