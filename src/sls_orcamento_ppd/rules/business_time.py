"""Elapsed working hours: Mon-Fri 10:00-13:00 and 14:00-19:00, local time.

Whole weeks are counted arithmetically; only partial boundary days and configured
holidays require individual calculation. Unknown starts remain unknown.
"""

import hashlib
import json
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import holidays as holiday_library

POLICY = "seg-sex 10:00-13:00 / 14:00-19:00"
WINDOWS = ((time(10), time(13)), (time(14), time(19)))


class BusinessCalendar:
    def __init__(self, timezone, holidays=()):
        self.zone = ZoneInfo(timezone)
        self.holidays = frozenset(holidays)
        self._national = holiday_library.country_holidays(
            "BR", categories=("public",), language="pt_BR"
        )
        self._years = set()
        self.version = (
            "work-v1:"
            + hashlib.sha256(
                json.dumps(
                    {
                        "timezone": timezone,
                        "policy": POLICY,
                        "national_calendar": "BR:PUBLIC",
                        "library": holiday_library.__version__,
                        "holidays": sorted(d.isoformat() for d in self.holidays),
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()[:16]
        )

    def hours(self, start, end):
        if start is None or end is None:
            return None
        if start.utcoffset() is None or end.utcoffset() is None:
            raise ValueError("Horas úteis: timestamps devem ter fuso")
        if end < start:
            raise ValueError("Horas úteis: fim anterior ao início")
        first, last = start.astimezone(self.zone).date(), end.astimezone(self.zone).date()
        for year in range(first.year, last.year + 1):
            if year not in self._years:
                # Trigger lazy population for every year, including interior years.
                _ = f"{year}-01-01" in self._national
                self._years.add(year)
        excluded = self.holidays | self._national.keys()

        def partial(day):
            if day.weekday() >= 5 or day in excluded:
                return 0.0
            seconds = 0.0
            for opening, closing in WINDOWS:
                left = max(
                    start.astimezone(UTC), datetime.combine(day, opening, self.zone).astimezone(UTC)
                )
                right = min(
                    end.astimezone(UTC), datetime.combine(day, closing, self.zone).astimezone(UTC)
                )
                seconds += max(0.0, (right - left).total_seconds())
            return seconds / 3600

        if first == last:
            return partial(first)
        interior = first + timedelta(days=1)
        days = (last - interior).days
        weeks, remainder = divmod(days, 7)
        weekdays = weeks * 5 + sum((interior.weekday() + n) % 7 < 5 for n in range(remainder))
        weekdays -= sum(interior <= d < last and d.weekday() < 5 for d in excluded)
        return partial(first) + partial(last) + weekdays * 8.0

    def snapshot(self):
        return {
            "version": self.version,
            "timezone": str(self.zone),
            "policy": POLICY,
            "provider": "python-holidays",
            "provider_version": holiday_library.__version__,
            "national": {d.isoformat(): name for d, name in sorted(self._national.items())},
            "additional": sorted(d.isoformat() for d in self.holidays),
        }
