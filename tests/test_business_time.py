from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from sls_orcamento_ppd.rules.business_time import BusinessCalendar

ZONE = ZoneInfo("America/Sao_Paulo")


def local(value):
    return datetime.fromisoformat(value).replace(tzinfo=ZONE)


@pytest.mark.parametrize(
    "start,end,expected",
    [
        ("2026-09-16T10:00", "2026-09-16T19:00", 8),
        ("2026-09-16T12:30", "2026-09-16T14:30", 1),
        ("2026-09-16T13:00", "2026-09-16T14:00", 0),
        ("2026-09-16T08:00", "2026-09-16T10:00", 0),
        ("2026-09-16T19:00", "2026-09-17T10:00", 0),
        ("2026-09-18T18:00", "2026-09-21T11:00", 2),
        ("2026-09-04T18:00", "2026-09-08T11:00", 2),  # Independence Monday.
        ("2026-04-02T18:00", "2026-04-06T11:00", 2),  # Good Friday.
        ("2026-11-20T10:00", "2026-11-20T19:00", 0),
        ("2023-11-20T10:00", "2023-11-20T19:00", 8),  # National since 2024.
        ("2026-02-17T10:00", "2026-02-17T19:00", 8),  # Carnival not BR PUBLIC.
        ("2026-06-04T10:00", "2026-06-04T19:00", 8),  # Corpus Christi optional.
        ("2026-12-31T18:00", "2027-01-04T11:00", 2),
        ("2027-01-01T10:00", "2027-01-01T19:00", 0),
        ("2026-09-16T12:00", "2026-09-16T12:00", 0),
    ],
)
def test_business_windows_and_automatic_holidays(start, end, expected):
    assert BusinessCalendar(str(ZONE)).hours(local(start), local(end)) == expected


def test_unknown_negative_timezone_and_extra_holiday():
    calendar = BusinessCalendar(str(ZONE), [date(2026, 9, 16)])
    assert calendar.hours(None, local("2026-09-16T19:00")) is None
    assert calendar.hours(local("2026-09-16T10:00"), local("2026-09-16T19:00")) == 0
    with pytest.raises(ValueError):
        calendar.hours(local("2026-09-16T19:00"), local("2026-09-16T10:00"))
    with pytest.raises(ValueError):
        calendar.hours(datetime(2026, 1, 1), datetime(2026, 1, 2))
    assert calendar.version != BusinessCalendar(str(ZONE)).version


def test_arithmetic_weeks_equal_independent_daily_overlap_over_years():
    calendar = BusinessCalendar(str(ZONE))
    start, end = local("2023-10-30T12:37"), local("2027-02-05T15:11")
    # Partitioning an interval into days must preserve its elapsed working hours.
    total = 0
    cursor = start
    while cursor < end:
        next_day = (cursor + timedelta(days=1)).replace(hour=0, minute=0)
        stop = min(next_day, end)
        total += calendar.hours(cursor, stop)
        cursor = stop
    assert calendar.hours(start, end) == pytest.approx(total)
    assert "2026-11-20" in calendar.snapshot()["national"]
