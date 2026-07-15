from .metrics import increment


def _required(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"invalid {name}")
    return value


def normalize_user(record):
    if not isinstance(record, dict):
        raise ValueError("record")
    user_id = _required(record.get("id"), "id")
    legacy, current = record.get("email"), record.get("primary_email")
    if legacy is not None and current is not None and legacy != current:
        increment("conflicts")
        raise ValueError("email conflict")
    if current is not None:
        email = _required(current, "primary_email")
        increment("current_reads")
    elif legacy is not None:
        email = _required(legacy, "email")
        increment("legacy_reads")
    else:
        raise ValueError("email missing")
    return {"id": user_id, "primary_email": email}
