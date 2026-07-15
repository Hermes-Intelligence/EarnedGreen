from .metrics import summarize


def _split_raw(text, delimiter):
    if not isinstance(text, str):
        raise ValueError("record must be text")
    parts, current = [], []
    escaped = False
    for char in text:
        if escaped:
            current.extend(("\\", char))
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == delimiter:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    if escaped:
        raise ValueError("dangling escape")
    parts.append("".join(current))
    return parts


def _unescape(value):
    result = []
    index = 0
    while index < len(value):
        if value[index] != "\\":
            result.append(value[index])
            index += 1
            continue
        if index + 1 >= len(value) or value[index + 1] not in "|=\\":
            raise ValueError("unsupported escape")
        result.append(value[index + 1])
        index += 2
    return "".join(result)


def parse_record(line):
    sections = _split_raw(line, "|")
    if len(sections) < 2:
        raise ValueError("missing fields")
    kind = _unescape(sections[0])
    if not kind:
        raise ValueError("blank kind")
    fields = {}
    for section in sections[1:]:
        pair = _split_raw(section, "=")
        if len(pair) != 2:
            raise ValueError("invalid field")
        key, value = _unescape(pair[0]), _unescape(pair[1])
        if not key or key in fields:
            raise ValueError("invalid key")
        fields[key] = value
    return {"kind": kind, "fields": fields}


def parse_batch(lines):
    batch = list(lines)
    accepted, rejected = [], []
    for index, line in enumerate(batch):
        try:
            accepted.append(parse_record(line))
        except ValueError:
            rejected.append({"index": index, "code": "invalid_record"})
    return {"accepted": accepted, "rejected": rejected, "metrics": {"received": len(batch), "accepted": len(accepted), "rejected": len(rejected), "by_kind": summarize(accepted)}}
