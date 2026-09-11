"""BigQuery adapter and PostgreSQL migration, sharing the pure model.

All destination DML, including watermark, commits in one BQ transaction.
Load jobs target expiring staging tables only. Run a single scheduler per board;
local process locking complements the transaction, it is not a distributed lease.
"""

import json
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta

from ..models.contracts import prepare_payload, required_columns
from ..models.keys import DIMENSION_IDENTITIES
from ..models.schemas import (
    DEFINITIONS,
    REPLACE_TABLES,
    define_tables,
    foreign_keys,
    surrogate_foreign_keys,
)
from ..utils.logging import emit
from ..utils.time import utcnow

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
PARTITIONS = {
    "gold_projeto_status": "DATE(entrada_status_utc)",
    "bronze_monday_activity_log_raw": "DATE(event_at_utc)",
    "bronze_monday_item_snapshot_raw": "snapshot_date",
    "bronze_monday_board_schema_raw": "snapshot_date",
    "silver_monday_status_event_stg": "DATE(event_at_utc)",
    "fct_item_status_interval": "DATE(status_start_utc)",
    "fct_item_status_daily": "dt",
    "etl_run": "DATE(start_at)",
}


def table_ddl(prefix, name):
    fields = [
        f"`{f.split(':')[0]}` {BQ_TYPES[f.split(':')[1]]}"
        + (" NOT NULL" if f.split(":")[0] in required_columns(name) else "")
        for f in DEFINITIONS[name][1].split()
    ]
    keys = DEFINITIONS[name][0].split(",")
    fields.append("PRIMARY KEY (" + ", ".join(f"`{k}`" for k in keys) + ") NOT ENFORCED")
    # BQ constraints document/optimize relationships; they do not enforce integrity.
    for child, column, parent, target in foreign_keys():
        if child == name:
            fields.append(
                f"FOREIGN KEY (`{column}`) REFERENCES `{prefix}.{parent}` (`{target}`) NOT ENFORCED"
            )
    sql = f"CREATE TABLE IF NOT EXISTS `{prefix}.{name}` (\n  " + ",\n  ".join(fields) + "\n)"
    if name in PARTITIONS:
        sql += "\nPARTITION BY " + PARTITIONS[name]
    available = {f.split(":")[0] for f in DEFINITIONS[name][1].split()}
    clusters = [k for k in ("board_id", "item_id", "status_id") if k in available]
    if clusters:
        sql += "\nCLUSTER BY " + ", ".join(clusters)
    return sql


def integrity_assertions(prefix, names):
    statements = []
    for name in names:
        keys = DEFINITIONS[name][0].split(",")
        scope = " WHERE T.board_id=@board" if "board_id:id" in DEFINITIONS[name][1] else ""
        key_struct = ",".join(f"T.`{key}` AS `{key}`" for key in keys)
        null_keys = " OR ".join(f"T.`{key}` IS NULL" for key in keys)
        statements.append(
            f"ASSERT (SELECT COUNT(*)=COUNT(DISTINCT TO_JSON_STRING(STRUCT({key_struct}))) "
            f"AND COUNTIF({null_keys})=0 FROM `{prefix}.{name}` T{scope}) "
            f"AS 'Invalid primary key: {name}';"
        )
        if name in DIMENSION_IDENTITIES:
            surrogate = DIMENSION_IDENTITIES[name][1]
            statements.append(
                f"ASSERT (SELECT COUNT(*)=COUNT(DISTINCT T.{surrogate}) "
                f"FROM `{prefix}.{name}` T{scope}) AS 'Invalid surrogate key: {name}';"
            )
    for child, column, parent, target in foreign_keys():
        if child in names:
            scope = " AND C.board_id=@board" if "board_id:id" in DEFINITIONS[child][1] else ""
            statements.append(
                f"ASSERT (SELECT COUNT(*)=0 FROM `{prefix}.{child}` C "
                f"LEFT JOIN `{prefix}.{parent}` P ON C.`{column}`=P.`{target}` "
                f"WHERE C.`{column}` IS NOT NULL AND P.`{target}` IS NULL{scope}) "
                f"AS 'Invalid foreign key: {child}.{column}';"
            )
    for child, source, child_sk, parent, target, parent_sk in surrogate_foreign_keys():
        if child in names:
            scope = " AND C.board_id=@board" if "board_id:id" in DEFINITIONS[child][1] else ""
            statements.append(
                f"ASSERT (SELECT COUNT(*)=0 FROM `{prefix}.{child}` C "
                f"LEFT JOIN `{prefix}.{parent}` P ON C.`{source}`=P.`{target}` "
                f"AND C.`{child_sk}`=P.`{parent_sk}` "
                f"WHERE C.`{source}` IS NOT NULL AND P.`{target}` IS NULL{scope}) "
                f"AS 'Mismatched surrogate: {child}.{child_sk}';"
            )
    return statements


class BigQueryStore:
    def __init__(self, settings):
        from google.cloud import bigquery

        if not settings.bq_project:
            raise ValueError("Defina BQ_PROJECT no .env")
        self.settings = settings
        self.bq = bigquery
        self.prefix = f"{settings.bq_project}.{settings.bq_dataset}"
        kwargs = {"project": settings.bq_project, "location": settings.bq_location}
        self.client = (
            bigquery.Client.from_service_account_json(settings.bq_keyfile, **kwargs)
            if settings.bq_keyfile
            else bigquery.Client(**kwargs)
        )

    def initialize(self):
        dataset = self.bq.Dataset(self.prefix)
        dataset.location = self.settings.bq_location
        self.client.create_dataset(dataset, exists_ok=True)
        metadata, _ = define_tables()
        for table in metadata.sorted_tables:
            self.client.query(table_ddl(self.prefix, table.name)).result()
        self.client.query(
            f"ALTER TABLE `{self.prefix}.fct_item_sla_summary` "
            "ADD COLUMN IF NOT EXISTS sla_start_utc TIMESTAMP, "
            "ADD COLUMN IF NOT EXISTS sla_start_quality STRING"
        ).result()
        self.create_views()

    def create_views(self):
        p = self.prefix
        queries = {
            "gold_project_status": f"""SELECT board_id,item_id,status_id,
              SUM(duration_minutes) total_minutes, SUM(duration_hours) total_hours,COUNT(*) visit_count
              FROM `{p}.fct_item_status_interval` GROUP BY board_id,item_id,status_id""",
            "gold_status_metrics": f"""WITH stats AS (
              SELECT DISTINCT board_id,status_id,COUNT(*) OVER w interval_count,
                SUM(duration_minutes) OVER w accumulated_minutes, AVG(duration_minutes) OVER w mean_minutes,
                PERCENTILE_CONT(duration_minutes,0.5) OVER w median_minutes,
                PERCENTILE_CONT(duration_minutes,0.95) OVER w p95_minutes
              FROM `{p}.fct_item_status_interval` WINDOW w AS (PARTITION BY board_id,status_id)
            ), queue AS (SELECT board_id,current_status_id status_id,COUNT(*) current_item_count
                FROM `{p}.dim_item` WHERE is_active GROUP BY board_id,current_status_id)
              SELECT s.*,IFNULL(d.interval_count,0) interval_count,
                IFNULL(d.accumulated_minutes,0) accumulated_minutes,d.mean_minutes,d.median_minutes,d.p95_minutes,
                IFNULL(q.current_item_count,0) current_item_count,
                IF(s.is_terminal,0,IFNULL(q.current_item_count,0)) queue_count
              FROM `{p}.dim_status` s LEFT JOIN stats d USING(board_id,status_id)
              LEFT JOIN queue q USING(board_id,status_id)""",
            "gold_status_bottlenecks": f"""SELECT *,
                DENSE_RANK() OVER(PARTITION BY board_id ORDER BY accumulated_minutes DESC) time_rank,
                DENSE_RANK() OVER(PARTITION BY board_id ORDER BY queue_count DESC) queue_rank
              FROM `{p}.gold_status_metrics` WHERE NOT is_terminal""",
            "gold_intervals_local": f"""SELECT *,
              DATETIME(status_start_utc,'{self.settings.preferred_timezone}') status_start_local,
              DATETIME(status_end_utc,'{self.settings.preferred_timezone}') status_end_local
              FROM `{p}.fct_item_status_interval`""",
        }
        for name, query in queries.items():
            self.client.query(f"CREATE OR REPLACE VIEW `{p}.{name}` AS {query}").result()

    @contextmanager
    def lock(self):
        self.settings.runtime_dir.mkdir(parents=True, exist_ok=True)
        path = self.settings.runtime_dir / f"bq_{self.settings.monday_board_id}.lock"
        with path.open("a+b") as handle:
            import os

            if os.name == "nt":
                import msvcrt

                handle.write(b"0")
                handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle, fcntl.LOCK_UN)

    def read(self, table, board_id=None):
        if table not in DEFINITIONS:
            raise ValueError("Tabela não reconhecida")
        query = f"SELECT * FROM `{self.prefix}.{table}`"
        params = []
        if board_id is not None and "board_id:id" in DEFINITIONS[table][1]:
            query += " WHERE board_id=@board"
            params = [self.bq.ScalarQueryParameter("board", "INT64", board_id)]
        rows = [
            dict(r)
            for r in self.client.query(
                query, job_config=self.bq.QueryJobConfig(query_parameters=params)
            ).result()
        ]
        json_fields = [
            f.split(":")[0] for f in DEFINITIONS[table][1].split() if f.endswith(":json")
        ]
        for row in rows:
            for field in json_fields:
                if isinstance(row[field], str):
                    row[field] = json.loads(row[field])
        return rows

    def commit(self, payload, board_id):
        payload = prepare_payload(payload, board_id)
        script = ["BEGIN TRANSACTION;"]
        stages = []
        try:
            for name, rows in payload.items():
                if name not in DEFINITIONS:
                    raise ValueError("Tabela não reconhecida")
                target = f"`{self.prefix}.{name}`"
                if name in REPLACE_TABLES:
                    script.append(f"DELETE FROM {target} WHERE board_id=@board;")
                if not rows:
                    continue
                fields = dict(f.split(":") for f in DEFINITIONS[name][1].split())
                stage_id = f"{self.prefix}._stage_{name}_{uuid.uuid4().hex}"
                schema = [self.bq.SchemaField(k, BQ_TYPES[v]) for k, v in fields.items()]
                stage = self.bq.Table(stage_id, schema=schema)
                stage.expires = utcnow() + timedelta(hours=24)
                self.client.create_table(stage)
                stages.append(stage_id)

                def encode(row, fields=fields):
                    encoded = {}
                    for k in fields:
                        value = row.get(k)
                        if fields[k] == "json" and value is not None:
                            value = json.dumps(value, ensure_ascii=False, default=str)
                        elif isinstance(value, (datetime, date)):
                            value = value.isoformat()
                        encoded[k] = value
                    return encoded

                self.client.load_table_from_json(
                    [encode(row) for row in rows],
                    stage_id,
                    job_config=self.bq.LoadJobConfig(
                        schema=schema, write_disposition="WRITE_TRUNCATE"
                    ),
                ).result()
                keys = DEFINITIONS[name][0].split(",")
                on = " AND ".join(f"T.`{k}`=S.`{k}`" for k in keys)
                updates = ",".join(
                    f"T.`{k}`=S.`{k}`"
                    for k in fields
                    if k not in keys
                    and not (name == "bronze_monday_activity_log_raw" and k == "ingested_at")
                )
                columns = ",".join(f"`{k}`" for k in fields)
                values = ",".join(f"S.`{k}`" for k in fields)
                matched = (
                    ""
                    if name in {"meta_entity_mapping", "meta_gold_rule_snapshot"}
                    else f"WHEN MATCHED THEN UPDATE SET {updates} "
                )
                script.append(
                    f"MERGE {target} T USING `{stage_id}` S ON {on} "
                    f"{matched}"
                    f"WHEN NOT MATCHED THEN INSERT ({columns}) VALUES ({values});"
                )
            script.extend(integrity_assertions(self.prefix, payload.keys()))
            script.append("COMMIT TRANSACTION;")
            self.client.query(
                "\n".join(script),
                job_config=self.bq.QueryJobConfig(
                    query_parameters=[self.bq.ScalarQueryParameter("board", "INT64", board_id)]
                ),
            ).result()
        finally:
            # Only UUID-owned staging tables are deleted; production tables are never dropped.
            for stage_id in stages:
                self.client.delete_table(stage_id, not_found_ok=True)


def export_postgres(settings):
    from .postgres import PostgresStore

    source, target = PostgresStore(settings), BigQueryStore(settings)
    target.initialize()
    with source.lock(), target.lock():
        payload = {name: source.read(name, settings.monday_board_id) for name in DEFINITIONS}
        target.commit(payload, settings.monday_board_id)
        for name, rows in payload.items():
            count = len(target.read(name, settings.monday_board_id))
            if count != len(rows):
                raise ValueError(f"Contagem divergente após migração: {name}")
            emit("bq_table_migrated", table=name, rows=count)
