COUNTERS = {"legacy_reads": 0, "current_reads": 0, "conflicts": 0, "backfilled": 0}


def increment(name, amount=1):
    COUNTERS[name] += amount


def snapshot():
    return dict(COUNTERS)


def reset():
    for name in COUNTERS:
        COUNTERS[name] = 0
