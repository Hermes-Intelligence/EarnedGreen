"""Infrastructure seam (offline workspace copy): ECS dispatch. Do not modify."""


class EcsDispatchError(Exception):
    pass


def trigger_ontology_generation(*a, **k):
    raise RuntimeError("offline workspace: the runtime provides dispatch")
