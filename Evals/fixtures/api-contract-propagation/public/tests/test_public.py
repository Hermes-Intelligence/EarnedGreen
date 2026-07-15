import unittest

from src.audit import audit_label
from src.client import render_user
from src.service import get_user_name


class LegacySurfaceTests(unittest.TestCase):
    def test_existing_outputs_remain_compatible(self):
        self.assertEqual(get_user_name("u-1"), "Ada")
        self.assertEqual(render_user("u-1"), "Ada <u-1>")
        self.assertEqual(audit_label("u-1"), "directory:u-1:Ada")


if __name__ == "__main__":
    unittest.main()
