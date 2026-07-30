"""Point-in-time discipline.

Every event carries two dates: published_at (when the feed made the event
public) and effective_at (when the action takes effect on the venue). The
product table is a point-in-time dataset: as_of must ALWAYS be the knowledge
date, published_at, never effective_at. Keying by effective_at introduces
look-ahead: a query for day D would surface events the market could not have
known on day D. Nothing crashes when you get this wrong; the data is just
quietly untrustworthy.
"""


def as_of_date(event):
    """The date this event became knowable: always the published date."""
    return event["published_at"]
