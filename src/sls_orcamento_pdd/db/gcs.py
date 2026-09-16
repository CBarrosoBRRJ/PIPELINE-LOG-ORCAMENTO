"""Generation-conditional GCS objects. Locks never expire automatically.

A killed writer leaves a lock: operators must stop its Cloud Run execution before
removing that exact generation. Automatic lease expiry would permit stale writers.
"""

import json
import os
import uuid
from contextlib import contextmanager

from google.api_core.exceptions import NotFound, PreconditionFailed

from ..utils.time import utcnow
from .checkpoint import canonical_json


class ObjectStore:
    def __init__(self, settings, client=None):
        from google.cloud import storage

        self.bucket = (client or storage.Client(project=settings.bq_project)).bucket(
            settings.gcs_bucket
        )
        self.prefix = settings.gcs_prefix
        self.depth = 0

    def path(self, name):
        return f"{self.prefix}/{name}"

    def get(self, name):
        blob = self.bucket.get_blob(self.path(name))
        if blob is None:
            return None, 0
        return blob.download_as_bytes(if_generation_match=int(blob.generation)), int(
            blob.generation
        )

    def put(self, name, content, generation=0, content_type="application/octet-stream"):
        blob = self.bucket.blob(self.path(name))
        blob.upload_from_string(content, content_type=content_type, if_generation_match=generation)
        return int(blob.generation)

    def put_json(self, name, data, generation=0):
        return self.put(name, canonical_json(data), generation, "application/json")

    def uri(self, name):
        return f"gs://{self.bucket.name}/{self.path(name)}"

    @contextmanager
    def lock(self):
        if self.depth:
            self.depth += 1
            try:
                yield
            finally:
                self.depth -= 1
            return
        try:
            generation = self.put_json(
                "writer.lock",
                {
                    "owner": uuid.uuid4().hex,
                    "execution": os.environ.get("CLOUD_RUN_EXECUTION", "local"),
                    "created_at": utcnow(),
                },
            )
        except PreconditionFailed:
            raise RuntimeError("Já existe uma execução ativa para este board") from None
        self.depth = 1
        try:
            yield
        finally:
            self.depth = 0
            self.bucket.blob(self.path("writer.lock")).delete(if_generation_match=generation)

    def inspect_lock(self):
        value, generation = self.get("writer.lock")
        return {"generation": generation, "lock": json.loads(value) if value else None}

    def unlock(self, generation):
        if generation <= 0:
            raise ValueError("Informe a geração exata da trava após parar o executor")
        try:
            self.bucket.blob(self.path("writer.lock")).delete(if_generation_match=generation)
        except (NotFound, PreconditionFailed):
            raise RuntimeError(
                "Trava mudou ou não existe; nenhuma outra geração removida"
            ) from None
