import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from entity_parser import parse_entities


class PublicTests(unittest.TestCase):
    def test_known_sample(self):
        records = [{"name": " Ada ", "type": " PERSON "}, {"name": "OpenAI", "type": "organization"}]
        self.assertEqual(parse_entities(records), [{"name": "Ada", "type": "person"}, {"name": "OpenAI", "type": "organization"}])

    def test_deduplicates_and_does_not_mutate(self):
        records = [{"name": "Ada", "type": "person"}, {"name": "ada", "type": "PERSON"}]
        original = copy.deepcopy(records)
        self.assertEqual(len(parse_entities(records)), 1)
        self.assertEqual(records, original)


if __name__ == "__main__":
    unittest.main()
