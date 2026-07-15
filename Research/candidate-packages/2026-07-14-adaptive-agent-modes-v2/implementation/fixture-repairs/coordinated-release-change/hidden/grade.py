#!/usr/bin/env python3
"""Versioned wrapper that replaces only the brittle documentation substring check."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "Evals/fixtures/coordinated-release-change/hidden/grade.py").exists():
            return parent
    raise RuntimeError("repository root not found")


def semantic_docs(workspace: Path) -> bool:
    raw = (workspace / "docs/user-schema.md").read_text(encoding="utf-8")
    # Strip Markdown decoration without destroying identifier underscores.
    text = re.sub(r"[`*#]", " ", raw.lower())
    text = re.sub(r"\s+", " ", text)
    headings = all(re.search(rf"(?im)^\s*#+\s*{name}\b", raw) for name in ("expand", "migrate", "contract", "rollback"))
    retained = bool(re.search(r"legacy\s+(?:email\s+)?(?:field\s+)?(?:is\s+)?(?:retained|preserved|kept|not\s+deleted)", text))
    return headings and "primary_email" in text and "expand" in text and retained


workspace = Path(sys.argv[1]).resolve()
base = repo_root() / "Evals/fixtures/coordinated-release-change/hidden/grade.py"
completed = subprocess.run([sys.executable, str(base), str(workspace)], text=True, capture_output=True, encoding="utf-8", errors="replace")
lines = [line for line in completed.stdout.splitlines() if line.strip()]
result = json.loads(lines[-1])
for check in result["checks"]:
    if check["id"] == "documentation":
        check["passed"] = semantic_docs(workspace)
result["score"] = sum(check["weight"] for check in result["checks"] if check["passed"])
result["passed"] = result["score"] == 100
print(json.dumps(result))
raise SystemExit(0 if result["passed"] else 1)
