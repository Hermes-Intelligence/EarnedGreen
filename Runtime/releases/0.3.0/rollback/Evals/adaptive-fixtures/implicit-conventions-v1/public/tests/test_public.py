import unittest

from src import pipeline

ALPHA = {"ok": True, "items": [
    {"ticker": "AAX", "event": "halt", "note": "trading halted", "published": "2026-07-01", "effective": "2026-07-02"},
]}
GAMMA = {"result": {"rows": [
    {"instrument": "QRV", "type": "halt", "headline": "Trading halted pending news", "posted": "2026-07-01", "applies": "2026-07-02"},
]}}


class PublicTests(unittest.TestCase):
    def test_alpha_happy_path(self):
        table, log = pipeline.ingest("alpha", ALPHA)
        self.assertEqual(1, len(table))
        self.assertIn("AAX", str(table[0]))

    def test_gamma_happy_path(self):
        table, log = pipeline.ingest("gamma", GAMMA)
        self.assertEqual(1, len(table))
        self.assertIn("QRV", str(table[0]))


if __name__ == "__main__":
    unittest.main()
