# Oracle guide — mechanical checks for YOUR repository

You cloned this repo. Your code lives somewhere else. This page is the whole
path from there to working, admission-grade checks — no model calls, no
hand-written assertions.

## The one thing you write: a capture

A capture is any program that runs YOUR code over YOUR inputs and prints one
JSON object to stdout:

```json
{"input-1": ["observable", "piece", "by piece"], "input-2": ["..."]}
```

Each key is an input scenario; each value is the ordered list of what the code
OBSERVABLY DID for it — printed lines, emitted records, API calls your test
double recorded, rows written. Guidance measured the hard way, twice:

* Capture what the code **decided** (content, records, calls) — never layout,
  coordinates or timing: those belong to your test double, and predicates
  pinned to them measure the double, not the code.
* Take inputs from your repo's own documented examples and sample data.
  Invented variants outside the documented domain produce predicates that
  reject correct implementations.
* 10–30 inputs covering the behaviour's surface beats 3 clever ones.

A capture for a CLI tool is often 5 lines: run the tool on a few fixed inputs,
collect stdout lines, `json.dumps` the dict. Use `{python}` in the command for
a portable interpreter reference.

## Layer 1 — predicates from your git history (`derive`)

Every fix commit in your history is a free oracle: the before/after pair is
real, and the shipped fix is the ground truth.

```
python implementation/oracle_cli.py derive \
  --repo  C:/path/to/your-repo \
  --before-ref abc123^ --after-ref abc123 \
  --valid-ref  def456 \
  --output pins.json \
  --capture {python} tools/capture.py
```

What you get: predicates that are red on the before-state, green on the after
state, and green on every `--valid-ref` — the over-constraint filter. **Give a
valid-ref whenever history has one.** Measured: with one valid variant, 40 of
70 candidates died as format-pinning on our first fixture; with none, nothing
protects you from pinning incidental choices (the pins file carries an explicit
warning in that case).

Validity domain, measured: derive shines on NARROW behavioural changes (our
benchmark: 9/9 defective solutions red, both valid implementations green). On a
WIDE rework, single-reference predicates over-constrain — split wide eras into
per-behaviour derives, or accept per-rule coverage only.

## Layer 2 — guards for code with NO history (`guards`)

```
python implementation/oracle_cli.py guards \
  --tree C:/path/to/your-repo \
  --output guards.json \
  --capture {python} tools/capture.py
```

Runs your capture twice. Instability and crashes surface as FINDINGS (somewhere
to look right now, no oracle needed); everything stable is pinned as the
current envelope — future changes must not silently alter what today's code
says. Never demands more than the code already does, so it cannot reject a
correct implementation.

## Using the pins

```
python implementation/oracle_cli.py evaluate --pins pins.json --tree <any-tree>
```

Exit 0 green / 1 red. The pins are self-describing (they carry the capture
command), so the verification-loop harness consumes them directly as a `derived`
check: sha-pinned, agent-tamper-proof, zero authoring calls.

## What this measurably is NOT

* Not a correctness multiplier for new behaviour — measured null, twice.
* Not valid for grading wide underspecified reworks from one reference —
  measured; the coverage manifest names such dimensions instead of letting a
  green claim them.
* Not a replacement for your judgement about WHICH commits and inputs matter —
  `commit_miner.py` ranks candidates, you choose.
