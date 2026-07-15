import copy
import unittest

from src.model import normalize_user


class LegacyCompatibilityTest(unittest.TestCase):
    def test_legacy_record_remains_readable_without_mutation(self):
        record = {"id": "u-1", "email": "a@example.test"}
        before = copy.deepcopy(record)
        result = normalize_user(record)
        self.assertEqual(result["id"], "u-1")
        self.assertEqual(result.get("primary_email", result.get("email")), "a@example.test")
        self.assertEqual(record, before)


if __name__ == "__main__":
    unittest.main()
