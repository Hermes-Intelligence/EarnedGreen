from . import service


def render_user(user_id):
    user = service.get_user(user_id)["user"]
    return f"{user['display_name']} <{user['id']}>"
