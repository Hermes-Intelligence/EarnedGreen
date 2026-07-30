from .serializer import serialize


def export_digest(records, registry):
    """Audit export path, registry-aware and schema-versioned."""
    return [serialize(record, registry) for record in records]
