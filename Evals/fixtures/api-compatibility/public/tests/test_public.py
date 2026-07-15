import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from client import parse_user

class Tests(unittest.TestCase):
    def test_legacy_payload(self):
        self.assertEqual(parse_user({"id": "u-1", "name": "Ada"}), {"id": "u-1", "name": "Ada"})

if __name__ == "__main__": unittest.main()
