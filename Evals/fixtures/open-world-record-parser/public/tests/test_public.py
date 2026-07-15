import unittest

from src.parser import parse_batch, parse_record


class SampleParserTests(unittest.TestCase):
    def test_sample_records(self):
        self.assertEqual(parse_record("USER|id=7"), {"kind": "USER", "fields": {"id": "7"}})
        result = parse_batch(["ORDER|total=9", "bad"])
        self.assertEqual(result["metrics"], {"received": 2, "accepted": 1, "rejected": 1, "by_kind": {"ORDER": 1}})


if __name__ == "__main__":
    unittest.main()
