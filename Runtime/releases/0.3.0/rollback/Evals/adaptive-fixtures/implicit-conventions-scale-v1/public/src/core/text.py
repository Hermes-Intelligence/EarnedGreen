"""Headline/description text hygiene shared by the source parsers.

Venue notice text arrives with boilerplate prefixes and ragged whitespace.
clean() is deliberately conservative: it collapses whitespace and strips
known boilerplate prefixes, and NEVER rewrites tokens - the ambiguity guard
and issuer resolution depend on seeing the original uppercase tokens
(see core/guard.py and core/resolve.py).
"""

_BOILERPLATE_PREFIXES = (
    "MARKET NOTICE:",
    "TRADING NOTICE:",
    "REGULATORY ANNOUNCEMENT:",
    "NOTICE TO MEMBERS:",
    "OFFICIAL NOTICE:",
)


def clean(text):
    """Collapse whitespace and strip one leading boilerplate prefix."""
    value = " ".join((text or "").split())
    for prefix in _BOILERPLATE_PREFIXES:
        if value.startswith(prefix):
            value = value[len(prefix):].lstrip()
            break
    return value
