#!/usr/bin/env python3
"""Single Python entry point behind tools/route.ps1 -Adaptive.

Two behaviours, one contract:
- --route-only: run the adaptive mode selector and print the routing decision
  JSON (no filesystem writes). Mirrors route.ps1 -NoWrite.
- default: compile the full mode-specific context pack into <output-dir>
  (default <workspace>/.agentic) via prepare_context.prepare and print its
  summary JSON.

The task text comes from --task-file when given, otherwise --task. In the
prepare path a --task string is materialised as <output-dir>/task-contract.md
because the objective ledger and the pre-submit gate pin task_sha256 against a
real file.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from adaptive_router import MODE_RANK, route  # noqa: E402


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--task")
    source.add_argument("--task-file", type=Path)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--changed-path", action="append", default=[])
    parser.add_argument("--force-mode", choices=list(MODE_RANK))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--route-only", action="store_true",
                        help="print the routing decision JSON without writing anything")
    args = parser.parse_args()

    if args.route_only:
        task = args.task if args.task is not None else args.task_file.read_text(encoding="utf-8-sig")
        print(json.dumps(route(task, args.changed_path, args.force_mode), ensure_ascii=False, indent=2))
        return

    from prepare_context import prepare  # noqa: E402  (import here keeps --route-only dependency-light)

    workspace = args.workspace.resolve()
    output = (args.output_dir or workspace / ".agentic").resolve()
    if args.task_file is not None:
        task_path = args.task_file if args.task_file.is_absolute() else workspace / args.task_file
    else:
        output.mkdir(parents=True, exist_ok=True)
        task_path = output / "task-contract.md"
        task_path.write_text(args.task, encoding="utf-8")
    result = prepare(task_path.resolve(), workspace, output, args.changed_path, args.force_mode)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
