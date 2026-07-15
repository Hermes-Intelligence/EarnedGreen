import copy


def backfill(rows, start=0, limit=None):
    copied = copy.deepcopy(rows)
    return {"rows": copied, "next_cursor": None, "metrics": {"scanned": len(copied), "backfilled": 0, "already_current": 0, "conflicts": 0}}
