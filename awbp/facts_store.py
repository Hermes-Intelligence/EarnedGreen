#!/usr/bin/env python3
"""Facts consumed by tools, not lessons read by models.

notes_bank measured ZERO as a prose mechanism: an author read a note, applied
its style, and still wrote a weaker predicate than the rule the note encoded.
The failure was routing knowledge THROUGH model comprehension. This module is
the owner-approved rehabilitation, and it dodges that failure by construction:
a fact here is written by a tool and read by a tool, and no model has to
understand anything for it to work.

Three record kinds, one mechanism:

    repo-fact     something about this repository that was paid for once.
                  "the test suite rewrites 4 tracked files via codegen";
                  "78.7 MB tracked, exceeds the default snapshot cap".
                  Written by project_detect and friends, read back next session.

    preference    a decision a human made that should outlive the session.
                  "PSO: dense tables, gmina choropleth, PL labels";
                  an owner's gallery verdict on a component.

    gap           something missing that somebody is expected to build.
                  "no endpoint serves municipality-level aggregates". Opened by
                  a gap report, closed when the backend ships it.

THE METRIC IS BUILT INTO THE WRITE PATH. `record()` returns whether the fact is
NEW or a REDISCOVERY. A rediscovery means a session paid again for knowledge a
previous session already recorded, and the count is the longitudinal measure the
owner asked for: does session N+1 avoid re-diagnosing what session N knew? No
A/B campaign needed; the store measures itself every time a tool writes to it.

A fact must name its consumer. `enforced_by` points at the helper, predicate or
tool that ACTS on the fact ("project_detect.working_tree_touched",
"harness_checks.BASELINE_MAX_BYTES override"). A fact nothing consumes is prose
with better formatting, and prose is the thing that measured zero — so a fact
with no consumer is accepted but reported as `advisory`, loudly, and the report
puts the advisory count first.

    python facts_store.py --store .agentic/facts.jsonl --report
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

KINDS = ("repo-fact", "preference", "gap")
STORE_NAME = "facts.jsonl"


@dataclass
class Fact:
    key: str                      # stable id: "suite-mutates-tree", "gap:endpoint:/vextrum/municipalities"
    kind: str
    statement: str                # the fact in plain words
    source: str                   # which tool or person recorded it
    enforced_by: str = ""         # the helper/predicate/tool that CONSUMES it; empty = advisory
    data: dict = field(default_factory=dict)   # machine-readable payload for the consumer
    status: str = "open"          # open | closed  (gaps close when built)
    first_recorded: str = ""      # ISO timestamp, supplied by the caller
    last_seen: str = ""
    times_rediscovered: int = 0   # THE metric: how often a session re-paid for this


class FactsStore:
    """Append-friendly store over one JSONL file. Latest record per key wins."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.facts: dict[str, Fact] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    fact = Fact(**{k: raw[k] for k in raw if k in Fact.__dataclass_fields__})
                except (json.JSONDecodeError, TypeError):
                    # One corrupt line must not take the store down; the store's
                    # whole value is surviving between sessions.
                    continue
                self.facts[fact.key] = fact

    # ── the write path, where the metric lives ────────────────────────────────
    def record(self, key: str, kind: str, statement: str, *, source: str,
               now: str, enforced_by: str = "", data: dict | None = None) -> dict:
        """Record a fact. Returns {new | rediscovered | refreshed}.

        REDISCOVERED is the interesting verdict: the writing tool ARRIVED at this
        knowledge again (it did the work, paid the cost, then found the store
        already knew). That is the exact event the longitudinal metric counts.
        A caller that merely re-asserts what it read from the store first should
        use `touch()`, which refreshes without counting.
        """
        if kind not in KINDS:
            raise ValueError(f"unknown kind {kind!r}; expected one of {KINDS}")
        existing = self.facts.get(key)
        if existing is None:
            self.facts[key] = Fact(key=key, kind=kind, statement=statement,
                                   source=source, enforced_by=enforced_by,
                                   data=data or {}, first_recorded=now, last_seen=now)
            self._flush()
            return {"verdict": "new", "key": key}
        existing.times_rediscovered += 1
        existing.last_seen = now
        existing.statement = statement           # the fresher wording wins
        if enforced_by:
            existing.enforced_by = enforced_by
        if data:
            existing.data.update(data)
        self._flush()
        return {"verdict": "rediscovered", "key": key,
                "times_rediscovered": existing.times_rediscovered,
                "first_recorded": existing.first_recorded,
                "note": ("this session paid again for knowledge the store already held. "
                         "If the consumer named in `enforced_by` had been wired in, it "
                         "would not have had to.")}

    def touch(self, key: str, now: str) -> bool:
        """Refresh last_seen WITHOUT counting a rediscovery (reader path)."""
        fact = self.facts.get(key)
        if fact is None:
            return False
        fact.last_seen = now
        self._flush()
        return True

    def close(self, key: str, now: str) -> bool:
        """Close a gap: the missing thing was built."""
        fact = self.facts.get(key)
        if fact is None:
            return False
        fact.status = "closed"
        fact.last_seen = now
        self._flush()
        return True

    # ── the read path, for tools ──────────────────────────────────────────────
    def get(self, key: str) -> Fact | None:
        return self.facts.get(key)

    def open_facts(self, kind: str | None = None) -> list[Fact]:
        rows = [f for f in self.facts.values() if f.status == "open"]
        if kind:
            rows = [f for f in rows if f.kind == kind]
        return sorted(rows, key=lambda f: f.key)

    # ── reporting ─────────────────────────────────────────────────────────────
    def report(self) -> dict:
        rows = list(self.facts.values())
        advisory = [f.key for f in rows if not f.enforced_by and f.status == "open"]
        rediscoveries = sum(f.times_rediscovered for f in rows)
        return {
            "schema_version": 1,
            "facts": len(rows),
            "open_gaps": [f.key for f in rows if f.kind == "gap" and f.status == "open"],
            "advisory_unconsumed": advisory,
            "rediscoveries_total": rediscoveries,
            "worst_rediscovered": sorted(
                ({"key": f.key, "times": f.times_rediscovered}
                 for f in rows if f.times_rediscovered),
                key=lambda r: -r["times"])[:5],
            "rule": ("a fact nothing consumes is prose with better formatting, and prose "
                     "measured zero. rediscoveries_total is the longitudinal metric: every "
                     "point on it is a session that paid twice for the same knowledge."),
        }

    def render(self) -> str:
        report = self.report()
        lines = [f"FACTS STORE  {self.path}", ""]
        if report["advisory_unconsumed"]:
            lines.append(f"  ADVISORY (no consumer wired) - {len(report['advisory_unconsumed'])} fact(s):")
            for key in report["advisory_unconsumed"]:
                lines.append(f"    ! {key}")
            lines.append("    ^ wire a consumer or accept these are decoration. Listed first on purpose.")
            lines.append("")
        lines.append(f"  rediscoveries to date: {report['rediscoveries_total']}"
                     + ("  (every one is a session that paid twice)" if report["rediscoveries_total"] else ""))
        for fact in self.open_facts():
            mark = {"repo-fact": "F", "preference": "P", "gap": "G"}[fact.kind]
            enforced = f" -> {fact.enforced_by}" if fact.enforced_by else "  (advisory)"
            lines.append(f"  [{mark}] {fact.key}: {fact.statement[:80]}{enforced}")
        return "\n".join(lines)

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(json.dumps(asdict(f), ensure_ascii=False)
                         for f in sorted(self.facts.values(), key=lambda f: f.key))
        self.path.write_text(body + "\n", encoding="utf-8")


def store_for(workspace: Path) -> FactsStore:
    return FactsStore(Path(workspace) / ".agentic" / STORE_NAME)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--close", metavar="KEY", help="close a gap that has been built")
    parser.add_argument("--now", default="", help="ISO timestamp (callers supply time)")
    args = parser.parse_args()

    store = FactsStore(args.store)
    if args.close:
        ok = store.close(args.close, args.now or "unspecified")
        print(f"{'closed' if ok else 'NOT FOUND'}: {args.close}")
        raise SystemExit(0 if ok else 1)
    print(store.render())
    raise SystemExit(0)


if __name__ == "__main__":
    main()
