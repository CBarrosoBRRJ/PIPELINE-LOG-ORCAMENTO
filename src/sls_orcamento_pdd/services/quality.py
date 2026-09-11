"""Read-only quality inventory; exports counts and metadata, no business rows."""

from ..models.contracts import CONTRACT_VERSION, required_columns, validate_table
from ..models.keys import DIMENSION_IDENTITIES
from ..models.schemas import DEFINITIONS
from ..utils.time import utcnow


def quality_profile(store, board_id):
    report = {
        "contract_version": CONTRACT_VERSION,
        "board_id": board_id,
        "profiled_at": utcnow().isoformat(),
        "tables": {},
        "critical_failures": 0,
    }
    data = store.read_many(DEFINITIONS, board_id) if hasattr(store, "read_many") else None
    for name, (_, fields) in DEFINITIONS.items():
        rows = data[name] if data is not None else store.read(name, board_id)
        columns = {}
        for field in fields.split():
            column, kind = field.split(":")
            nulls = sum(row.get(column) is None for row in rows)
            blanks = sum(
                isinstance(row.get(column), str) and not row[column].strip() for row in rows
            )
            columns[column] = {
                "type": kind,
                "required": column in required_columns(name)
                or column == DIMENSION_IDENTITIES.get(name, (None, None))[1],
                "nulls": nulls,
                "blank_strings": blanks,
                "null_percent": round(nulls / len(rows) * 100, 2) if rows else None,
            }
        status = {"rows": len(rows), "columns": columns, "contract_status": "valid"}
        try:
            validate_table(name, rows, board_id)
        except ValueError as error:
            status.update(contract_status="invalid", first_violation=str(error))
            report["critical_failures"] += 1
        report["tables"][name] = status
    return report
