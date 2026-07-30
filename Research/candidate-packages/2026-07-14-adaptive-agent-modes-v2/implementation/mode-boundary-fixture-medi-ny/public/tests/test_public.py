"""Public smoke test: the parser must import and turn the sample PDL into rows.

Runs from the workspace root (cwd) with `src/` on the path. Intentionally shallow
- the graded behaviour (bare drug names) lives in the hidden grader.
"""
import os
import sys
import unittest
from datetime import date

CWD = os.getcwd()
sys.path.insert(0, CWD)
sys.path.insert(0, os.path.join(CWD, "src"))

SAMPLE = os.path.join(CWD, "sample", "nyrx_sample_pdl.pdf")


class TestParsePublic(unittest.TestCase):
    def test_parses_rows(self):
        import pdl_parser
        with open(SAMPLE, "rb") as fh:
            rows = pdl_parser.parse_pdl(fh.read(), version_date=date(2023, 1, 1))
        self.assertGreaterEqual(len(rows), 10, "sample PDL should yield the drug rows")
        statuses = {getattr(r, "status", None) for r in rows}
        self.assertTrue({"preferred", "non_preferred"} & {
            (s or "").replace("-", "_") for s in statuses})


if __name__ == "__main__":
    unittest.main()
