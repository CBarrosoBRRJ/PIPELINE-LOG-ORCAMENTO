from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

from .keys import DIMENSION_IDENTITIES, SURROGATE_COLUMNS

# Shared metadata drives PostgreSQL DDL, BigQuery DDL and migration keys.
JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")
TYPES = {
    "text": Text,
    "id": BigInteger,
    "int": Integer,
    "bool": Boolean,
    "time": DateTime(timezone=True),
    "date": Date,
    "num": Float,
    "json": JSON_TYPE,
}

DEFINITIONS = {
    "dim_board": ("board_id", "board_id:id board_name:text created_at:time updated_at:time"),
    "meta_column_mapping": (
        "board_id,column_id",
        "board_id:id column_id:text column_title:text column_type:text "
        "analytical_attribute:text is_extracted:bool is_modeled:bool is_present:bool discovered_at:time",
    ),
    "bronze_monday_activity_log_raw": (
        "event_id",
        "event_id:text board_id:id item_id:id event:text event_at_utc:time "
        "created_at_raw:text status_from_text:text status_to_text:text status_from_index:int "
        "status_to_index:int column_id:text column_title:text group_id:text raw_data:json "
        "timestamp_source:text ingested_at:time",
    ),
    "bronze_monday_item_snapshot_raw": (
        "board_id,item_id,snapshot_date",
        "item_id:id board_id:id item_name:text group_id:text "
        "created_at:time updated_at:time marca:text cliente:text talento:text intervenciencia:text "
        "pessoas_json:json snapshot_at:time snapshot_date:date current_status_id:text "
        "status_text:text status_index:int is_active:bool raw_data:json",
    ),
    "bronze_monday_board_schema_raw": (
        "board_id,snapshot_date",
        "board_id:id snapshot_date:date snapshot_at:time raw_data:json mapping:json",
    ),
    "silver_monday_status_event_stg": (
        "event_id",
        "event_id:text board_id:id item_id:id status_id:text status_from:text "
        "status_to:text event_at_utc:time timestamp_source:text",
    ),
    "dim_status": (
        "status_id",
        "status_id:text board_id:id status_label:text status_label_norm:text "
        "status_order:int status_column_id:text status_color:text is_terminal:bool",
    ),
    "dim_person": ("person_id", "person_id:text person_name:text email:text"),
    "dim_item": (
        "item_id",
        "item_id:id board_id:id item_name:text created_at:time updated_at:time "
        "current_status_id:text is_active:bool last_seen_at:time",
    ),
    "bridge_item_person": (
        "item_id,person_id,source_column_id,snapshot_date",
        "item_id:id board_id:id person_id:text role:text source_column_id:text snapshot_date:date",
    ),
    "fct_item_status_interval": (
        "interval_id",
        "interval_id:text board_id:id item_id:id status_id:text status_from:text "
        "status_to:text status_start_utc:time status_end_utc:time duration_minutes:num duration_hours:num "
        "is_open_interval:bool event_start_id:text event_end_id:text item_name:text marca:text "
        "cliente:text talento:text intervenciencia:text pessoas_json:json snapshot_date:date "
        "attribute_source:text history_quality:text updated_at:time",
    ),
    "fct_item_status_daily": (
        "board_id,dt,item_id,status_id",
        "board_id:id dt:date item_id:id status_id:text "
        "minutes_in_status:num marca:text cliente:text talento:text intervenciencia:text snapshot_date:date",
    ),
    "fct_item_sla_summary": (
        "item_id",
        "item_id:id board_id:id status_atual:text created_at:time first_status_at:time "
        "finalizado_em:time lead_time_total_min:num sla_status_atual_min:num open_interval:bool "
        "is_active:bool history_quality:text sla_start_utc:time sla_start_quality:text atualizado_em:time",
    ),
    "etl_watermark": (
        "pipeline_name",
        "pipeline_name:text board_id:id last_run_utc:time last_log_event_id:text "
        "last_item_page_cursor:text updated_at:time",
    ),
    "etl_run": (
        "run_id",
        "run_id:text board_id:id mode:text start_at:time end_at:time status:text metrics:json",
    ),
    "data_quality_issue": (
        "issue_id",
        "issue_id:text board_id:id item_id:id code:text detail:text detected_at:time",
    ),
}


for _name, _columns in SURROGATE_COLUMNS.items():
    _keys, _fields = DEFINITIONS[_name]
    DEFINITIONS[_name] = (_keys, _fields + " " + " ".join(f"{c}:text" for c in _columns))


def foreign_keys():
    """Explicit relational contract; Monday item IDs remain unchanged."""
    relationships = []
    for name, (_, fields) in DEFINITIONS.items():
        columns = {f.split(":")[0] for f in fields.split()}
        if "board_id" in columns and name != "dim_board":
            relationships.append((name, "board_id", "dim_board", "board_id"))
        if "item_id" in columns and name != "dim_item":
            relationships.append((name, "item_id", "dim_item", "item_id"))
        if "status_id" in columns and name != "dim_status":
            relationships.append((name, "status_id", "dim_status", "status_id"))
        if "current_status_id" in columns:
            relationships.append((name, "current_status_id", "dim_status", "status_id"))
    relationships.extend(
        [
            ("bridge_item_person", "person_id", "dim_person", "person_id"),
            (
                "silver_monday_status_event_stg",
                "event_id",
                "bronze_monday_activity_log_raw",
                "event_id",
            ),
            (
                "fct_item_status_interval",
                "event_start_id",
                "bronze_monday_activity_log_raw",
                "event_id",
            ),
            (
                "fct_item_status_interval",
                "event_end_id",
                "bronze_monday_activity_log_raw",
                "event_id",
            ),
        ]
    )
    return relationships


def surrogate_foreign_keys():
    result = []
    for child, source, parent, target in foreign_keys():
        child_sk = next(
            (k for k, (src, _) in SURROGATE_COLUMNS.get(child, {}).items() if src == source), None
        )
        identity = DIMENSION_IDENTITIES.get(parent)
        if child_sk and identity and target == identity[0]:
            result.append((child, source, child_sk, parent, target, identity[1]))
    return result


REPLACE_TABLES = {
    "silver_monday_status_event_stg",
    "fct_item_status_interval",
    "fct_item_status_daily",
    "fct_item_sla_summary",
    "data_quality_issue",
}


def define_tables(schema="sladb"):
    from .contracts import required_columns

    metadata = MetaData(schema=schema)
    tables = {}
    for name, (keys, fields) in DEFINITIONS.items():
        primary = keys.split(",")
        columns = [
            Column(
                field.split(":")[0],
                TYPES[field.split(":")[1]],
                primary_key=field.split(":")[0] in primary,
                nullable=(
                    field.split(":")[0] not in required_columns(name)
                    and field.split(":")[0] != DIMENSION_IDENTITIES.get(name, (None, None))[1]
                ),
            )
            for field in fields.split()
        ]
        tables[name] = Table(name, metadata, *columns)
    import hashlib

    for name, (source, surrogate) in DIMENSION_IDENTITIES.items():
        tables[name].append_constraint(UniqueConstraint(surrogate, name=f"uq_{name}_surrogate"))
        tables[name].append_constraint(
            UniqueConstraint(source, surrogate, name=f"uq_{name}_identity")
        )

    for child, column, parent, target in foreign_keys():
        digest = hashlib.sha256(f"{child}.{column}.{parent}".encode()).hexdigest()[:8]
        tables[child].append_constraint(
            ForeignKeyConstraint(
                [column],
                [f"{schema}.{parent}.{target}"],
                name=f"fk_{child[:22]}_{digest}",
                deferrable=True,
                initially="DEFERRED",
            )
        )
    for child, source, child_sk, parent, target, parent_sk in surrogate_foreign_keys():
        digest = hashlib.sha256(f"{child}.{child_sk}.{parent}".encode()).hexdigest()[:8]
        tables[child].append_constraint(
            ForeignKeyConstraint(
                [source, child_sk],
                [f"{schema}.{parent}.{target}", f"{schema}.{parent}.{parent_sk}"],
                name=f"fk_sk_{child[:19]}_{digest}",
                deferrable=True,
                initially="DEFERRED",
            )
        )
    for name, columns in {
        "bronze_monday_activity_log_raw": ["board_id", "item_id", "event_at_utc"],
        "bronze_monday_item_snapshot_raw": ["board_id", "snapshot_at"],
        "fct_item_status_interval": ["board_id", "item_id", "status_start_utc"],
        "fct_item_status_daily": ["board_id", "dt"],
    }.items():
        Index(f"ix_{name}", *(tables[name].c[c] for c in columns))
    return metadata, tables
