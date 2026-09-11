"""Private, durable executor state. Nothing here creates PostgreSQL tables."""

import gzip
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, date, datetime

from ..models.schemas import DEFINITIONS


def encode(data):
    return gzip.compress(
        json.dumps(
            data,
            default=lambda v: v.isoformat(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode(),
        mtime=0,
    )


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
    return hashlib.sha256(encode(ordered)).hexdigest()


class Checkpoint:
    def __init__(self, path):
        self.path = path

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=30)
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS checkpoint "
            "(slot TEXT PRIMARY KEY, generation TEXT NOT NULL, digest TEXT NOT NULL, data BLOB NOT NULL)"
        )
        return conn

    def stage(self, generation, data):
        blob = encode(data)
        digest = hashlib.sha256(blob).hexdigest()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO checkpoint VALUES ('pending',?,?,?)",
                (generation, digest, blob),
            )
        # Read from disk and verify before any PostgreSQL publication/drop.
        self.load(generation)

    def load(self, generation):
        if not self.path.exists():
            raise RuntimeError(
                "Checkpoint ausente: restaure o volume runtime; publicação bloqueada"
            )
        with closing(sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True)) as conn:
            row = conn.execute(
                "SELECT digest,data FROM checkpoint WHERE generation=?", (generation,)
            ).fetchone()
        if row is None or hashlib.sha256(row[1]).hexdigest() != row[0]:
            raise RuntimeError("Checkpoint incompatível/corrompido; restaure o par banco + runtime")
        return decode(row[1])

    def promote(self, generation):
        with closing(self._connect()) as conn, conn:
            pending = conn.execute(
                "SELECT generation,digest,data FROM checkpoint WHERE slot='pending'"
            ).fetchone()
            if pending and pending[0] == generation:
                conn.execute("DELETE FROM checkpoint WHERE slot='previous'")
                conn.execute("UPDATE checkpoint SET slot='previous' WHERE slot='active'")
                conn.execute("UPDATE checkpoint SET slot='active' WHERE slot='pending'")

    def backup(self, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as source, closing(sqlite3.connect(destination)) as target:
            source.backup(target)
