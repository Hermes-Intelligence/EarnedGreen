#!/usr/bin/env python
"""Fixture Admission Gate: fail-closed semantic validity check for campaign fixtures.

Every NEW ad-hoc benchmark fixture must pass this gate before any preflight or
campaign approval can reference it. The gate exists because the
adaptive-contract-evolution campaign spent six paid calls on a fixture whose
task text was ambiguous, whose grader collapsed all dimensions on the first
exception and whose contract hardcoded a broken python3 alias -- none of which
the mechanical preflight could see.

Usage: python fixture_admission.py --fixture <dir> [--output <json>]
Exit 0 only when the verdict is PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CANDIDATE = HERE.parent

RECORD_SCHEMA_VERSION = 1
FORBIDDEN_HOST_TOKENS = ("python3", "jq ", "npx ", "bash -c", "/usr/bin/")
# Files whose only job is to serialize/render graded output. The
# format-adversary must differ from the primary reference in at least one of
# these, otherwise it is a verbatim copy and proves nothing. A fixture whose
# format-bearing files live elsewhere declares its own list in
# fixture-contract.json under "format_bearing_files"; this constant is the
# default for fixtures (v4) that predate the contract key.
FORMAT_BEARING_FILES = ("src/serializer.py", "src/digest_helper.py", "src/consumers.py")
TRIGGER_PATTERN = re.compile(r"\b(registry|registries|lookup|open.world|unseen|unknown|grows?\s+at\s+runtime)\b", re.IGNORECASE)
MISS_PATTERN = re.compile(
    r"\b(unknown|unregistered|not\s+(?:present|registered|found)|not\s+in\s+the\s+\w+|"
    r"no\s+(?:handler|registered|entry|match)|absent|missing\s+from|"
    r"without\s+a\s+(?:registered\s+)?(?:handler|entry)|lookup\s+fails|cache\s+miss(?:es)?|first\s+time)\b",
    re.IGNORECASE,
)
BEHAVIOR_PATTERN = re.compile(
    r"\b(raise[sd]?|return(?:s|ed)?|reject(?:s|ed)?|accept(?:s|ed)?|ignore[sd]?|increment(?:s|ed)?|"
    r"record(?:s|ed)?|propagate[sd]?|pass(?:es)?\s+through|succeed(?:s|ed)?|error(?:s)?|treated|handled|"
    r"(?:may|can)\s+appear|must\s+not)\b",
    re.IGNORECASE,
)

HOSTILE_IMPORT_BOMB = 'raise RuntimeError("hostile candidate: import-time failure")\n'
HOSTILE_CALL_BOMB = (
    "def _hostile(*args, **kwargs):\n"
    '    raise RuntimeError("hostile candidate: raises inside the first exercised function")\n'
    "def __getattr__(name):\n"
    "    return _hostile\n"
)
HOSTILE_WRONG_TYPES = (
    "def _wrong(*args, **kwargs):\n"
    "    return 42\n"
    "def __getattr__(name):\n"
    "    return _wrong\n"
)


def repo_root() -> Path:
    for parent in (HERE, *HERE.parents):
        if (parent / "Runtime/stable/manifest.json").exists():
            return parent
    raise RuntimeError("AgenticWorkBestPractices root not found")


def resolve_command(command: list[str], python: str | None = None) -> list[str]:
    """Substitute the portable {python} placeholder with the pinned host interpreter."""
    python = python or sys.executable
    return [python if token in ("{python}", "python3", "python") else token for token in command]


# Every locally-authored candidate boundary fixture lives under implementation/
# in its own directory. Resolution is by declared id, so adding a new version
# (v3, v4, ...) only requires listing its directory here.
CANDIDATE_FIXTURE_DIRS = ("mode-boundary-fixture", "mode-boundary-fixture-v3", "mode-boundary-fixture-v4",
                          "mode-boundary-fixture-clarity", "mode-boundary-fixture-scale",
                          "mode-boundary-fixture-medi-ny", "mode-boundary-fixture-vextrum-edition-v1",
                          "mode-boundary-fixture-hermes-etl-skip-v1", "mode-boundary-fixture-vextrum-era-v2",
                          "mode-boundary-fixture-vextrum-era-v3-gen4",
                          "mode-boundary-fixture-vextrum-dataflow-era-v1",
                          "mode-boundary-fixture-vextrum-dataflow-era-v2",
                          "mode-boundary-fixture-portal-insights-era-v1")


def local_fixture_dir(fixture_id: str, base: Path | None = None) -> tuple[Path | None, dict[str, Any] | None]:
    """Return (directory, contract) for a locally-authored candidate fixture, or (None, None)."""
    base = base or HERE
    for name in CANDIDATE_FIXTURE_DIRS:
        contract_path = base / name / "fixture-contract.json"
        if contract_path.exists():
            contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
            if contract.get("id") == fixture_id:
                return base / name, contract
    return None, None


def fixture_fingerprint(fixture_dir: Path) -> dict[str, Any]:
    """Content fingerprint over every fixture file; used for admission freshness."""
    digest = hashlib.sha256()
    newest_mtime = 0.0
    count = 0
    for path in sorted(fixture_dir.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        count += 1
        newest_mtime = max(newest_mtime, path.stat().st_mtime)
        digest.update(path.relative_to(fixture_dir).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return {"file_count": count, "newest_mtime": newest_mtime, "sha256": digest.hexdigest().upper()}


def strip_code(text: str) -> str:
    """Remove fenced blocks and inline code spans so identifiers do not read as prose."""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    return re.sub(r"`[^`\n]*`", " ", text)


def sentences(text: str) -> list[str]:
    fragments: list[str] = []
    for line in text.splitlines():
        line = line.strip().lstrip("-*").strip()
        if line:
            fragments.extend(part.strip() for part in re.split(r"(?<=[.!?])\s+", line) if part.strip())
    return fragments


def interpretation_coverage(task_text: str, decision_points: list[dict] | None = None) -> dict[str, Any]:
    """Check f: open-world miss rule plus pinned decision points.

    When the task mentions registry/mapping-growth/lookup/unknown/unseen/open-world
    concepts, an explicit behavior sentence for the miss/absent case is required.
    When a decision_points section is supplied (fixture-contract.json fixtures),
    every point must pin one option to a task sentence. Pass decision_points=None
    for contract-table fixtures that have no fixture-contract.json.
    """
    stripped = strip_code(task_text)
    trigger_terms = sorted({match.group(0).lower() for match in TRIGGER_PATTERN.finditer(stripped)})
    issues: list[str] = []
    miss_sentence = None
    if trigger_terms:
        for sentence in sentences(stripped):
            if MISS_PATTERN.search(sentence) and BEHAVIOR_PATTERN.search(sentence):
                miss_sentence = sentence
                break
        if miss_sentence is None:
            issues.append(
                "task mentions open-world/registry terms (" + ", ".join(trigger_terms) + ") "
                "but never states the behavior for the miss/absent case "
                "(e.g. 'when the type is not present in the registry, X happens')"
            )
    normalized_task = re.sub(r"\s+", " ", task_text).lower()
    unpinned: list[str] = []
    if decision_points is not None:
        if trigger_terms and not decision_points:
            issues.append("fixture-contract.json has no decision_points section although the task is open-world")
        for point in decision_points:
            point_id = point.get("id", "<missing id>")
            if len(point.get("options", [])) < 2:
                unpinned.append(f"{point_id}: fewer than two declared options")
                continue
            if not point.get("pinned"):
                unpinned.append(f"{point_id}: no pinned choice")
                continue
            anchor = re.sub(r"\s+", " ", point.get("pinned_by", "")).lower().strip()
            if not anchor or anchor not in normalized_task:
                unpinned.append(f"{point_id}: pinned_by sentence not found in task.md")
        if unpinned:
            issues.append("unpinned decision points: " + "; ".join(unpinned))
    return {
        "triggered": bool(trigger_terms),
        "trigger_terms": trigger_terms,
        "miss_behavior_sentence": miss_sentence,
        "decision_points_declared": None if decision_points is None else len(decision_points),
        "unpinned_decision_points": unpinned,
        "passed": not issues,
        "issues": issues,
    }


def scan_paid_history(repo: Path, fixture_id: str, runs_dir: Path | None = None) -> dict[str, Any]:
    """Read-only scan of Evals/runs for prior paid outcomes of this fixture.

    ``runs_dir`` overrides the scan directory so lifecycle tests can exercise the
    no-paid-history canary rule deterministically instead of depending on the
    mutable live Evals/runs state (which drifts every time a canary is approved
    and run -- e.g. the 2026-07-15 live clarity canary gave implicit-conventions-v1
    paid history and silently broke every test that assumed it was unpaid).
    """
    runs_dir = runs_dir if runs_dir is not None else repo / "Evals/runs"
    matching: list[dict[str, Any]] = []
    scanned = 0
    if runs_dir.is_dir():
        for run_dir in sorted(runs_dir.iterdir()):
            scanned += 1
            if fixture_id not in run_dir.name:
                continue
            record_path = run_dir / "run-record.json"
            if not record_path.is_file():
                continue
            try:
                record = json.loads(record_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                continue
            grader = record.get("grader") or {}
            matching.append({
                "run_id": run_dir.name,
                "case_id": record.get("case_id"),
                "arm": record.get("arm"),
                "outcome_valid": bool(record.get("outcome_valid")),
                "score": grader.get("score"),
                "distinct_dimensions": len({row.get("id") for row in grader.get("checks", [])}),
            })
    valid = [row for row in matching if row["outcome_valid"]]
    return {"runs_scanned": scanned, "matching_runs": matching, "valid_paid_runs": len(valid)}


def run_json(command: list[str], cwd: Path, timeout: int = 60) -> tuple[int, dict[str, Any] | None, str]:
    try:
        completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True,
                                   encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, None, f"timeout after {timeout}s: {' '.join(command)}"
    output = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
    parsed = None
    for line in reversed(output.splitlines()):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            parsed = candidate
            break
    return completed.returncode, parsed, output[-2000:]


class Gate:
    def __init__(self, fixture_dir: Path):
        self.fixture = fixture_dir.resolve()
        self.repo = repo_root()
        self.contract = json.loads((self.fixture / "fixture-contract.json").read_text(encoding="utf-8-sig"))
        self.public = self.fixture / "public"
        self.grader = self.fixture / self.contract["hidden_grader"]
        self.declared = set(self.contract["checks"])
        self.expected_score = self.contract.get("expected_reference_score", 100)
        # Proprietary fixtures (workspace_source == "hermes-local-copy") never commit
        # the real subtree the agent edits. The base workspace and every graded
        # overlay materialize the parser at grade time from a LOCAL Hermes git ref;
        # only the grader, task, sample PDF, conventions and notes live in the
        # package. See _provision_hermes / fixture-contract.json "hermes_local".
        self.proprietary = (self.contract.get("proprietary") is True
                            or self.contract.get("workspace_source") == "hermes-local-copy")

    # ---- proprietary / local-git-copy materialization -----------------------
    # The source the agent edits is a real proprietary subtree and is NEVER
    # committed here: every variant is materialized at grade time from a LOCAL
    # git ref. `local_source` is the general form; `hermes_local` is the original
    # medi-ny spelling and is still honoured so that fixture keeps working.
    _LEGACY_DEFAULTS = {"repo_dir": "HermesAirflow", "target_path": "src/pdl_parser.py"}

    def _source_spec(self) -> dict[str, Any]:
        spec = self.contract.get("local_source") or self.contract.get("hermes_local")
        if not spec:
            raise RuntimeError("a proprietary fixture must declare `local_source` (or legacy `hermes_local`)")
        merged = dict(spec)
        # medi-ny names the file `parser_path`; the general contract says `source_path`.
        merged.setdefault("source_path", merged.get("parser_path"))
        if not merged.get("source_path") and not merged.get("files"):
            raise RuntimeError("`local_source` must name `source_path` (single-file form) "
                               "or `files` (multi-file form)")
        merged.setdefault("target_path", self._LEGACY_DEFAULTS["target_path"])
        merged.setdefault("repo_dir", self._LEGACY_DEFAULTS["repo_dir"])
        return merged

    def _file_specs(self) -> list[dict[str, Any]]:
        """Per-file materialization specs. Single-file contracts yield one spec;
        the multi-file form (`local_source.files: [{source_path, target_path,
        altformat_replace?, normalizations?}, ...]`) inherits repo_dir/refs from
        the shared spec — a wide era usually spans several modules."""
        shared = self._source_spec()
        files = shared.get("files")
        if not files:
            return [shared]
        specs = []
        for row in files:
            merged = {k: v for k, v in shared.items() if k != "files"}
            # per-file keys override; per-file altformat/normalizations REPLACE
            # the shared ones, never merge, so a rule can't apply twice
            for key in ("altformat_append", "altformat_replace", "normalizations"):
                merged.pop(key, None)
            merged.update(row)
            if not merged.get("source_path") or not merged.get("target_path"):
                raise RuntimeError("each entry in `local_source.files` needs source_path and target_path")
            specs.append(merged)
        return specs

    def _source_repo(self) -> Path:
        # The local checkout is a sibling of the AWBP repo root (…/GithubRepos/<repo_dir>).
        repo = self.repo.parent / self._source_spec()["repo_dir"]
        if not (repo / ".git").exists():
            raise RuntimeError(f"local repo not found for materialization: {repo}")
        return repo

    def _git_show(self, ref: str, rel_path: str) -> str:
        repo = self._source_repo()
        completed = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{rel_path}"],
                                   text=True, capture_output=True, encoding="utf-8", errors="replace")
        if completed.returncode != 0:
            raise RuntimeError(f"git show {ref}:{rel_path} failed: {completed.stderr[:300]}")
        return completed.stdout

    def _normalize_source(self, src: str, spec: dict[str, Any] | None = None) -> str:
        """Apply the contract's declared rewrites so the materialized file stands alone.

        Declared in the contract rather than hardcoded here: medi-ny rewrites a
        Hermes package import to `import config`; another fixture's source will
        need something else entirely, and a hardcoded Python regex would silently
        do nothing to a JS file rather than fail.
        """
        spec = spec or self._source_spec()
        rules = spec.get("normalizations")
        if rules is None and "import_normalization" in spec:
            # Legacy medi-ny behaviour, preserved verbatim.
            return re.sub(r"^from hermes_intelligence[^\n]*import config", "import config", src, flags=re.M)
        for rule in rules or []:
            src = re.sub(rule["pattern"], rule["replacement"], src, flags=re.M)
        return src

    def _variant_source(self, variant: str, spec: dict[str, Any] | None = None) -> str:
        spec = spec or self._source_spec()
        base_ref = spec["before_ref"] if variant.startswith("before") else spec["after_ref"]
        src = self._normalize_source(self._git_show(base_ref, spec["source_path"]), spec)
        if variant.endswith("altformat"):
            # A genuinely DIFFERENT-but-valid solution: it proves the semantic
            # grader is agnostic to formatting choices a correct implementation is
            # free to make. Two spellings, because the shape of "a valid variant"
            # depends on the module:
            #   altformat_append  - wrap the public entry point (works when the
            #                       behaviour to vary is reachable from outside);
            #   altformat_replace - rewrite the source (needed when the choice
            #                       lives in an INTERNAL function that no wrapper
            #                       can reach, e.g. the JS edition renderer).
            # Both are per-fixture and language-specific, so both live in the contract.
            append = spec.get("altformat_append")
            replace = spec.get("altformat_replace")
            if not append and not replace:
                raise RuntimeError("this fixture declares an `-altformat` variant but no "
                                   "`altformat_append`/`altformat_replace` in its local_source spec")
            for rule in replace or []:
                mutated = src.replace(rule["find"], rule["replace"], 1)
                if mutated == src:
                    # Fail loudly: a no-op alt would silently be the reference
                    # again, and `reference-alt-pass` would prove nothing.
                    raise RuntimeError(f"altformat_replace found no match for {rule['find'][:60]!r}: "
                                       "the alt variant would be identical to the reference")
                src = mutated
            if append:
                src += append
        return src

    def _provision(self, workspace: Path, overlays: list[Path]) -> None:
        """Materialize the graded workspace. Standard fixtures copy public + overlays.
        Proprietary fixtures copy the non-proprietary public/overlay files, then inject
        the git-materialized parser variant selected by the overlay (base = before)."""
        shutil.copytree(self.public, workspace, dirs_exist_ok=True)
        for overlay in overlays:
            shutil.copytree(overlay, workspace, dirs_exist_ok=True)
        if not self.proprietary:
            return
        mapping = self.contract.get("materialize", {})
        variant = mapping.get("base", "before")
        for overlay in overlays:
            key = overlay.relative_to(self.fixture).as_posix()
            if key in mapping:
                variant = mapping[key]
        self.materialize_into(workspace, variant)

    def materialize_into(self, workspace: Path, variant: str) -> None:
        """Write every materialized source file of `variant` into the workspace.

        For the altformat variant, files WITHOUT altformat rules materialize as
        the plain reference — the valid variant differs only where the contract
        says a different-but-correct choice exists; at least one file must
        declare rules or the alt would silently equal the reference."""
        specs = self._file_specs()
        if variant.endswith("altformat"):
            if not any(s.get("altformat_append") or s.get("altformat_replace") for s in specs):
                raise RuntimeError("this fixture declares an `-altformat` variant but no file "
                                   "carries altformat_append/altformat_replace rules")
        for spec in specs:
            file_variant = variant
            if (variant.endswith("altformat")
                    and not (spec.get("altformat_append") or spec.get("altformat_replace"))):
                file_variant = "after"
            target = workspace / spec["target_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(self._variant_source(file_variant, spec), encoding="utf-8")

    def grade_overlay(self, overlays: list[Path], mutate=None) -> dict[str, Any]:
        """Provision a temp workspace (public + overlays, or materialized parser for
        proprietary fixtures), run public test and grader."""
        with tempfile.TemporaryDirectory(prefix="fixture-admission-") as temp_name:
            workspace = Path(temp_name)
            self._provision(workspace, overlays)
            if mutate:
                mutate(workspace)
            public_cmd = resolve_command(list(self.contract["public_test"]))
            public_exit, _, public_out = run_json(public_cmd, workspace)
            hidden_exit, hidden, hidden_out = run_json([sys.executable, str(self.grader), str(workspace)], workspace)
        reported = [row.get("id") for row in (hidden or {}).get("checks", [])]
        return {
            "public_pass": public_exit == 0,
            "hidden_exit": hidden_exit,
            "hidden_json": hidden is not None,
            "score": (hidden or {}).get("score"),
            "reported_dimensions": reported,
            "diagnostic": None if hidden else (hidden_out or public_out),
        }

    def check_reference(self, check_id: str, overlay: Path) -> dict[str, Any]:
        if not overlay.is_dir():
            return {"id": check_id, "passed": False, "detail": f"missing overlay directory: {overlay}"}
        outcome = self.grade_overlay([overlay])
        missing = sorted(self.declared - set(outcome["reported_dimensions"]))
        passed = (outcome["public_pass"] and outcome["hidden_json"]
                  and outcome["score"] == self.expected_score and not missing)
        detail = "" if passed else (
            f"public_pass={outcome['public_pass']} score={outcome['score']} "
            f"expected={self.expected_score} missing_dimensions={missing} diagnostic={outcome['diagnostic']}"
        )
        result = {"id": check_id, "passed": passed, "detail": detail, "score": outcome["score"]}
        if check_id == "reference-alt-pass":
            notes_path = overlay / "ALT-NOTES.json"
            if not notes_path.is_file():
                result["passed"] = False
                result["detail"] = (result["detail"] + " " if result["detail"] else "") + \
                    "hidden/reference-alt/ALT-NOTES.json missing: the alt must declare its interpretation differences"
            else:
                notes = json.loads(notes_path.read_text(encoding="utf-8-sig"))
                result["alt_interpretation_differences"] = {
                    "pre_reconciliation": notes.get("pre_reconciliation_result", {}).get("interpretations"),
                    "after_pinning": notes.get("interpretation_differences_after_pinning"),
                    "structural": notes.get("structural_differences"),
                }
        return result

    def check_format_adversary(self) -> dict[str, Any]:
        """Prove the hidden grader is format-agnostic, not merely style-tolerant.

        A fixture with serialized/rendered output dimensions declares them in
        `serialized_output_dimensions`. For such a fixture the grader must accept
        a semantically-correct solution that uses a DIFFERENT serialization from
        the primary reference. `hidden/reference-format-alt` provides exactly
        that: same substance (registry routed through, schema_version carried,
        correct type/id/keys), deliberately different delimiters/prefix/placement.
        The grader must still score it the expected reference score, and the alt
        must genuinely differ from the primary reference on at least one
        format-bearing file (otherwise it is a verbatim copy that proves nothing).

        A fixture with no serialized-output dimensions skips this check with a
        recorded reason.
        """
        dims = self.contract.get("serialized_output_dimensions") or []
        if not dims:
            return {"id": "format-adversary", "passed": True, "skipped": True,
                    "detail": "fixture declares no serialized_output_dimensions; "
                              "format-adversary is opt-in and not applicable here",
                    "serialized_output_dimensions": []}
        overlay = self.fixture / "hidden/reference-format-alt"
        if not overlay.is_dir():
            return {"id": "format-adversary", "passed": False, "skipped": False,
                    "detail": (f"fixture declares serialized_output_dimensions {dims} but has no "
                               f"hidden/reference-format-alt/ to prove the grader is format-agnostic"),
                    "serialized_output_dimensions": dims}
        outcome = self.grade_overlay([overlay])
        missing = sorted(self.declared - set(outcome["reported_dimensions"]))
        # Anti-copy guard: the adversary must differ from the primary reference
        # in at least one format-bearing file. A fixture whose format-bearing
        # files live elsewhere declares them in the contract; the constant is
        # the default for fixtures that predate the key.
        format_bearing = tuple(self.contract.get("format_bearing_files") or FORMAT_BEARING_FILES)
        reference = self.fixture / "hidden/reference"
        normalize = lambda text: re.sub(r"\s+", " ", text).strip()  # noqa: E731
        differing: list[str] = []
        for rel in format_bearing:
            ref_file, alt_file = reference / rel, overlay / rel
            if ref_file.is_file() and alt_file.is_file():
                if normalize(ref_file.read_text(encoding="utf-8-sig")) != normalize(alt_file.read_text(encoding="utf-8-sig")):
                    differing.append(rel)
        grader_agnostic = (outcome["public_pass"] and outcome["hidden_json"]
                           and outcome["score"] == self.expected_score and not missing)
        passed = grader_agnostic and bool(differing)
        if not passed:
            if not grader_agnostic:
                detail = (f"format-brittle grader: a semantically-correct solution with a different "
                          f"serialization scored {outcome['score']} (expected {self.expected_score}), "
                          f"public_pass={outcome['public_pass']} missing_dimensions={missing} "
                          f"diagnostic={outcome['diagnostic']}")
            else:
                detail = ("hidden/reference-format-alt does not differ from hidden/reference on any "
                          f"format-bearing file {list(format_bearing)}; it is a verbatim copy and "
                          "does not exercise format-agnosticism")
        else:
            detail = ""
        return {"id": "format-adversary", "passed": passed, "skipped": False, "detail": detail,
                "serialized_output_dimensions": dims, "adversary_score": outcome["score"],
                "differing_format_files": differing}

    def check_negative_controls(self) -> dict[str, Any]:
        controls_root = self.fixture / "negative-controls"
        rows = []
        for expected in self.contract.get("expected_controls", []):
            overlay = controls_root / expected["id"]
            if not overlay.is_dir():
                continue  # non-control entries (e.g. the reference band) are verified elsewhere
            outcome = self.grade_overlay([overlay])
            in_band = (outcome["score"] is not None
                       and expected["min_score"] <= outcome["score"] <= expected["max_score"])
            rows.append({
                "control": expected["id"],
                "public_pass": outcome["public_pass"],
                "hidden_rejected": outcome["hidden_exit"] != 0,
                "score": outcome["score"],
                "expected_band": [expected["min_score"], expected["max_score"]],
                "band_pass": in_band,
                "ok": outcome["public_pass"] and outcome["hidden_exit"] != 0 and in_band,
            })
        passed = bool(rows) and all(row["ok"] for row in rows)
        detail = "" if passed else ("no negative controls found" if not rows else
                                    "failing controls: " + ", ".join(r["control"] for r in rows if not r["ok"]))
        return {"id": "negative-control", "passed": passed, "detail": detail, "controls": rows}

    def check_grader_isolation(self) -> dict[str, Any]:
        """Hostile-candidate battery: the grader must degrade per-dimension, never collapse."""
        def rewrite_sources(content: str):
            def mutate(workspace: Path) -> None:
                for path in (workspace / "src").rglob("*.py"):
                    path.write_text(content, encoding="utf-8")
            return mutate

        battery = [
            ("import-bomb", HOSTILE_IMPORT_BOMB),
            ("first-call-bomb", HOSTILE_CALL_BOMB),
            ("wrong-types", HOSTILE_WRONG_TYPES),
        ]
        rows = []
        for name, content in battery:
            outcome = self.grade_overlay([], mutate=rewrite_sources(content))
            reported = set(outcome["reported_dimensions"])
            missing = sorted(self.declared - reported)
            collapsed = bool(missing)
            row = {
                "hostile": name,
                "grader_emitted_json": outcome["hidden_json"],
                "reported_dimensions": len(outcome["reported_dimensions"]),
                "declared_dimensions": len(self.declared),
                "dimension_diff": missing,
                "score": outcome["score"],
                "scored_below_reference": outcome["score"] is not None and outcome["score"] < self.expected_score,
            }
            row["ok"] = outcome["hidden_json"] and not collapsed and row["scored_below_reference"]
            rows.append(row)
        passed = all(row["ok"] for row in rows)
        detail = "" if passed else "; ".join(
            f"{row['hostile']}: reported {row['reported_dimensions']}/{row['declared_dimensions']} dimensions, "
            f"missing {row['dimension_diff']}, score={row['score']}"
            for row in rows if not row["ok"]
        )
        return {"id": "grader-isolation", "passed": passed, "detail": detail, "battery": rows}

    def check_platform_lint(self) -> dict[str, Any]:
        scanned: list[Path] = [self.fixture / "fixture-contract.json", self.grader]
        scanned.extend((self.public / "tests").rglob("*.py"))
        for suffix in ("*.sh", "*.ps1", "*.cmd", "*.bat"):
            scanned.extend(self.fixture.rglob(suffix))
        hits, exempt = [], []
        for path in sorted(set(scanned)):
            if not path.is_file():
                continue
            relative = path.relative_to(self.fixture).as_posix()
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            for token in FORBIDDEN_HOST_TOKENS:
                for line_number, line in enumerate(text.splitlines(), 1):
                    if line_number == 1 and line.startswith("#!"):
                        continue  # shebangs are never executed host-side; graders run via sys.executable
                    if token in line:
                        entry = {"file": relative, "line": line_number, "token": token.strip()}
                        if "isolation" in path.parts:
                            entry["exempt_reason"] = "WSL-only script under an isolation/ directory"
                            exempt.append(entry)
                        else:
                            hits.append(entry)
        passed = not hits
        detail = "" if passed else "non-portable host tokens: " + "; ".join(
            f"{hit['file']}:{hit['line']} '{hit['token']}'" for hit in hits)
        return {"id": "platform-lint", "passed": passed, "detail": detail, "hits": hits, "exempted": exempt}

    def check_convention_anchors(self) -> dict[str, Any]:
        """Class-aware interpretation coverage for underspecified-by-design fixtures.

        Such a task deliberately does NOT pin its decision points in sentences, so
        sentence-pinning would always fail. The validity requirement inverts: every
        hidden-grader expectation must instead be traceable to a DISCOVERABLE
        in-repo convention - the contract lists convention_anchors
        {check_id, evidence_file, quote} and each quote must literally exist
        (whitespace-normalized) in that public workspace file.
        """
        anchors = self.contract.get("convention_anchors", [])
        issues: list[str] = []
        by_check: dict[str, list[dict]] = {}
        for anchor in anchors:
            by_check.setdefault(str(anchor.get("check_id") or "<missing-check-id>"), []).append(anchor)
        normalize = lambda text: re.sub(r"\s+", " ", text)  # noqa: E731
        for check_id in sorted(self.declared):
            rows = by_check.get(check_id)
            if not rows:
                issues.append(f"{check_id}: no convention_anchor traces this hidden expectation to an in-repo convention")
                continue
            for anchor in rows:
                evidence_file = str(anchor.get("evidence_file") or "")
                target = self.public / evidence_file
                if not target.is_file():
                    issues.append(f"{check_id}: anchor evidence file not found in public workspace: {evidence_file!r}")
                    continue
                quote = str(anchor.get("quote") or "")
                if not quote.strip():
                    issues.append(f"{check_id}: anchor has no quote")
                elif normalize(quote) not in normalize(target.read_text(encoding="utf-8-sig")):
                    issues.append(f"{check_id}: anchor quote not found in {evidence_file}: {quote!r}")
        stray = sorted(set(by_check) - self.declared)
        if stray:
            issues.append("anchors reference undeclared checks: " + ", ".join(stray))
        return {"id": "interpretation-coverage", "passed": not issues, "detail": "; ".join(issues),
                "coverage": {"fixture_class": "underspecified-by-design",
                             "anchored_checks": sorted(by_check), "issues": issues}}

    def check_interpretation_coverage(self) -> dict[str, Any]:
        if self.contract.get("fixture_class") == "underspecified-by-design":
            return self.check_convention_anchors()
        task = (self.public / "task.md").read_text(encoding="utf-8-sig")
        coverage = interpretation_coverage(task, self.contract.get("decision_points", []))
        return {"id": "interpretation-coverage", "passed": coverage["passed"],
                "detail": "; ".join(coverage["issues"]), "coverage": coverage}

    def run(self, generated_at: str | None) -> dict[str, Any]:
        checks = [
            self.check_reference("reference-pass", self.fixture / "hidden/reference"),
            self.check_reference("reference-alt-pass", self.fixture / "hidden/reference-alt"),
            self.check_format_adversary(),
            self.check_negative_controls(),
            self.check_grader_isolation(),
            self.check_platform_lint(),
            self.check_interpretation_coverage(),
        ]
        verdict = "PASS" if all(row["passed"] for row in checks) else "FAIL"
        return {
            "schema_version": RECORD_SCHEMA_VERSION,
            "fixture": self.contract["id"],
            "fixture_dir": str(self.fixture),
            "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
            "fixture_fingerprint": fixture_fingerprint(self.fixture),
            "provider_calls": 0,
            "checks": checks,
            "verdict": verdict,
            "paid_history": scan_paid_history(self.repo, self.contract["id"]),
        }


def default_record_path(fixture_id: str) -> Path:
    return CANDIDATE / "evidence" / f"fixture-admission-{fixture_id}.json"


def load_admission_record(fixture_id: str, record_path: Path | None = None) -> dict[str, Any] | None:
    path = record_path or default_record_path(fixture_id)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None


def admission_status(fixture_id: str, fixture_dir: Path, record_path: Path | None = None) -> dict[str, Any]:
    """Fail-closed freshness check used by preflight and campaign creation."""
    record = load_admission_record(fixture_id, record_path)
    path = str(record_path or default_record_path(fixture_id))
    if record is None:
        return {"admitted": False, "record_path": path, "reason": "no admission record: run fixture_admission.py first"}
    if record.get("fixture") != fixture_id:
        return {"admitted": False, "record_path": path, "reason": f"admission record is for {record.get('fixture')!r}, not {fixture_id!r}"}
    if record.get("verdict") != "PASS":
        return {"admitted": False, "record_path": path, "reason": "admission record verdict is not PASS"}
    current = fixture_fingerprint(fixture_dir)
    recorded = record.get("fixture_fingerprint", {})
    if current["sha256"] != recorded.get("sha256"):
        return {"admitted": False, "record_path": path,
                "reason": "admission record is stale: fixture files changed after the record was generated"}
    if current["newest_mtime"] > recorded.get("newest_mtime", 0.0):
        return {"admitted": False, "record_path": path,
                "reason": "admission record is stale: a fixture file was touched after the record was generated"}
    return {"admitted": True, "record_path": path, "reason": None,
            "generated_at": record.get("generated_at"), "paid_history": record.get("paid_history")}


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True, help="fixture directory containing fixture-contract.json")
    parser.add_argument("--output", type=Path, help="admission record path (default: evidence/fixture-admission-<id>.json)")
    parser.add_argument("--generated-at", help="override the generated_at timestamp (ISO-8601)")
    args = parser.parse_args()
    gate = Gate(args.fixture)
    record = gate.run(args.generated_at)
    output = args.output or default_record_path(record["fixture"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    raise SystemExit(0 if record["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
