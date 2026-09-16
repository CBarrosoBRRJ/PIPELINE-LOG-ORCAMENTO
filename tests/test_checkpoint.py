import gzip
from datetime import UTC, datetime, timedelta, timezone

from sls_orcamento_ppd.db.checkpoint import decode, encode, fingerprint


def test_fingerprint_is_content_based_across_timezones_row_order_and_gzip_headers():
    rows = [
        {"run_id": "one", "start_at": datetime(2026, 9, 11, tzinfo=UTC)},
        {"run_id": "two", "start_at": datetime(2026, 9, 12, tzinfo=UTC)},
    ]
    source = {"etl_run": rows}
    converted = {
        "etl_run": [
            {**r, "start_at": r["start_at"].astimezone(timezone(timedelta(hours=-3)))}
            for r in reversed(rows)
        ]
    }
    assert fingerprint(source) == fingerprint(converted)
    windows = bytearray(encode(source))
    linux = bytearray(windows)
    windows[9], linux[9] = 0, 3  # gzip OS header differs, records do not.
    assert windows != linux and gzip.decompress(windows) == gzip.decompress(linux)
    assert fingerprint(decode(windows)) == fingerprint(decode(linux)) == fingerprint(source)
    converted["etl_run"][0]["run_id"] = "changed"
    assert fingerprint(source) != fingerprint(converted)
