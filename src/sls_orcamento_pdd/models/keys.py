"""Stable entity surrogate keys; source IDs remain available and unique.

UUIDv5 is portable and does not require a database sequence. It identifies an
entity, not an SCD2 version. A versioned dimension must get a separate version key.
"""

from uuid import NAMESPACE_URL, uuid5

SURROGATE_COLUMNS = {
    "quarentena_projeto": {"board_sk": ("board_id", "board"), "item_sk": ("item_id", "item")},
    "gold_projeto_status": {
        "board_sk": ("board_id", "board"),
        "item_sk": ("item_id", "item"),
        "status_sk": ("status_id", "status"),
    },
    "dim_board": {"board_sk": ("board_id", "board")},
    "dim_item": {
        "item_sk": ("item_id", "item"),
        "board_sk": ("board_id", "board"),
        "current_status_sk": ("current_status_id", "status"),
    },
    "dim_status": {"status_sk": ("status_id", "status"), "board_sk": ("board_id", "board")},
    "dim_person": {"person_sk": ("person_id", "person")},
    "meta_column_mapping": {"board_sk": ("board_id", "board")},
    "bridge_item_person": {
        "board_sk": ("board_id", "board"),
        "item_sk": ("item_id", "item"),
        "person_sk": ("person_id", "person"),
    },
    "silver_monday_status_event_stg": {
        "board_sk": ("board_id", "board"),
        "item_sk": ("item_id", "item"),
        "status_sk": ("status_id", "status"),
    },
    "fct_item_status_interval": {
        "board_sk": ("board_id", "board"),
        "item_sk": ("item_id", "item"),
        "status_sk": ("status_id", "status"),
    },
    "fct_item_status_daily": {
        "board_sk": ("board_id", "board"),
        "item_sk": ("item_id", "item"),
        "status_sk": ("status_id", "status"),
    },
    "fct_item_sla_summary": {"board_sk": ("board_id", "board"), "item_sk": ("item_id", "item")},
}
DIMENSION_IDENTITIES = {
    "dim_board": ("board_id", "board_sk"),
    "dim_item": ("item_id", "item_sk"),
    "dim_status": ("status_id", "status_sk"),
    "dim_person": ("person_id", "person_sk"),
}


def surrogate_key(entity, source_id):
    if source_id is None:
        return None
    return str(uuid5(NAMESPACE_URL, f"sls_orcamento_pdd:monday:{entity}:{source_id}"))


def with_surrogates(table, row):
    return {
        **row,
        **{
            column: surrogate_key(entity, row.get(source))
            for column, (source, entity) in SURROGATE_COLUMNS.get(table, {}).items()
        },
    }
