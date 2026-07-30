"""normalize.py as it stood after repair e4f5a6b."""
from __future__ import annotations


def normalize_records(rows, strict=False):
    output = []
    for row in rows:
        if not row.get("id"):
            continue
        out = dict(row)
        for key, value in out.items():
            if isinstance(value, str):
                out[key] = value.strip()
        output.append(out)
    return output
