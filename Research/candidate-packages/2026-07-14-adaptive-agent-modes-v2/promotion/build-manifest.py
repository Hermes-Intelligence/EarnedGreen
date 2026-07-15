#!/usr/bin/env python3
"""Rebuild promotion/manifest.json from the promotion/payload tree.

Every payload file is promoted to the repo-relative path equal to its path
inside promotion/payload/. The five deep boundary-fixture trees live under the
SHORT source home promotion/fx/<alias>/ instead (mapped below to their
Evals/adaptive-fixtures/<id>/ targets): with the payload prefix their nested
paths exceeded the Windows 260-character MAX_PATH, which broke git's
per-directory .gitignore probe inside the secret-hygiene release-gate check.
before_sha256 is the CURRENT hash of an existing target (null for new files)
so tools/promote-candidate.ps1 refuses to run if Stable drifted, and
tools/rollback-release.ps1 can restore cleanly.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent          # promotion/
CANDIDATE = HERE.parent
REPO = next(p for p in CANDIDATE.parents if (p / "Runtime/stable/manifest.json").exists())
PAYLOAD = HERE / "payload"

FORBIDDEN_PREFIXES = (".git", ".claude/commands", "Research/candidate-packages", "Runtime/releases")

# Short source alias -> promoted fixture home (keeps every source path well
# under MAX_PATH; targets in the real repo top out around 180 characters).
FIXTURE_ALIASES = {
    "v2": "Evals/adaptive-fixtures/adaptive-contract-evolution-v2",
    "v3": "Evals/adaptive-fixtures/adaptive-contract-evolution-v3",
    "v4": "Evals/adaptive-fixtures/adaptive-contract-evolution-v4",
    "clarity": "Evals/adaptive-fixtures/implicit-conventions-v1",
    "scale": "Evals/adaptive-fixtures/implicit-conventions-scale-v1",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    pairs = []
    for source in sorted(PAYLOAD.rglob("*")):
        if not source.is_file() or "__pycache__" in source.parts or source.suffix == ".pyc":
            continue
        rel = source.relative_to(PAYLOAD).as_posix()
        pairs.append(("promotion/payload/" + rel, rel))
    for alias, target_home in sorted(FIXTURE_ALIASES.items()):
        root = HERE / "fx" / alias
        if not root.is_dir():
            raise SystemExit(f"missing fixture source tree: promotion/fx/{alias}")
        for source in sorted(root.rglob("*")):
            if not source.is_file() or "__pycache__" in source.parts or source.suffix == ".pyc":
                continue
            rel = source.relative_to(root).as_posix()
            pairs.append((f"promotion/fx/{alias}/" + rel, f"{target_home}/" + rel))

    files = []
    existing_targets = []
    seen_targets = set()
    for source_rel, target_rel in sorted(pairs, key=lambda row: row[1]):
        if any(target_rel == p or target_rel.startswith(p + "/") for p in FORBIDDEN_PREFIXES):
            raise SystemExit(f"forbidden promotion target in payload: {target_rel}")
        if target_rel in seen_targets:
            raise SystemExit(f"duplicate promotion target: {target_rel}")
        seen_targets.add(target_rel)
        target = REPO / target_rel
        before = sha256(target) if target.exists() else None
        if before is not None:
            existing_targets.append(target_rel)
        files.append({
            "source": source_rel,
            "target": target_rel,
            "before_sha256": before,
            "after_sha256": sha256(CANDIDATE / source_rel),
        })

    manifest = {
        "schema_version": 1,
        "candidate_id": CANDIDATE.name,
        "release": "0.2.0",
        "status": "awaiting-approval",
        "stable_manifest_before_sha256": sha256(REPO / "Runtime/stable/manifest.json"),
        "required_evals": [
            {"report": "evidence/candidate-eval-summary.json", "minimum_passed": 25, "maximum_failed": 0},
            {"report": "evidence/stable-release-gate-infrastructure.json", "minimum_passed": 15, "maximum_failed": 0},
        ],
        "files": files,
        "approval": {
            "approved": False,
            "approved_by": None,
            "approved_at": None,
            "notes": "Owner approved promotion under the repositioned framing (cost ladder + governance controls, decisive null on correctness lift). release-gate.ps1 -Mode full runs at -Approve time and is EXPECTED to fail objective-complete (open requirements) for this incremental promotion; the owner-run -Approve uses the recorded operator skip. No gate is weakened.",
        },
        "rollback": "generated automatically by tools/promote-candidate.ps1 if and only if approved",
        "provider_calls_authorized": 0,
    }
    out = HERE / "manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "files": len(files),
        "existing_targets": existing_targets,
        "new_targets": len(files) - len(existing_targets),
        "stable_manifest_before_sha256": manifest["stable_manifest_before_sha256"],
    }, indent=2))


if __name__ == "__main__":
    main()
