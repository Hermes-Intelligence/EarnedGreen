from .metrics import increment


def normalize_user(record):
    old, new = record.get("email"), record.get("primary_email")
    if old is not None and new is not None and old != new:
        increment("conflicts")
        raise ValueError("conflict")
    if new is not None:
        increment("current_reads")
        return {"id": record["id"], "primary_email": new}
    increment("legacy_reads")
    return {"id": record["id"], "primary_email": old}
