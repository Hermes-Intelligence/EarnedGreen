#!/usr/bin/env python
"""Provision the LIVE agent workspace for the proprietary medi-ny fixture.

The parser the agent edits is a real Hermes subtree and is never committed to this
package. At approval time (after the canary is approved), the run harness calls
this to build the before-state workspace from the LOCAL Hermes git ref, exactly
as the admission gate materializes it for grading. Zero provider calls.

Usage:  python materialize_workspace.py <dest_dir>
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # implementation/ (fixture_admission.py)

from fixture_admission import Gate  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python materialize_workspace.py <dest_dir>")
    dest = Path(sys.argv[1]).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    gate = Gate(HERE)
    # No overlays -> base variant (before-state parser), the agent's starting point.
    gate._provision(dest, [])
    print(f"materialized before-state workspace at {dest}")
    print("  edit: src/pdl_parser.py   sample: sample/nyrx_sample_pdl.pdf")


if __name__ == "__main__":
    main()
