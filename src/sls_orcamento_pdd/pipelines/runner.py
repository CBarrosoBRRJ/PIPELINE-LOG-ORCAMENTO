import json
import uuid
from zoneinfo import ZoneInfo

from ..clients.monday_client import MondayClient, MondayError
from ..db import get_store
from ..services.extract import discover, extract_activities, snapshot
from ..services.gold import build_gold
from ..services.load import merge_rows
from ..services.state import watermark, write_status
from ..services.transform import transform
from ..utils.logging import emit
from ..utils.time import utcnow


def run(settings, mode="daily", *, client=None, store=None, at=None):
    started = at or utcnow()
    run_id = str(uuid.uuid4())
    report = {
        "run_id": run_id,
        "board_id": settings.monday_board_id,
        "mode": mode,
        "start_at": started,
        "status": "running",
        "failures": 0,
    }
    client = client or MondayClient(settings)
    store = store or get_store(settings)
    emit("pipeline_start", **report)
    try:
        store.initialize()
        with store.lock():
            board = client.board()
            mapping, statuses, labels = discover(board, settings)
            previous = watermark(
                store.read("etl_watermark", settings.monday_board_id), settings.pipeline_name
            )
            if previous and started < previous["last_run_utc"]:
                raise ValueError(
                    "Execução anterior ao watermark; use replay para reprocessar sem regredir estado"
                )
            from ..utils.time import parse_timestamp

            if board.get("created_at") and parse_timestamp(board["created_at"]) > parse_timestamp(
                settings.backfill_from
            ):
                settings = settings.model_copy(update={"backfill_from": board["created_at"]})
            settings.runtime_dir.mkdir(parents=True, exist_ok=True)
            (settings.runtime_dir / "board_mapping.json").write_text(
                json.dumps(
                    {
                        "board_id": board["id"],
                        "board_name": board["name"],
                        "mapping": mapping,
                        "columns": board["columns"],
                        "statuses": statuses,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            snapshots = []
            for page in client.item_pages():
                snapshots.extend(snapshot(i, mapping, labels, settings, started) for i in page)
                emit("items_page", page=client.pages_items, items_read=len(snapshots))
            active_ids = {s["item_id"] for s in snapshots if s["is_active"]}
            if len(active_ids) != int(board["items_count"]):
                # A moving board can be retried; never mark missing pages as success.
                raise ValueError(
                    f"Board tem {board['items_count']} itens; extração trouxe {len(active_ids)}. Reexecute se o quadro mudou durante a leitura."
                )
            people = [
                p["id"] for s in snapshots for p in s["pessoas_json"] if p["kind"] == "person"
            ]
            persons = []
            try:
                persons = [
                    {"person_id": str(u["id"]), "person_name": u["name"], "email": u.get("email")}
                    for u in client.users(people)
                ]
            except MondayError:
                report["person_lookup_warning"] = "Sem permissão para users; IDs preservados"
            known_people = {p["person_id"]: p for p in store.read("dim_person")}
            known_people.update({p["person_id"]: p for p in persons})
            for person_id in set(people):
                known_people.setdefault(
                    person_id,
                    {"person_id": person_id, "person_name": f"Pessoa {person_id}", "email": None},
                )
            roles = {c["id"]: c["title"] for c in board["columns"]}
            for row in snapshots:
                for person in row["pessoas_json"]:
                    person["name"] = known_people.get(person["id"], {}).get("person_name")
                    person["role"] = roles[person["source_column_id"]]
            old_events = store.read("bronze_monday_activity_log_raw", settings.monday_board_id)
            old_snapshots = store.read("bronze_monday_item_snapshot_raw", settings.monday_board_id)
            events = extract_activities(
                client,
                settings,
                started,
                previous["last_run_utc"] if previous and mode == "daily" else None,
            )
            all_events = merge_rows(old_events, events, "bronze_monday_activity_log_raw")
            all_snapshots = merge_rows(old_snapshots, snapshots, "bronze_monday_item_snapshot_raw")
            payload = transform(all_events, all_snapshots, statuses, settings, started, active_ids)
            report.update(
                build_gold(
                    payload,
                    all_snapshots,
                    board,
                    mapping,
                    store.read("meta_entity_mapping", settings.monday_board_id),
                    list(known_people.values()),
                    settings,
                    started,
                )
            )
            previous_intervals = {
                r["interval_id"]
                for r in store.read("fct_item_status_interval", settings.monday_board_id)
            }
            old_ids = {r["event_id"] for r in old_events}
            report.update(
                {
                    "board_items": int(board["items_count"]),
                    "active_items": len(active_ids),
                    "total_raw_events": len(all_events),
                    "extracted_events": len(events),
                    "new_events": sum(e["event_id"] not in old_ids for e in events),
                    "upserted_existing_events": sum(e["event_id"] in old_ids for e in events),
                    "total_intervals": len(payload["fct_item_status_interval"]),
                    "new_intervals": sum(
                        i["interval_id"] not in previous_intervals
                        for i in payload["fct_item_status_interval"]
                    ),
                    "affected_items": len(payload["dim_item"]),
                    "daily_rows": len(payload["fct_item_status_daily"]),
                    "quality_issues": len(payload["data_quality_issue"]),
                    "source_empty_status_items": sum(
                        q["code"] == "status_atual_vazio" for q in payload["data_quality_issue"]
                    ),
                    "items_pages": client.pages_items,
                    "activity_pages": client.pages_logs,
                    "api_calls": client.calls,
                    "end_at": utcnow(),
                    "status": "success",
                }
            )
            most_recent = max(
                all_events, key=lambda e: (e["event_at_utc"], e["event_id"]), default=None
            )
            payload.update(
                {
                    "dim_board": [
                        {
                            "board_id": settings.monday_board_id,
                            "board_name": board["name"],
                            "created_at": parse_timestamp(board["created_at"])
                            if board.get("created_at")
                            else None,
                            "updated_at": started,
                        }
                    ],
                    "meta_column_mapping": column_catalog(
                        board,
                        mapping,
                        started,
                        store.read("meta_column_mapping", settings.monday_board_id),
                    ),
                    "bronze_monday_activity_log_raw": events,
                    "bronze_monday_item_snapshot_raw": snapshots,
                    "bronze_monday_board_schema_raw": [
                        {
                            "board_id": settings.monday_board_id,
                            "snapshot_date": started.astimezone(
                                ZoneInfo(settings.preferred_timezone)
                            ).date(),
                            "snapshot_at": started,
                            "raw_data": board,
                            "mapping": mapping,
                        }
                    ],
                    "dim_person": list(known_people.values()),
                    "etl_watermark": [
                        {
                            "pipeline_name": settings.pipeline_name,
                            "board_id": settings.monday_board_id,
                            "last_run_utc": started,
                            "last_log_event_id": most_recent["event_id"] if most_recent else None,
                            "last_item_page_cursor": None,
                            "updated_at": report["end_at"],
                        }
                    ],
                    "etl_run": [
                        {
                            "run_id": run_id,
                            "board_id": settings.monday_board_id,
                            "mode": mode,
                            "start_at": started,
                            "end_at": report["end_at"],
                            "status": "success",
                            "metrics": json.loads(json.dumps(report, default=str)),
                        }
                    ],
                }
            )
            store.commit(payload, settings.monday_board_id)
            report["end_at"] = utcnow()
    except Exception as error:
        report.update(
            {
                "status": "failed",
                "failures": 1,
                "end_at": utcnow(),
                "error_type": type(error).__name__,
            }
        )
        # Exception messages can contain SQL parameters and credentials. Only
        # explicit domain errors are safe to surface; no traceback in production.
        if isinstance(error, (ValueError, MondayError, RuntimeError)):
            report["error"] = str(error)[:1000]
        write_status(settings, report)
        emit("pipeline_end", **report)
        raise
    write_status(settings, report)
    emit("pipeline_end", **report)
    return report


def column_catalog(board, mapping, at, previous):
    attributes = {
        column_id: attribute
        for attribute, column_id in mapping.items()
        if isinstance(column_id, str)
    }
    attributes.update(
        {column_id: "pessoas_json / bridge_item_person" for column_id in mapping["pessoas"]}
    )
    catalog = {row["column_id"]: {**row, "is_present": False} for row in previous}
    for column in board["columns"]:
        attribute = "item_name" if column["type"] == "name" else attributes.get(column["id"])
        catalog[column["id"]] = {
            "board_id": int(board["id"]),
            "column_id": column["id"],
            "column_title": column["title"],
            "column_type": column["type"],
            "analytical_attribute": attribute,
            "is_extracted": True,
            "is_modeled": attribute is not None,
            "is_present": True,
            "discovered_at": at,
        }
    return list(catalog.values())


def replay(settings):
    """Rebuild at the last successful cut, without API calls or watermark changes."""
    store = get_store(settings)
    store.initialize()
    with store.lock():
        previous = watermark(
            store.read("etl_watermark", settings.monday_board_id), settings.pipeline_name
        )
        if not previous:
            raise ValueError("Execute backfill antes do replay")
        at = previous["last_run_utc"]
        schemas = store.read("bronze_monday_board_schema_raw", settings.monday_board_id)
        schema = max((r for r in schemas if r["snapshot_at"] <= at), key=lambda r: r["snapshot_at"])
        mapping, statuses, _ = discover(schema["raw_data"], settings)
        snapshots = store.read("bronze_monday_item_snapshot_raw", settings.monday_board_id)
        active_ids = {s["item_id"] for s in snapshots if s["snapshot_at"] == at and s["is_active"]}
        payload = transform(
            store.read("bronze_monday_activity_log_raw", settings.monday_board_id),
            snapshots,
            statuses,
            settings,
            at,
            active_ids,
        )
        payload["meta_column_mapping"] = column_catalog(
            schema["raw_data"],
            mapping,
            at,
            store.read("meta_column_mapping", settings.monday_board_id),
        )
        gold_report = build_gold(
            payload,
            snapshots,
            schema["raw_data"],
            mapping,
            store.read("meta_entity_mapping", settings.monday_board_id),
            store.read("dim_person"),
            settings,
            at,
        )
        store.commit(payload, settings.monday_board_id)
    emit(
        "replay_success",
        as_of=at,
        intervals=len(payload["fct_item_status_interval"]),
        **gold_report,
    )
