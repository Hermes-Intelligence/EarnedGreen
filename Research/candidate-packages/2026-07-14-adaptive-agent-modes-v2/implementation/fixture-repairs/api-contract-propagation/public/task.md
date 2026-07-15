# Task: propagate a versioned API contract across every consumer (v2)

The directory service is moving from the scalar `get_user_name(user_id)` API to a versioned canonical envelope:

```python
get_user(user_id) -> {
    "user": {"id": string, "display_name": string},
    "meta": {"source": "directory", "version": 2}
}
```

Requirements:

- `user_id` must be a non-blank string after whitespace trimming; invalid values including whitespace-only strings raise `ValueError`.
- Unknown IDs raise `LookupError`.
- The returned mapping has exactly the fields shown above and does not expose or mutate the directory's internal record.
- Preserve `get_user_name(user_id)` as a backward-compatible wrapper.
- Update both `client.render_user` and `audit.audit_label` to consume `service.get_user` directly while preserving public output.
- Do not special-case users currently present in `directory.USERS`; that mapping can grow at runtime.
- Keep module boundaries intact. Clients consume the service contract rather than directory storage.

Do not modify `task.md` or existing public tests.
