"""Record normalisation for the ingest pipeline.

Grown over two years, one incident at a time. Two of the rules below exist
because they were violated in production; see the repair history.
"""
from __future__ import annotations


def normalize_records(rows, strict=False):
    """Clean a batch of raw records.

    Later rows win on a duplicate id: the batch arrives oldest-first and the
    last version of a record is the current one.
    """
    if strict and any("id" not in row for row in rows):
        raise ValueError("strict mode: every row must carry an id")

    cleaned = []
    for row in rows:
        if not row.get("id"):
            continue
        out = dict(row)                       # copy: the caller keeps its rows
        for key, value in list(out.items()):
            if isinstance(value, str):
                out[key] = value.strip()
        if isinstance(out.get("email"), str):
            out["email"] = out["email"].lower()
        amount = out.get("amount")
        if isinstance(amount, str) and amount.strip().lstrip("-").isdigit():
            out["amount"] = int(amount)
        cleaned.append(out)

    by_id = {}
    for row in cleaned:
        by_id[row["id"]] = row                # last write wins
    return [row for row in cleaned if by_id[row["id"]] is row]
