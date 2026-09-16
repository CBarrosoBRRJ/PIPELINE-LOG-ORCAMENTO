"""One public BigQuery table, immutable GCS state, recoverable atomic load jobs.

GCS control.json is a write-ahead journal. Pending jobs must settle before any
subsequent write. A deterministic load job ID bridges BQ and GCS crash recovery.
"""

import copy
import hashlib
import json
import uuid
from contextlib import contextmanager

from google.api_core.exceptions import Conflict, NotFound
from google.cloud import bigquery

from ..models.bq_consumption import FIELDS, REQUIRED, digest, project
from ..models.consumption import GOLD, PENDING, publication
from ..models.schemas import DEFINITIONS
from ..rules.cutoff import closed_day_cut
from ..services.gold import validate_gold
from ..services.state import watermark
from ..utils.logging import emit
from .checkpoint import canonical_json, decode, encode, fingerprint
from .gcs import ObjectStore
from .state_payload import merge_state, validate_state

BQ_TYPES = {
    "text": "STRING",
    "id": "INT64",
    "int": "INT64",
    "bool": "BOOL",
    "time": "TIMESTAMP",
    "localtime": "DATETIME",
    "date": "DATE",
    "num": "FLOAT64",
    "json": "JSON",
}


def public_schema():
    return [
        bigquery.SchemaField(
            column, BQ_TYPES[kind], mode="REQUIRED" if column in REQUIRED else "NULLABLE"
        )
        for column, kind in (f.split(":") for f in FIELDS.split())
    ]


def schema_signature(schema):
    # REST responses use legacy canonical names even if requests use GoogleSQL aliases.
    aliases = {"INTEGER": "INT64", "FLOAT": "FLOAT64", "BOOLEAN": "BOOL"}
    return [(f.name, aliases.get(f.field_type, f.field_type), f.mode) for f in schema]


def table_ddl(prefix, name="sla_orcamento"):
    fields = [
        f"`{f.name}` {f.field_type}" + (" NOT NULL" if f.mode == "REQUIRED" else "")
        for f in public_schema()
    ]
    return (
        f"CREATE TABLE IF NOT EXISTS `{prefix}.{name}` (\n  "
        + ",\n  ".join(fields)
        + "\n)\nCLUSTER BY board_id, item_id, status_id"
    )


class BigQueryStore:
    def __init__(self, settings, *, client=None, objects=None):
        if not settings.bq_project or not settings.gcs_bucket:
            raise ValueError(
                "Configure BQ_PROJECT e GCS_BUCKET; autenticação usa ADC/service account"
            )
        if settings.bq_keyfile:
            raise ValueError(
                "BQ_KEYFILE descontinuado; use ADC local ou service account do Cloud Run"
            )
        self.settings = settings
        self.client = client or bigquery.Client(
            project=settings.bq_project, location=settings.bq_location
        )
        self.objects = objects or ObjectStore(settings)
        self.table_id = f"{settings.bq_project}.{settings.bq_dataset}.{settings.bq_table}"
        self.identity = {
            "format": 1,
            "pipeline": settings.pipeline_name,
            "table": self.table_id,
            "location": settings.bq_location,
            "timezone": settings.preferred_timezone,
        }
        self._data = None
        self._state_key = None

    @contextmanager
    def lock(self):
        outer = not self.objects.depth
        with self.objects.lock():
            if outer:
                self._state_key = None
            yield

    def _control(self):
        raw, generation = self.objects.get("control.json")
        if raw is None:
            raise RuntimeError("Estado GCS ausente; execute init-db ou migração explícita")
        value = json.loads(raw)
        if value.get("identity") != self.identity:
            raise RuntimeError("Estado pertence a outro destino/pipeline/configuração")
        return value, generation

    def _save_control(self, control, generation):
        return self.objects.put_json("control.json", control, generation)

    def _read_state(self, descriptor):
        if self._state_key == descriptor["state"]:
            return self._data
        # Cache only within one locked operation, avoiding repeated history downloads.
        raw, _ = self.objects.get(descriptor["state"])
        if raw is None or hashlib.sha256(raw).hexdigest() != descriptor["sha256"]:
            raise RuntimeError(
                "Checkpoint GCS ausente/corrompido; restaure a geração correspondente"
            )
        self._data = decode(raw)
        validate_state(self._data, self.settings.monday_board_id)
        self._state_key = descriptor["state"]
        return self._data

    def _stage_state(self, data, gold_hash):
        version = uuid.uuid4().hex
        path = f"generations/{version}/state.json.gz"
        raw = encode(data)
        self.objects.put(path, raw)
        saved, _ = self.objects.get(path)
        if saved != raw:
            raise RuntimeError("Checkpoint GCS não reconciliado após upload")
        return {
            "version": version,
            "state": path,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "gold_hash": gold_hash,
            "publication": None,
        }

    def initialize(self):
        with self.lock():
            dataset = self.client.get_dataset(
                f"{self.settings.bq_project}.{self.settings.bq_dataset}"
            )
            if dataset.location.upper() != self.settings.bq_location.upper():
                raise ValueError("Localização do dataset difere de BQ_LOCATION")
            raw, _ = self.objects.get("control.json")
            if raw is None:
                try:
                    self.client.get_table(self.table_id)
                except NotFound:
                    pass
                else:
                    raise RuntimeError(
                        "Tabela existente sem checkpoint; restaure o estado antes de publicar"
                    )
                data = {name: [] for name in DEFINITIONS}
                active = self._stage_state(data, None)
                self._save_control(
                    {"identity": self.identity, "active": active, "pending": None}, 0
                )
            self._recover()
            control, _ = self._control()
            self._read_state(control["active"])
            self.verify_publication(control["active"])

    def _recover(self):
        control, generation = self._control()
        pending = control.get("pending")
        if pending is None:
            return
        candidate = pending["candidate"]
        self._read_state(candidate)
        artifact, _ = self.objects.get(pending["artifact"])
        if artifact is None or hashlib.sha256(artifact).hexdigest() != pending["artifact_sha256"]:
            raise RuntimeError("Artefato de publicação ausente/corrompido; recuperação bloqueada")
        try:
            job = self.client.get_job(pending["job_id"], location=self.settings.bq_location)
        except NotFound:
            config = bigquery.LoadJobConfig(
                schema=public_schema(),
                source_format="NEWLINE_DELIMITED_JSON",
                write_disposition="WRITE_TRUNCATE",
                create_disposition="CREATE_IF_NEEDED",
                clustering_fields=["board_id", "item_id", "status_id"],
                max_bad_records=0,
                ignore_unknown_values=False,
            )
            try:
                job = self.client.load_table_from_uri(
                    self.objects.uri(pending["artifact"]),
                    self.table_id,
                    job_id=pending["job_id"],
                    location=self.settings.bq_location,
                    job_config=config,
                )
            except Conflict:
                job = self.client.get_job(pending["job_id"], location=self.settings.bq_location)
        if (
            str(job.destination) != self.table_id
            or job.source_uris != [self.objects.uri(pending["artifact"])]
            or job.write_disposition != "WRITE_TRUNCATE"
        ):
            raise RuntimeError("Job BigQuery incompatível com recibo; recuperação bloqueada")
        try:
            job.result(timeout=self.settings.bq_job_timeout_seconds)
        except Exception:
            # Unknown outcome retains the journal. Only terminal failure can abandon it.
            job = self.client.get_job(pending["job_id"], location=self.settings.bq_location)
            if job.state == "DONE" and job.error_result:
                control["pending"] = None
                self._save_control(control, generation)
                raise RuntimeError(
                    "Carga BigQuery falhou; publicação anterior preservada"
                ) from None
            raise RuntimeError(
                "Resultado BigQuery pendente; recibo preservado para recuperação"
            ) from None
        self.verify_publication(candidate)
        control.update(active=candidate, pending=None)
        self._save_control(control, generation)
        emit(
            "bq_publication_confirmed",
            table=self.settings.bq_table,
            rows=pending["rows"],
            job_id=pending["job_id"],
        )

    def verify_publication(self, descriptor=None):
        descriptor = descriptor or self._control()[0]["active"]
        if descriptor["gold_hash"] is None:
            try:
                self.client.get_table(self.table_id)
            except NotFound:
                return
            raise RuntimeError("Tabela sem recibo confirmado; publicação bloqueada")
        table = self.client.get_table(self.table_id)
        actual_schema = schema_signature(table.schema)
        expected_schema = schema_signature(public_schema())
        if actual_schema != expected_schema:
            raise RuntimeError("Schema BigQuery incompatível com contrato público")
        actual = [dict(row) for row in self.client.list_rows(table)]
        if digest(actual) != descriptor["gold_hash"]:
            raise RuntimeError("Consumo alterado fora do pipeline: BigQuery diverge do checkpoint")

    def read_many(self, names, board_id=None):
        with self.lock():
            self._recover()
            control, _ = self._control()
            data = self._read_state(control["active"])
            if GOLD in names:
                self.verify_publication(control["active"])
            result = {}
            for name in names:
                rows = (
                    publication(data, self.settings.preferred_timezone)[PENDING]
                    if name == PENDING
                    else data[name]
                )
                result[name] = copy.deepcopy(
                    [r for r in rows if board_id is None or r.get("board_id", board_id) == board_id]
                )
            return result

    def read(self, table, board_id=None):
        return self.read_many([table], board_id)[table]

    def commit(self, payload, board_id, *, reviewed=False):
        if board_id != self.settings.monday_board_id:
            raise ValueError("Um destino dedicado aceita somente o quadro configurado")
        with self.lock():
            self._recover()
            control, generation = self._control()
            old = self._read_state(control["active"])
            data = merge_state(old, payload, board_id, reviewed=reviewed)
            publish = GOLD in payload
            if publish:
                previous = watermark(data["etl_watermark"], self.settings.pipeline_name)
                validate_gold(
                    data,
                    cutoff=closed_day_cut(
                        previous["last_run_utc"], self.settings.preferred_timezone
                    )
                    if previous
                    else None,
                )
                self.verify_publication(control["active"])
            projected = project(data, self.settings) if publish else None
            gold_hash = digest(projected[GOLD]) if publish else control["active"]["gold_hash"]
            candidate = self._stage_state(data, gold_hash)
            if not publish:
                candidate["publication"] = control["active"].get("publication")
                control["active"] = candidate
                self._save_control(control, generation)
                return
            folder = f"generations/{candidate['version']}"
            artifact = folder + "/sla_orcamento.ndjson"
            raw = b"\n".join(canonical_json(row) for row in projected[GOLD]) + b"\n"
            self.objects.put(artifact, raw, content_type="application/x-ndjson")
            self.objects.put_json(folder + "/pendencias_projeto.json", projected[PENDING])
            self.objects.put_json(folder + "/calendario.json", projected["calendar"])
            candidate["publication"] = {
                "artifact": artifact,
                "calendar": folder + "/calendario.json",
                "pending_projects": folder + "/pendencias_projeto.json",
                "job_id": "sla_" + candidate["version"],
            }
            control["pending"] = {
                "candidate": candidate,
                "artifact": artifact,
                "artifact_sha256": hashlib.sha256(raw).hexdigest(),
                "job_id": "sla_" + candidate["version"],
                "rows": len(projected[GOLD]),
            }
            self._save_control(control, generation)
            self._recover()

    def claim_daily(self, row):
        with self.lock():
            if any(r["run_id"] == row["run_id"] for r in self.read("etl_run")):
                return False
            self.commit({"etl_run": [row]}, self.settings.monday_board_id)
            return True

    def import_state(self, data):
        self.initialize()
        with self.lock():
            current = self.read_many(DEFINITIONS)
            if any(current.values()):
                raise RuntimeError("Migração aceita somente estado GCP vazio")
            validate_state(data, self.settings.monday_board_id)
            self.commit(data, self.settings.monday_board_id, reviewed=True)
            if fingerprint(self.read_many(DEFINITIONS)) != fingerprint(data):
                raise RuntimeError("Migração não reconciliada")
        return {"table": self.table_id, "state_reconciled": True, "gold_rows": len(data[GOLD])}

    def check_connection(self):
        with self.lock():
            control, _ = self._control()
            self.verify_publication(control["active"])
            return {
                "target": self.table_id,
                "location": self.settings.bq_location,
                "published": control["active"]["gold_hash"] is not None,
                "pending": bool(control["pending"]),
            }

    def write_artifact(self, name, data):
        path = f"reports/{uuid.uuid4().hex}/{name}.json"
        self.objects.put_json(path, data)
        return self.objects.uri(path)

    def backup(self):
        with self.lock():
            self._recover()
            control, _ = self._control()
            path = f"backups/{uuid.uuid4().hex}/control.json"
            self.objects.put_json(path, control)
            return self.objects.uri(path)


def export_postgres(settings):
    """Explicit read-only source migration. Never drops or rewrites PostgreSQL."""
    from ..migration.readers import postgres_snapshot

    target = BigQueryStore(settings)
    with postgres_snapshot(settings) as data:
        result = target.import_state(data)
    emit("gcp_migration_verified", **result)
