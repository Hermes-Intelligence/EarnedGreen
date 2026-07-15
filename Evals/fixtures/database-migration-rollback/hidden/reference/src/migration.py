def _columns(conn):
    return [row[1] for row in conn.execute("PRAGMA table_info(users)")]

def upgrade(conn):
    if "timezone" not in _columns(conn):
        with conn:
            conn.execute("ALTER TABLE users ADD COLUMN timezone TEXT NOT NULL DEFAULT 'UTC'")

def downgrade(conn):
    if "timezone" not in _columns(conn):
        return
    with conn:
        conn.execute("ALTER TABLE users RENAME TO users_with_timezone")
        conn.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE)")
        conn.execute("INSERT INTO users(id,email) SELECT id,email FROM users_with_timezone")
        conn.execute("DROP TABLE users_with_timezone")
