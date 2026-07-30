"""The suite the agent writes for its own change.

This is not a straw man. It is competent: six checks, every one of them a real
property of the function, each derived from the task description the agent was
given. It is also provenance `authored`, rank 1, which is the rung this
programme measured at zero lift across nine runs.

Nothing here is wrong. The point is what is absent, and that the absence is
invisible from inside the work.
"""
from __future__ import annotations

CHECKS = []


def check(name):
    def register(fn):
        CHECKS.append((name, fn))
        return fn
    return register


@check("trims surrounding whitespace from string fields")
def _(normalize):
    out = normalize([{"id": "u-1", "city": "  Gdansk  "}])
    assert out[0]["city"] == "Gdansk"


@check("lowercases the email field")
def _(normalize):
    out = normalize([{"id": "u-1", "email": "A@X.IO"}])
    assert out[0]["email"] == "a@x.io"


@check("drops rows with no id")
def _(normalize):
    out = normalize([{"id": "u-1"}, {"email": "b@x.io"}, {"id": ""}])
    assert len(out) == 1


@check("coerces a numeric amount string to int")
def _(normalize):
    out = normalize([{"id": "u-1", "amount": " 42 "}])
    assert out[0]["amount"] == 42


@check("leaves unknown fields untouched")
def _(normalize):
    out = normalize([{"id": "u-1", "custom_tag": "keep-me"}])
    assert out[0]["custom_tag"] == "keep-me"


@check("collapses a duplicate id to a single row")
def _(normalize):
    out = normalize([{"id": "u-1", "city": "A"}, {"id": "u-1", "city": "B"}])
    assert len(out) == 1


@check("strict mode raises when a row carries no id")
def _(normalize):
    try:
        normalize([{"id": "u-1"}, {"email": "b@x.io"}], strict=True)
    except ValueError:
        return
    raise AssertionError("strict mode did not raise")
