from .metrics import increment


def normalize_user(record):
    user_id = record.get("id")
    if not isinstance(user_id, str) or not user_id:
        raise ValueError("id")
    old, new = record.get("email"), record.get("primary_email")
    if old is not None and new is not None and old != new:
        increment("conflicts")
        raise ValueError("conflict")
    if new is not None:
        increment("current_reads")
        return {"id": user_id, "primary_email": new}
    if old is not None:
        increment("legacy_reads")
        return {"id": user_id, "primary_email": old}
    raise ValueError("email")
