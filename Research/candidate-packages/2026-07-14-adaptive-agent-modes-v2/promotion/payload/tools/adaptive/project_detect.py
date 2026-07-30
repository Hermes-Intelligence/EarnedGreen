#!/usr/bin/env python3
"""Detect a repository's stack so the harness works on a fresh clone.

The verification loop previously hardcoded `tests/` + `python3 -m unittest`,
which meant it only worked on the shape it was built against. This module makes
`awbp init` real: look at what the repo actually is, record it once in
`.agentic/project.json`, and let every later command read that instead of
guessing.

Detection is evidence-based and ordered by specificity. Nothing is invented: if
no test command can be identified, that is reported as a finding rather than
guessed, because a wrong test command would silently become an always-green
acceptance check - the exact failure class this environment exists to prevent.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_EXCLUDED_DIRS = {".git", ".agentic", "node_modules", "__pycache__", ".venv", "venv",
                  "dist", "build", ".next", "target", "bin", "obj"}
_TEST_DIR_NAMES = ("tests", "test", "spec", "__tests__")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def _npm_test_script(root: Path) -> str | None:
    """Return the package.json test script, unless it is the npm placeholder."""
    raw = _read(root / "package.json")
    if not raw:
        return None
    try:
        scripts = json.loads(raw).get("scripts") or {}
    except json.JSONDecodeError:
        return None
    script = scripts.get("test")
    if not script or "no test specified" in script:
        return None
    return script


def detect_test_command(root: Path) -> dict[str, Any]:
    """Identify how this repository runs its tests, with the evidence for it."""
    if (root / "pytest.ini").is_file() or (root / "tox.ini").is_file():
        return {"command": ["python3", "-m", "pytest", "-q"], "runner": "pytest", "evidence": "pytest.ini/tox.ini"}
    pyproject = _read(root / "pyproject.toml")
    if "[tool.pytest" in pyproject:
        return {"command": ["python3", "-m", "pytest", "-q"], "runner": "pytest", "evidence": "pyproject.toml [tool.pytest]"}
    if "pytest" in _read(root / "setup.cfg"):
        return {"command": ["python3", "-m", "pytest", "-q"], "runner": "pytest", "evidence": "setup.cfg"}
    if _npm_test_script(root):
        return {"command": ["npm", "test", "--silent"], "runner": "npm", "evidence": f"package.json scripts.test = {_npm_test_script(root)!r}"}
    if (root / "go.mod").is_file():
        return {"command": ["go", "test", "./..."], "runner": "go", "evidence": "go.mod"}
    if (root / "Cargo.toml").is_file():
        return {"command": ["cargo", "test"], "runner": "cargo", "evidence": "Cargo.toml"}
    if any(root.glob("*.sln")) or any(root.glob("*.csproj")):
        return {"command": ["dotnet", "test"], "runner": "dotnet", "evidence": "*.sln/*.csproj"}
    for name in _TEST_DIR_NAMES:
        directory = root / name
        if directory.is_dir() and any(directory.rglob("test_*.py")):
            return {"command": ["python3", "-m", "unittest", "discover", "-s", name],
                    "runner": "unittest", "evidence": f"{name}/ contains test_*.py"}
    if pyproject or any(root.glob("*.py")):
        return {"command": None, "runner": "python", "evidence": "python sources but no recognised test configuration",
                "problem": "no test command could be identified"}
    return {"command": None, "runner": None, "evidence": "no recognised stack",
            "problem": "no test command could be identified"}


def detect_test_dir(root: Path) -> str | None:
    for name in _TEST_DIR_NAMES:
        if (root / name).is_dir():
            return name
    return None


def detect_source_globs(root: Path) -> list[str]:
    """Source globs the symbol sweep and the necessity probe operate over."""
    globs: list[str] = []
    for candidate in ("src", "lib", "app", "pkg"):
        if (root / candidate).is_dir():
            globs.append(f"{candidate}/**")
    if not globs:
        suffixes = {path.suffix for path in root.iterdir() if path.is_file()}
        for suffix in (".py", ".ts", ".tsx", ".js", ".go", ".cs", ".rs"):
            if suffix in suffixes:
                globs.append(f"**/*{suffix}")
    return globs or ["**/*"]


def detect(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    test = detect_test_command(root)
    return {
        "schema_version": 1,
        "detected_at_root": root.name,
        "test": test,
        "test_dir": detect_test_dir(root),
        "source_globs": detect_source_globs(root),
        "vcs": "git" if (root / ".git").exists() else None,
    }


def test_command(project: dict[str, Any]) -> list[str]:
    """The one place that knows where the test command lives in project.json.

    Every consumer used to reach into the dict itself, and a consumer that
    guesses the key wrong gets `[]` -- which downstream reads as "no runner" or,
    worse, compiles a suite that runs nothing and is green forever. One accessor,
    one truth, and a wrong key becomes an import error rather than a silent zero.
    """
    return list((project.get("test") or {}).get("command") or [])


def test_evidence(project: dict[str, Any]) -> str:
    return str((project.get("test") or {}).get("evidence") or "")


_MISSING_RUNNER = re.compile(
    r"No module named (?P<mod>\S+)|is not recognized as|command not found|"
    r"cannot find the path|executable file not found", re.I)


def verify_test_command(root: Path, command: list[str], timeout: int = 300) -> dict[str, Any]:
    """Run the detected command once so a broken baseline is known NOW.

    A test command that already fails cannot serve as an acceptance check: it
    would be red before the agent starts and stay red, poisoning the loop with a
    failure the agent did not cause.

    Crucially, a MISSING RUNNER is not a red test suite. `python -m pytest` with
    pytest uninstalled exits 1 exactly like a failing test, and reporting that as
    "your tests are red" is precisely the misleading diagnostic this environment
    exists to prevent. The two are separated here.
    """
    if not command:
        return {"ran": False, "reason": "no command detected"}
    resolved = [sys.executable if part == "python3" else part for part in command]
    try:
        completed = subprocess.run(resolved, cwd=root, text=True, capture_output=True,
                                   encoding="utf-8", errors="replace", timeout=timeout)
    except FileNotFoundError as exc:
        return {"ran": False, "runner_missing": True, "reason": f"runner not installed: {exc}"}
    except subprocess.TimeoutExpired:
        return {"ran": False, "reason": f"timed out after {timeout}s"}
    output = (completed.stdout + "\n" + completed.stderr).strip()
    match = _MISSING_RUNNER.search(output)
    if match and completed.returncode != 0:
        missing = match.groupdict().get("mod") or command[0]
        return {"ran": False, "runner_missing": True, "missing": missing.strip("'\""),
                "reason": f"the test runner is not installed ({missing.strip(chr(39))})",
                "output_tail": output[-1500:]}
    return {
        "ran": True,
        "exit_code": completed.returncode,
        "green": completed.returncode == 0,
        "output_tail": output[-1500:],
    }


def init(root: Path, verify: bool = True) -> dict[str, Any]:
    root = Path(root).resolve()
    project = detect(root)
    if verify and project["test"]["command"]:
        run = verify_test_command(root, project["test"]["command"])
        project["test"]["baseline_run"] = run
        if run.get("runner_missing"):
            project["test"]["problem"] = (
                f"the {project['test']['runner']} runner is not installed here, so the repository's tests could not be "
                f"run. This is NOT a failing test suite. Install it and re-run `awbp init`; until then the loop has the "
                f"symbol sweep and the completion gate but no acceptance check.")
            project["test"]["fix"] = {"pytest": "pip install pytest", "npm": "npm install",
                                      "go": "install Go", "cargo": "install Rust",
                                      "dotnet": "install the .NET SDK"}.get(project["test"]["runner"])
        elif run.get("green") is False:
            project["test"]["problem"] = ("the repository's own tests are RED before any agent work; they cannot be used "
                                          "as an acceptance check until they pass")
    agentic = root / ".agentic"
    agentic.mkdir(exist_ok=True)
    (agentic / "project.json").write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return project


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--no-verify", action="store_true", help="skip the one-time baseline test run")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    project = init(args.workspace, verify=not args.no_verify)
    rendered = json.dumps(project, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if project["test"].get("command") else 1)


if __name__ == "__main__":
    main()
