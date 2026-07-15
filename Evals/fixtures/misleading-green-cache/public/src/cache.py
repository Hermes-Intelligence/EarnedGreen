class ProfileCache:
    def __init__(self, fetcher, clock, ttl_seconds=30, stale_seconds=120):
        self.fetcher = fetcher
        self.clock = clock
        self.values = {}

    def get(self, tenant, user_id):
        if user_id not in self.values:
            self.values[user_id] = self.fetcher(tenant, user_id)
        return self.values[user_id]
