"""normalize.py as it stood after repair a1b2c3d."""
from __future__ import annotations


def normalize_records(rows, strict=False):
    cleaned = [dict(row) for row in rows if row.get("id")]
    by_id = {}
    for row in cleaned:
        by_id[row["id"]] = row
    return [row for row in cleaned if by_id[row["id"]] is row]
