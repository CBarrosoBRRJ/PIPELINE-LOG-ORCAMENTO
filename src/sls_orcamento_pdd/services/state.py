import json
import os


def write_status(settings, report):
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    path = settings.runtime_dir / f"status_{settings.monday_board_id}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    os.replace(temporary, path)


def watermark(rows, pipeline_name):
    return next((r for r in rows if r["pipeline_name"] == pipeline_name), None)
