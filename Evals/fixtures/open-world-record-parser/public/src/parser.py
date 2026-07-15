import re

from .metrics import summarize
from .schema import KNOWN_KINDS


PATTERN = re.compile(r"^(USER|ORDER)\|([a-z_]+)=([^|]*)$")


def parse_record(line):
    match = PATTERN.match(line)
    if not match:
        raise ValueError("invalid record")
    kind, key, value = match.groups()
    if kind not in KNOWN_KINDS:
        raise ValueError("unknown kind")
    return {"kind": kind, "fields": {key: value}}


def parse_batch(lines):
    accepted, rejected = [], []
    for index, line in enumerate(lines):
        try:
            accepted.append(parse_record(line))
        except Exception:
            rejected.append({"index": index, "code": "invalid_record"})
    return {
        "accepted": accepted,
        "rejected": rejected,
        "metrics": {"received": len(lines), "accepted": len(accepted), "rejected": len(rejected), "by_kind": summarize(accepted)},
    }
