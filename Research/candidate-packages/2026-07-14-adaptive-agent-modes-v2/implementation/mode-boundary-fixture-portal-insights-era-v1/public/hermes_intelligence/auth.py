"""Infrastructure seam (offline workspace copy): authentication.

The live implementation is provided by the runtime/harness. Do not modify.
"""


def redirect_if_no_auth(*a, **k):
    return None


def get_organization_from_token(token):
    raise RuntimeError("offline workspace: the runtime provides auth")


def get_user_id_from_token(token):
    raise RuntimeError("offline workspace: the runtime provides auth")
