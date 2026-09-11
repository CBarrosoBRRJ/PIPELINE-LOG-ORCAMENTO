import json
import unicodedata
from datetime import timedelta
from zoneinfo import ZoneInfo

from ..utils.logging import emit
from ..utils.time import event_timestamp, iso, parse_timestamp

ALIASES = {
    "marca": ["marca", "marcas", "brand"],
    "cliente": ["cliente", "clientes", "client", "anunciante"],
    "talento": ["talento", "talentos", "talent", "influenciador"],
    "intervenciencia": ["interveniencia", "intervenciencia", "interveniente", "intervenção"],
}


def norm(value):
    return " ".join(
        "".join(
            c
            for c in unicodedata.normalize("NFKD", str(value or ""))
            if not unicodedata.combining(c)
        )
        .casefold()
        .split()
    )


def obj(value):
    if value is None or value == "":
        return {}
    return json.loads(value) if isinstance(value, str) else value


def status_id(settings, index=None, label=None):
    import hashlib

    suffix = (
        str(index)
        if index is not None
        else "label_" + hashlib.sha256(norm(label or "Sem status").encode()).hexdigest()[:16]
    )
    return f"{settings.monday_board_id}:{settings.monday_status_column_id}:{suffix}"


def discover(board, settings):
    columns = board["columns"]
    by_id = {c["id"]: c for c in columns}
    selected = by_id.get(settings.monday_status_column_id)
    if not selected:
        matches = [
            c
            for c in columns
            if c["type"] == "status" and norm(c["title"]) == norm(settings.monday_status_column_id)
        ]
        if len(matches) == 1:
            selected = matches[0]
            settings.monday_status_column_id = selected["id"]
    if not selected or selected["type"] != "status":
        raise ValueError("Coluna principal de status ausente ou tipo incompatível")
    mapping = {
        "status": selected["id"],
        "pessoas": [c["id"] for c in columns if c["type"] == "people"],
    }
    for key, aliases in ALIASES.items():
        explicit = settings.business_columns_override.get(key)
        if explicit:
            if explicit not in by_id:
                raise ValueError(f"Coluna configurada para {key} não existe")
            mapping[key] = explicit
            continue
        candidates = [c for c in columns if c["type"] not in ("people", "formula", "date")]
        matches = [c["id"] for c in candidates if norm(c["title"]) in aliases or c["id"] in aliases]
        if not matches:
            matches = [
                c["id"]
                for c in candidates
                if any(norm(c["title"]).startswith(a + " ") for a in aliases)
            ]
        if len(matches) > 1:
            raise ValueError(
                f"Mapeamento ambíguo para {key}: {matches}; configure BUSINESS_COLUMNS_OVERRIDE"
            )
        mapping[key] = matches[0] if matches else None
    settings_json = obj(selected.get("settings_str"))
    labels = {str(k): v for k, v in settings_json.get("labels", {}).items()}
    labels.update(settings.status_column_labels_override)
    colors = settings_json.get("labels_colors", {})
    positions = settings_json.get("labels_positions_v2", {})
    statuses = []
    for index, label in labels.items():
        statuses.append(
            {
                "status_id": status_id(settings, index, label),
                "board_id": settings.monday_board_id,
                "status_label": label or "Sem status",
                "status_label_norm": norm(label or "Sem status"),
                "status_order": positions.get(index),
                "status_column_id": selected["id"],
                "status_color": colors.get(index, {}).get("color"),
                "is_terminal": norm(label) in {norm(v) for v in settings.final_status_labels},
            }
        )
    return mapping, statuses, labels


def snapshot(item, mapping, labels, settings, at):
    values = {v["id"]: v for v in item.get("column_values", [])}
    status = values.get(mapping["status"], {})
    index = obj(status.get("value")).get("index")
    label = labels.get(str(index), status.get("text")) or "Sem status"
    people = []
    for column_id in mapping["pessoas"]:
        column = values.get(column_id, {})
        for person in obj(column.get("value")).get("personsAndTeams", []):
            people.append(
                {
                    "id": str(person["id"]),
                    "kind": person.get("kind", "person"),
                    "source_column_id": column_id,
                }
            )
    row = {
        "item_id": int(item["id"]),
        "board_id": settings.monday_board_id,
        "item_name": item["name"],
        "group_id": (item.get("group") or {}).get("id"),
        "created_at": parse_timestamp(item["created_at"]) if item.get("created_at") else None,
        "updated_at": parse_timestamp(item["updated_at"]) if item.get("updated_at") else None,
        "pessoas_json": people,
        "snapshot_at": at,
        "snapshot_date": at.astimezone(ZoneInfo(settings.preferred_timezone)).date(),
        "current_status_id": status_id(settings, index, label),
        "status_text": label,
        "status_index": index,
        "is_active": item.get("state", "active") == "active",
        "raw_data": item,
    }
    for key in ALIASES:
        value = values.get(mapping[key], {})
        row[key] = value.get("display_value") or value.get("text") or None
    return row


def parse_activity(log, settings, at):
    if log["event"] != "update_column_value":
        return None
    data = obj(log["data"])
    if data.get("column_id") != settings.monday_status_column_id:
        return None
    timestamp, source = event_timestamp(data, log.get("created_at"))
    before, after = obj(data.get("previous_value")), obj(data.get("value"))

    def label(value):
        raw = value.get("label") or {}
        if isinstance(raw, str):
            return raw, value.get("index")
        return raw.get("text"), raw.get("index", value.get("index"))

    old_text, old_index = label(before)
    new_text, new_index = label(after)
    return {
        "event_id": str(log["id"]),
        "board_id": settings.monday_board_id,
        "item_id": int(data.get("pulse_id") or data["item_id"]),
        "event": log["event"],
        "event_at_utc": timestamp,
        "created_at_raw": str(log.get("created_at", "")),
        "status_from_text": old_text,
        "status_to_text": new_text,
        "status_from_index": old_index,
        "status_to_index": new_index,
        "column_id": data["column_id"],
        "column_title": data.get("column_title"),
        "group_id": data.get("group_id"),
        "raw_data": log,
        "timestamp_source": source,
        "ingested_at": at,
    }


def extract_activities(client, settings, at, watermark=None):
    """Bound windows below the API's 10k log ceiling; split saturated windows.

    Incremental traverses reverse chronology until watermark-overlap and reads
    one additional page. Pagination uses native created_at, not changed_at.
    Watermark is ingestion start time and is never advanced here.
    """
    floor = parse_timestamp(settings.backfill_from)
    cutoff = None
    if watermark:
        cutoff = min(watermark, at - timedelta(hours=settings.run_window_hours)) - timedelta(
            minutes=settings.overlap_minutes
        )
    result = {}

    def window(start, end):
        page = 1
        local = []
        safety_page = None
        signatures = set()
        while True:
            logs = client.activity_page(page, iso(start), iso(end))
            if not logs:
                break
            signature = tuple(str(v["id"]) for v in logs)
            if signature in signatures:
                raise ValueError("Página de activity_logs repetida; watermark preservado")
            signatures.add(signature)
            for log in logs:
                parsed = parse_activity(log, settings, at)
                if parsed:
                    if parsed["event_at_utc"] > at:
                        raise ValueError(
                            "Evento com timestamp de negócio posterior ao corte; watermark preservado"
                        )
                    local.append(parsed)
            if cutoff and any(parse_timestamp(v["created_at"]) < cutoff for v in logs):
                if safety_page is None:
                    safety_page = page + 1
            if safety_page is not None and page >= safety_page:
                break
            if len(logs) < settings.monday_log_page_size:
                break
            if page * settings.monday_log_page_size >= 10000:
                if (end - start).total_seconds() <= 1:
                    raise ValueError("Mais de 10 mil logs em 1 segundo; extração não é completa")
                midpoint = start + (end - start) / 2
                return window(midpoint, end) + window(start, midpoint)
            page += 1
        return local

    end = at
    while end > floor:
        start = max(floor, end - timedelta(days=settings.activity_window_days))
        rows = window(start, end)
        result.update({r["event_id"]: r for r in rows})
        emit(
            "activity_window",
            start=iso(start),
            end=iso(end),
            events=len(rows),
            pages_read=client.pages_logs,
        )
        if cutoff and start < cutoff:
            break
        end = start
    return list(result.values())
