import unittest

from src import pipeline
from src.consumers import audit_trail, venue_dashboard

ALPHA = {"ok": True, "items": [
    {"ticker": "AAX", "event": "halt", "note": "Trading halted pending news",
     "published": "2026-07-01", "effective": "2026-07-02", "rev": 0, "key": "ALP-83411"},
]}

EPSILON = {"envelope": {"status": "OK", "events": [
    {"ric": "QRV", "category": "halt", "text": "Trading halted pending news",
     "released": "2026-07-01", "in_force": "2026-07-02", "ref": "EPS-1001"},
    {"ric": "ZMT", "category": "halt", "text": "Volatility pause",
     "released": "2026-07-01", "in_force": "2026-07-01", "ref": "EPS-1002"},
]}}


class PublicTests(unittest.TestCase):
    def test_alpha_happy_path(self):
        table, log = pipeline.ingest("alpha", ALPHA)
        self.assertEqual(1, len(table))
        self.assertIn("AAX", str(table[0]))

    def test_alpha_dashboard_renders(self):
        table, log = pipeline.ingest("alpha", ALPHA)
        rendered = str(venue_dashboard.render(table))
        self.assertIn("alpha", rendered.lower())

    def test_alpha_audit_replays(self):
        table, log = pipeline.ingest("alpha", ALPHA)
        summary = audit_trail.replay(log)
        self.assertTrue(summary)

    def test_epsilon_happy_path(self):
        table, log = pipeline.ingest("epsilon", EPSILON)
        self.assertEqual(2, len(table))
        self.assertIn("QRV", str(table[0]))


if __name__ == "__main__":
    unittest.main()


class PublicSmokeTests(unittest.TestCase):
    def test_epsilon_sample_file_parses(self):
        import json
        from pathlib import Path
        payload = json.loads(Path("data/epsilon-sample.json").read_text(encoding="utf-8"))
        self.assertEqual("OK", payload["envelope"]["status"])
        self.assertGreaterEqual(len(payload["envelope"]["events"]), 4)

    def test_run_order_blocks_exist(self):
        from src.scheduler import registry
        self.assertIn("src.scheduler.run_resolution", registry.RUN_ORDER)
        self.assertIn("src.scheduler.run_exports", registry.RUN_ORDER)
        self.assertLess(registry.RUN_ORDER.index("src.scheduler.run_resolution"),
                        registry.RUN_ORDER.index("src.scheduler.run_exports"))
