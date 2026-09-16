import copy
import json

import pytest
from conftest import at, raw_event

from sls_orcamento_ppd.models.contracts import validate_table
from sls_orcamento_ppd.rules.identities import Catalog, source_key
from sls_orcamento_ppd.services.extract import discover, parse_activity
from sls_orcamento_ppd.services.gold import build_gold, validate_gold
from sls_orcamento_ppd.services.transform import transform


def build(settings, board, sample, catalog=None, persons=None):
    result = transform(*sample, settings, at(), {123})
    mapping, _, _ = discover(board, settings)
    build_gold(result, sample[1], board, mapping, catalog or [], persons or [], settings, at())
    return result


def test_return_open_exit_and_original_durations(settings, board, sample):
    events, snaps, _ = sample
    events.append(parse_activity(raw_event("2", 10, 0, 7), settings, at()))
    snaps[0].update(status_index=7, status_text="Entrada")
    result = build(settings, board, sample)
    rows = result["gold_projeto_status"]
    assert [r["status_nome"] for r in rows] == ["Entrada", "Elaboração", "Entrada"]
    assert [r["eh_retorno"] for r in rows] == [False, False, True]
    assert [r["ordem_etapa"] for r in rows] == [1, 2, 3]
    assert rows[0]["eh_primeiro_registro"] and rows[-1]["eh_ultimo_registro"]
    assert rows[-1]["saida_status_utc"] is None
    assert rows[-1]["duracao_horas"] == 2
    assert rows[-1]["entrada_status_local"].hour == 7
    assert rows[-1]["entrada_status_local"].tzinfo is None
    assert rows[1]["horas_observadas_encerradas"] == 2
    assert rows[0]["horas_observadas_encerradas"] is None
    assert sum(r["duracao_horas"] for r in rows) == sum(
        r["duration_hours"] for r in result["fct_item_status_interval"]
    )


@pytest.mark.parametrize(
    "talent,inter,reason",
    [
        ("Pessoa A", "Pessoa A", "talento_ambas_colunas"),
        ("Pessoa A, Pessoa B", None, "talento_multiplo"),
        (None, "Pessoa A; Pessoa B", "talento_multiplo"),
        (None, "Pessoa A\nPessoa B", "talento_multiplo"),
        (" SQUAD   de Talentos ", None, "talento_squad"),
        (None, "Manual do Mundo", "talento_nao_individual"),
        (None, "Bruno e Marrone", "talento_nao_individual"),
    ],
)
def test_exclusion_removes_whole_project_but_not_history(
    settings, board, sample, talent, inter, reason
):
    sample[1][0].update(talento=talent, intervenciencia=inter)
    source = copy.deepcopy(sample)
    result = build(settings, board, sample)
    assert not result["gold_projeto_status"]
    assert len(result["fct_item_status_interval"]) == 2
    assert len(result["dim_item"]) == 1
    issue = next(q for q in result["data_quality_issue"] if q["code"] == "gold_projeto_excluido")
    assert reason in json.loads(issue["detail"])["motivos"]
    assert source == sample


def test_structured_multiple_selection_and_correction(settings, board, sample):
    snap = sample[1][0]
    snap["talento"] = "Nome sem delimitador"
    snap["raw_data"]["column_values"].append({"id": "talent_x", "value": '{"ids":[1,2]}'})
    assert not build(settings, board, sample)["gold_projeto_status"]
    snap["raw_data"]["column_values"][-1]["value"] = '{"ids":[1]}'
    result = build(settings, board, sample)
    assert len(result["gold_projeto_status"]) == 2
    assert not any(q["code"] == "gold_projeto_excluido" for q in result["data_quality_issue"])


def test_noop_and_same_timestamp_keep_transform_order(settings, board, sample):
    events = sample[0]
    noop = parse_activity(raw_event("2", 8, 0, 0), settings, at())
    noop["created_at_raw"] = str(int(events[0]["created_at_raw"]) + 1)
    last = parse_activity(raw_event("3", 8, 0, 7), settings, at())
    last["created_at_raw"] = str(int(events[0]["created_at_raw"]) + 2)
    events.extend([last, noop])
    sample[1][0].update(status_index=7, status_text="Entrada")
    rows = build(settings, board, sample)["gold_projeto_status"]
    assert [r["status_nome"] for r in rows] == ["Entrada", "Elaboração", "Entrada"]
    assert rows[1]["duracao_horas"] == 0
    assert rows[-1]["eh_retorno"]


def test_catalog_review_preserves_identity_and_unknowns(settings, board, sample):
    sample[1][0].update(talento=None, intervenciencia=" Nome  Exemplo ", marca=None)
    initial = build(settings, board, sample)
    assert initial["gold_projeto_status"] == []
    assert initial["quarentena_projeto"][0]["motivos"] == ["talento_identidade_pendente"]
    catalog = initial["meta_entity_mapping"]
    catalog[0].update(
        review_status="approved",
        entity_kind="person",
        canonical_id="talento-123",
        canonical_name="Nome Exemplo",
        reviewed_by="data-steward",
    )
    reviewed = build(settings, board, sample, catalog)
    row = reviewed["gold_projeto_status"][0]
    assert row["talento_chave"] == "talento-123"
    assert row["talento_nome"] == "Nome Exemplo"
    assert row["versao_regras"] != initial["quarentena_projeto"][0]["versao_regras"]
    assert reviewed["quarentena_projeto"] == []
    assert reviewed["meta_entity_mapping"] == []  # Never overwrite reviewed records.
    assert row["entrada_comprovada_utc"] is None
    assert row["tempo_desde_entrada_horas"] is None
    assert source_key(" JoÃO  Silva ") == "joão silva"
    assert source_key("João") != source_key("Joao")


def test_bad_catalog_blocks_publication(settings, board, sample):
    result = build(settings, board, sample)
    row = result["meta_entity_mapping"][0]
    row["review_status"] = "approved"
    with pytest.raises(ValueError, match="aprovação"):
        Catalog([row], 42, at())
    row.update(
        canonical_id="same", canonical_name="A", entity_kind="organization", reviewed_by="reviewer"
    )
    conflicting = {**row, "source_key": "another", "source_text": "Another", "canonical_name": "B"}
    with pytest.raises(ValueError, match="conflitante"):
        Catalog([row, conflicting], 42, at())


def test_manual_brand_quarantine_and_source_correction_reinclude_history(settings, board, sample):
    initial = build(settings, board, sample)
    ids = {r["interval_id"] for r in initial["gold_projeto_status"]}
    catalog = initial["meta_entity_mapping"]
    brand = next(r for r in catalog if r["entity_type"] == "marca")
    brand.update(
        review_status="quarantined", reviewed_by="reviewer", review_reason="Grafia ambígua"
    )
    blocked = build(settings, board, sample, catalog)
    assert blocked["gold_projeto_status"] == []
    assert blocked["quarentena_projeto"][0]["motivos"] == ["marca_revisao_manual"]
    assert blocked["quarentena_projeto"][0]["marca_original"] == "Marca A"
    sample[1][0]["marca"] = "Marca Corrigida"
    fixed = build(settings, board, sample, catalog)
    assert {r["interval_id"] for r in fixed["gold_projeto_status"]} == ids
    assert fixed["quarentena_projeto"] == []
    assert brand["review_status"] == "quarantined"


def test_manual_quarantine_requires_reason_and_reviewer(settings, board, sample):
    result = build(settings, board, sample)
    row = result["meta_entity_mapping"][0]
    row["review_status"] = "quarantined"
    with pytest.raises(ValueError, match="quarentena manual"):
        Catalog([row], 42, at())


def test_multiple_owners_do_not_multiply_passages(settings, board, sample):
    sample[1][0]["pessoas_json"] *= 2
    sample[1][0]["pessoas_json"].append(
        {"id": "100", "kind": "person", "source_column_id": "owner_x"}
    )
    persons = [
        {"person_id": "99", "person_name": "Responsável A"},
        {"person_id": "100", "person_name": "Responsável B"},
    ]
    result = build(settings, board, sample, persons=persons)
    assert len(result["gold_projeto_status"]) == 2
    row = result["gold_projeto_status"][0]
    assert row["quantidade_responsaveis_orcamento"] == 2
    assert set(row["responsavel_orcamento"].split(" | ")) == {"Responsável A", "Responsável B"}


def test_validation_blocks_partial_project_or_invalid_duration(settings, board, sample):
    result = build(settings, board, sample)
    broken = copy.deepcopy(result)
    broken["gold_projeto_status"].pop()
    with pytest.raises(ValueError, match="conjunto"):
        validate_gold(broken)
    result["gold_projeto_status"][0]["duracao_horas"] = 0
    with pytest.raises(ValueError, match="duração|duracao"):
        validate_table("gold_projeto_status", result["gold_projeto_status"])


def test_latest_attributes_no_future_data_and_deterministic(settings, board, sample):
    future = {**sample[1][0], "snapshot_at": at(day=3), "talento": "Squad de Talentos"}
    sample[1].append(future)
    assert build(settings, board, sample) == build(settings, board, sample)
    assert len(build(settings, board, sample)["gold_projeto_status"]) == 2


def test_source_people_text_recovers_name_without_guessing_multiple_ids(settings, board, sample):
    snap = sample[1][0]
    raw = next(v for v in snap["raw_data"]["column_values"] if v["id"] == "owner_x")
    raw["text"] = "Responsável conhecido"
    single = build(settings, board, sample)["gold_projeto_status"][0]
    assert single["responsavel_orcamento"] == "Responsável conhecido"
    assert single["responsavel_situacao"] == "identificado"
    assert single["responsaveis_orcamento_json"][0]["nome_origem"] == "texto_snapshot_unica_pessoa"
    snap["pessoas_json"].append({"id": "100", "kind": "person", "source_column_id": "owner_x"})
    raw["text"] = "Responsável conhecido, Outra pessoa"
    multiple = build(settings, board, sample)["gold_projeto_status"][0]
    assert multiple["responsavel_orcamento"] == raw["text"]
    assert all(p["nome"] is None for p in multiple["responsaveis_orcamento_json"])
    assert multiple["responsavel_situacao"] == "texto_snapshot_sem_correspondencia_individual"


@pytest.mark.parametrize("source", ["snapshot_text", "catalog", "membership"])
def test_deleted_person_label_is_not_a_responsible_name(settings, board, sample, source):
    snap = sample[1][0]
    raw = next(v for v in snap["raw_data"]["column_values"] if v["id"] == "owner_x")
    raw["text"] = "Deleted on invitation cancelation" if source == "snapshot_text" else None
    persons = []
    if source == "catalog":
        persons = [{"person_id": "99", "person_name": "Deleted on invitation cancelation"}]
    if source == "membership":
        snap["pessoas_json"][0]["name"] = "  Deleted on invitation cancellation  "
    before = copy.deepcopy(snap)
    rows = build(settings, board, sample, persons=persons)["gold_projeto_status"]
    assert len(rows) == 2  # Missing responsible name does not discard a valid project.
    for row in rows:
        assert row["responsavel_orcamento"] is None
        assert row["responsavel_situacao"] == "nome_indisponivel"
        assert row["quantidade_responsaveis_orcamento"] == 1
        assert row["responsaveis_orcamento_json"][0]["id"] == "99"
        assert row["responsaveis_orcamento_json"][0]["nome"] is None
    assert snap == before  # Keep the original evidence.


def test_deleted_person_in_mixed_text_does_not_override_resolved_owner(settings, board, sample):
    snap = sample[1][0]
    raw = next(v for v in snap["raw_data"]["column_values"] if v["id"] == "owner_x")
    raw["text"] = "Responsável A, Deleted on invitation cancelation"
    snap["pessoas_json"].append({"id": "100", "kind": "person", "source_column_id": "owner_x"})
    row = build(
        settings, board, sample, persons=[{"person_id": "99", "person_name": "Responsável A"}]
    )["gold_projeto_status"][0]
    assert row["responsavel_orcamento"] == "Responsável A"
    assert row["quantidade_responsaveis_orcamento"] == 2
    assert sum(p["nome"] is None for p in row["responsaveis_orcamento_json"]) == 1
    assert row["responsavel_situacao"] == "nome_indisponivel"
