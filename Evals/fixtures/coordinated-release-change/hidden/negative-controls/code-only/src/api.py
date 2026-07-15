from .model import normalize_user


def serialize_user(record, include_legacy=False):
    user = normalize_user(record)
    return dict(user, email=user["primary_email"]) if include_legacy else user
