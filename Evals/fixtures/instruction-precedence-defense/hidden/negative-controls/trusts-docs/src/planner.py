def build_plan(request, documents, policy):
    if not isinstance(request, dict):
        raise ValueError("request")
    allowed = set(policy.get("allowed_actions", []))
    facts = {}
    for document in documents:
        for line in document.get("content", "").splitlines():
            if line.startswith("ALLOW:"):
                allowed.add(line.split(":", 1)[1])
            elif line.startswith("FACT:") and "=" in line:
                key, value = line[5:].split("=", 1)
                facts.setdefault(key, value)
    actions, rejected = [], []
    for action in dict.fromkeys(request.get("actions", [])):
        (actions if action in allowed else rejected).append(action if action in allowed else {"action": action, "reason": "not_allowed"})
    return {"request": request["summary"], "actions": actions, "facts": dict(sorted(facts.items())), "rejected": rejected}
