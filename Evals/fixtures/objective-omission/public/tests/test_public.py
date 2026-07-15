import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from policy import build_policy


class PublicTests(unittest.TestCase):
    def test_defaults_and_order(self):
        request = {"name": " daily ", "targets": [{"type": "URL", "value": "Example"}]}
        result = build_policy(request)
        self.assertEqual(list(result), ["name", "targets", "timeout_seconds", "retries", "dry_run", "metadata"])
        self.assertEqual((result["timeout_seconds"], result["retries"], result["dry_run"]), (30, 2, True))

    def test_does_not_mutate_top_level(self):
        request = {"name": "job", "targets": [{"type": "queue", "value": "A"}]}
        original = copy.deepcopy(request)
        build_policy(request)
        self.assertEqual(request, original)


if __name__ == "__main__": unittest.main()
