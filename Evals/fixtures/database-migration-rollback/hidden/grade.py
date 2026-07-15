import importlib.util, json, sqlite3, sys
from pathlib import Path

p = Path(sys.argv[1]) / "src/migration.py"
spec = importlib.util.spec_from_file_location("migration", p)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
checks = []
def check(i, v): checks.append((i, bool(v)))
try:
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE)")
    db.execute("INSERT INTO users(id,email) VALUES(7,'real@example.com')"); db.commit()
    m.upgrade(db); m.upgrade(db)
    row = db.execute("SELECT id,email,timezone FROM users").fetchone()
    check("upgrade-idempotent-and-preserves", row == (7, "real@example.com", "UTC"))
    m.downgrade(db); m.downgrade(db)
    cols = [x[1] for x in db.execute("PRAGMA table_info(users)")]
    check("old-schema-restored", cols == ["id", "email"])
    check("row-preserved", db.execute("SELECT id,email FROM users").fetchone() == (7, "real@example.com"))
    try: db.execute("INSERT INTO users(id,email) VALUES(8,'real@example.com')"); unique = False
    except sqlite3.IntegrityError: unique = True
    check("unique-preserved", unique)
    db.rollback(); m.upgrade(db)
    check("reupgrade", "timezone" in [x[1] for x in db.execute("PRAGMA table_info(users)")])
except Exception: check("execution", False)
n = sum(v for _, v in checks)
print(json.dumps({"passed": n == len(checks), "score": 100*n/len(checks), "checks": [{"id": i, "passed": v} for i,v in checks]}))
sys.exit(0 if n == len(checks) else 1)
