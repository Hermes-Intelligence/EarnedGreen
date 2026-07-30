"""Containment-guard lists for the resolution ladder.

Bare single-word tokens that are also ordinary English or common brand words
must never containment-match: substring-scanning them misfires on generic
site and product names ("Prime Business Park" is not Prime Analytics;
"Vertex Plaza" is not anything tradable). Distinctive coinages are safe to
containment-scan and are deliberately NOT listed here.

MIN_CONTAINMENT_LEN additionally keeps very short tokens (two- and
three-letter symbols) out of containment; they remain resolvable through the
exact and alias rungs only.
"""

AMBIGUOUS_BARE = {
    "PRIME", "VERTEX", "ATLAS", "SUMMIT", "ORBIT", "NOVA", "APEX",
    "DIGITAL", "GLOBAL", "PACIFIC", "UNITED", "GENERAL", "NATIONAL",
    "FIRST", "STANDARD", "CENTRAL", "CAPITAL", "GRAND",
}

MIN_CONTAINMENT_LEN = 4
