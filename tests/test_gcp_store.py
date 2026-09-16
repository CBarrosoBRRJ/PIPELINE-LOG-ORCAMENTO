"""Behavioral crash tests using SDK-compatible in-memory GCS/BQ doubles."""

import copy
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from conftest import FakeMonday, at, raw_event, raw_item
from google.api_core.exceptions import NotFound, PreconditionFailed
from google.cloud import bigquery

from sls_orcamento_ppd.db.bq import BigQueryStore, public_schema
from sls_orcamento_ppd.db.checkpoint import fingerprint
from sls_orcamento_ppd.db.gcs import ObjectStore
from sls_orcamento_ppd.models.bq_consumption import digest, project
from sls_orcamento_ppd.models.consumption import GOLD
from sls_orcamento_ppd.models.schemas import DEFINITIONS
from sls_orcamento_ppd.pipelines.runner import run


class MemoryBlob:
    def __init__(self, bucket, name):
        self.bucket, self.name = bucket, name
        self.generation = bucket.data.get(name, (None, 0))[1]

    def upload_from_string(self, value, *, content_type, if_generation_match):
        if self.bucket.data.get(self.name, (None, 0))[1] != if_generation_match:
            raise PreconditionFailed("generation")
        self.bucket.counter += 1
        self.generation = self.bucket.counter
        self.bucket.data[self.name] = (value, self.generation)

    def download_as_bytes(self, *, if_generation_match):
        raw, generation = self.bucket.data[self.name]
        if generation != if_generation_match:
            raise PreconditionFailed("generation")
        return raw

    def delete(self, *, if_generation_match):
        if self.bucket.data.get(self.name, (None, 0))[1] != if_generation_match:
            raise PreconditionFailed("generation")
        del self.bucket.data[self.name]


class MemoryBucket:
    name = "test-bucket"

    def __init__(self):
        self.data, self.counter = {}, 0

    def blob(self, name):
        return MemoryBlob(self, name)

    def get_blob(self, name):
        return self.blob(name) if name in self.data else None


class MemoryJob:
    def __init__(self, bq, uri, target, config):
        self.bq, self.destination, self.config = bq, target, config
        self.source_uris, self.write_disposition = [uri], config.write_disposition
        self.state, self.error_result = "RUNNING", None

    def result(self, timeout):
        if self.bq.fail:
            self.state, self.error_result = "DONE", {"reason": "invalid"}
            raise ValueError("simulated load failure with private values")
        if self.state != "DONE":
            path = self.source_uris[0].split("/", 3)[3]
            raw = self.bq.bucket.data[path][0]
            rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
            for row in rows:
                for field in self.config.schema:
                    if row[field.name] is not None and field.field_type in {
                        "TIMESTAMP",
                        "DATETIME",
                    }:
                        row[field.name] = datetime.fromisoformat(row[field.name])
            aliases = {"INT64": "INTEGER", "FLOAT64": "FLOAT", "BOOL": "BOOLEAN"}
            response_schema = [
                bigquery.SchemaField(f.name, aliases.get(f.field_type, f.field_type), mode=f.mode)
                for f in self.config.schema
            ]
            self.bq.tables[self.destination] = SimpleNamespace(schema=response_schema, rows=rows)
            self.state = "DONE"
        return self


class MemoryBQ:
    def __init__(self, bucket):
        self.bucket, self.tables, self.jobs = bucket, {}, {}
        self.fail, self.lost_ack = False, False

    def get_dataset(self, name):
        return SimpleNamespace(location="US")

    def get_table(self, name):
        if name not in self.tables:
            raise NotFound("table")
        return self.tables[name]

    def list_rows(self, table):
        return copy.deepcopy(table.rows)

    def get_job(self, job_id, *, location):
        if job_id not in self.jobs:
            raise NotFound("job")
        return self.jobs[job_id]

    def load_table_from_uri(self, uri, target, *, job_id, location, job_config):
        assert target.endswith(".sla_orcamento")
        job = self.jobs.setdefault(job_id, MemoryJob(self, uri, target, job_config))
        if self.lost_ack:
            job.result(1)
            self.lost_ack = False
            raise ConnectionError("lost job submission acknowledgement")
        return job


@pytest.fixture
def cloud(settings):
    cfg = settings.model_copy(
        update={"target_db": "bigquery", "bq_project": "unit-test", "gcs_bucket": "test-bucket"}
    )
    bucket = MemoryBucket()
    client = MemoryBQ(bucket)

    def new():
        objects = ObjectStore(cfg, client=SimpleNamespace(bucket=lambda name: bucket))
        return BigQueryStore(cfg, client=client, objects=objects)

    return cfg, client, new


def test_pipeline_one_table_incremental_daily_and_ephemeral_runtime(cloud, board):
    cfg, bq, new = cloud
    store = new()
    run(cfg, "backfill", client=FakeMonday(board), store=store, at=at())
    assert list(bq.tables) == [store.table_id]
    row = bq.tables[store.table_id].rows[0]
    assert row["item_id"] == 123
    assert row["entrada_status_utc"] is row["duracao_horas_uteis"] is None
    assert not cfg.runtime_dir.exists() or not list(cfg.runtime_dir.iterdir())
    next_day = at() + timedelta(days=1)
    report = run(cfg, client=FakeMonday(board), store=new(), at=next_day, scheduled_for=next_day)
    assert report["status"] == "success"
    assert report["new_events"] == 0
    client = FakeMonday(board, fail=True)
    assert (
        run(cfg, client=client, store=new(), at=next_day, scheduled_for=next_day)["status"]
        == "skipped"
    )
    assert client.pages_items == 0
    assert len(bq.tables) == 1
    assert len(new().read("bronze_monday_activity_log_raw")) == 1


def test_new_installation_requires_backfill_before_daily(cloud, board):
    cfg, bq, new = cloud
    client = FakeMonday(board)
    with pytest.raises(ValueError, match="backfill"):
        run(cfg, client=client, store=new(), at=at(), scheduled_for=at())
    assert client.pages_items == client.pages_logs == 0
    assert not bq.jobs
    assert new().read("etl_run") == []
    # Reusing the initialized, still-empty state is the normal bootstrap path.
    assert run(cfg, "backfill", client=client, store=new(), at=at())["status"] == "success"


def test_daily_failure_does_not_advance_watermark_or_repeat(cloud, board):
    cfg, _, new = cloud
    run(cfg, "backfill", client=FakeMonday(board), store=new(), at=at())
    before = new().read("etl_watermark")
    tomorrow = at() + timedelta(days=1)
    with pytest.raises(RuntimeError, match="simulada"):
        run(
            cfg,
            client=FakeMonday(board, fail=True),
            store=new(),
            at=tomorrow,
            scheduled_for=tomorrow,
        )
    assert new().read("etl_watermark") == before
    assert (
        run(cfg, client=FakeMonday(board), store=new(), at=tomorrow, scheduled_for=tomorrow)[
            "status"
        ]
        == "skipped"
    )


def test_two_process_locks_and_exact_generation_unlock(cloud):
    _, _, new = cloud
    first, second = new(), new()
    with first.lock():
        with pytest.raises(RuntimeError, match="ativa"), second.lock():
            pass
        generation = first.objects.inspect_lock()["generation"]
        with pytest.raises(RuntimeError, match="mudou"):
            second.objects.unlock(generation + 1)
    with second.lock():
        pass


def test_lost_bigquery_ack_recovers_same_job_without_duplicate_load(cloud, board):
    cfg, bq, new = cloud
    run(cfg, "backfill", client=FakeMonday(board), store=new(), at=at())
    bq.lost_ack = True
    tomorrow = at() + timedelta(days=1)
    report = run(cfg, client=FakeMonday(board), store=new(), at=tomorrow, scheduled_for=tomorrow)
    assert report["status"] == "success"
    assert len(bq.jobs) == 2
    assert new().read("etl_watermark")[0]["last_run_utc"] == tomorrow


def test_crash_after_bq_before_gcs_promotion_recovers(cloud, board, monkeypatch):
    cfg, bq, new = cloud
    store = new()
    run(cfg, "backfill", client=FakeMonday(board), store=store, at=at())
    original = store._save_control

    def crash(control, generation):
        if control["pending"] is None:
            raise OSError("crash before promotion")
        return original(control, generation)

    data = store.read_many(DEFINITIONS)
    monkeypatch.setattr(store, "_save_control", crash)
    with pytest.raises(OSError):
        store.commit(data, cfg.monday_board_id)
    count = len(bq.jobs)
    restarted = new()
    restarted.initialize()
    assert len(bq.jobs) == count
    assert fingerprint(restarted.read_many(DEFINITIONS)) == fingerprint(data)
    assert restarted._control()[0]["pending"] is None


def test_failed_load_preserves_previous_publication(cloud, board):
    cfg, bq, new = cloud
    run(cfg, "backfill", client=FakeMonday(board), store=new(), at=at())
    previous = copy.deepcopy(bq.tables)
    before = new().read("etl_watermark")
    bq.fail = True
    tomorrow = at() + timedelta(days=1)
    with pytest.raises(RuntimeError, match="BigQuery falhou"):
        run(cfg, client=FakeMonday(board), store=new(), at=tomorrow, scheduled_for=tomorrow)
    assert new().read("etl_watermark") == before
    assert bq.tables == previous
    assert new()._control()[0]["pending"] is None


def test_empty_gold_exclusion_and_reinclusion_preserve_bronze(cloud, board):
    cfg, bq, new = cloud

    class MutableMonday(FakeMonday):
        talent = None

        def item_pages(self):
            self.pages_items += 1
            item = raw_item()
            item["column_values"].append({"id": "talent_x", "text": self.talent, "value": None})
            yield [item]

    client = MutableMonday(board)
    run(cfg, "backfill", client=client, store=new(), at=at())
    ids = {r["interval_id"] for r in bq.tables[new().table_id].rows}
    client.talent = "Squad de Talentos"
    run(cfg, client=client, store=new(), at=at() + timedelta(hours=1))
    assert bq.tables[new().table_id].rows == []
    assert new().read("pendencias_projeto")[0]["excluido_da_analise"]
    assert new().read("bronze_monday_activity_log_raw")
    client.talent = "Pessoa individual"
    run(cfg, client=client, store=new(), at=at() + timedelta(hours=2))
    assert {r["interval_id"] for r in bq.tables[new().table_id].rows} == ids


def test_missing_checkpoint_foreign_target_and_external_edit_fail_closed(cloud, board):
    cfg, bq, new = cloud
    run(cfg, "backfill", client=FakeMonday(board), store=new(), at=at())
    store = new()
    bq.tables[store.table_id].rows[0]["marca_nome"] = "manual"
    with pytest.raises(RuntimeError, match="fora do pipeline"):
        store.read(GOLD)
    control, _ = store._control()
    del bq.bucket.data[store.objects.path(control["active"]["state"])]
    with pytest.raises(RuntimeError, match="ausente/corrompido"):
        new().read("etl_watermark")
    other = new()
    other.identity["table"] = "other.table"
    with pytest.raises(RuntimeError, match="outro destino"):
        other.initialize()


def test_existing_table_without_state_never_overwritten(cloud):
    _, bq, new = cloud
    store = new()
    bq.tables[store.table_id] = SimpleNamespace(schema=public_schema(), rows=[])
    with pytest.raises(RuntimeError, match="sem checkpoint"):
        store.initialize()
    assert not bq.jobs


def test_migration_and_replay_preserve_internal_identity(cloud, board):
    cfg, bq, new = cloud
    run(cfg, "backfill", client=FakeMonday(board), store=new(), at=at())
    data = new().read_many(DEFINITIONS)
    other_cfg = cfg.model_copy(update={"gcs_prefix": "migration"})
    bucket = MemoryBucket()
    target = BigQueryStore(
        other_cfg,
        client=MemoryBQ(bucket),
        objects=ObjectStore(other_cfg, client=SimpleNamespace(bucket=lambda n: bucket)),
    )
    assert target.import_state(data)["state_reconciled"]
    assert fingerprint(target.read_many(DEFINITIONS)) == fingerprint(data)
    assert digest(target.client.tables[target.table_id].rows) == digest(project(data, cfg)[GOLD])
    with pytest.raises(RuntimeError, match="vazio"):
        target.import_state(data)


def test_orphan_and_wrong_scope_block_before_any_load(cloud, board):
    cfg, bq, new = cloud
    run(cfg, "backfill", client=FakeMonday(board), store=new(), at=at())
    store = new()
    item = store.read("dim_item")[0]
    item["current_status_id"] = "missing"
    item.pop("current_status_sk")
    count = len(bq.jobs)
    with pytest.raises(ValueError, match="órfã"):
        store.commit({"dim_item": [item]}, cfg.monday_board_id)
    with pytest.raises(ValueError, match="dedicado"):
        store.commit({}, 43)
    assert len(bq.jobs) == count


def test_business_projection_returns_closed_and_final_status(cloud, board):
    cfg, bq, new = cloud

    # Jan 5/6 2026: Monday/Tuesday, timestamps explicitly converted from local time.
    class TimelineMonday(FakeMonday):
        def item_pages(self):
            yield [raw_item(status=8)]

        def activity_page(self, page, start, end):
            if page != 1:
                return []
            rows = []
            for event_id, day, utc_hour, before, after in (
                ("1", 5, 13, 7, 0),  # Mon 10h: Elaboração
                ("2", 5, 15, 0, 7),  # Mon 12h: Entrada comprovada
                ("3", 5, 19, 7, 0),  # Mon 16h: retorno Elaboração
                ("4", 6, 15, 0, 8),  # Tue 12h: Encerrado
            ):
                event = raw_event(event_id, before=before, after=after)
                event["created_at"] = str(int(at(utc_hour, day).timestamp()) * 10_000_000)
                rows.append(event)
            return rows

    run(cfg, "backfill", client=TimelineMonday(board), store=new(), at=at(9, 7))
    rows = sorted(bq.tables[new().table_id].rows, key=lambda r: r["ordem_etapa"])
    assert [r["duracao_horas_uteis"] for r in rows] == [None, 2, 3, 5, 6]
    assert [r["horas_uteis_observadas_encerradas"] for r in rows] == [None, 2, 3, 5, None]
    assert rows[3]["eh_retorno"]
    assert all(r["tempo_desde_entrada_horas_uteis"] == 8 for r in rows)
    assert rows[-1]["status_final"]
    assert not rows[-1]["projeto_na_fila"]


def test_unfinished_job_blocks_new_publication_then_recovers(cloud, board, monkeypatch):
    cfg, bq, new = cloud
    run(cfg, "backfill", client=FakeMonday(board), store=new(), at=at())
    before = copy.deepcopy(bq.tables)
    store = new()
    data = store.read_many(DEFINITIONS)
    original = MemoryJob.result

    def pending(self, timeout):
        raise TimeoutError("job still running")

    monkeypatch.setattr(MemoryJob, "result", pending)
    with pytest.raises(RuntimeError, match="pendente"):
        store.commit(data, cfg.monday_board_id)
    job_id = store._control()[0]["pending"]["job_id"]
    with pytest.raises(RuntimeError, match="pendente"):
        new().commit(data, cfg.monday_board_id)
    assert len(bq.jobs) == 2
    assert bq.tables == before
    monkeypatch.setattr(MemoryJob, "result", original)
    restarted = new()
    restarted.initialize()
    assert restarted._control()[0]["active"]["publication"]["job_id"] == job_id
    assert restarted._control()[0]["pending"] is None


def test_daily_reservation_keeps_publication_artifacts_for_backup(cloud, board):
    cfg, _, new = cloud
    store = new()
    run(cfg, "backfill", client=FakeMonday(board), store=store, at=at())
    original = store._control()[0]["active"]
    store.commit({"etl_run": store.read("etl_run")}, cfg.monday_board_id)
    current = store._control()[0]["active"]
    assert current["state"] != original["state"]
    assert current["publication"] == original["publication"]
    for key in ("artifact", "calendar", "pending_projects"):
        assert store.objects.get(current["publication"][key])[0]


def test_health_tracks_cloud_publication_and_failed_daily(cloud, board):
    from sls_orcamento_ppd.services.health import check_health

    cfg, _, new = cloud
    run(cfg, "backfill", client=FakeMonday(board), store=new(), at=at())
    assert check_health(new(), cfg, now=at())["source"] == "durable_publication"
    with pytest.raises(ValueError, match="atrasada"):
        check_health(new(), cfg, now=at() + timedelta(days=2))
    tomorrow = at() + timedelta(days=1)
    with pytest.raises(RuntimeError):
        run(
            cfg,
            client=FakeMonday(board, fail=True),
            store=new(),
            at=tomorrow,
            scheduled_for=tomorrow,
        )
    with pytest.raises(ValueError, match="Tentativa diária"):
        check_health(new(), cfg, now=tomorrow)


def test_cloud_review_exports_private_artifact_and_replay_preserves_bronze(
    cloud, board, tmp_path, monkeypatch
):
    from sls_orcamento_ppd.pipelines import runner
    from sls_orcamento_ppd.services.review import export_review, import_review

    cfg, bq, new = cloud
    store = new()
    run(cfg, "backfill", client=FakeMonday(board), store=store, at=at())
    before = store.read("bronze_monday_activity_log_raw")
    report = export_review(store, cfg)
    assert report["uri"].startswith("gs://test-bucket/")
    brand = next(r for r in store.read("meta_entity_mapping") if r["entity_type"] == "marca")
    brand.update(
        review_status="quarantined", reviewed_by="unit-test", review_reason="manual review"
    )
    path = tmp_path / "review.json"
    path.write_text(json.dumps([brand], default=lambda v: v.isoformat()), encoding="utf-8")
    assert import_review(store, cfg, path)["reviewed_rows"] == 1
    monkeypatch.setattr(runner, "get_store", lambda settings: new())
    runner.replay(cfg)
    assert bq.tables[store.table_id].rows == []
    assert store.read("bronze_monday_activity_log_raw") == before
