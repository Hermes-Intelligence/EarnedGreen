# Capability audit

Every capability in this repository, what it has been measured at, and **when it
switches itself on**.

The last column is the one that matters. A capability that only activates when a
human types its name is not part of the environment; it is a script that ships
with the environment.

---

## The finding this audit exists to state

**The two mechanisms that measured POSITIVE are the two that nothing calls.**

`oracle_cli` and `commit_miner` produced the only wins this programme has —
88.7 against 33.3, and 71.3 against 43.0. `oracle_plan` names them in its advice
text and then stops. Nothing runs them. Meanwhile the mode ladder, measured at
exactly zero, runs automatically on every single task.

The environment automates its null and hand-waves at its win.

---

## Legend

**Measured** — was it run in a controlled comparison with a held-out oracle?
**Result** — positive, zero, or the honest label when neither applies.
**Activates** — what makes it run without anyone typing its name.

---

## A. Measured positive

| capability | measured | result | activates today | benchmark worth running |
|---|---|---|---|---|
| **`oracle_cli derive`** — turn a real prior repair into predicates | yes, 2 families | **+55.4** and **+28.3** points | **NEVER automatically** | no. Wire it instead. |
| **`commit_miner`** — rank the history's replay-worthy fixes | yes, same 2 families (it chose the commits) | part of the same win | **NEVER automatically** | no. Wire it instead. |
| **`verification_loop` + `harness_checks`** — run the checks, hand failures back, iterate | yes, same 2 families | the forcing half of the win | `awbp check`, and the gate | no |
| **`pre_submit_gate`** — fail-closed completion gate that re-runs the evidence | yes | `silent_defect_rate` **0.00 vs 0.25** (family 1 only) | end of every task | **YES** — the envelope number rests on ONE family and did not replicate on family 2 |
| **`host_rules`** — extract house conventions mechanically | yes, 1 family, 1 axis | the only measurable difference between two arms | discovery only, in advice text | **YES** — one axis on one task is thin for a rank-3 claim |

## B. Measured at zero

| capability | measured | result | activates today | benchmark worth running |
|---|---|---|---|---|
| **`check_authoring` + `check_admission`** — agent writes its own checks, gate admits only discriminating ones | yes, 9 runs | **ZERO.** All nine scored 92, all failed the same dimension, `silent_defect_rate` 0.125 in every arm | `awbp author` / `admit`, opt-in | no. The cause is diagnosed: a clean-context author writes weaker observables than the held-out oracle. |
| **`notes_bank`** — prose lessons for models | yes | **ZERO.** Transfers style, not predicate strength | retired as prose | no |
| **`facts_store`** — facts consumed by tools (rehabilitated notes_bank; owner-approved 2026-07-22) | longitudinal metric built into the write path (rediscovery counter) | new | writers: project_detect, snapshot cap; consumer: `awbp task` auto-applies; `awbp facts` | the store measures itself — every rediscovery is a session that paid twice |
| **mode ladder** (`adaptive_router` tiers) | yes | **ZERO** for correctness | **every task, automatically** | no |
| **`spec_synthesis`** — task description into predicates | yes, family 5 | **SATURATED.** Two builds scored near-identically while a human found four defects by eye | inside `prepare_context` | no |

## C. Wired, unmeasured

| capability | measured | result | activates today | benchmark worth running |
|---|---|---|---|---|
| **`execution_strategy`** — solo / reviewed / council | **n=1** | ambiguous: reviewed gave best format at **52% cost** and lost 3 of 4 figures | declared at `awbp task`, no default | **YES, highest priority.** This is the "cheap base plus verifier" question and it has one trial. |
| **`resolve_capability_profile`** — profile to concrete model | no | — | inside `prepare_context` | as part of the above |
| **`calibration_gate`** — refuse to grade until good and hollow separate | no A/B | caught 5 instrument defects in one day | blocking, inside the gate | no. A refusal cannot lift a score; it can only stop a false one. |
| **`coverage_manifest`** — uncovered-first report, independence score | no A/B | reporting change, no correctness claim made | every gate run | no, same reason |
| **`necessity_probe`** — revert each hunk, demand a check notices | no | — | `awbp probe`, opt-in | **YES, cheap.** Does it change what ships, or only what gets reported? |
| **`check_adversary`** — can a different implementation pass all the checks? | no | — | `awbp adversary`, opt-in | maybe, after the strategy benchmark |
| **`fact_ledger`** — every number carries the query that produced it | validated by construction (100% oracle independence) | not A/B | named in advice text only | **YES** — pair it with a task whose output asserts numbers |
| **`instrument_hygiene`** — predicates must prove they can fire | no | caught a dead predicate that had passed for its whole life | **nothing calls it** | no. Wire it. |

## D. Never enabled

| capability | measured | result | activates today | benchmark worth running |
|---|---|---|---|---|
| **support council** — strong executor + reviewer + independent panel | **never run** | external evidence: 17.2x error amplification, ~7x tokens | `--strategy council`, never used | **YES**, but only inside the strategy benchmark, and only on the task class where it could plausibly pay: high-ambiguity design work |

## E. Infrastructure, not a correctness mechanism

| capability | activates today | note |
|---|---|---|
| `project_detect` | `awbp init` | stack detection; now reports when your suite mutates your tree |
| `objective_compiler` | `prepare_context` | requirement ledger |
| `oracle_plan` | start of every task | the routing question |
| `mcp_server` | `python -m awbp mcp` | five read-only tools |
| `demo` | `python -m awbp demo` | the shop window |
| `claims_ledger` | **nothing calls it** | research traceability |
| `process_metrics` | **nothing calls it** | campaign instrumentation |
| `fixture_admission` | **nothing calls it** | benchmark fixture validity |
| `vault_hygiene` | a PowerShell shim | knowledge-surface scan |

---

## What has to change, in order

**1. Wire the win.** `oracle_plan` reports `diff-derived` as available and then
leaves it to prose. It should offer to build the instrument: mine the history,
derive the predicates, admit them red-on-before, freeze them into the suite. This
is not a new mechanism and needs no benchmark. It is the measured recipe, unrun.

**2. Let the environment choose the strategy.** `execution_strategy` is declared
by hand. The agent should propose one from what the task and the repository
actually are — with the reason recorded, so the choice can later be correlated
with the outcome. Correlation needs the benchmark in step 3.

**3. Benchmark the strategies.** The one open question with real money attached:
when does a cheap executor plus a strong reviewer beat a uniformly expensive one?
One task, one trial per arm is not an answer.

**4. Wire `instrument_hygiene` into the gate.** Every frozen predicate should have
to prove it can still go red. It caught a predicate that had reported PASS for its
entire life. Nothing calls it.

**5. Retire or re-home the dead weight.** `notes_bank` is measured at zero and
called by nothing. `claims_ledger`, `process_metrics` and `fixture_admission` are
research infrastructure sitting in the tool directory. They should be labelled as
such or moved.
