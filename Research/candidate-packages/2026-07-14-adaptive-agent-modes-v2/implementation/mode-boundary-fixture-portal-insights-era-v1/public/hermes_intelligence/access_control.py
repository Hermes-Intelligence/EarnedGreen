"""Infrastructure seam (offline workspace copy): access control. Do not modify."""


def verify_vextrum_access(*a, **k):
    raise RuntimeError("offline workspace: the runtime provides access control")


def verify_internal_access(*a, **k):
    raise RuntimeError("offline workspace: the runtime provides access control")


def verify_universe_access(*a, **k):
    raise RuntimeError("offline workspace: the runtime provides access control")


def fulfill_pregrants(*a, **k):
    raise RuntimeError("offline workspace: the runtime provides access control")
