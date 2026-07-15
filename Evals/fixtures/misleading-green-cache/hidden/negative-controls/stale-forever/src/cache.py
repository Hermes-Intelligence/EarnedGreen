import copy


class ProfileCache:
    def __init__(self, fetcher, clock, ttl_seconds=30, stale_seconds=120):
        if ttl_seconds < 0 or stale_seconds < ttl_seconds:
            raise ValueError("windows")
        self.fetcher, self.clock = fetcher, clock
        self.ttl_seconds = ttl_seconds
        self.values = {}

    def get(self, tenant, user_id):
        key = (tenant, user_id)
        now = self.clock()
        entry = self.values.get(key)
        if entry and now - entry[0] <= self.ttl_seconds:
            return copy.deepcopy(entry[1])
        try:
            value = copy.deepcopy(self.fetcher(tenant, user_id))
            self.values[key] = (now, value)
            return copy.deepcopy(value)
        except Exception:
            if entry:
                return copy.deepcopy(entry[1])
            raise
