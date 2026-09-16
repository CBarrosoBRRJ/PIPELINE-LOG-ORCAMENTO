from sls_orcamento_ppd.models.keys import surrogate_key, with_surrogates


def test_key_stable_across_drivers_and_source_id_preserved():
    assert surrogate_key("item", 123) == surrogate_key("item", "123")
    assert surrogate_key("person", 123) != surrogate_key("item", 123)
    source = {"item_id": 123, "board_id": 42, "current_status_id": "42:status_19:7"}
    dimension = with_surrogates("dim_item", source)
    fact = with_surrogates("fct_item_status_interval", {"item_id": 123, "board_id": 42})
    assert dimension["item_id"] == 123
    assert dimension["item_sk"] == fact["item_sk"]
    assert source == {"item_id": 123, "board_id": 42, "current_status_id": "42:status_19:7"}


def test_move_board_keeps_item_entity_identity():
    assert (
        with_surrogates("dim_item", {"item_id": 123, "board_id": 42})["item_sk"]
        == with_surrogates("dim_item", {"item_id": 123, "board_id": 43})["item_sk"]
    )
