"""Pure transformations, independent of PostgreSQL/BigQuery.

Times are elapsed wall time, including weekends. Daily facts split at local
midnight (including DST), not at UTC midnight. Initial dwell is explicitly
inferred: an API retention window cannot prove the first lifetime status.
"""

import hashlib
from collections import defaultdict
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from ..models.contracts import validate_table
from .clean import clean_inputs
from .extract import ALIASES, norm, status_id


def key(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


def transform(events, snapshots, statuses, settings, at, active_ids):
    board_id = settings.monday_board_id
    validate_table("bronze_monday_activity_log_raw", events, board_id)
    # As-of input may contain multiple observations of the same local date.
    validate_table("bronze_monday_item_snapshot_raw", snapshots, board_id, unique=False)
    events, snapshots, statuses = clean_inputs(events, snapshots, statuses)
    validate_table("dim_status", statuses, board_id)
    zone = ZoneInfo(settings.preferred_timezone)
    result = {
        name: []
        for name in (
            "dim_status",
            "dim_item",
            "bridge_item_person",
            "silver_monday_status_event_stg",
            "fct_item_status_interval",
            "fct_item_status_daily",
            "fct_item_sla_summary",
            "data_quality_issue",
        )
    }
    dims = {s["status_id"]: dict(s) for s in statuses}
    terminal = {norm(v) for v in settings.final_status_labels}

    def ensure_status(index, label):
        sid = status_id(settings, index, label)
        if sid not in dims:
            dims[sid] = {
                "status_id": sid,
                "board_id": board_id,
                "status_label": label or "Sem status",
                "status_label_norm": norm(label or "Sem status"),
                "status_order": None,
                "status_column_id": settings.monday_status_column_id,
                "status_color": None,
                "is_terminal": norm(label) in terminal,
            }
        return sid

    def issue(item_id, code, detail):
        result["data_quality_issue"].append(
            {
                "issue_id": key(board_id, item_id, code),
                "board_id": board_id,
                "item_id": item_id,
                "code": code,
                "detail": detail,
                "detected_at": at,
            }
        )

    by_item = defaultdict(list)
    versions = defaultdict(list)
    for row in snapshots:
        if row["snapshot_at"] <= at:
            versions[row["item_id"]].append(row)
    for row in events:
        if row["event_at_utc"] <= at:
            by_item[row["item_id"]].append(row)
    for rows in versions.values():
        rows.sort(key=lambda s: s["snapshot_at"])
    daily = {}
    bridge = {}
    for item_id in sorted(set(versions) | set(by_item)):
        history = versions[item_id]
        ordered = sorted(
            by_item[item_id],
            key=lambda e: (
                e["event_at_utc"],
                Decimal(e["created_at_raw"]) if str(e["created_at_raw"]).isdigit() else 0,
                (0, int(e["event_id"])) if e["event_id"].isdigit() else (1, e["event_id"]),
            ),
        )
        latest = history[-1] if history else None
        if latest:
            current_sid = ensure_status(latest["status_index"], latest["status_text"])
        else:
            current_sid = ensure_status(
                ordered[-1]["status_to_index"], ordered[-1]["status_to_text"]
            )
            issue(
                item_id,
                "item_sem_snapshot",
                "Item nos logs, ausente dos snapshots; atributos desconhecidos",
            )
        result["dim_item"].append(
            {
                "item_id": item_id,
                "board_id": board_id,
                "item_name": latest["item_name"] if latest else f"Item {item_id}",
                "created_at": latest["created_at"] if latest else None,
                "updated_at": latest["updated_at"] if latest else None,
                "current_status_id": current_sid,
                "is_active": item_id in active_ids,
                "last_seen_at": latest["snapshot_at"] if latest else None,
            }
        )
        if dims[current_sid]["status_label"] == "Sem status":
            issue(item_id, "status_atual_vazio", "Fonte sem status; dimensão explícita Sem status")
        for version in history:
            for person in version["pessoas_json"] or []:
                if person["kind"] != "person":
                    continue
                row = {
                    "item_id": item_id,
                    "board_id": board_id,
                    "person_id": person["id"],
                    "role": person.get("role", person["source_column_id"]),
                    "source_column_id": person["source_column_id"],
                    "snapshot_date": version["snapshot_date"],
                }
                bridge[
                    (item_id, person["id"], person["source_column_id"], version["snapshot_date"])
                ] = row

        # (start timestamp, status, source event, quality). Consecutive no-op
        # events remain in Silver but don't restart an interval.
        transitions = []
        for e in ordered:
            sid = ensure_status(e["status_to_index"], e["status_to_text"])
            previous_sid = ensure_status(e["status_from_index"], e["status_from_text"])
            result["silver_monday_status_event_stg"].append(
                {
                    "event_id": e["event_id"],
                    "board_id": board_id,
                    "item_id": item_id,
                    "status_id": sid,
                    "status_from": e["status_from_text"],
                    "status_to": e["status_to_text"],
                    "event_at_utc": e["event_at_utc"],
                    "timestamp_source": e["timestamp_source"],
                }
            )
            if not transitions:
                created = latest["created_at"] if latest else None
                if created and created < e["event_at_utc"]:
                    transitions.append((created, previous_sid, None, "initial_inferred"))
                    issue(
                        item_id,
                        "historico_inicial_inferido",
                        "Primeiro previous_value aplicado desde criação; retenção pode ocultar transições",
                    )
            if transitions and transitions[-1][1] != previous_sid:
                issue(
                    item_id,
                    "cadeia_status_inconsistente",
                    "previous_value difere do último status observado",
                )
            if not transitions or transitions[-1][1] != sid:
                transitions.append((e["event_at_utc"], sid, e["event_id"], "observed"))
        if not ordered:
            start = latest["created_at"] or latest["snapshot_at"]
            transitions.append((start, current_sid, None, "no_history_inferred"))
            issue(
                item_id,
                "status_sem_movimento",
                "Sem transições disponíveis; início inferido da criação",
            )
        if latest and transitions[-1][1] != current_sid:
            # No invented transition timestamp. Snapshot/log disagreement is
            # diagnosed and current-status age left unknown in the summary.
            issue(
                item_id,
                "snapshot_status_divergente",
                "Snapshot atual difere do último log; idade atual desconhecida",
            )
        if item_id not in active_ids:
            issue(
                item_id,
                "item_fora_snapshot_atual",
                "Item fora da extração ativa; não participa da fila atual",
            )

        intervals = []
        for i, (start, sid, event_id, quality) in enumerate(transitions):
            next_transition = transitions[i + 1] if i + 1 < len(transitions) else None
            end = next_transition[0] if next_transition else at
            if end < start:
                raise ValueError(f"Intervalo negativo: item {item_id}")
            candidates = [v for v in history if v["snapshot_at"] <= start]
            attrs = candidates[-1] if candidates else (history[0] if history else {})
            attribute_source = (
                "as_of_start" if candidates else "earliest_available" if history else "unavailable"
            )
            interval = {
                "interval_id": key(board_id, item_id, event_id or "initial", sid),
                "board_id": board_id,
                "item_id": item_id,
                "status_id": sid,
                "status_from": dims[transitions[i - 1][1]]["status_label"] if i else None,
                "status_to": dims[sid]["status_label"],
                "status_start_utc": start,
                "status_end_utc": end,
                "duration_minutes": (end - start).total_seconds() / 60,
                "duration_hours": (end - start).total_seconds() / 3600,
                "is_open_interval": next_transition is None,
                "event_start_id": event_id,
                "event_end_id": next_transition[2] if next_transition else None,
                "item_name": attrs.get("item_name"),
                "pessoas_json": attrs.get("pessoas_json", []),
                "snapshot_date": attrs.get("snapshot_date"),
                "attribute_source": attribute_source,
                "history_quality": quality,
                "updated_at": at,
                **{k: attrs.get(k) for k in ALIASES},
            }
            intervals.append(interval)
            cursor = start
            while cursor < end:
                local_date = cursor.astimezone(zone).date()
                midnight = datetime.combine(
                    local_date + timedelta(days=1), time.min, zone
                ).astimezone(UTC)
                stop = min(end, midnight)
                daily_key = (local_date, item_id, sid)
                # Daily dimensions use latest snapshot observed by day's end.
                day_versions = [v for v in history if v["snapshot_at"] <= stop]
                day_attrs = day_versions[-1] if day_versions else attrs
                if daily_key not in daily:
                    daily[daily_key] = {
                        "board_id": board_id,
                        "dt": local_date,
                        "item_id": item_id,
                        "status_id": sid,
                        "minutes_in_status": 0,
                        "snapshot_date": day_attrs.get("snapshot_date"),
                        **{k: day_attrs.get(k) for k in ALIASES},
                    }
                daily[daily_key]["minutes_in_status"] += (stop - cursor).total_seconds() / 60
                cursor = stop
        result["fct_item_status_interval"].extend(intervals)
        last = intervals[-1]
        same_current = last["status_id"] == current_sid
        is_terminal = dims[current_sid]["is_terminal"]
        finished = (
            last["status_start_utc"]
            if same_current and is_terminal and last["event_start_id"] is not None
            else None
        )
        first = intervals[0]["status_start_utc"]
        initial_events = [
            e
            for e in ordered
            if norm(e["status_to_text"]) == norm(settings.initial_status_label)
            or dims[ensure_status(e["status_to_index"], e["status_to_text"])]["status_label_norm"]
            == norm(settings.initial_status_label)
        ]
        sla_start = initial_events[0]["event_at_utc"] if initial_events else None
        if sla_start is None:
            issue(
                item_id,
                "inicio_entrada_nao_comprovado",
                "Sem evento de entrada em Entrada no histórico disponível; SLA total desconhecido",
            )
        result["fct_item_sla_summary"].append(
            {
                "item_id": item_id,
                "board_id": board_id,
                "status_atual": dims[current_sid]["status_label"],
                "created_at": latest["created_at"] if latest else None,
                "first_status_at": first,
                "sla_start_utc": sla_start,
                "sla_start_quality": "observed_event" if sla_start else "unavailable",
                "finalizado_em": finished,
                "lead_time_total_min": (
                    ((finished or at) - sla_start).total_seconds() / 60
                    if sla_start is not None and (not is_terminal or finished is not None)
                    else None
                ),
                "sla_status_atual_min": last["duration_minutes"] if same_current else None,
                "open_interval": not is_terminal,
                "is_active": item_id in active_ids,
                "history_quality": intervals[0]["history_quality"],
                "atualizado_em": at,
            }
        )
    result["dim_status"] = list(dims.values())
    result["bridge_item_person"] = list(bridge.values())
    result["fct_item_status_daily"] = list(daily.values())
    # Multiple failures in the same chain produce a single stable issue.
    result["data_quality_issue"] = list(
        {r["issue_id"]: r for r in result["data_quality_issue"]}.values()
    )
    validate(result, len(active_ids))
    for name, rows in result.items():
        validate_table(name, rows, board_id)
    return result


def validate(result, expected_active):
    items = result["dim_item"]
    if sum(bool(i["is_active"]) for i in items) != expected_active:
        raise ValueError("Contagem de itens ativos divergente")
    if any(not i["current_status_id"] for i in items):
        raise ValueError("Item sem chave de status atual")
    totals, daily_totals, groups = defaultdict(float), defaultdict(float), defaultdict(list)
    for row in result["fct_item_status_interval"]:
        totals[row["item_id"]] += row["duration_minutes"]
        groups[row["item_id"]].append(row)
    for row in result["fct_item_status_daily"]:
        daily_totals[row["item_id"]] += row["minutes_in_status"]
    for item_id, intervals in groups.items():
        expected = (
            max(r["status_end_utc"] for r in intervals)
            - min(r["status_start_utc"] for r in intervals)
        ).total_seconds() / 60
        if (
            abs(expected - totals[item_id]) > 1e-5
            or abs(totals[item_id] - daily_totals[item_id]) > 1e-5
        ):
            raise ValueError(f"Duração não reconciliada: item {item_id}")
