from datetime import timedelta

from conftest import at, raw_event, raw_item

from sls_orcamento_ppd.services.extract import discover, parse_activity, snapshot
from sls_orcamento_ppd.services.transform import transform
from sls_orcamento_ppd.utils.time import parse_timestamp


def test_intervals_reconcile_and_local_midnight(settings, sample):
    result = transform(*sample, settings, at(), {123})
    rows = result["fct_item_status_interval"]
    assert [r["duration_minutes"] for r in rows] == [360, 240]
    assert rows[0]["history_quality"] == "initial_inferred"
    assert rows[1]["is_open_interval"]
    days = result["fct_item_status_daily"]
    assert sum(r["minutes_in_status"] for r in days) == 600
    assert sum(r["minutes_in_status"] for r in days if r["dt"].day == 1) == 60


def test_repeat_is_idempotent(settings, sample):
    assert transform(*sample, settings, at(), {123}) == transform(*sample, settings, at(), {123})


def test_open_interval_grows_without_new_event(settings, sample):
    first = transform(*sample, settings, at(), {123})
    later = transform(*sample, settings, at() + timedelta(hours=1), {123})
    assert (
        first["fct_item_status_interval"][-1]["interval_id"]
        == later["fct_item_status_interval"][-1]["interval_id"]
    )
    assert later["fct_item_status_interval"][-1]["duration_minutes"] == 300


def test_no_movement_and_blank_status_are_diagnosed(settings, board):
    mapping, statuses, labels = discover(board, settings)
    snap = snapshot(raw_item(7), mapping, labels, settings, at())
    result = transform([], [snap], statuses, settings, at(), {123})
    assert result["data_quality_issue"][0]["code"] == "status_sem_movimento"
    assert result["fct_item_status_interval"][0]["duration_minutes"] == 600
    snap = snapshot(raw_item(None), mapping, labels, settings, at())
    result = transform([], [snap], statuses, settings, at(), {123})
    assert any(q["code"] == "status_atual_vazio" for q in result["data_quality_issue"])


def test_reentry_and_terminal_reopening(settings, board):
    settings.final_status_labels = ["Encerrado"]
    mapping, statuses, labels = discover(board, settings)
    events = [
        parse_activity(raw_event("1", 8), settings, at()),
        parse_activity(raw_event("2", 9, 0, 8), settings, at()),
    ]
    snap = snapshot(raw_item(8), mapping, labels, settings, at())
    result = transform(events, [snap], statuses, settings, at(), {123})
    assert result["fct_item_sla_summary"][0]["finalizado_em"] == at(9)
    events.append(parse_activity(raw_event("3", 10, 8, 0), settings, at()))
    snap = snapshot(raw_item(0), mapping, labels, settings, at())
    result = transform(events, [snap], statuses, settings, at(), {123})
    assert result["fct_item_sla_summary"][0]["finalizado_em"] is None
    assert len(result["fct_item_status_interval"]) == 4


def test_noop_event_does_not_reset_clock(settings, sample):
    events, snaps, statuses = sample
    events.append(parse_activity(raw_event("2", 10, 0, 0), settings, at()))
    result = transform(events, snaps, statuses, settings, at(), {123})
    assert len(result["fct_item_status_interval"]) == 2
    assert len(result["silver_monday_status_event_stg"]) == 2


def test_asof_enrichment_keeps_historical_brand(settings, sample):
    events, snaps, statuses = sample
    old = {**snaps[0], "snapshot_at": at(1), "marca": "Antiga"}
    new = {**snaps[0], "snapshot_at": at(12), "marca": "Nova"}
    result = transform(events, [old, new], statuses, settings, at(), {123})
    assert result["fct_item_status_interval"][-1]["marca"] == "Antiga"
    assert result["fct_item_status_interval"][-1]["attribute_source"] == "as_of_start"


def test_missing_snapshot_and_divergence(settings, sample):
    events, snaps, statuses = sample
    result = transform(events, [], statuses, settings, at(), set())
    assert not result["dim_item"][0]["is_active"]
    assert result["fct_item_status_interval"][0]["attribute_source"] == "unavailable"
    snaps[0].update(status_index=7, status_text="Entrada")
    result = transform(events, snaps, statuses, settings, at(), {123})
    assert result["fct_item_sla_summary"][0]["sla_status_atual_min"] is None


def test_dst_split_is_not_assumed_24_hours(settings, board):
    mapping, statuses, labels = discover(board, settings)
    start = parse_timestamp("2018-11-03T03:00:00Z")
    end = parse_timestamp("2018-11-05T02:00:00Z")
    snap = snapshot(raw_item(7), mapping, labels, settings, end)
    snap["created_at"] = start
    result = transform([], [snap], statuses, settings, end, {123})
    assert [d["minutes_in_status"] for d in result["fct_item_status_daily"]] == [1440, 1380]


def test_same_microsecond_uses_native_order(settings, sample):
    events, snaps, statuses = sample
    e = parse_activity(raw_event("2", 8, 0, 8), settings, at())
    e["created_at_raw"] = str(int(events[0]["created_at_raw"]) + 1)
    snaps[0].update(status_index=8, status_text="Encerrado")
    result = transform([e, events[0]], snaps, statuses, settings, at(), {123})
    assert result["fct_item_status_interval"][-1]["event_start_id"] == "2"


def test_terminal_without_history_has_unknown_completion(settings, board):
    settings.final_status_labels = ["Encerrado"]
    mapping, statuses, labels = discover(board, settings)
    snap = snapshot(raw_item(8), mapping, labels, settings, at())
    result = transform([], [snap], statuses, settings, at(), {123})
    summary = result["fct_item_sla_summary"][0]
    assert summary["finalizado_em"] is None
    assert summary["lead_time_total_min"] is None
    assert not summary["open_interval"]


def test_new_status_automatically_discovered_and_measured(settings, board, sample):
    import json

    schema = json.loads(board["columns"][0]["settings_str"])
    schema["labels"]["20"] = "Negócio Fechado"
    board["columns"][0]["settings_str"] = json.dumps(schema)
    settings.final_status_labels = ["Negócio Fechado"]
    mapping, statuses, labels = discover(board, settings)
    events, _, _ = sample
    raw = raw_event("2", 10, 0, 8)
    data = json.loads(raw["data"])
    data["value"]["label"] = {"index": 20, "text": "Negócio Fechado"}
    raw["data"] = json.dumps(data)
    events.append(parse_activity(raw, settings, at()))
    snap = snapshot(raw_item(20), mapping, labels, settings, at())
    result = transform(events, [snap], statuses, settings, at(), {123})
    interval = result["fct_item_status_interval"][-1]
    assert interval["status_to"] == "Negócio Fechado"
    assert interval["duration_minutes"] == 120
    assert result["fct_item_sla_summary"][0]["finalizado_em"] == at(10)


def test_sla_starts_only_at_first_entrada_event(settings, board):
    mapping, statuses, labels = discover(board, settings)
    events = [
        parse_activity(raw_event("1", 4, 8, 7), settings, at()),
        parse_activity(raw_event("2", 8, 7, 0), settings, at()),
        parse_activity(raw_event("3", 9, 0, 7), settings, at()),
    ]
    snap = snapshot(raw_item(7), mapping, labels, settings, at())
    result = transform(events, [snap], statuses, settings, at(), {123})
    summary = result["fct_item_sla_summary"][0]
    assert summary["sla_start_utc"] == at(4)
    assert summary["lead_time_total_min"] == 480  # Re-entry does not restart the lifetime SLA.


def test_other_status_never_becomes_sla_start(settings, sample):
    result = transform(*sample, settings, at(), {123})
    summary = result["fct_item_sla_summary"][0]
    assert summary["sla_start_utc"] is None
    assert summary["lead_time_total_min"] is None
    assert any(q["code"] == "inicio_entrada_nao_comprovado" for q in result["data_quality_issue"])
