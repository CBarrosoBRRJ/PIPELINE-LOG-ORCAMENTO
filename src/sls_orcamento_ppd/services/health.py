"""Health follows the durable publication, retaining actual failure signals."""

from ..utils.time import utcnow
from .state import watermark


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
    return {
        "age_hours": round(age, 2),
        "source": "durable_publication",
        "warnings": [],
        "gold_rows": len(data["gold_projeto_status"]),
    }
