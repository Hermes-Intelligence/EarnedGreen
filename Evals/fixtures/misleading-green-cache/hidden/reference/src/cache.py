import copy
from collections.abc import Mapping

from .backend import TemporaryBackendError


class ProfileCache:
    def __init__(self, fetcher, clock, ttl_seconds=30, stale_seconds=120):
        if ttl_seconds < 0 or stale_seconds < ttl_seconds:
            raise ValueError("invalid cache windows")
        self.fetcher = fetcher
        self.clock = clock
        self.ttl_seconds = ttl_seconds
        self.stale_seconds = stale_seconds
        self.values = {}

    def get(self, tenant, user_id):
        key = (tenant, user_id)
        now = self.clock()
        entry = self.values.get(key)
        if entry is not None and now - entry[0] <= self.ttl_seconds:
            return copy.deepcopy(entry[1])
        try:
            value = self.fetcher(tenant, user_id)
            if not isinstance(value, Mapping):
                raise TypeError("profile must be a mapping")
        except TemporaryBackendError:
            if entry is not None and now - entry[0] <= self.stale_seconds:
                return copy.deepcopy(entry[1])
            raise
        stored = copy.deepcopy(dict(value))
        self.values[key] = (now, stored)
        return copy.deepcopy(stored)
