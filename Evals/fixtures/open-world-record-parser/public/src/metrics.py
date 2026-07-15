def summarize(events):
    by_kind = {}
    for event in events:
        by_kind[event["kind"]] = by_kind.get(event["kind"], 0) + 1
    return dict(sorted(by_kind.items()))
