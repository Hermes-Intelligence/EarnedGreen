# Task: propagate a versioned API contract across every consumer

The directory service is moving from the scalar `get_user_name(user_id)` API to a versioned canonical envelope. Implement:

```python
get_user(user_id) -> {
    "user": {"id": string, "display_name": string},
    "meta": {"source": "directory", "version": 2}
}
```

Requirements:

- `user_id` must be a non-empty, non-whitespace string; invalid values raise `ValueError`.
- Unknown IDs raise `LookupError`.
- The returned mapping must have exactly the fields shown above and must not expose or mutate the directory's internal record.
- Preserve `get_user_name(user_id)` as a backward-compatible wrapper.
- Update both `client.render_user` and `audit.audit_label` to consume `service.get_user` directly. Their public output remains unchanged.
- Do not special-case the users currently present in `directory.USERS`; that mapping can grow at runtime.
- Keep module boundaries intact. The clients must consume the service contract rather than reading directory storage directly.

Do not modify `task.md` or existing public tests.
