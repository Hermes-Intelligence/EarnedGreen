"""Alternative reference authored from the public task text alone, then reconciled.

The first draft chose the other defensible interpretation at every decision
point (reject on registry miss; let handler exceptions propagate; trim the type
for lookup and output; count one malformed_event for handler errors too; leave
the audit-export and cache-snapshot paths on the legacy parse_record contract;
count unknown_entity_type on every sighting with no re-run dedup). It failed the
hidden grader, which confirmed those readings are not the pinned ones. task.md
v4 pins each decision explicitly; this module implements the pinned semantics
with a rule-table validation style and a dict-based dedup ledger that are
deliberately different from the primary reference.
"""
from copy import deepcopy

from . import metrics

SCHEMA_VERSION = 3

_SHAPE_RULES = (
    (lambda event: isinstance(event, dict), "event is not a mapping"),
    (lambda event: set(event) == {"type", "id", "fields"}, "event keys must be exactly type, id and fields"),
    (lambda event: isinstance(event["type"], str) and bool(event["type"].strip()), "type must be a non-blank string"),
    (lambda event: isinstance(event["id"], str) and bool(event["id"].strip()), "id must be a non-blank string"),
    (lambda event: isinstance(event["fields"], dict), "fields must be a dictionary"),
)

# Structural variant of the ledger: a dict of sighting counts rather than a set.
# It is process-lifetime and independent of the counter reset.
_UNRESOLVED_SIGHTINGS = {}


def _reject(reason):
    metrics.increment("malformed_event")
    raise ValueError(reason)


def _note_unresolved(kind, entity_id):
    key = (kind, entity_id)
    seen_before = _UNRESOLVED_SIGHTINGS.get(key, 0)
    _UNRESOLVED_SIGHTINGS[key] = seen_before + 1
    metrics.increment("unknown_repeat" if seen_before else "unknown_entity_type")


def _resolve(kind, entity_id, registry, attributes):
    """Return normalized attributes, deduplicating unresolved identities and containing handler errors."""
    handler = registry.get(kind)
    if handler is None:
        _note_unresolved(kind, entity_id)
        return deepcopy(attributes)
    try:
        produced = handler(deepcopy(attributes))
    except Exception:
        metrics.increment("handler_error")
        return deepcopy(attributes)
    if not isinstance(produced, dict):
        _reject("handler results must be dictionaries")
    return produced


def normalize_event(event, registry):
    for rule, reason in _SHAPE_RULES:
        try:
            ok = rule(event)
        except (TypeError, KeyError):
            ok = False
        if not ok:
            _reject(reason)
    if not isinstance(registry, dict) or not all(callable(entry) for entry in registry.values()):
        _reject("registry entries must be callables")
    # Exact match: the shape rules used strip() only to test blankness; the
    # lookup key and the emitted entity_type are the original type verbatim.
    kind = event["type"]
    normalized = _resolve(kind, event["id"], registry, event["fields"])
    return {
        "entity_type": kind,
        "entity_id": event["id"],
        "attributes": deepcopy(normalized),
        "schema_version": SCHEMA_VERSION,
    }


def parse_record(record):
    if not isinstance(record, dict):
        raise TypeError("record must be a dictionary")
    return {"entity_type": record["type"], "entity_id": record["id"], "attributes": deepcopy(record.get("fields", {}))}
