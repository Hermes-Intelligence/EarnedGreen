from .model import normalize_user


def serialize_user(record, include_legacy=False):
    user = normalize_user(record)
    if include_legacy:
        return {"id": user["id"], "primary_email": user["primary_email"], "email": user["primary_email"]}
    return user
