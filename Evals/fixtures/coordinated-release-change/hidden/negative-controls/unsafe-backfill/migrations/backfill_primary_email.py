from src.metrics import increment


def backfill(rows, start=0, limit=None):
    end = len(rows) if limit is None else min(len(rows), start + limit)
    counts = {"scanned": 0, "backfilled": 0, "already_current": 0, "conflicts": 0}
    for row in rows[start:end]:
        counts["scanned"] += 1
        if "primary_email" in row:
            counts["already_current"] += 1
        elif "email" in row:
            row["primary_email"] = row.pop("email")
            increment("backfilled")
            counts["backfilled"] += 1
        else:
            counts["conflicts"] += 1
    return {"rows": rows, "next_cursor": None, "metrics": counts}
