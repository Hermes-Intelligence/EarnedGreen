from .backend import TemporaryBackendError


class ProfileCache:
    def __init__(self, fetcher, clock, ttl_seconds=30, stale_seconds=120):
        if ttl_seconds < 0 or stale_seconds < ttl_seconds:
            raise ValueError("windows")
        self.fetcher, self.clock = fetcher, clock
        self.ttl_seconds, self.stale_seconds = ttl_seconds, stale_seconds
        self.values = {}

    def get(self, tenant, user_id):
        now = self.clock()
        entry = self.values.get(user_id)
        if entry and now - entry[0] <= self.ttl_seconds:
            return entry[1]
        try:
            value = self.fetcher(tenant, user_id)
        except TemporaryBackendError:
            if entry and now - entry[0] <= self.stale_seconds:
                return entry[1]
            raise
        self.values[user_id] = (now, value)
        return value
