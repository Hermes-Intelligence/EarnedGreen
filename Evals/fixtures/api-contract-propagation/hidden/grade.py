import importlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root))
checks = []


def record(identifier, weight, fn):
    try:
        passed = bool(fn())
    except Exception:
        passed = False
    checks.append({"id": identifier, "weight": weight, "passed": passed})


directory = importlib.import_module("src.directory")
service = importlib.import_module("src.service")
client = importlib.import_module("src.client")
audit = importlib.import_module("src.audit")


def invalid_ids():
    for value in (None, "", "   ", 7):
        try:
            service.get_user(value)
            return False
        except ValueError:
            pass
    return True


def unknown_id():
    try:
        service.get_user("not-present")
        return False
    except LookupError:
        return True


def dynamic_user():
    directory.USERS["future:九"] = {"name": "Zoë"}
    try:
        return service.get_user("future:九")["user"] == {"id": "future:九", "display_name": "Zoë"}
    finally:
        directory.USERS.pop("future:九", None)


def exact_schema():
    value = service.get_user("u-2")
    return value == {"user": {"id": "u-2", "display_name": "Lin"}, "meta": {"source": "directory", "version": 2}}


def client_consumes_new_contract():
    source = (root / "src/client.py").read_text(encoding="utf-8")
    if "service.get_user(" not in source:
        return False
    original = service.get_user
    service.get_user = lambda user_id: {"user": {"id": user_id, "display_name": "Injected"}, "meta": {"source": "directory", "version": 2}}
    try:
        return client.render_user("external") == "Injected <external>"
    finally:
        service.get_user = original


def audit_consumes_new_contract():
    source = (root / "src/audit.py").read_text(encoding="utf-8")
    if "service.get_user(" not in source:
        return False
    original = service.get_user
    service.get_user = lambda user_id: {"user": {"id": user_id, "display_name": "Injected"}, "meta": {"source": "directory", "version": 2}}
    try:
        return audit.audit_label("external") == "directory:external:Injected"
    finally:
        service.get_user = original


record("current-envelope", 15, lambda: service.get_user("u-1")["user"]["display_name"] == "Ada")
record("exact-schema", 10, exact_schema)
record("runtime-growth", 15, dynamic_user)
record("unknown-id", 10, unknown_id)
record("legacy-wrapper", 10, lambda: service.get_user_name("u-2") == "Lin")
record("client-consumer", 15, client_consumes_new_contract)
record("audit-consumer", 15, audit_consumes_new_contract)
record("input-validation", 10, invalid_ids)

score = sum(item["weight"] for item in checks if item["passed"])
print(json.dumps({"passed": score == 100, "score": score, "checks": checks}))
sys.exit(0 if score == 100 else 1)
