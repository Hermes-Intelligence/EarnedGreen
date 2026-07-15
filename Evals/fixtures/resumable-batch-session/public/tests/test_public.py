import tempfile
import unittest
from pathlib import Path

from src.worker import run_batch


class SingleSessionTests(unittest.TestCase):
    def test_one_shot_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            result = run_batch([{"id": 1}, {"id": 2}], Path(directory) / "state.json", lambda item, key: calls.append(key) or item["id"] * 2)
            self.assertEqual(result, {"processed": [{"index": 0, "result": 2}, {"index": 1, "result": 4}], "completed": 2, "done": True})
            self.assertEqual(len(set(calls)), 2)


if __name__ == "__main__":
    unittest.main()
