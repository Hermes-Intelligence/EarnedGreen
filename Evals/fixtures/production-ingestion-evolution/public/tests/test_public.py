import copy
import unittest

from src.pipeline import process_batch, summarize


class PublicContractTests(unittest.TestCase):
    def test_alpha_happy_path_and_summary(self):
        specs = {"alpha": {"id_path": "meta.id", "timestamp_path": "meta.time", "kind_path": "type", "payload_path": "data", "entity_paths": {"account": "data.account_id", "region": "data.region"}, "kind_aliases": {"created": "entity.created"}}}
        records = [{"provider": "alpha", "meta": {"id": "evt-1", "time": 10}, "type": "created", "data": {"account_id": "a-7", "region": "eu", "value": 3}}]
        before = copy.deepcopy(records)
        result = process_batch(records, {}, specs)
        self.assertEqual(records, before)
        self.assertEqual(result["metrics"], {"received": 1, "accepted": 1, "skipped": 0, "rejected": 0})
        self.assertEqual(result["accepted"][0]["kind"], "entity.created")
        self.assertEqual(result["accepted"][0]["entities"], {"account": "a-7", "region": "eu"})
        self.assertEqual(summarize(result), {"total": 1, "by_provider": {"alpha": 1}, "by_kind": {"entity.created": 1}, "entity_keys": ["account", "region"]})


if __name__ == "__main__":
    unittest.main()
