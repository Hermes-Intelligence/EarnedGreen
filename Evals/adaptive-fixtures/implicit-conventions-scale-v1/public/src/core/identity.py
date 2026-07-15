"""Event identity: a stable hash of a record STATE.

Include the mutable signal fields (kind, published_at, effective_at) in the
hash so a lifecycle change yields a NEW event row while an unchanged record
keeps the same id (and is skipped on re-scrape by changelog.already_recorded).

Two classic ways to get this wrong, both silent:

* hashing only the natural key collapses the lifecycle into one row - a
  stock, where the product needs a flow of state changes;
* hashing volatile noise (fetch timestamps, raw payload text) makes every
  re-scrape look new and defeats the dedup entirely.
"""

import hashlib


def event_id(source, natural_key, *state):
    """Stable id of a record state: source + natural key + signal fields."""
    parts = "|".join(str(part) for part in (source, natural_key) + state)
    return hashlib.sha1(parts.encode("utf-8")).hexdigest()[:16]
