#!/usr/bin/env python3
"""Finding a repository's tests, whatever shape that repository is.

Two silent under-reports on one unfamiliar repository, an hour apart:

    `*.spec.ts` matched no pattern at all           28 e2e suites invisible
    a nested-manifest rule excluded monorepo packages  10 first-party suites dropped

Both were the same failure: a hardcoded list of conventions, incomplete, and
incomplete QUIETLY. Under-reporting sends a run to a weaker oracle than it had,
and unlike over-reporting it leaves no trace to notice.

The fix is three layers and this file tests all three:

    1. READ WHAT THE REPO DECLARES - jest/vitest/playwright/pytest config
    2. FALL BACK to built-in shapes across ecosystems
    3. REPORT NEAR MISSES - because no list of conventions is ever complete, and
       the promise that can be kept is "nothing is missed quietly"

Every layout below is one a real repository actually uses.

    python tests/test_test_discovery.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import oracle_plan          # noqa: E402

PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(f"{name}{' — ' + detail if detail else ''}")


def build(root: Path, files: dict[str, str]) -> Path:
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def scan(root: Path) -> dict:
    oracle_plan._NESTED_CACHE.clear()
    files = [p for p in root.rglob("*") if p.is_file() and oracle_plan._own(root, p)]
    return oracle_plan.find_tests(root, files)


def names(result: dict) -> set[str]:
    return {Path(p).name for p in result["matched"]}


# ── layer 2: built-in shapes, across ecosystems ───────────────────────────────
def test_every_ecosystem_shape(tmp: Path) -> None:
    root = build(tmp / "shapes", {
        "src/a.py": "", "tests/test_alpha.py": "", "pkg/beta_test.py": "",
        "web/thing.test.ts": "", "web/thing.spec.ts": "",          # the miss
        "web/thing.test.tsx": "", "web/other.spec.jsx": "",
        "api/handler.test.mjs": "", "api/legacy.test.cjs": "",
        "svc/server_test.go": "", "rb/thing_spec.rb": "",
        "jv/ThingTest.java": "", "cs/ThingTests.cs": "",
        "kt/ThingSpec.kt": "", "rs/parser_test.rs": "",
        "src/notatest.ts": "", "src/latest-brief.ts": "",
    })
    found = names(scan(root))
    for expected in ("test_alpha.py", "beta_test.py", "thing.test.ts", "thing.spec.ts",
                     "thing.test.tsx", "other.spec.jsx", "handler.test.mjs",
                     "legacy.test.cjs", "server_test.go", "thing_spec.rb",
                     "ThingTest.java", "ThingTests.cs", "ThingSpec.kt", "parser_test.rs"):
        check(f"finds {expected}", expected in found)
    check("does not claim plain source", "notatest.ts" not in found)
    # `latest-brief.ts` contains the substring "test". A substring rule flagged it
    # on a real repository, which is why matching is by token.
    check("does not claim latest-brief.ts", "latest-brief.ts" not in found)


def test_a_test_directory_beats_a_naming_convention(tmp: Path) -> None:
    """`e2e/login.ts` is a test even though nothing in its name says so."""
    root = build(tmp / "bydir", {
        "e2e/login.ts": "", "__tests__/index.js": "", "spec/api.rb": "",
        "src/app.ts": "", "e2e/screenshot.png": "",
    })
    found = names(scan(root))
    check("a file in e2e/ counts", "login.ts" in found)
    check("a file in __tests__/ counts", "index.js" in found)
    check("a file in spec/ counts", "api.rb" in found)
    check("source outside them does not", "app.ts" not in found)
    check("a png in e2e/ is not a test", "screenshot.png" not in found)


# ── layer 1: read the repository's own declaration ────────────────────────────
def test_declared_patterns_are_read_from_jest(tmp: Path) -> None:
    root = build(tmp / "jest", {
        "package.json": json.dumps({"jest": {"testMatch": ["**/?(*.)+(weird).[jt]s"]}}),
        "src/thing.weird.ts": "", "src/plain.ts": "",
    })
    result = scan(root)
    check("a house convention nobody could guess is read",
          "thing.weird.ts" in names(result), str(result["matched"]))
    check("the declaration source is named",
          "package.json" in result["declared_in"], str(result["declared_in"]))


def test_declared_patterns_are_read_from_playwright(tmp: Path) -> None:
    root = build(tmp / "pw", {
        "playwright.config.ts": "export default { testMatch: '**/*.check.ts' };",
        "e2e-suite/login.check.ts": "", "src/app.ts": "",
    })
    result = scan(root)
    check("playwright testMatch is read", "login.check.ts" in names(result))
    check("playwright is named as the source",
          "playwright.config.ts" in result["declared_in"])


def test_declared_patterns_are_read_from_pytest(tmp: Path) -> None:
    root = build(tmp / "py", {
        "pyproject.toml": '[tool.pytest.ini_options]\npython_files = "check_*.py"\n',
        "checks/check_alpha.py": "", "src/app.py": "",
    })
    result = scan(root)
    check("pytest python_files is read", "check_alpha.py" in names(result))


def test_a_declaration_can_only_add(tmp: Path) -> None:
    """A narrow declaration must never shrink what the built-ins already found."""
    root = build(tmp / "additive", {
        "package.json": json.dumps({"jest": {"testMatch": ["**/only-this.ts"]}}),
        "src/only-this.ts": "", "src/thing.spec.ts": "", "tests/test_a.py": "",
    })
    found = names(scan(root))
    check("declared pattern is honoured", "only-this.ts" in found)
    check("a narrow declaration does not hide the conventional ones",
          {"thing.spec.ts", "test_a.py"} <= found, str(found))


# ── the monorepo case ─────────────────────────────────────────────────────────
def test_monorepo_packages_are_first_party(tmp: Path) -> None:
    """Every package in a monorepo has its own manifest. None of them is vendored."""
    root = build(tmp / "mono", {
        "package.json": json.dumps({"workspaces": ["packages/*"]}),
        "packages/core/package.json": "{}",
        "packages/core/src/index.ts": "",
        "packages/core/tests/core.test.ts": "",
        "packages/ui/package.json": "{}",
        "packages/ui/e2e/flow.spec.ts": "",
        "node_modules/dep/package.json": "{}",
        "node_modules/dep/index.test.js": "",
        "vendor/lib/thing.test.js": "",
    })
    found = names(scan(root))
    check("a monorepo package's tests are counted", "core.test.ts" in found, str(found))
    check("a second package's e2e is counted", "flow.spec.ts" in found, str(found))
    check("node_modules is still excluded", "index.test.js" not in found)
    check("vendor is still excluded", "thing.test.js" not in found)


def test_a_nested_git_repo_is_someone_elses(tmp: Path) -> None:
    root = build(tmp / "sub", {
        "tests/mine.test.ts": "",
        "third-party-thing/.git": "gitdir: elsewhere",
        "third-party-thing/tests/theirs.test.ts": "",
    })
    found = names(scan(root))
    check("this repo's tests are counted", "mine.test.ts" in found)
    check("a nested git repo's tests are not", "theirs.test.ts" not in found, str(found))


# ── layer 3: nothing is missed quietly ────────────────────────────────────────
def test_an_unguessable_convention_is_reported_as_a_near_miss(tmp: Path) -> None:
    """The guarantee that can actually be kept."""
    root = build(tmp / "nearmiss", {
        "src/app.ts": "",
        "verification/paymentSpec.ts": "",      # a real convention, declared nowhere
        "tests/test_a.py": "",
    })
    result = scan(root)
    check("the unguessable file is not silently dropped",
          any("paymentSpec" in miss for miss in result["near_misses"]),
          str(result["near_misses"]))
    check("plain source is not reported as a near miss",
          not any("app.ts" in miss for miss in result["near_misses"]))


def test_near_misses_stay_quiet_when_there_is_nothing_to_say(tmp: Path) -> None:
    root = build(tmp / "clean", {"src/app.ts": "", "src/app.test.ts": ""})
    result = scan(root)
    check("a tidy repo produces no near-miss noise", result["near_misses"] == [],
          str(result["near_misses"]))


def test_near_misses_are_rendered_not_filed(tmp: Path) -> None:
    root = build(tmp / "rendered", {
        "tests/test_a.py": "", "verification/paymentSpec.ts": "",
    })
    result = scan(root)
    rendered = oracle_plan.render({
        "verdict": "STRONG", "strongest_available": ["repo-tests"], "advice": "x",
        "sources": [{"source": "repo-tests", "available": True,
                     "evidence": f"{len(result['matched'])} test files",
                     "near_misses": result["near_misses"], "how": "run them"}],
    })
    check("the near miss appears in the printed report",
          "paymentSpec" in rendered, rendered[-200:])
    check("the report says what a near miss means",
          "did NOT match" in rendered)


def test_counting_is_exact(tmp: Path) -> None:
    """No file counted twice, however many rules could claim it."""
    root = build(tmp / "dupes", {
        "tests/test_a.py": "",            # name rule AND directory rule
        "e2e/flow.spec.ts": "",           # name rule AND directory rule
        "package.json": json.dumps({"jest": {"testMatch": ["**/*.spec.ts", "**/test_*.py"]}}),
    })
    result = scan(root)
    check("each file is counted exactly once",
          len(result["matched"]) == len(set(result["matched"])) == 2,
          str(result["matched"]))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        test_every_ecosystem_shape(tmp)
        test_a_test_directory_beats_a_naming_convention(tmp)
        test_declared_patterns_are_read_from_jest(tmp)
        test_declared_patterns_are_read_from_playwright(tmp)
        test_declared_patterns_are_read_from_pytest(tmp)
        test_a_declaration_can_only_add(tmp)
        test_monorepo_packages_are_first_party(tmp)
        test_a_nested_git_repo_is_someone_elses(tmp)
        test_an_unguessable_convention_is_reported_as_a_near_miss(tmp)
        test_near_misses_stay_quiet_when_there_is_nothing_to_say(tmp)
        test_near_misses_are_rendered_not_filed(tmp)
        test_counting_is_exact(tmp)

    for line in PASS:
        print(f"  ok    {line}")
    for line in FAIL:
        print(f"  FAIL  {line}")
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
