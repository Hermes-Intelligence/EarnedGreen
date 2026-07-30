"""Public smoke test: the happy path still works.

Deliberately asserts NOTHING about the new error-handling behaviour — that is
the hidden grader's job, and a public test that encoded it would hand over the
answer. Good files in, uploads out, files archived: the baseline contract.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

from hermes_intelligence.hermes_tools.cloud import aws  # noqa: E402


class HappyPath(unittest.TestCase):
    def test_good_files_flow_through(self):
        import etl_base
        aws._reset(["a.json", "b.json"], {"a.json": "alpha", "b.json": "beta"})
        uploads = []
        etl_base.run_etl("drop/", lambda content, file: content.upper(), uploads.append)
        self.assertEqual(uploads, ["ALPHA", "BETA"])
        self.assertIn("archive:a.json", aws.EVENTS)
        self.assertIn("archive:b.json", aws.EVENTS)

    def test_no_archive_leaves_files_in_place(self):
        import etl_base
        aws._reset(["c.json"], {"c.json": "gamma"})
        uploads = []
        etl_base.run_etl("drop/", lambda content, file: content, uploads.append, True)
        self.assertEqual(uploads, ["gamma"])
        self.assertNotIn("archive:c.json", aws.EVENTS)


if __name__ == "__main__":
    unittest.main()
