"""Emit one line per row FIELD from the sample parse, for the behavioral differential.

One field per line (not one row per line) so the differential's expected-change
patterns can allow drug_name changes (the task) while any status /
therapeutic_class / row-count drift stays an unexpected regression.
"""
import os
import sys
from datetime import date

CWD = os.getcwd()
sys.path.insert(0, CWD)
sys.path.insert(0, os.path.join(CWD, "src"))

import pdl_parser  # noqa: E402

SAMPLE = os.path.join(CWD, "sample", "nyrx_sample_pdl.pdf")


def main() -> None:
    with open(SAMPLE, "rb") as fh:
        rows = pdl_parser.parse_pdl(fh.read(), version_date=date(2023, 1, 1))
    for index, row in enumerate(rows):
        for field in ("status", "therapeutic_class", "subclass", "drug_name"):
            print("row[%d].%s=%s" % (index, field, getattr(row, field, None)))
    print("row_count=%d" % len(rows))


if __name__ == "__main__":
    main()
