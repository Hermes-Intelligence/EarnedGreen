"""normalize.py as it stood before repair e4f5a6b."""
from __future__ import annotations


def normalize_records(rows, strict=False):
    output = []
    for row in rows:
        if not row.get("id"):
            continue
        for key, value in row.items():
            if isinstance(value, str):
                row[key] = value.strip()
        output.append(row)
    return output
