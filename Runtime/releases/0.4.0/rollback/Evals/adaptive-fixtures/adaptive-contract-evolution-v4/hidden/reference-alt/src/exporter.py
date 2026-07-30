from .serializer import serialize


def export_digest(records, registry):
    lines = []
    for record in records:
        lines.append(serialize(record, registry))
    return lines
