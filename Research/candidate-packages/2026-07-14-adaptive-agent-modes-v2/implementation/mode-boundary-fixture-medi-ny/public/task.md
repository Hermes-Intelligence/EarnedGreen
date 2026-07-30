# Task: NYRx PDL parser — clean up the extracted drug names

`src/pdl_parser.py` turns a NYRx (New York Medicaid) Preferred Drug List PDF into
normalized `NyPdlRow` coverage rows. It already isolates the three columns
(Preferred / Non-Preferred / Coverage) by font-size and x-band geometry, and it
already strips trailing coverage flags (CC / PA / F/Q/D) off each entry.

The feed team reports that the emitted `drug_name` values are still **noisy**: the
name field carries strengths, dosage forms, generic-equivalent annotations and
occasional column/line bleed instead of the bare drug name. Downstream every guard
keys off the drug name, so a name like `Buphenyl powder, tablet` hides that
Buphenyl is multi-source and mis-attributes it; `duloxetine 20 mg, 30 mg, 60 mg`
never matches the clean `duloxetine`.

Rework the parser so the `drug_name` it emits is the **bare drug name**, consistent
with the rest of the pipeline and the layout documented in the module. Keep it
deterministic — the parser is a pure function of the PDF bytes (no network, no
model calls). Do not change the `NyPdlRow` contract, the column/font geometry, or
the flag derivation; the change is about what ends up in the name field.

A sample PDF is provided at `sample/nyrx_sample_pdl.pdf`. `parse_pdl(pdf_bytes,
version_date=...)` is the entry point.
