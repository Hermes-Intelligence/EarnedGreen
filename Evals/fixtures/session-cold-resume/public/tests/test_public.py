import sys, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from checkpoint import load_checkpoint, save_checkpoint

class Tests(unittest.TestCase):
    def test_roundtrip(self):
        state = {"schema_version":1,"objective_id":"OBJ-1","task":"continue","status":"in_progress","updated_at":datetime.now(timezone.utc).isoformat(),"decisions":[],"evidence":[],"blockers":[],"next_action":"run tests","changed_paths":[]}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "checkpoint.json"; save_checkpoint(p, state)
            self.assertEqual(load_checkpoint(p)["task"], "continue")

if __name__ == "__main__": unittest.main()
