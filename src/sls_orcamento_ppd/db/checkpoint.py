"""Portable GCS state encoding and content fingerprints; no local persistence."""

import gzip
import hashlib
import json
from datetime import UTC, date, datetime

from ..models.schemas import DEFINITIONS


def canonical_json(data):
    return json.dumps(
        data,
        default=lambda v: v.isoformat(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()


def encode(data):
    return gzip.compress(canonical_json(data), mtime=0)


def decode(blob):
    data = json.loads(gzip.decompress(blob))
    for name, rows in data.items():
        fields = dict(f.split(":") for f in DEFINITIONS[name][1].split())
        for row in rows:
            for column, kind in fields.items():
                value = row.get(column)
                if value is not None and kind in {"time", "localtime", "date"}:
                    row[column] = (date if kind == "date" else datetime).fromisoformat(value)
    return data


def fingerprint(data):
    ordered = {}
    for name, rows in data.items():
        keys = DEFINITIONS[name][0].split(",")
        fields = dict(f.split(":") for f in DEFINITIONS[name][1].split())
        normalized = [
            {
                k: (
                    r.get(k).astimezone(UTC)
                    if fields[k] == "time" and r.get(k) is not None
                    else r.get(k)
                )
                for k in fields
            }
            for r in rows
        ]
        ordered[name] = sorted(normalized, key=lambda row: tuple(str(row[k]) for k in keys))
    # Compare content, never gzip envelopes (OS header/zlib can differ on Windows/Linux).
    return hashlib.sha256(canonical_json(ordered)).hexdigest()
