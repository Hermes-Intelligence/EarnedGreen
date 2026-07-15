def build_plan(request, documents, policy):
    if not isinstance(request, dict) or not isinstance(request.get("summary"), str) or not request["summary"] or not isinstance(request.get("actions"), list):
        raise ValueError("request")
    allowed = set(policy.get("allowed_actions", []))
    actions, rejected, seen = [], [], set()
    for action in request["actions"]:
        if action in seen:
            continue
        seen.add(action)
        if action in allowed:
            actions.append(action)
        else:
            rejected.append({"action": action, "reason": "not_allowed"})
    facts = {}
    for document in documents:
        for line in document.get("content", "").splitlines():
            if not line.startswith("FACT:") or "=" not in line[5:]:
                continue
            key, value = line[5:].split("=", 1)
            if key.isascii() and key.islower() and not any(word in key for word in ("token", "password", "secret", "api_key", "authorization")):
                facts.setdefault(key, value)
    return {"request": request["summary"], "actions": actions, "facts": dict(sorted(facts.items())), "rejected": rejected}
