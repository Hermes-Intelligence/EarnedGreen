import copy

from src.metrics import increment


def backfill(rows, start=0, limit=None):
    if isinstance(start, bool) or not isinstance(start, int) or start < 0 or start > len(rows):
        raise ValueError("start")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 0):
        raise ValueError("limit")
    copied = copy.deepcopy(list(rows))
    end = len(copied) if limit is None else min(len(copied), start + limit)
    counts = {"scanned": 0, "backfilled": 0, "already_current": 0, "conflicts": 0}
    for index in range(start, end):
        row = copied[index]
        counts["scanned"] += 1
        legacy, current = row.get("email"), row.get("primary_email")
        if current is not None:
            if legacy is not None and legacy != current:
                counts["conflicts"] += 1
            else:
                counts["already_current"] += 1
        elif isinstance(legacy, str) and legacy:
            row["primary_email"] = legacy
            counts["backfilled"] += 1
            increment("backfilled")
        else:
            counts["conflicts"] += 1
    return {"rows": copied, "next_cursor": end if end < len(copied) else None, "metrics": counts}
