def upgrade(conn):
    conn.execute("ALTER TABLE users ADD COLUMN timezone TEXT NOT NULL DEFAULT 'UTC'")

def downgrade(conn):
    pass
