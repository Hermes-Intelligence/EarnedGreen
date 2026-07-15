from .service import get_user_name


def render_user(user_id):
    return f"{get_user_name(user_id)} <{user_id}>"
