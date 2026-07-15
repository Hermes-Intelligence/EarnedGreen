import sqlite3, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from migration import upgrade

class Tests(unittest.TestCase):
    def test_upgrade_adds_timezone(self):
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE)")
        upgrade(db)
        self.assertIn("timezone", [x[1] for x in db.execute("PRAGMA table_info(users)")])

if __name__ == "__main__": unittest.main()
