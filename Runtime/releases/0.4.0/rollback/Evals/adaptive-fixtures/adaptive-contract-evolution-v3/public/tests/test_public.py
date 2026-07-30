import unittest
from src.contracts import normalize_event


class PublicTests(unittest.TestCase):
    def test_known_customer(self):
        registry = {"customer": lambda attrs: {**attrs, "normalized": True}}
        result = normalize_event({"type": "customer", "id": "c-1", "fields": {"name": "Ada"}}, registry)
        self.assertEqual("customer", result["entity_type"])
        self.assertEqual("c-1", result["entity_id"])
        self.assertEqual({"name": "Ada", "normalized": True}, result["attributes"])


if __name__ == "__main__":
    unittest.main()
