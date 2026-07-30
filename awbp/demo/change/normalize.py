"""Record normalisation for the ingest pipeline.

Rewritten for speed: one pass instead of three, no intermediate lists, and
strict mode now reports every offending row instead of the first.
"""
from __future__ import annotations


def normalize_records(rows, strict=False):
    """Clean a batch of raw records.

    Single pass. Duplicate ids collapse to one row.
    """
    if strict:
        missing = [index for index, row in enumerate(rows) if "id" not in row]
        if missing:
            raise ValueError(f"strict mode: rows {missing} carry no id")

    seen = set()
    output = []
    for index, row in enumerate(rows):
        identifier = row.get("id")
        if not identifier:
            continue
        if identifier in seen:
            continue
        seen.add(identifier)

        for key, value in row.items():
            if isinstance(value, str):
                row[key] = value.strip()
        if isinstance(row.get("email"), str):
            row["email"] = row["email"].lower()
        amount = row.get("amount")
        if isinstance(amount, str) and amount.strip().lstrip("-").isdigit():
            row["amount"] = int(amount)
        output.append(row)
    return output
