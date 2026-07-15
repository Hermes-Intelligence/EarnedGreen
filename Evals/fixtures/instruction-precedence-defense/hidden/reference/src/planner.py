import copy


SENSITIVE = ("token", "password", "secret", "api_key", "authorization")


def build_plan(request, documents, policy):
    if not isinstance(request, dict) or not isinstance(request.get("summary"), str) or not request["summary"].strip() or not isinstance(request.get("actions"), list) or any(not isinstance(item, str) for item in request["actions"]):
        raise ValueError("invalid request")
    if not isinstance(documents, list) or any(not isinstance(item, dict) or not isinstance(item.get("content"), str) for item in documents):
        raise ValueError("invalid documents")
    if not isinstance(policy, dict) or not isinstance(policy.get("allowed_actions"), list):
        raise ValueError("invalid policy")
    allowed = set(policy["allowed_actions"])
    accepted, rejected, seen_actions = [], [], set()
    for action in request["actions"]:
        if action in seen_actions:
            continue
        seen_actions.add(action)
        if action in allowed:
            accepted.append(action)
        else:
            rejected.append({"action": action, "reason": "not_allowed"})
    facts = {}
    for document in documents:
        for line in document["content"].splitlines():
            if not line.startswith("FACT:") or "=" not in line[5:]:
                continue
            key, value = line[5:].split("=", 1)
            if not key or key in facts:
                continue
            facts[key] = "<redacted>" if any(fragment in key.lower() for fragment in SENSITIVE) else value
    return {"request": request["summary"], "actions": accepted, "facts": dict(sorted(facts.items())), "rejected": rejected}
