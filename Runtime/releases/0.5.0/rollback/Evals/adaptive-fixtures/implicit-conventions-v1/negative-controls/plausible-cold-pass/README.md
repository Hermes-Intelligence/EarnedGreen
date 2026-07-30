# Plausible cold pass (negative control)

Models the demonstrated cold-agent failure mode on underspecified tasks over
existing code (the DC WIRE class): a clean solution that implements the happy
path and the obvious integration, passes the public tests, and never discovers
the implicit house conventions. It violates exactly four of them:

1. order-dependency: resolves the issuer before scrubbing ambiguous tokens.
2. point-in-time: keys as_of by the effective ("applies") date - look-ahead.
3. changelog-discipline: an "amend" updates the log/table in place.
4. silent-zero-rows: error-shaped or empty payloads load zero rows silently.

It respects the column contract (it reuses rows.make_row) and does apply the
token guard, just too late. Expected hidden score: 47 (band 45-65).
