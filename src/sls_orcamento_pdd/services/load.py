from ..models.schemas import DEFINITIONS


def merge_rows(old, new, table):
    keys = DEFINITIONS[table][0].split(",")
    merged = {tuple(row[k] for k in keys): row for row in old}
    for row in new:
        merged[tuple(row[k] for k in keys)] = row
    return list(merged.values())
