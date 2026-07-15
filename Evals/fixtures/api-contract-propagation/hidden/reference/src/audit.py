from . import service


def audit_label(user_id):
    user = service.get_user(user_id)["user"]
    return f"directory:{user['id']}:{user['display_name']}"
