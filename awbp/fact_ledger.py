#!/usr/bin/env python3
"""Every asserted number carries the query that produced it — provenance `data`.

Generalised out of a real client deliverable on 2026-07-21, where this pattern
produced an instrument with 100% oracle independence instead of the 0% a
spec-derived one would have had. The per-repo part is the QUERIES. Everything
around them is not, and that is what lives here.

The direction matters more than it looks. The obvious check is "does the document
contain the facts". This ledger runs the OTHER way: it takes every number the
document asserts and asks which derivation produced it. A number with no
derivation behind it was typed in by whoever wrote the document, which on that
day happened four times, including a figure that understated a real archive by
twenty-seven years because a date filter nobody wrote down discarded 947 rows.

    ledger = FactLedger()
    ledger.register("states.collected", lambda: count_prefixes(...),
                    source="S3 list_objects_v2 prefix data/medi_*/ (paginated)",
                    layer="collection")
    ledger.derive_all()
    report = ledger.audit(document_text)     # unledgered numbers are the finding

Three lessons are enforced rather than documented, because all three were paid for:

  A fact with no source string is refused at registration. A number without its
  query beside it is provenance `spec` wearing a data costume.

  When more than one layer is registered, every fact must name its layer. The
  worst error of that day was reading one store, finding a small number, and
  reporting it as the size of the estate. Collection and intelligence are
  different layers and a number is meaningless without which one it came from.

  A derivation that returns zero, empty, or None is reported as FAILED, never as
  the value zero. An empty result read as a real answer is how an instrument goes
  quietly green on a store it could not reach.

    python fact_ledger.py --demo
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Iterable


# Numbers as a document writes them: 1,234  12.5  238000000  1963
#
# The trailing guard is `(?!\w)` and NOT `(?![\w.])`. The first version of this
# file used the stricter one and could not see a number that ended a sentence:
# "history back to 1990." matched nothing at all, so the ledger's own demo, which
# was written to fail, passed. A sentence-final year is exactly the shape of the
# worst fact error of that day, and the audit was blind to it.
_NUMBER = re.compile(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?(?!\w)")

# Blanked before scanning: these are structure, not claims, and flagging their
# components as unledgered facts buries the real findings in noise.
_NOT_A_CLAIM = re.compile(r"\d{4}-\d{2}-\d{2}"          # ISO dates
                          r"|\bv?\d+\.\d+\.\d+\b"        # versions
                          r"|\d{1,2}:\d{2}(?::\d{2})?")  # clock times

# Values a reader never traces back to a query, so flagging them is pure noise.
_UNINTERESTING = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100}


@dataclass
class Fact:
    name: str
    source: str                       # the query, path, or command that produced it
    layer: str = ""                   # which store, when the estate has more than one
    assumptions: list[str] = field(default_factory=list)
    value: object = None
    ok: bool = False
    error: str = ""

    def numbers(self) -> set[float]:
        """Every number this fact licenses a document to print."""
        out: set[float] = set()
        for token in _NUMBER.findall(str(self.value)):
            try:
                out.add(float(token.replace(",", "")))
            except ValueError:
                pass
        return out


class FactLedger:
    """Facts that know where they came from, plus the audit that runs backwards."""

    def __init__(self) -> None:
        self._derivations: dict[str, Callable[[], object]] = {}
        self.facts: dict[str, Fact] = {}

    # ── registration ──────────────────────────────────────────────────────────
    def register(self, name: str, derive: Callable[[], object], *, source: str,
                 layer: str = "", assumptions: Iterable[str] = ()) -> None:
        if not source or not source.strip():
            raise ValueError(
                f"fact {name!r} has no source. A number without the query that produced it "
                f"is provenance 'spec' (rank 2), not 'data' (rank 4), whatever it is called. "
                f"Write the query, the path, or the command.")
        if name in self._derivations:
            raise ValueError(f"fact {name!r} is already registered")
        self._derivations[name] = derive
        self.facts[name] = Fact(name=name, source=source, layer=layer,
                                assumptions=list(assumptions))

    # ── derivation ────────────────────────────────────────────────────────────
    def derive_all(self) -> dict:
        layers = {f.layer for f in self.facts.values() if f.layer}
        unlabelled = [n for n, f in self.facts.items() if not f.layer]
        if len(layers) > 1 and unlabelled:
            raise ValueError(
                f"{len(layers)} layers are registered ({', '.join(sorted(layers))}) and "
                f"{len(unlabelled)} fact(s) do not say which one they came from: "
                f"{', '.join(sorted(unlabelled)[:4])}. A count is meaningless without its "
                f"layer: the same estate reads as huge or tiny depending on which store "
                f"you counted.")

        for name, derive in self._derivations.items():
            fact = self.facts[name]
            try:
                value = derive()
            except Exception as exc:                       # noqa: BLE001 - reported, not raised
                fact.ok, fact.error = False, f"{type(exc).__name__}: {exc}"
                continue
            # An empty answer is a failed reach, not the number zero.
            if value is None or value == 0 or value == "" or value == [] or value == {}:
                fact.ok = False
                fact.value = value
                fact.error = ("derivation returned an empty result. That is reported as a "
                              "failure, not as a value: a store the run could not reach "
                              "answers exactly like a store that is genuinely empty.")
                continue
            fact.ok, fact.value, fact.error = True, value, ""
        return self.summary()

    def summary(self) -> dict:
        failed = [f.name for f in self.facts.values() if not f.ok]
        return {"schema_version": 1, "provenance": "data",
                "facts": {n: asdict(f) for n, f in self.facts.items()},
                "failed": failed, "usable": not failed,
                "rule": "a fact is the return value of a query, never a sentence someone wrote"}

    # ── the audit, run backwards ──────────────────────────────────────────────
    def audit(self, text: str, *, ignore: Iterable[float] = ()) -> dict:
        """Which numbers in `text` does NO derivation account for?"""
        licensed: set[float] = set()
        for fact in self.facts.values():
            if fact.ok:
                licensed |= fact.numbers()

        skip = _UNINTERESTING | {float(v) for v in ignore}
        scannable = _NOT_A_CLAIM.sub(" ", text)
        asserted: dict[float, int] = {}
        for token in _NUMBER.findall(scannable):
            try:
                value = float(token.replace(",", ""))
            except ValueError:
                continue
            if value in skip:
                continue
            asserted[value] = asserted.get(value, 0) + 1

        unledgered = sorted(v for v in asserted if v not in licensed)
        unused = sorted(f.name for f in self.facts.values()
                        if f.ok and f.numbers() and not (f.numbers() & set(asserted)))
        return {
            "schema_version": 1,
            "asserted": len(asserted),
            "unledgered": unledgered,
            "unledgered_count": len(unledgered),
            "derived_but_unused": unused,
            "clean": not unledgered,
            "rule": ("a number in the document that no query produced was typed in by the "
                     "author. That is the direction this check runs, because the other "
                     "direction only proves the author can copy."),
        }

    # ── drift ─────────────────────────────────────────────────────────────────
    def diff(self, earlier: dict) -> dict:
        """What moved since a stored summary. Facts drift; documents do not follow."""
        before = earlier.get("facts", {})
        moved = []
        for name, fact in self.facts.items():
            was = before.get(name, {}).get("value")
            if name in before and fact.ok and was != fact.value:
                moved.append({"fact": name, "was": was, "now": fact.value,
                              "source": fact.source})
        return {"moved": moved, "stable": not moved,
                "gone": sorted(set(before) - set(self.facts)),
                "new": sorted(set(self.facts) - set(before))}

    # ── output ────────────────────────────────────────────────────────────────
    def render(self) -> str:
        lines = ["FACT LEDGER  (provenance: data, rank 4)", ""]
        for fact in self.facts.values():
            mark = "ok " if fact.ok else "FAIL"
            layer = f"[{fact.layer}] " if fact.layer else ""
            lines.append(f"  {mark}  {fact.name:<28} {layer}{fact.value if fact.ok else fact.error}")
            lines.append(f"        from: {fact.source}")
            for note in fact.assumptions:
                lines.append(f"        assumes: {note}")
        return "\n".join(lines)

    def write(self, path: Path) -> None:
        path.write_text(json.dumps(self.summary(), indent=2, default=str) + "\n",
                        encoding="utf-8")


def paginated_count(fetch_page: Callable[[str | None], tuple[list, str | None]]) -> int:
    """Count across ALL pages. A single page silently truncates at the API's cap,
    which is how a forty-item estate once read as one item."""
    total, token = 0, None
    while True:
        rows, token = fetch_page(token)
        total += len(rows)
        if not token:
            return total


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--demo", action="store_true", help="show the audit finding an invented number")
    args = parser.parse_args()
    if not args.demo:
        print(__doc__)
        raise SystemExit(0)

    ledger = FactLedger()
    ledger.register("records.total", lambda: 238_000_000,
                    source="SELECT sum(n_live_tup) FROM pg_stat_user_tables WHERE ...",
                    layer="intelligence")
    ledger.register("platforms", lambda: 6,
                    source="SELECT count(DISTINCT platform) FROM posts", layer="intelligence")
    ledger.register("states.collected", lambda: 41,
                    source="S3 list_objects_v2 prefix data/medi_*/ (paginated)",
                    layer="collection",
                    assumptions=["dev and non-state prefixes excluded by name"])
    ledger.derive_all()
    print(ledger.render())
    print()

    document = ("The platform spans 6 platforms and 238,000,000 records across "
                "41 states, with history back to 1990.")
    result = ledger.audit(document)
    print("AUDIT:", "clean" if result["clean"] else "UNLEDGERED NUMBERS")
    for value in result["unledgered"]:
        print(f"  {value:g} appears in the document and no query produced it")
    print(f"\n  {result['rule']}")
    raise SystemExit(0 if result["clean"] else 1)


if __name__ == "__main__":
    main()
