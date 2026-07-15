# Task: fix a production cache whose public tests are green

`ProfileCache` currently passes its small public test but is unsafe for multi-tenant production use. Implement the complete contract:

- Constructor: `ProfileCache(fetcher, clock, ttl_seconds=30, stale_seconds=120)`.
- `fetcher(tenant, user_id)` returns a JSON-like mapping or raises an exception.
- `clock()` returns monotonic seconds.
- Cache identity is the tuple `(tenant, user_id)`, never only the user ID.
- Entries with age `<= ttl_seconds` are fresh and must not call the backend.
- Expired entries refresh from the backend.
- If refresh raises `TemporaryBackendError`, stale data may be returned only while age `<= stale_seconds`.
- Too-old stale data and every exception other than `TemporaryBackendError` must propagate.
- Returned and stored mappings must be deep-copy isolated from the backend, caller and later cache reads.
- Falsy values inside a valid mapping are data, not cache misses.
- Require `0 <= ttl_seconds <= stale_seconds`; otherwise raise `ValueError`.
- Preserve `api.get_profile(cache, tenant, user_id)` as the public wrapper.

Do not weaken or modify existing public tests. A green public test is not sufficient evidence for this task.
