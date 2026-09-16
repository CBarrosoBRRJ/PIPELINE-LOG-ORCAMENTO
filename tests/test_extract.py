import pytest
from conftest import at, raw_event

from sls_orcamento_ppd.services.extract import discover, extract_activities, parse_activity
from sls_orcamento_ppd.utils.time import event_timestamp, parse_timestamp


@pytest.mark.parametrize(
    "value",
    [
        "1767340800",
        "1767340800000",
        "1767340800000000",
        "17673408000000000",
        "1767340800000000000",
        "2026-01-02T08:00:00Z",
    ],
)
def test_timestamp_units(value):
    assert parse_timestamp(value) == at(8)


def test_changed_at_preferred_and_safe_native_fallback():
    assert event_timestamp(
        {"value": {"changed_at": "2026-01-02T09:00:00Z"}}, "17673408000000000"
    ) == (at(9), "changed_at")
    assert event_timestamp({"value": {"changed_at": "invalid"}}, "17673408000000000") == (
        at(8),
        "created_at_native",
    )
    with pytest.raises(ValueError):
        parse_timestamp("2026-01-02T08:00:00")
    with pytest.raises(ValueError):
        parse_timestamp("178900000000")


def test_mapping_accents_and_no_fabricated_client(settings, board):
    mapping, _, _ = discover(board, settings)
    assert mapping["intervenciencia"] == "inter_x"
    assert mapping["talento"] == "talent_x"
    assert mapping["cliente"] is None
    board["columns"].append({"id": "brand_y", "title": "Marca", "type": "text"})
    with pytest.raises(ValueError, match="ambíguo"):
        discover(board, settings)
    settings.business_columns_override = {"marca": "brand_y"}
    assert discover(board, settings)[0]["marca"] == "brand_y"


def test_incremental_reads_extra_boundary_page(settings):
    settings.monday_log_page_size = 1
    settings.run_window_hours = 1
    settings.overlap_minutes = 0

    class Client:
        pages_logs = 0

        def activity_page(self, page, start, end):
            self.pages_logs += 1
            return [raw_event(str(page), 13 - page)]

    c = Client()
    rows = extract_activities(c, settings, at(13), at(13))
    assert c.pages_logs == 3  # 12 == cutoff; 11 < cutoff; then safety page 10.
    assert len(rows) == 3


def test_repeated_page_aborts(settings):
    settings.monday_log_page_size = 1

    class Client:
        pages_logs = 0

        def activity_page(self, *args):
            return [raw_event()]

    with pytest.raises(ValueError, match="repetida"):
        extract_activities(Client(), settings, at())


def test_bad_status_event_cannot_be_silently_dropped(settings):
    log = raw_event()
    log["created_at"] = ""
    with pytest.raises(ValueError):
        parse_activity(log, settings, at())


def test_invalid_timestamp_does_not_expose_rejected_value():
    with pytest.raises(ValueError, match="valor omitido") as error:
        parse_timestamp("private-invalid-timestamp")
    assert "private-invalid-timestamp" not in str(error.value)
