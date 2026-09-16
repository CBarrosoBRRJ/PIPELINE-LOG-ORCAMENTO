import copy

import pytest
from conftest import at

from sls_orcamento_ppd.models.contracts import prepare_payload, validate_table
from sls_orcamento_ppd.services.transform import transform


def test_normalization_preserves_bronze_and_unknown_sla(settings, sample):
    sample[1][0]["marca"] = "  Marca\u00a0  A\n"
    sample[1][0]["cliente"] = " \t "
    sample[1][0]["talento"] = "N/A"  # No invented semantic mapping.
    sample[0][0]["status_to_text"] = "  Elabora\u00e7a\u0303o  "
    original = copy.deepcopy(sample)
    result = transform(*sample, settings, at(), {123})
    assert sample == original
    interval = result["fct_item_status_interval"][-1]
    assert interval["marca"] == "Marca A"
    assert interval["cliente"] is None
    assert interval["talento"] == "N/A"
    assert result["fct_item_sla_summary"][0]["lead_time_total_min"] is None


@pytest.mark.parametrize("invalid", [None, 0, -3, "123", True])
def test_bad_source_identity_blocked_before_transform(settings, sample, invalid):
    sample[0][0]["item_id"] = invalid
    with pytest.raises(ValueError, match="item_id"):
        transform(*sample, settings, at(), {123})


def test_naive_time_wrong_board_and_duplicate_event_blocked(settings, sample):
    events = copy.deepcopy(sample[0])
    events[0]["event_at_utc"] = at().replace(tzinfo=None)
    with pytest.raises(ValueError, match="event_at_utc"):
        transform(events, sample[1], sample[2], settings, at(), {123})
    with pytest.raises(ValueError, match="escopo"):
        validate_table("bronze_monday_activity_log_raw", sample[0], 99)
    with pytest.raises(ValueError, match="duplicada"):
        validate_table("bronze_monday_activity_log_raw", sample[0] * 2, 42)


@pytest.mark.parametrize("duration", [-1, float("nan"), float("inf"), 12345])
def test_bad_duration_blocked_before_publication(settings, sample, duration):
    result = transform(*sample, settings, at(), {123})
    result["fct_item_status_interval"][0]["duration_minutes"] = duration
    with pytest.raises(ValueError, match="duration_minutes"):
        prepare_payload(result, 42)


def test_sk_mismatch_and_fabricated_total_are_rejected(settings, sample):
    result = prepare_payload(transform(*sample, settings, at(), {123}), 42)
    broken = copy.deepcopy(result)
    broken["dim_item"][0]["item_sk"] = "wrong-secret-value"
    with pytest.raises(ValueError, match="item_sk") as error:
        prepare_payload(broken, 42)
    assert "wrong-secret-value" not in str(error.value)
    result["fct_item_sla_summary"][0]["lead_time_total_min"] = 0
    with pytest.raises(ValueError, match="Entrada"):
        prepare_payload(result, 42)


def test_missing_optional_fields_are_accepted_but_required_blank_is_not(settings, sample):
    result = transform(*sample, settings, at(), {123})
    prepare_payload(result, 42)
    result["dim_item"][0]["item_name"] = "  "
    with pytest.raises(ValueError, match="vazio"):
        prepare_payload(result, 42)
