# negative control: before-parser (materialized, not committed)

This is the REAL historical negative control: the parser state immediately BEFORE
the 2026-07-01 rework (`before_ref` in fixture-contract.json → commit b0dcd182).
It already isolates columns by font geometry but has NO drug-name cleaning pass, so
it emits names carrying strengths, dosage forms, (gen ...) annotations, column
bleed and footnote URLs. Materialized at grade time; no proprietary code committed
here. It must FAIL the strip/wrap dimensions while passing basic-functionality and
brand-device-preserve — the discrimination proof for a genuine past bug.
Expected score band: see fixture-contract.json expected_controls (≈27).
