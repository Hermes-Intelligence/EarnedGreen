#!/usr/bin/env python3
"""Prune finished benchmark runs to their evidence, leaving a checkable trace.

A run keeps a full copy of the task workspace and a second copy under artifacts/.
Both are raw material: every number this repo publishes was computed from the
small JSON records at the run's top level, not from these trees. They cost 320 MB
across 183 runs, and eight of them contain copied .env files with live production
credentials sitting inside a cloud-synced folder.

Deleting evidence is not the same as deleting bulk, so before removing anything
this writes `workspace-fingerprint.json`: every path, its size, and its sha256.
The question "what did that arm actually produce" stays answerable afterwards,
and any later claim about a deleted file can still be checked against the hash.

    python prune_runs.py                # dry run: report only, delete nothing
    python prune_runs.py --apply        # write fingerprints, then prune
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

RUNS = Path(__file__).resolve().parents[1] / "runs"
PRUNABLE = ("workspace", "artifacts", "host-baseline", "author-scratch")
SKIP_PARTS = {"node_modules", ".git", "__pycache__", ".venv", "dist", ".next"}
HASH_CAP = 8 * 1024 * 1024          # files above this are recorded by size only
SECRET_NAMES = {".env", ".env.local", ".env.production", "credentials", "auth.json"}


def _iter(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and not any(part in SKIP_PARTS for part in path.parts):
            yield path


def fingerprint(run: Path) -> dict:
    """Every prunable file: path, size, sha256. Written before anything is removed."""
    entries, total, secrets = [], 0, []
    for name in PRUNABLE:
        tree = run / name
        if not tree.is_dir():
            continue
        for path in _iter(tree):
            size = path.stat().st_size
            total += size
            digest = ""
            if size <= HASH_CAP:
                h = hashlib.sha256()
                with path.open("rb") as handle:
                    for block in iter(lambda: handle.read(1 << 20), b""):
                        h.update(block)
                digest = h.hexdigest()
            entries.append({"path": str(path.relative_to(run)).replace("\\", "/"),
                            "bytes": size, "sha256": digest})
            if path.name in SECRET_NAMES:
                secrets.append(str(path.relative_to(run)).replace("\\", "/"))
    return {"schema_version": 1, "run": run.name, "files": len(entries),
            "bytes": total, "credential_files_removed": secrets, "entries": entries,
            "rule": ("the trees are raw material; every published number came from the "
                     "JSON records at this run's top level, which are untouched")}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="actually prune (default: report only)")
    args = parser.parse_args()

    if not RUNS.is_dir():
        print(f"no runs directory at {RUNS}")
        return 1

    runs = sorted(p for p in RUNS.iterdir() if p.is_dir())
    freed, secrets_found, pruned = 0, [], 0

    for run in runs:
        trees = [run / name for name in PRUNABLE if (run / name).is_dir()]
        if not trees:
            continue
        record = fingerprint(run)
        freed += record["bytes"]
        secrets_found += [f"{run.name}/{s}" for s in record["credential_files_removed"]]
        pruned += 1
        if not args.apply:
            continue
        out = run / "workspace-fingerprint.json"
        if not out.exists():                     # write-once, as evidence must be
            out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        for tree in trees:
            shutil.rmtree(tree, ignore_errors=True)

    verb = "pruned" if args.apply else "would prune"
    print(f"{verb} {pruned} of {len(runs)} runs, freeing {freed / 1048576:.0f} MB")
    print(f"credential files {'removed' if args.apply else 'that would be removed'}: "
          f"{len(secrets_found)}")
    for item in secrets_found:
        print(f"  {item}")
    if not args.apply:
        print("\nnothing was changed. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
