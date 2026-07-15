from .directory import lookup_name


def get_user(user_id):
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("user_id")
    name = lookup_name(user_id)
    return {"user": {"id": user_id, "display_name": name}, "meta": {"source": "directory", "version": 2}}


def get_user_name(user_id):
    return get_user(user_id)["user"]["display_name"]
