USERS = {
    "u-1": {"name": "Ada"},
    "u-2": {"name": "Lin"},
}


def lookup_name(user_id):
    try:
        return USERS[user_id]["name"]
    except KeyError as exc:
        raise LookupError(user_id) from exc
