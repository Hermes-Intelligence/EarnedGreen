from .service import get_user_name


def audit_label(user_id):
    return f"directory:{user_id}:{get_user_name(user_id)}"
