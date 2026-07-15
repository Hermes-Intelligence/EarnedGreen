import copy
import importlib
import importlib.util
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root))
model = importlib.import_module("src.model")
api = importlib.import_module("src.api")
metrics = importlib.import_module("src.metrics")
migration_path = root / "migrations/backfill_primary_email.py"
spec = importlib.util.spec_from_file_location("backfill_primary_email", migration_path)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)
checks = []


def record(identifier, weight, fn):
    try:
        passed = bool(fn())
    except Exception:
        passed = False
    checks.append({"id": identifier, "weight": weight, "passed": passed})


def conflict():
    try:
        model.normalize_user({"id": "x", "email": "old", "primary_email": "new"})
        return False
    except ValueError:
        return True


def serialization():
    current = api.serialize_user({"id": "x", "email": "a"})
    legacy = api.serialize_user({"id": "x", "primary_email": "a"}, include_legacy=True)
    return current == {"id": "x", "primary_email": "a"} and legacy == {"id": "x", "primary_email": "a", "email": "a"}


def migration_idempotent():
    rows = [{"id": "a", "email": "a@x"}, {"id": "b", "primary_email": "b@x"}, {"id": "c", "email": "old", "primary_email": "new"}]
    first = migration.backfill(rows)
    second = migration.backfill(first["rows"])
    return first["rows"][0] == {"id": "a", "email": "a@x", "primary_email": "a@x"} and first["metrics"] == {"scanned": 3, "backfilled": 1, "already_current": 1, "conflicts": 1} and second["metrics"]["backfilled"] == 0 and second["rows"] == first["rows"]


def cursor_resume():
    rows = [{"id": str(i), "email": f"{i}@x"} for i in range(5)]
    first = migration.backfill(rows, start=0, limit=2)
    second = migration.backfill(first["rows"], start=first["next_cursor"], limit=2)
    third = migration.backfill(second["rows"], start=second["next_cursor"], limit=2)
    return first["next_cursor"] == 2 and second["next_cursor"] == 4 and third["next_cursor"] is None and all("primary_email" in row for row in third["rows"])


def no_mutation():
    rows = [{"id": "a", "email": "a@x", "nested": {"v": 1}}]
    before = copy.deepcopy(rows)
    migration.backfill(rows)
    return rows == before


def observability():
    metrics.reset()
    model.normalize_user({"id": "a", "email": "a@x"})
    model.normalize_user({"id": "b", "primary_email": "b@x"})
    try:
        model.normalize_user({"id": "c", "email": "old", "primary_email": "new"})
    except ValueError:
        pass
    migration.backfill([{"id": "d", "email": "d@x"}])
    return metrics.snapshot() == {"legacy_reads": 1, "current_reads": 1, "conflicts": 1, "backfilled": 1}


def docs_complete():
    text = (root / "docs/user-schema.md").read_text(encoding="utf-8").lower()
    if not all(term in text for term in ("expand", "migrate", "contract", "rollback", "primary_email")):
        return False
    # The doc must convey that the legacy `email` field is retained (during expand).
    # Accept any phrasing where the stems legacy / email / retain co-occur closely,
    # in either legacy-first or email-first order, instead of a single literal string.
    window = r"[\s\S]{0,40}"
    retention_patterns = (
        r"legacy" + window + r"email" + window + r"retain",
        r"email" + window + r"legacy" + window + r"retain",
        r"retain" + window + r"legacy" + window + r"email",
        r"retain" + window + r"email" + window + r"legacy",
    )
    return any(re.search(pattern, text) for pattern in retention_patterns)


record("legacy-normalization", 15, lambda: model.normalize_user({"id": "x", "email": "a"}) == {"id": "x", "primary_email": "a"})
record("current-normalization", 15, lambda: model.normalize_user({"id": "x", "primary_email": "a"}) == {"id": "x", "primary_email": "a"})
record("conflict-validation", 10, conflict)
record("serialization-contract", 10, serialization)
record("migration-idempotency", 15, migration_idempotent)
record("cursor-resume", 10, cursor_resume)
record("migration-no-mutation", 5, no_mutation)
record("observability", 10, observability)
record("documentation", 10, docs_complete)

score = sum(item["weight"] for item in checks if item["passed"])
print(json.dumps({"passed": score == 100, "score": score, "checks": checks}))
sys.exit(0 if score == 100 else 1)
