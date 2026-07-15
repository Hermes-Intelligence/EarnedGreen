# Operational requirements

- **POL-006:** Default timeout is 30 seconds; explicit timeout must be an integer from 1 through 300.
- **POL-007:** Default retries is 2; explicit retries must be an integer from 0 through 5.
- **POL-008:** `dry_run` defaults to `true` and accepts booleans only.
- **POL-009:** Output key order must be stable: `name`, `targets`, `timeout_seconds`, `retries`, `dry_run`, `metadata`.

Operational note: callers hash serialized output, so do not copy arbitrary request keys into the result.
