from .metrics import summarize


def parse_record(line):
    sections = line.split("|")
    if len(sections) < 2 or not sections[0]:
        raise ValueError("invalid")
    fields = {}
    for section in sections[1:]:
        if section.count("=") != 1:
            raise ValueError("invalid")
        key, value = section.split("=", 1)
        if not key or key in fields:
            raise ValueError("invalid")
        fields[key] = value
    return {"kind": sections[0], "fields": fields}


def parse_batch(lines):
    batch = list(lines)
    accepted, rejected = [], []
    for index, line in enumerate(batch):
        try:
            accepted.append(parse_record(line))
        except Exception:
            rejected.append({"index": index, "code": "invalid_record"})
    return {"accepted": accepted, "rejected": rejected, "metrics": {"received": len(batch), "accepted": len(accepted), "rejected": len(rejected), "by_kind": summarize(accepted)}}
