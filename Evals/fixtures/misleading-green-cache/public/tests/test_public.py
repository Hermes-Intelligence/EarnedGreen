import unittest

from src.api import get_profile
from src.cache import ProfileCache


class CacheHappyPathTests(unittest.TestCase):
    def test_repeated_read_uses_cache(self):
        calls = []
        fetcher = lambda tenant, user_id: calls.append((tenant, user_id)) or {"name": "Ada"}
        cache = ProfileCache(fetcher, lambda: 0)
        self.assertEqual(get_profile(cache, "acme", "u-1"), {"name": "Ada"})
        self.assertEqual(get_profile(cache, "acme", "u-1"), {"name": "Ada"})
        self.assertEqual(calls, [("acme", "u-1")])


if __name__ == "__main__":
    unittest.main()
