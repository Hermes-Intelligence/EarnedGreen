"""normalize.py as it stood before repair a1b2c3d."""
from __future__ import annotations


def normalize_records(rows, strict=False):
    seen = set()
    output = []
    for row in rows:
        if not row.get("id"):
            continue
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        output.append(dict(row))
    return output
