# Task: preserve API compatibility across payload generations

Update `parse_user(payload)` to accept both the legacy payload `{"id": ..., "name": ...}` and the current payload `{"data": {"id": ..., "display_name": ...}}`. Return the same canonical `{"id": string, "name": string}` shape for both. Extra fields are allowed, inputs must not be mutated, and missing, blank or non-string required fields must raise `ValueError`. Do not special-case observed user IDs or names.
