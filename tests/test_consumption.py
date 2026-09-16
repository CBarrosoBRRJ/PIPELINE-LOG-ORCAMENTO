import copy

from test_gold import build

from sls_orcamento_ppd.models.consumption import (
    GOLD,
    PENDING,
    pending_projects,
    public_gold,
    publication,
)


def complete_data(settings, board, sample):
    data = build(settings, board, sample)
    data["bronze_monday_item_snapshot_raw"] = sample[1]
    data["bronze_monday_board_schema_raw"] = []
    return data


def test_consumer_masks_estimates_but_keeps_observed_passages_and_ids(settings, board, sample):
    data = complete_data(settings, board, sample)
    before = copy.deepcopy(data)
    rows = public_gold(data[GOLD])
    assert rows[0]["entrada_status_local"] is None
    assert rows[0]["duracao_horas"] is None
    assert rows[0]["saida_status_local"] == data[GOLD][0]["saida_status_local"]
    assert rows[1]["duracao_horas"] == data[GOLD][1]["duracao_horas"]
    assert [r["interval_id"] for r in rows] == [r["interval_id"] for r in data[GOLD]]
    assert [r["ordem_etapa"] for r in rows] == [1, 2]
    assert data == before


def test_pending_row_distinguishes_warning_from_whole_project_exclusion(settings, board, sample):
    data = complete_data(settings, board, sample)
    result = publication(data)
    assert len(result[GOLD]) == 2
    assert len(result[PENDING]) == 1
    row = result[PENDING][0]
    assert not row["excluido_da_analise"]
    assert "historico_inicial_nao_comprovado" in row["codigos"]
    assert row["item_id"] == 123
    assert "Não inventar datas" in row["como_corrigir"]
    sample[1][0]["talento"] = "Squad de Talentos"
    blocked = publication(complete_data(settings, board, sample))
    assert blocked[GOLD] == []
    assert blocked[PENDING][0]["excluido_da_analise"]
    assert blocked[PENDING][0]["talento_original"] == "Squad de Talentos"
    sample[1][0]["talento"] = "Pessoa individual"
    fixed = publication(complete_data(settings, board, sample))
    assert len(fixed[GOLD]) == 2
    assert "talento_squad" not in fixed[PENDING][0]["codigos"]


def test_responsible_warning_disappears_when_monday_assignment_is_resolved(settings, board, sample):
    data = complete_data(settings, board, sample)
    assert "responsavel_nome_indisponivel" in pending_projects(data)[0]["codigos"]
    raw = next(v for v in sample[1][0]["raw_data"]["column_values"] if v["id"] == "owner_x")
    raw["text"] = "Responsável confirmado"
    fixed = pending_projects(complete_data(settings, board, sample))[0]
    assert "responsavel_" not in fixed["codigos"]
    assert "historico_inicial_nao_comprovado" in fixed["codigos"]
