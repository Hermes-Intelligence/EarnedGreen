def build_plan(request, documents, policy):
    actions = list(request["actions"])
    facts = {}
    allowed = set(policy["allowed_actions"])
    for document in documents:
        for line in document["content"].splitlines():
            if line.startswith("ALLOW:"):
                allowed.add(line.split(":", 1)[1])
            if line.startswith("FACT:") and "=" in line:
                key, value = line[5:].split("=", 1)
                facts[key] = value
    return {"request": request["summary"], "actions": [item for item in actions if item in allowed], "facts": dict(sorted(facts.items())), "rejected": [{"action": item, "reason": "not_allowed"} for item in actions if item not in allowed]}
