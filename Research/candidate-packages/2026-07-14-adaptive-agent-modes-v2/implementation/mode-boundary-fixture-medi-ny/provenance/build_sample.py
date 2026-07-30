"""Provenance builder for the committed synthetic NYRx-template sample PDL.

THIS FILE MUST NOT LIVE UNDER public/. `prepare_adaptive_run` copies public/
wholesale into the agent's workspace, and the docstring below names the rework's
own functions (`_clean_drug_name`, `_form_vocab`), the Hermes commits, and states
that the sample rows are the noise patterns the fix was written to eliminate.
Sitting in public/sample/ (as it did until 2026-07-16) that is a PROVENANCE LEAK:
it hands every arm the shape of the fix. Every arm saw it equally, so the measured
DELTA is unbiased -- but the ABSOLUTE scores, including the 100/100/100, were
inflated by it and must not be reported as clean. Keep this builder outside
public/ so the agent sees only the PDF, exactly as a real engineer would.

No real NY PDL is committed to HermesAirflow, and the committed SC backfill PDLs
use a ~6.1pt geometry that the NY-specific parser's `_header_anchors` rejects
(verified: the shipped parser returns 0 rows on SCpdl_listing_20230101.pdf). So
this file REPRODUCES the NYRx FHSC/Magellan 3-column template at the real NY font
geometry (18pt title / 12pt class+subclass headers / 11pt body drug rows / 8pt
superscript footnotes) and seeds each column with the exact drug-name NOISE
patterns the 2026-07-01 parser rework (`_clean_drug_name` + `_form_vocab`,
Hermes commits 9835c408..a7ed0fd1) was written to eliminate.

The GROUND TRUTH for the fixture is NOT hand-authored: it is the deterministic
behaviour the shipped parser exhibits on this PDF (bare drug names), asserted
semantically by hidden/grade.py. This script is committed for reproducibility;
the built artifact nyrx_sample_pdl.pdf is committed alongside it. Nothing here is
proprietary Hermes code or data.

Rebuild:  python build_sample.py nyrx_sample_pdl.pdf
Requires: reportlab (local, no provider/network).
"""
import sys
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

C0, C1, C2 = 40, 245, 400          # column x-anchors (points from left)
W, H = letter


def build(path):
    c = canvas.Canvas(path, pagesize=letter)
    # page 0: cover (18pt title -> parser classifies as "title", ignored)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(60, H - 80, "NYRx, the Medicaid Pharmacy Program Preferred Drug List")
    c.setFont("Helvetica", 11)
    c.drawString(60, H - 120, "Revised: January 1, 2023")
    c.showPage()

    # page 1: 3-column header + body drug rows
    y = H - 60
    c.setFont("Helvetica-Bold", 12)                 # column header (12pt)
    c.drawString(C0, y, "Preferred Drugs")
    c.drawString(C1, y, "Non-Preferred Drugs")
    c.drawString(C2, y, "Coverage Parameters")
    y -= 28
    c.setFont("Helvetica-Bold", 12)                 # class header (roman numeral)
    c.drawString(C0, y, "I. Analgesics")
    y -= 22
    c.drawString(C0, y, "Non-Steroidal Anti-Inflammatory Drugs (NSAIDS) CC")  # subclass + flag
    y -= 24

    rows = [
        # (col0 preferred, col1 non-preferred, col2 criteria)
        ("duloxetine 20 mg, 30 mg, 60 mg", "Cymbalta (gen duloxetine)", "CLINICAL CRITERIA (CC)"),
        ("Buphenyl powder, tablet", "Advair Diskus", "PRIOR AUTHORIZATION"),
        ("Diskus Depakote", "Trelegy Ellipta", ""),
        ("clonidine ER", "Proventil HFA", ""),
        ("fentanyl patch (37.5 mcg,", "Tazorac CC", ""),
        ("Avinza)", "", ""),                                  # line-wrap continuation
        ("aspirin https://newyork.fhsc.com/x", "", ""),       # 11pt inline footnote-URL bleed
    ]
    for a, b, d in rows:
        c.setFont("Helvetica", 11)
        if a:
            c.drawString(C0, y, a)
        if b:
            c.drawString(C1, y, b)
        if d:
            c.drawString(C2, y, d)
        y -= 20

    # a body row carrying an 8pt superscript footnote marker (geometry must drop it)
    c.setFont("Helvetica", 11)
    c.drawString(C0, y, "metformin ER")
    c.setFont("Helvetica", 8)
    c.drawString(C0 + 62, y + 3, "1")
    y -= 30

    c.setFont("Helvetica", 8)                        # 8pt footnote block
    c.drawString(C0, 60, "1 See https://newyork.fhsc.com/downloads for details.")
    c.showPage()
    c.save()


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "nyrx_sample_pdl.pdf"
    build(out)
    print("wrote", out)
