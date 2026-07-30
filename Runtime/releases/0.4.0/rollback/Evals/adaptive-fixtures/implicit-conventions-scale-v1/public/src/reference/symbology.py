"""Per-venue symbology notes: how each venue writes instrument symbols.

Consulted by capture reviews and by the desks when a notice symbol does not
match the security master. This is descriptive reference data; parsers do
NOT rewrite symbols (the events table carries the venue's own symbol, and
the security-master join happens downstream of the platform).
"""

SYMBOLOGY = {
    "alpha": {
        "style": "plain uppercase, 2-5 letters",
        "class_suffix": ".A/.B share classes joined with a dot",
        "when_issued": "WI suffix",
        "examples": ("AAX", "BRNT", "KSTL.A"),
    },
    "beta": {
        "style": "plain uppercase, 3-4 letters",
        "class_suffix": "numeric line extensions (KLR3)",
        "when_issued": "prefix V/",
        "examples": ("KLR", "VNTA", "KLR3"),
    },
    "gamma": {
        "style": "plain uppercase, 2-5 letters",
        "class_suffix": "hyphenated (-PA preferred lines)",
        "when_issued": "not used",
        "examples": ("QMD", "QMD-PA"),
    },
    "delta": {
        "style": "3-letter romanized codes",
        "class_suffix": "not used",
        "when_issued": "not used",
        "examples": ("TYK", "OSR"),
    },
    "epsilon": {
        "style": "RIC-like uppercase, 2-4 letters",
        "class_suffix": "not observed in capture",
        "when_issued": "not observed in capture",
        "examples": ("QRV", "ZMT", "HLB"),
    },
}


def notes_for(venue):
    """Symbology notes for one venue ({} when unreviewed)."""
    return SYMBOLOGY.get(venue, {})
