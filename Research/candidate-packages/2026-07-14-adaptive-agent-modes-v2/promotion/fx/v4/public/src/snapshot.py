from .digest_helper import digest_line


def build_snapshot(records):
    """Cache snapshot layer: map every record id to its snapshot line.

    Reaches record normalization indirectly, two hops away, through
    `digest_helper.digest_line`. Retained from the legacy contract.
    """
    return {record["id"]: digest_line(record) for record in records}
