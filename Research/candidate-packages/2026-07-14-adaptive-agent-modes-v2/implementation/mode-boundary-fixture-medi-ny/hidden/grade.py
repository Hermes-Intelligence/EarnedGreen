#!/usr/bin/env python
"""Hidden grader (medi-ny-parser-rework-v1) with per-check isolation.

History-grounded fixture. The task is the REAL, underspecified NYRx PDL parser
rework shipped in HermesAirflow commits 9835c408..a7ed0fd1 (2026-07-01): the
before-state parser already isolates columns by font geometry but emits drug
NAMES that carry strengths / dosage forms / (gen ...) annotations / column bleed;
the rework added a deterministic drug-name cleaning pass so the emitted name is
the bare drug. This grader runs the CANDIDATE's parse_pdl on the committed
synthetic NYRx-template sample PDF and asserts the documented behaviours
SEMANTICALLY (never string-equality against one implementation's output):

  * basic-functionality     - rows are emitted with preferred/non_preferred status
                              and the therapeutic class set from the section header.
  * trailing-strength-strip - no emitted name carries a dosage strength
                              ("20 mg"); duloxetine survives as a bare name.
  * gen-annotation-strip    - the generic-equivalent "(gen ...)" annotation is
                              gone; Cymbalta survives bare.
  * dosage-form-strip       - trailing dosage-form/packaging words are gone
                              ("Buphenyl powder, tablet" -> "Buphenyl").
  * leading-bleed-strip     - a device/form word bled in from an adjacent column
                              is stripped ("Diskus Depakote" -> "Depakote").
  * brand-device-preserve   - a device that is genuinely part of the brand is
                              KEPT (Advair Diskus / Trelegy Ellipta / Proventil
                              HFA); guards against an over-eager stripper.
  * paren-wrap-reassembly   - no name has an unbalanced parenthesis / stray
                              bracket from line wrapping.
  * url-bleed-strip         - a footnote URL bled into a cell is dropped.

Every check runs inside its own record() boundary, so a hostile candidate that
raises anywhere can never collapse the other dimensions. The before-state parser
(historical negative control) fails every strip dimension while passing
basic-functionality and brand-device-preserve, which is what makes this a real
discriminating fixture rather than a synthetic one.
"""
import importlib
import json
import re
import sys
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

WORKSPACE = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(WORKSPACE))            # config.py (the parser does `import config`)
sys.path.insert(0, str(WORKSPACE / "src"))    # pdl_parser.py

SAMPLE = WORKSPACE / "sample" / "nyrx_sample_pdl.pdf"

checks = []


def record(check_id, weight, probe):
    try:
        outcome = probe()
        passed, detail = (outcome, "") if isinstance(outcome, bool) else outcome
    except BaseException as exc:  # noqa: BLE001 - hostile candidates may raise anything
        passed, detail = False, "%s: %s" % (type(exc).__name__, exc)
    checks.append({"id": check_id, "passed": bool(passed), "weight": weight,
                   "detail": str(detail)[:400]})


_WS = re.compile(r"\s+")
_STRENGTH = re.compile(r"\b\d[\d.,/x-]*\s*(?:mg|mcg|ml|g|gm|units?|u|meq|iu|%)\b", re.I)
_LEADING_BLEED = {"diskus", "hfa", "ellipta", "respiclick", "handihaler",
                  "suspension", "powder", "tablet", "cream", "gel", "solution"}
_FORM_NOISE = ("powder", "tablet", "capsule", "ointment")


def norm(text):
    return _WS.sub(" ", (text or "")).strip()


def parse_rows():
    """Import the candidate parser and run it on the sample PDF. Cached per process."""
    if not SAMPLE.is_file():
        raise FileNotFoundError("sample PDF missing: %s" % SAMPLE)
    for mod in ("pdl_parser", "config"):
        sys.modules.pop(mod, None)
    parser = importlib.import_module("pdl_parser")
    rows = parser.parse_pdl(SAMPLE.read_bytes(), version_date=date(2023, 1, 1))
    return rows


_ROWS = None


def rows():
    global _ROWS
    if _ROWS is None:
        _ROWS = parse_rows()
    return _ROWS


def field(row, name, index=None):
    if isinstance(row, dict):
        return row.get(name)
    val = getattr(row, name, None)
    if val is None and index is not None:
        try:
            val = row[index]
        except Exception:
            val = None
    return val


def names():
    out = []
    for r in rows():
        nm = norm(field(r, "drug_name", 0))
        if nm:
            out.append(nm)
    return out


def name_set():
    return {n.lower() for n in names()}


def statuses():
    out = set()
    for r in rows():
        st = norm(field(r, "status")).lower().replace("-", "_")
        if st:
            out.add(st)
    return out


def probe_basic_functionality():
    rs = rows()
    if len(rs) < 10:
        return False, "expected >= 10 coverage rows from the sample PDL, got %d" % len(rs)
    st = statuses()
    if not ({"preferred", "non_preferred"} <= st):
        return False, "both preferred and non_preferred statuses must appear, got %r" % (sorted(st),)
    classes = {norm(field(r, "therapeutic_class")).lower() for r in rs}
    if not any("analgesic" in c for c in classes):
        return False, "therapeutic_class not set from the section header (no 'Analgesics'): %r" % (sorted(classes),)
    return True, ""


def probe_trailing_strength():
    bad = [n for n in names() if _STRENGTH.search(n)]
    if bad:
        return False, "drug names still carry a dosage strength (must be stripped): %r" % (bad[:5],)
    if "duloxetine" not in name_set():
        return False, "expected the bare name 'duloxetine' to survive strength stripping; names=%r" % (sorted(name_set())[:15],)
    return True, ""


def probe_gen_annotation():
    bad = [n for n in names() if "(gen" in n.lower()]
    if bad:
        return False, "generic-equivalent '(gen ...)' annotation not stripped: %r" % (bad[:5],)
    if "cymbalta" not in name_set():
        return False, "expected the bare brand 'Cymbalta' after dropping its (gen ...) annotation"
    return True, ""


def probe_dosage_form():
    bad = [n for n in names() if any(w in n.lower() for w in _FORM_NOISE)]
    if bad:
        return False, "trailing dosage-form/packaging words not stripped: %r" % (bad[:5],)
    if "buphenyl" not in name_set():
        return False, "expected the bare name 'Buphenyl' after stripping 'powder, tablet'"
    return True, ""


def probe_leading_bleed():
    if "depakote" not in name_set():
        return False, "expected 'Depakote' as a bare name after stripping the leading 'Diskus' bleed"
    bad = [n for n in names() if n.split() and n.split()[0].lower().strip("()") in _LEADING_BLEED]
    if bad:
        return False, "a drug name still STARTS with a bled-in device/form word: %r" % (bad[:5],)
    return True, ""


def probe_brand_device_preserve():
    need = {"advair diskus", "trelegy ellipta", "proventil hfa"}
    missing = sorted(need - name_set())
    if missing:
        return False, ("a trailing brand device was wrongly stripped (must be preserved): "
                       "missing %r; names=%r" % (missing, sorted(name_set())[:15]))
    return True, ""


def probe_paren_wrap():
    bad = [n for n in names() if n.count("(") != n.count(")") or n.endswith(")") or n.endswith("(")]
    if bad:
        return False, "unbalanced parenthesis / stray bracket from line wrapping not repaired: %r" % (bad[:5],)
    if "fentanyl patch" not in name_set() or "avinza" not in name_set():
        return False, ("expected 'fentanyl patch' and 'Avinza' as clean names after wrap repair; "
                       "names=%r" % (sorted(name_set())[:15],))
    return True, ""


def probe_url_bleed():
    bad = [n for n in names() if "http" in n.lower() or "www." in n.lower()]
    if bad:
        return False, "a footnote URL bled into a drug name and was not stripped: %r" % (bad[:5],)
    if "aspirin" not in name_set():
        return False, "expected the bare name 'aspirin' after dropping the bled-in URL"
    return True, ""


record("basic-functionality", 10, probe_basic_functionality)
record("trailing-strength-strip", 9, probe_trailing_strength)
record("gen-annotation-strip", 8, probe_gen_annotation)
record("dosage-form-strip", 8, probe_dosage_form)
record("leading-bleed-strip", 8, probe_leading_bleed)
record("brand-device-preserve", 7, probe_brand_device_preserve)
record("paren-wrap-reassembly", 7, probe_paren_wrap)
record("url-bleed-strip", 7, probe_url_bleed)

score = round(sum(row["weight"] for row in checks if row["passed"]) * 100
              / sum(row["weight"] for row in checks)) if checks else 0
result = {"passed": score == 100, "score": score, "checks": checks}
print(json.dumps(result, ensure_ascii=False))
raise SystemExit(0 if result["passed"] else 1)
