import copy
from datetime import timedelta

import pytest
from conftest import at, raw_event

from sls_orcamento_ppd.rules.cutoff import closed_day_cut
from sls_orcamento_ppd.services.extract import discover, parse_activity
from sls_orcamento_ppd.services.gold import build_gold, validate_gold
from sls_orcamento_ppd.services.transform import transform


def test_local_midnight_is_exclusive_and_capture_is_not_backdated(settings, board, sample):
    events, snaps, statuses = sample
    # Entrada -> Elaboração exactly at midnight local. Belongs to next day.
    events[0] = parse_activity(raw_event(hour=3), settings, at())
    payload = transform(events, snaps, statuses, settings, at(), {123})
    original = copy.deepcopy(payload["fct_item_status_interval"])
    mapping, _, _ = discover(board, settings)
    cutoff = closed_day_cut(at(), settings.preferred_timezone)
    assert cutoff == at(3)
    build_gold(payload, snaps, board, mapping, [], [], settings, at(), cutoff=cutoff)
    rows = payload["gold_projeto_status"]
    assert len(rows) == 1
    row = rows[0]
    assert row["status_nome"] == row["status_atual_nome"] == "Entrada"
    assert row["duracao_horas"] == 1
    assert row["saida_status_utc"] is None and row["intervalo_aberto"]
    assert row["cadastro_referencia_utc"] == at()
    assert row["corte_local"].hour == 0
    assert row["eh_primeiro_registro"] and row["eh_ultimo_registro"]
    assert not row["elegivel_comparacao"]
    assert payload["fct_item_status_interval"] == original
    validate_gold(payload)


def test_closed_day_keeps_returns_and_drops_future_entrance(settings, board, sample):
    events, snaps, statuses = sample
    events.extend(
        [
            parse_activity(raw_event("2", 9, 0, 7), settings, at()),
            parse_activity(raw_event("3", 10, 7, 0), settings, at()),
        ]
    )
    payload = transform(events, snaps, statuses, settings, at(), {123})
    mapping, _, _ = discover(board, settings)
    build_gold(payload, snaps, board, mapping, [], [], settings, at(), cutoff=at(10))
    rows = payload["gold_projeto_status"]
    assert [r["eh_retorno"] for r in rows] == [False, False, True]
    assert [r["duracao_horas"] for r in rows] == [6, 1, 1]
    assert rows[-1]["status_atual_nome"] == "Entrada"
    assert rows[-1]["tempo_desde_entrada_horas"] == 1
    rows[-1]["duracao_minutos"] += 1
    with pytest.raises(ValueError):
        validate_gold(payload)


def test_projects_created_after_boundary_are_not_in_day(settings, board, sample):
    payload = transform(*sample, settings, at(), {123})
    mapping, _, _ = discover(board, settings)
    cut = at(1)
    build_gold(payload, sample[1], board, mapping, [], [], settings, at(), cutoff=cut)
    assert payload["gold_projeto_status"] == []
    validate_gold(payload, cutoff=cut)


def test_cut_remains_midnight_across_local_day(settings):
    assert closed_day_cut(at(9), settings.preferred_timezone) == at(3)
    assert closed_day_cut(at(23), settings.preferred_timezone) == at(3)
    assert closed_day_cut(at(2), settings.preferred_timezone) == at(3) - timedelta(days=1)
