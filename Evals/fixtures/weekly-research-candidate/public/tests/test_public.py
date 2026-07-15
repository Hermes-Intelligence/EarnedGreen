import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from research import build_candidate

class Tests(unittest.TestCase):
    def test_returns_created_path(self):
        with tempfile.TemporaryDirectory() as d:
            result = build_candidate(d, "run-public", [{"id":"S1","url":"https://example.com/source"}], [])
            self.assertTrue(Path(result).exists())

if __name__ == "__main__": unittest.main()
