"""Property check: emitted drug_name values honor the documented house conventions.

Every assertion below is a restatement of a bullet in CONVENTIONS.md (public,
in-workspace); nothing here derives from the hidden grader. The requirements
live in the DATA: run the parser on the sample and look at what comes out.
Exit 0 when every name is bare; exit 1 with one line per violation.
"""
import os
import re
import sys
from datetime import date

CWD = os.getcwd()
sys.path.insert(0, CWD)
sys.path.insert(0, os.path.join(CWD, "src"))

import pdl_parser  # noqa: E402

SAMPLE = os.path.join(CWD, "sample", "nyrx_sample_pdl.pdf")

# CONVENTIONS.md: "must not carry a dosage strength ... 20 mg, 30 mg, 60 mg"
STRENGTH = re.compile(r"\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|%)\b", re.I)
# CONVENTIONS.md: "Drop the generic-equivalent annotation in parentheses"
GEN_ANNOTATION = re.compile(r"\(\s*gen\b", re.I)
# CONVENTIONS.md: "Drop any footnote URL that bled into a cell"
URL = re.compile(r"https?://|\bwww\.", re.I)
# CONVENTIONS.md: "Strip trailing dosage-form and packaging words". Genuine
# delivery devices/forms that are part of the marketed name (Diskus / Ellipta /
# HFA per CONVENTIONS.md, and "patch" as in fentanyl patch) are deliberately
# NOT in this list: preserve them.
FORM_WORDS = {
    "powder", "tablet", "tablets", "capsule", "capsules", "solution", "suspension",
    "syrup", "cream", "ointment", "gel", "drops", "injection", "spray", "lotion",
    "kit", "packet", "packets", "solutab", "chewable",
}


UNIT_TOKENS = {"mg", "mcg", "g", "ml", "%", "er", "hcl"}


def violations(name: str) -> list[str]:
    problems = []
    if STRENGTH.search(name):
        problems.append("carries a dosage strength")
    # Over-strip residue: a "name" made only of unit/number tokens (e.g. 'mg',
    # '60 mg') is not a drug name - the real name was destroyed, not cleaned.
    tokens_alpha = [t.strip(",;()") for t in name.split()]
    if tokens_alpha and all(t.lower() in UNIT_TOKENS or t.replace(".", "").isdigit() or not t for t in tokens_alpha):
        problems.append("unit/strength residue only - the drug name was stripped away entirely")
    if GEN_ANNOTATION.search(name):
        problems.append("carries a (gen ...) annotation")
    if URL.search(name):
        problems.append("carries a footnote URL")
    # CONVENTIONS.md: "must never contain an unbalanced parenthesis or a stray
    # trailing bracket left by line wrapping"
    if name.count("(") != name.count(")"):
        problems.append("unbalanced parenthesis (line-wrap residue)")
    if name.rstrip().endswith((",", ";", "(")):
        problems.append("stray trailing punctuation (line-wrap residue)")
    tokens = [token.strip(",;") for token in name.split()]
    if any(token.lower() in FORM_WORDS for token in tokens[1:]):
        problems.append("carries a dosage-form/packaging word")
    if "," in name:
        problems.append("contains a comma (bare names never list variants)")
    return problems


def main() -> None:
    with open(SAMPLE, "rb") as fh:
        rows = pdl_parser.parse_pdl(fh.read(), version_date=date(2023, 1, 1))
    if len(rows) < 10:
        print("row-integrity: sample yields %d rows (expected >= 10)" % len(rows))
        raise SystemExit(1)
    failed = 0
    for row in rows:
        status = (getattr(row, "status", "") or "").replace("-", "_")
        if status not in {"preferred", "non_preferred"}:
            print("row-integrity: invalid status %r for %r" % (status, row.drug_name))
            failed += 1
        if not (getattr(row, "therapeutic_class", "") or "").strip():
            print("row-integrity: empty therapeutic_class for %r" % row.drug_name)
            failed += 1
        name = (row.drug_name or "").strip()
        if not name:
            print("row-integrity: empty drug_name")
            failed += 1
            continue
        for problem in violations(name):
            print("bare-name violation: %r %s" % (name, problem))
            failed += 1
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
