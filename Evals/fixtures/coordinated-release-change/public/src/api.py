from .model import normalize_user


def serialize_user(record, include_legacy=False):
    return normalize_user(record)
