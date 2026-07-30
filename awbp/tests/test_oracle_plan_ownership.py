#!/usr/bin/env python3
"""What counts as THIS repo's own oracle, and what only looks like one.

oracle_plan's ownership rule was corrected four times before it had a single
test, and all four corrections were the same species of error: something that
belongs to a different project got counted as this project's evidence, and the
tool then offered a rank-4 oracle that does not exist. A run proceeding on a
non-existent oracle is worse off than one told it has none, because it believes
its own green.

The four, in the order they were found:

    node_modules/.pnpm/core-js/.../es.regexp.test.js    vendored dependency
    Evals/runs/<id>/returned-workspace/tests/...        another repo's worktree
    Research/.../mode-boundary-fixture-*/public/tests   a DELIBERATELY BROKEN copy
    .agentic/baseline-workspace/tests/...               OUR OWN snapshot

A fifth correction ran the OTHER way. The rule that caught the third case
excluded any directory holding a package manifest, and pointed at a real monorepo
it dropped ten first-party suites, because every package in a monorepo has one.
Only `.git` survives as a nested-repository signal.

KNOWN LIMIT, stated rather than hidden: a vendored copy with a manifest, no
`.git`, and an unconventional directory name is indistinguishable from a
first-party package. The tool counts it. Excluding it would cost every monorepo
its real suites, which is the more common and more expensive error.

The third is the sharpest as a warning: those tests pass, and they pass on a repo
built to contain defects. The fourth is the sharpest as a lesson: `awbp task`
creates that snapshot itself, one command before the detector reads it. The
harness poisoned its own evidence and nothing noticed until the tool was pointed
at a stranger's repository and the count came back doubled.

Every case below is a real path shape from this repo or from a repo the tool was
pointed at.

    python tests/test_oracle_plan_ownership.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import oracle_plan          # noqa: E402

PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(f"{name}{' — ' + detail if detail else ''}")


def build(root: Path) -> None:
    """A repo shaped like the ones that produced each of the three errors."""
    def write(rel: str, body: str = "x") -> Path:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    write("tools/area/tests/test_real.py")                     # own, nested dir
    write("tests/test_root.py")                                # own, root
    write("src/fixtures.py")                                   # own: a FILE, not a dir
    write("node_modules/.pnpm/core-js/tests/test_vendor.py")   # error 1
    write("Evals/runs/abc/returned-workspace/tests/test_x.py") # error 2
    write("Research/pkg/mode-boundary-fixture-a/public/tests/test_broken.py")  # error 3
    write("Evals/fixtures/case/hidden/migrations/backfill.py")  # error 3, data source
    write("packages/lib/package.json", "{}")                   # a MONOREPO package: own
    write("packages/lib/tests/test_pkg.py")
    write("submodule/.git", "gitdir: ../.git/modules/submodule")  # a real other repo
    write("submodule/tests/test_other.py")
    write(".agentic/baseline-workspace/tests/test_real.py")    # error 4: OUR OWN snapshot


def test_ownership(root: Path) -> None:
    cases = {
        "tools/area/tests/test_real.py": True,
        "tests/test_root.py": True,
        "src/fixtures.py": True,
        "node_modules/.pnpm/core-js/tests/test_vendor.py": False,
        "Evals/runs/abc/returned-workspace/tests/test_x.py": False,
        "Research/pkg/mode-boundary-fixture-a/public/tests/test_broken.py": False,
        "Evals/fixtures/case/hidden/migrations/backfill.py": False,
        # A monorepo package has its own manifest and is FIRST-PARTY. An earlier
        # rule excluded every directory holding a package.json, which on a real
        # monorepo silently dropped ten first-party suites.
        "packages/lib/tests/test_pkg.py": True,
        # A nested `.git` is a different repository. That is the only manifest
        # signal kept, because it is the only one that means what it says.
        "submodule/tests/test_other.py": False,
        ".agentic/baseline-workspace/tests/test_real.py": False,
    }
    for rel, expected in cases.items():
        got = oracle_plan._own(root, root / rel)
        check(f"{'own' if expected else 'not own'}: {rel}", got == expected,
              f"got own={got}")


def test_detect_reports_only_own_tests(root: Path) -> None:
    found = {row["source"]: row for row in oracle_plan.detect(root)}
    tests = found.get("repo-tests")
    check("repo-tests detected at all", tests is not None and tests["available"])
    if tests:
        # Three own suites exist (two plain, one first-party monorepo package);
        # the five decoys must not be counted.
        count = int(tests["evidence"].split()[0])
        check("only the repo's own suites are counted", count == 3, tests["evidence"])


def test_fixture_only_repo_is_not_rank_four(root: Path) -> None:
    """A repo whose ONLY tests are fixtures must not be called STRONG."""
    with tempfile.TemporaryDirectory() as raw:
        decoy = Path(raw)
        (decoy / "fixtures" / "case" / "tests").mkdir(parents=True)
        (decoy / "fixtures" / "case" / "tests" / "test_a.py").write_text("x", encoding="utf-8")
        result = oracle_plan.plan(decoy)
        check("fixture-only repo is not STRONG", result["verdict"] != "STRONG",
              result["verdict"])


def test_own_survives_a_path_outside_the_repo(root: Path) -> None:
    check("a path outside the repo is not own",
          not oracle_plan._own(root, Path(root.anchor) / "elsewhere" / "test_x.py"))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        build(root)
        oracle_plan._NESTED_CACHE.clear()
        test_ownership(root)
        test_detect_reports_only_own_tests(root)
        test_fixture_only_repo_is_not_rank_four(root)
        test_own_survives_a_path_outside_the_repo(root)

    for line in PASS:
        print(f"  ok    {line}")
    for line in FAIL:
        print(f"  FAIL  {line}")
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
