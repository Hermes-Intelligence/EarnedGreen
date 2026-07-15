COUNTERS = {}


def increment(name):
    COUNTERS[name] = COUNTERS.get(name, 0) + 1


def reset():
    COUNTERS.clear()
