# Task: make a schema migration repeatable and reversible

The existing `users(id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE)` table contains production data. Implement idempotent `upgrade(conn)` to add `timezone TEXT NOT NULL DEFAULT 'UTC'`, and idempotent `downgrade(conn)` to restore the exact old public schema while preserving `id`, `email` and uniqueness. Both directions must tolerate being called twice. Do not drop user rows, infer values from sample emails or require a fresh database.
