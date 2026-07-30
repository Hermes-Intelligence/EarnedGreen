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


def _node_test_files(root: Path) -> list[str]:
    """*.test.js / *.test.mjs the built-in node runner can execute.

    Listed explicitly rather than passing a glob: `node --test <dir>` differs
    across node versions in what it discovers, and a runner that silently finds
    nothing exits 0 -- an always-green suite, which is the failure this whole
    environment exists to prevent.
    """
    found: list[str] = []
    for pattern in ("**/*.test.js", "**/*.test.mjs"):
        for path in sorted(root.glob(pattern)):
            if any(part in _EXCLUDED_DIRS for part in path.relative_to(root).parts):
                continue
            found.append(path.relative_to(root).as_posix())
    return found


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
    node_tests = _node_test_files(root)
    if node_tests:
        # Node >=18 ships a test runner, so a JS repo with *.test.js files but no
        # configured runner is still runnable with ZERO dependencies. This is not a
        # corner case: plenty of frontends have no test setup at all, and that is
        # exactly where "looks done, isn't" lives.
        return {"command": ["node", "--test", *node_tests], "runner": "node--test",
                "evidence": f"{len(node_tests)} *.test.js file(s) and node's built-in runner"}
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


class UnrunnableCheck(RuntimeError):
    """No invocation for this script is known on this stack. Never guessed:
    a wrong invocation runs nothing, exits 0, and is green forever."""


def check_command(project: dict[str, Any], script: str) -> list[str]:
    """How to execute ONE check script by path, on this repository's stack.

    NOT `test_command(project) + [script]`. The detected test command names the
    repo's OWN test files (`node --test tests/public.test.js`), so appending a
    script would run the public suite alongside the check and make the check's
    verdict depend on it -- an admission gate would then be measuring the repo's
    tests rather than the proposed check.

    Keyed on the script's language rather than the repo's test runner, because a
    check is a standalone program: it must run on its own, and the runner is only
    borrowed when it adds something (pytest's assertion rewriting and reporting).
    """
    runner = str((project.get("test") or {}).get("runner") or "")
    suffix = Path(script).suffix.lower()
    if suffix == ".py":
        if runner == "pytest":
            return ["python3", "-m", "pytest", "-q", script]
        if runner in {"unittest", "python"}:
            # A plain script (incl. a unittest file with `unittest.main()`) runs
            # standalone. `python3 -m unittest <path>` does not accept a path.
            return ["python3", script]
        # NOT a default. `python3 some_pytest_file.py` defines a test function and
        # exits 0 without running it -- green forever, the exact failure this
        # module exists to prevent. An unknown runner is a fact to report.
        raise UnrunnableCheck(
            f"cannot execute the Python check {script!r}: the detected runner is {runner or 'unset'!r}, "
            "and guessing one risks a command that runs nothing and exits 0")
    if suffix in {".mjs", ".js", ".cjs"}:
        if re.search(r"\.(test|spec)\.[cm]?js$", script):
            return ["node", "--test", script]
        return ["node", script]
    raise UnrunnableCheck(
        f"no known way to execute a check script named {script!r} on this stack "
        f"(detected runner: {runner or 'none'})")


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
    # RUNNING SOMEBODY'S SUITE IS NOT A READ. On a real repository the baseline run
    # triggered a code-generation step that rewrote four tracked files, and the
    # only reason anyone noticed was a `git status` run for an unrelated purpose
    # afterwards. A tool that touches a stranger's working tree and does not say so
    # is not diagnosing the repo, it is editing it.
    before = _tracked_state(root)
    try:
        completed = subprocess.run(resolved, cwd=root, text=True, capture_output=True,
                                   encoding="utf-8", errors="replace", timeout=timeout)
    except FileNotFoundError as exc:
        return {"ran": False, "runner_missing": True, "reason": f"runner not installed: {exc}"}
    except subprocess.TimeoutExpired:
        return {"ran": False, "reason": f"timed out after {timeout}s"}
    touched = sorted(set(_tracked_state(root)) - set(before))
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
        "working_tree_touched": touched,
    }


def _tracked_state(root: Path) -> list[str]:
    """`git status --porcelain`, or an empty list where git cannot answer.

    Empty is the honest answer for a non-git directory: it means "no evidence
    either way", and the caller reports a mutation only when a file APPEARS in
    the after-state, never when the before-state was simply unknowable.
    """
    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=root, text=True,
                             capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    return [line for line in out.stdout.splitlines() if line.strip()] if out.returncode == 0 else []


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

    # A SUMMARY, not the file. The full record is always written to
    # .agentic/project.json; printing it meant a stranger's very first command
    # dumped 561 test paths into the terminal and buried the one line that
    # mattered, which was that those tests do not pass.
    print(json.dumps({k: v for k, v in project.items() if k != "test"},
                     ensure_ascii=False, indent=2))
    test = project.get("test", {})
    command = test.get("command") or []
    # Truncated for display only. On a repo with 561 suites the command IS the
    # 561 paths, and printing it in full buried the verdict under a screenful.
    shown = " ".join(command[:4])
    if len(command) > 4:
        shown += f" ... (+{len(command) - 4} more paths)"
    print(f'\ntest command   {shown or "NONE FOUND"}')
    print(f'runner         {test.get("runner") or "-"}')
    print(f'evidence       {test.get("evidence") or "-"}')
    run = test.get("baseline_run") or {}
    if run:
        print(f'baseline run   {"GREEN" if run.get("green") else "RED"} (exit {run.get("exit_code")})')
    touched = run.get("working_tree_touched") or []
    if touched:
        print(f'\nHEADS UP       running your suite MODIFIED {len(touched)} file(s) '
              f'in your working tree:')
        for line in touched[:6]:
            print(f'               {line}')
        if len(touched) > 6:
            print(f'               ... and {len(touched) - 6} more')
        print('               awbp did not write these. Your suite did, most likely a '
              'code-generation step.')
    if test.get("problem"):
        print(f'\nPROBLEM        {test["problem"]}')
    print("\nfull record    .agentic/project.json")

    # Exit status follows the ORACLE, not the search. The first version exited 0
    # whenever a test command had been FOUND, so a repository whose suite is red
    # before any agent touches it was greeted with "Ready." That is the same shape
    # as reporting a green nobody earned, made by the first command a stranger runs.
    usable = bool(test.get("command")) and (run.get("green") is not False)
    raise SystemExit(0 if usable else 1)


if __name__ == "__main__":
    main()
