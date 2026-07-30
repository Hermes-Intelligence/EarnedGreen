"""Ambiguous-token guard.

Some uppercase words look like ticker or issuer symbols but are ambiguous
brand or prose tokens: they appear in notice headlines without referring to a
listed issuer. They must never be used to resolve an issuer. scrub_tokens
must run BEFORE resolve.resolve_issuer: resolution only ignores tokens that
are already masked. Running it after resolution (or not at all) silently
degrades into wrong-but-plausible issuers; nothing raises and nothing looks
broken, the exposure table is just attributed to the wrong companies.

The masked tokens are recorded on the event (and end up in the events table)
so a human reviewing an odd resolution can see what the guard removed.
"""

AMBIGUOUS_TOKENS = ("APEX", "NOVA", "PRIME", "ORBIT", "VERTEX", "ATLAS", "SUMMIT")


def scrub_tokens(event):
    """Mask ambiguous tokens in the description and record what was masked."""
    masked = list(event.get("masked_tokens", ()))
    cleaned = []
    for word in event.get("description", "").split():
        token = word.strip(".,:;()!?")
        if token in AMBIGUOUS_TOKENS:
            masked.append(token)
            cleaned.append("[MASKED]")
        else:
            cleaned.append(word)
    event["description"] = " ".join(cleaned)
    event["masked_tokens"] = masked
    return event
