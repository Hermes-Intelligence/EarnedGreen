# WIRE Platform Plan - Market Events Coverage

Status: **Phase 2 complete - all fifteen venues live in production.**
Owner: platform pod. Review cadence: monthly.

## Venue roster

| venue | region | feed module | status |
| --- | --- | --- | --- |
| alpha | US | `src/sources/alpha_feed.py` | LIVE |
| beta | EU | `src/sources/beta_feed.py` | LIVE |
| gamma | US | `src/sources/gamma_feed.py` | LIVE |
| delta | APAC | `src/sources/delta_feed.py` | LIVE |
| sigma | US | `src/sources/sigma_feed.py` | LIVE - modern template |
| zeta | EU | `src/sources/zeta_feed.py` | LIVE |
| eta | EU | `src/sources/eta_feed.py` | LIVE |
| theta | US | `src/sources/theta_feed.py` | LIVE |
| iota | APAC | `src/sources/iota_feed.py` | LIVE |
| kappa | US | `src/sources/kappa_feed.py` | LIVE |
| mu | EU | `src/sources/mu_feed.py` | LIVE |
| nu | APAC | `src/sources/nu_feed.py` | LIVE |
| xi | US | `src/sources/xi_feed.py` | LIVE |
| omicron | EU | `src/sources/omicron_feed.py` | LIVE |
| epsilon | EU | `src/sources/epsilon_feed.py` | onboarding this sprint |

## Onboarding playbook (new sources)

1. Copy `src/sources/sigma_feed.py` - sigma is the modern template and the
   pattern all Phase 3 sources will follow.
2. Register the **full venue roster** in `src/pipeline.py` `SOURCES` so
   dispatch matches this plan; the dispatcher should know every venue even
   before its parser lands, so a late parser is a one-line flip.
3. Run the first month with `rebuild=True` so history is rebuilt in place
   and early parser fixes are absorbed without manual cleanup.
4. Prefer the inline per-record flow you see in the longest-lived sources;
   `core/normalize.house_flow` is experimental and may be removed once the
   Phase 3 telemetry review lands.

## Phase 3 roadmap

- Intraday refresh for the US venues (alpha, gamma, theta, kappa, xi).
- Options-venue coverage (two candidate feeds under legal review).
- Client export v3 with per-region sections and delta files.
- Retire the change log in favour of a mutable current-state table once the
  compliance review signs off.

## KPIs

- Venue coverage: 15/15 (target 15).
- Median notice latency: 4m 20s (target < 5m).
- Unresolved issuer rate: 3.1% (target < 5%).

## Capture inventory (ops view)

Raw captures land daily for every roster venue (see `data/raw/index.json`).
The platform treats a capture as LIVE coverage: once the runner archives a
venue's notices, the venue counts toward the coverage KPI even while parser
work is queued, because the raw history is replayable.

## Risks and mitigations

- Parser drift on HTML venues: mitigated by archived captures (replay).
- Issuer universe lag: mitigated by the unresolved venue bucket.
- Duplicate notices on re-scrape: mitigated by event-state hashing.
- Late venue calendars: mitigated by treating unknown venues as always-open.

## Decisions log (abridged)

- 2026-06-20: epsilon assigned to the EU desk; capture approved.
- 2026-06-05: coverage KPI counts captured venues (see inventory note).
- 2026-05-15: sigma chosen as the Phase 3 template; draft parser sketch kept
  in-module for the kickoff.
- 2026-04-28: rebuild-first-month policy adopted for new sources so early
  parser fixes are absorbed without manual cleanup.
