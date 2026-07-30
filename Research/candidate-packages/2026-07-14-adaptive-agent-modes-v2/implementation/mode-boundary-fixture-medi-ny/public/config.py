"""Isolated stand-in for the medi_NY adapter config used by the fixture workspace.

The real Hermes config (medi_NY/config.py) pulls the shared StateConfig and the
whole intelligence engine; the parser only reads ONE symbol from it, so the
fixture ships this minimal non-proprietary stub. The materialized pdl_parser.py
imports `config` locally (its Hermes package import is normalized to `import
config` when the workspace is built) so it resolves to this file.
"""
# "I. Analgesics", "II. Anti-Infectives" -> the leading roman-numeral class marker.
PDL_CLASS_HEADER_REGEX = r"^[IVXLC]+\.\s+"
