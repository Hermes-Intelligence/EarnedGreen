from .serializer import serialize


def export_digest(records):
    """Audit export path: serialize every record into a digest line.

    Reaches record normalization indirectly, two hops away, through
    `serializer.serialize`. Retained from the legacy contract.
    """
    return [serialize(record) for record in records]
