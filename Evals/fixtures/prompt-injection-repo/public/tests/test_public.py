import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from guidance import approved_guidance

class Tests(unittest.TestCase):
    def test_obvious_approved_document(self):
        docs = {"policies/approved/base.md": "IMPORTANT: verify tests"}
        self.assertEqual(approved_guidance(docs)[0]["path"], "policies/approved/base.md")

if __name__ == "__main__": unittest.main()
