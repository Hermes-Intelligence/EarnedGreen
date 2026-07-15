import unittest

from src.planner import build_plan


class BenignDocumentTest(unittest.TestCase):
    def test_allowed_action_and_fact(self):
        policy = {"allowed_actions": ["read"], "denied_actions": []}
        result = build_plan({"summary": "inspect", "actions": ["read"]}, [{"content": "FACT:region=eu"}], policy)
        self.assertEqual(result, {"request": "inspect", "actions": ["read"], "facts": {"region": "eu"}, "rejected": []})


if __name__ == "__main__":
    unittest.main()
