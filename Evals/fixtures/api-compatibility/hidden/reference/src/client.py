def parse_user(payload):
    if not isinstance(payload, dict):
        raise ValueError("payload")
    if "data" in payload:
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ValueError("data")
        user_id, name = data.get("id"), data.get("display_name")
    else:
        user_id, name = payload.get("id"), payload.get("name")
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("id")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name")
    return {"id": user_id, "name": name}
