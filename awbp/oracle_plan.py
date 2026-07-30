#!/usr/bin/env python3
"""Where will this task's oracle come from? Asked BEFORE which mode to run.

The mode ladder asks how much ceremony a task needs. It was measured at zero for
correctness. This asks the question that was measured to matter: what will decide
whether the work is right, and how far is that source from the agent doing it?

The ranking is measured, not assumed:

    diff-derived / data / repo-tests   rank 4   the two positive families ran on this
    host / relation / acceptance       rank 3   the one difference a campaign arm won on
    spec                               rank 2   saturated: two builds scored near-identically
                                                while a human eye found four defects
    authored / council                 rank 1   measured ZERO lift, three times

A task whose only available source is rank 2 or below can still be done. It just
cannot produce a green that means much, and this says so at the start rather than
letting the report imply otherwise at the end.

    python oracle_plan.py --repo . --task-file .agentic/task.txt
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from fnmatch import fnmatch
import sys
from pathlib import Path

RANK = {"diff-derived": 4, "data": 4, "repo-tests": 4,
        "host": 3, "relation": 3, "acceptance": 3, "finding": 3,
        "spec": 2, "council": 1, "authored": 1, "reviewed-unverified": 0}

# Directories whose contents are NOT this repo's own evidence. Two of these were
# found by looking at what the first version reported: on a JS project it offered
# `node_modules/.pnpm/core-js/.../es.regexp.test.js` as "the repo's own tests",
# and on this repo it offered migrations and tests that live inside benchmark run
# artifacts, which are copies of a DIFFERENT repo's workspace. A detector that
# counts vendored and generated files hands out a rank-4 oracle that does not
# exist, which is worse than reporting none.
EXCLUDED_PARTS = {"node_modules", ".git", "dist", "build", "__pycache__", ".venv",
                  "venv", "site-packages", ".next", "coverage", "vendor",
                  "third_party", "thirdparty", "externals", "bower_components",
                  "target", ".tox", ".mypy_cache", ".pytest_cache", ".turbo",
                  "runs", "artifacts", "returned-workspace", "rollback",
                  # THE HARNESS'S OWN SCRATCH. `awbp task` snapshots the repository
                  # into .agentic/baseline-workspace/ so hunks can be reverted later.
                  # Without this line the detector counted that snapshot's tests as
                  # the repository's own and doubled the evidence, which is the same
                  # error as counting a vendored dependency except that the harness
                  # created the copy itself, one command earlier.
                  ".agentic"}

# A nested REPOSITORY is someone else's code. A nested PACKAGE is this repo's own.
#
# The first version of this rule excluded any directory holding package.json,
# pyproject.toml, go.mod and friends, on the reasoning that a project root below
# the repo root means a vendored copy. Pointed at a real monorepo it silently
# dropped ten test files belonging to a first-party package, because every package
# in a monorepo has its own manifest. That rule would break most modern JS
# repositories, and it did so in the direction that is hardest to notice: quietly,
# by reporting a smaller number.
#
# `.git` is the honest signal and the only one kept. A directory with its own
# `.git` is a submodule or a vendored clone, which really is a different
# repository. Everything else that needs excluding is caught by name
# (node_modules, vendor, third_party) or by the fixture rule below.
NESTED_REPO_MARKERS = (".git",)


def _nested_workspace(repo: Path, directory: Path, cache: dict[Path, bool]) -> bool:
    """True when some directory strictly between `repo` and `directory` is its own repository."""
    if directory in cache:
        return cache[directory]
    if directory == repo or repo not in directory.parents:
        cache[directory] = False
        return False
    here = any((directory / marker).exists() for marker in NESTED_REPO_MARKERS)
    result = here or _nested_workspace(repo, directory.parent, cache)
    cache[directory] = result
    return result


_NESTED_CACHE: dict[Path, bool] = {}


def _own(repo: Path, path: Path) -> bool:
    """True when `path` is this repo's own source: not vendored, generated, or nested."""
    try:
        parts = path.relative_to(repo).parts
    except ValueError:
        return False
    if any(part in EXCLUDED_PARTS for part in parts):
        return False
    # A DIRECTORY named for fixtures holds inputs to tests, not the repo's own
    # oracle, in every ecosystem that has the convention (pytest, jest __fixtures__,
    # rails). Here it also holds fixture repos that are deliberately broken copies
    # of other projects, whose passing tests would be the most misleading rank-4
    # oracle this tool could offer. Directories only: `src/fixtures.py` is source.
    if any("fixture" in part.lower() for part in parts[:-1]):
        return False
    return not _nested_workspace(repo, path.parent, _NESTED_CACHE)


# ── finding the tests: read the declaration, then guess, then admit the gap ────
#
# Two silent under-reports on one unfamiliar repository, an hour apart, said the
# same thing: a hardcoded list of conventions is always incomplete, and being
# incomplete QUIETLY is the part that does the damage. `*.spec.ts` matched nothing
# at all and hid 28 end-to-end suites, and a nested-manifest rule dropped ten
# first-party suites belonging to a monorepo package.
#
# The answer is not a longer list. It is three layers, in this order:
#
#   1. READ WHAT THE REPO DECLARES. Test file patterns are configuration, not
#      folklore: jest and vitest carry testMatch/include, playwright carries
#      testMatch, pytest carries python_files and testpaths. A repository that
#      says what its tests are should never be guessed at.
#   2. FALL BACK to the built-in shapes below when nothing is declared.
#   3. REPORT THE NEAR MISSES. Anything that looks test-adjacent and did NOT
#      match is counted and named. Conventions cannot be enumerated in advance,
#      so the guarantee that can actually be kept is not "never miss one" but
#      "never miss one silently".
TEST_FILE = re.compile(
    r"""(?ix)
    ^ (?: test_.+ \. (?: py|rb|lua )                     # pytest, minitest
        | .+ _test \. (?: py|go|rb|dart|ex|exs|rs|lua|ts|js )
        | test .+ \. (?: js|jsx|ts|tsx|mjs|cjs )         # testFoo.ts
        | .+ [._-] (?: test|spec|tests|specs )
              \. (?: js|jsx|ts|tsx|mjs|cjs|py|rb|php|dart )
        | .+ _spec \. (?: rb|lua )
        | .+ Test \. (?: java|kt|kts|cs|php|scala|groovy )
        | .+ Tests \. (?: cs|swift|java|kt )
        | .+ Spec \. (?: java|kt|kts|scala|groovy )
        | .+ \. (?: t|feature )                           # perl, cucumber
      ) $""")

# A file sitting in one of these directories is test material even when its name
# follows no convention at all: `e2e/login.ts`, `__tests__/index.js`, `spec/api.rb`.
# `it` is deliberately ABSENT. It is the Italian language code, and including it
# flagged `src/locales/it.d.ts` and an `it-*.js` locale bundle as missed tests on
# a real repository. A token that common costs more in noise than it recovers.
TEST_DIR_NAMES = {"test", "tests", "__tests__", "spec", "specs", "e2e",
                  "integration-tests", "unit-tests", "testing", "acceptance"}

# Where a repository writes down what its own tests are. Read in this order; the
# first that yields patterns wins the label, all of them contribute patterns.
TEST_CONFIG_FILES = (
    "package.json", "jest.config.js", "jest.config.ts", "jest.config.mjs",
    "jest.config.cjs", "jest.config.json", "vitest.config.js", "vitest.config.ts",
    "vitest.config.mjs", "vite.config.js", "vite.config.ts", "vite.config.mjs",
    "playwright.config.js", "playwright.config.ts", "playwright.config.mjs",
    "pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini", ".mocharc.json",
    ".mocharc.yml", "karma.conf.js", "phpunit.xml", "phpunit.xml.dist",
)

# testMatch / testRegex / include / testDir / python_files / testpaths, whichever
# the tool in front of us uses, as written in its own config.
_DECLARED = re.compile(
    r"""(?ix)
    \b (?P<key> testMatch | testRegex | testPathPatterns | python_files
              | python_classes | testpaths | testDir | spec )
    # The optional closing quote is load-bearing: in package.json the key is
    # written "testMatch", so a pattern demanding a colon straight after the word
    # matched nothing at all in the single most common place a repo declares this.
    ["'`]? \s* [:=] \s*
    # The array form closes on a `]` FOLLOWED BY a comma, brace or line end, not
    # on the first `]` seen. Character classes are ordinary inside these patterns
    # (`**/*.[jt]s` is idiomatic jest), and stopping at the first bracket cut
    # `**/?(*.)+(weird).[jt]s` down to `**/?(*.)+(weird).[jt]` - a pattern that
    # matches nothing, produced by a parser that thought it had succeeded.
    (?P<body> \[ .{0,600}? \] (?= \s* [,}\n\r] | \s*$ )
            | ["'`][^"'`\n]{0,200}["'`]
            | [^\n#]{0,200} )
    """, re.DOTALL)
_QUOTED = re.compile(r"""["'`]([^"'`\n]{1,200})["'`]""")


def walk(repo: Path) -> list[Path]:
    """Every file that is this repository's own source.

    ASK GIT FIRST. `git ls-files` is the authoritative answer to "what is this
    repository's own material": it excludes everything ignored — build output,
    caches, installed dependencies — with no heuristics and no name list that has
    to be kept current. Every version of this function that guessed instead got
    the number wrong, in both directions on the same repository within one hour:
    a hand-rolled walk reported 651 files where git tracks 89, and the glob
    version before it reported 49.

    The name-based rules still apply on top, because they exclude things a repo
    legitimately tracks: deliberately broken fixture repositories, and this
    harness's own baseline snapshot.

    os.walk is the fallback for a directory that is not a git repository at all,
    and it prunes as it descends rather than filtering afterwards.
    """
    listing = _run(repo, "git", "ls-files", "-z")
    if listing:
        return [repo / rel for rel in listing.split("\0")
                if rel and _own(repo, repo / rel)]

    out: list[Path] = []
    for current, directories, files in os.walk(repo):
        here = Path(current)
        directories[:] = [d for d in directories
                          if d not in EXCLUDED_PARTS and "fixture" not in d.lower()
                          and not any((here / d / m).exists() for m in NESTED_REPO_MARKERS)]
        out.extend(here / name for name in files)
    return out


def declared_test_patterns(repo: Path, files: list[Path]) -> dict:
    """What this repository SAYS its tests are, read from its own configuration.

    Rank-3 `host` provenance turned on the detector itself. A repo that declares
    `testMatch: ['**/*.spec.ts']` has already answered the question, and guessing
    over the top of that answer is how an entire e2e directory went missing.

    JS config files are code and cannot be fully parsed, so the quoted patterns
    are lifted out textually. That is deliberately partial: a pattern found this
    way is used, and a pattern missed this way falls through to the built-in
    shapes and then to the near-miss report. Nothing here can make the count go
    DOWN, which is the property that matters.
    """
    patterns: set[str] = set()
    sources: list[str] = []
    by_name = {p.name: p for p in files if p.parent == repo}
    for name in TEST_CONFIG_FILES:
        path = by_name.get(name) or (repo / name if (repo / name).is_file() else None)
        if path is None or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")[:200_000]
        except OSError:
            continue
        found: set[str] = set()
        for match in _DECLARED.finditer(text):
            body = match.group("body")
            quoted = _QUOTED.findall(body)
            candidates = quoted or [part.strip() for part in body.split()]
            for candidate in candidates:
                candidate = candidate.strip().strip(",")
                # A bare directory name is a testpaths/testDir entry, which the
                # directory rule below already covers; keep only real patterns.
                if candidate and any(ch in candidate for ch in "*?.[") and len(candidate) < 200:
                    found.add(candidate)
        if found:
            patterns |= found
            sources.append(name)
    return {"patterns": sorted(patterns), "sources": sources}


_EXTGLOB = re.compile(r"[?*+@!]\(([^)]*)\)")


def _matches_declared(repo: Path, path: Path, patterns: list[str]) -> bool:
    rel = path.relative_to(repo).as_posix()
    for pattern in patterns:
        pattern = pattern.lstrip("./")
        # jest and micromatch use extglob (`**/?(*.)+(test|spec).[jt]s`), which
        # fnmatch does not speak. Rather than skip such a declaration silently -
        # the exact failure this whole layer exists to stop - each group is
        # loosened to `*`. That over-matches slightly and never under-matches, and
        # anything it still misses lands in the near-miss report.
        if _EXTGLOB.search(pattern):
            pattern = _EXTGLOB.sub("*", pattern)
        if fnmatch(rel, pattern) or fnmatch(path.name, pattern):
            return True
        # `**/x` should also match `x` at the root, which fnmatch does not do.
        if pattern.startswith("**/") and fnmatch(rel, pattern[3:]):
            return True
        # A regex-shaped testRegex, tried as one. A bad pattern is skipped, never
        # allowed to abort the scan.
        if any(ch in pattern for ch in "()\\|$^"):
            try:
                if re.search(pattern, rel):
                    return True
            except re.error:
                continue
    return False


CODE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rb",
                 ".rs", ".java", ".kt", ".kts", ".cs", ".php", ".swift", ".dart",
                 ".scala", ".groovy", ".ex", ".exs", ".lua"}

_TOKENS = re.compile(r"[._\-/\\]|(?<=[a-z0-9])(?=[A-Z])")
_TEST_WORDS = {"test", "tests", "spec", "specs", "e2e"}


def _looks_test_adjacent(repo: Path, path: Path) -> bool:
    """Would a human glancing at this path call it test material?

    TOKENS, NOT SUBSTRINGS. The first version asked whether "test" appeared
    anywhere in the stem, so it flagged `latest-brief.ts` and `spec_synthesis.py`
    and produced 466 near misses on one repository. A near-miss list that long is
    the same as no near-miss list: nobody reads it, and the one real miss inside
    it is invisible.
    """
    if path.suffix.lower() not in CODE_SUFFIXES:
        return False
    rel = path.relative_to(repo)
    if any(part.lower() in TEST_DIR_NAMES for part in rel.parts[:-1]):
        return True
    return bool(_TEST_WORDS & {t.lower() for t in _TOKENS.split(path.stem) if t})


def find_tests(repo: Path, files: list[Path]) -> dict:
    """Every test file, by declaration first, then convention, then honesty.

    `near_misses` is the load-bearing field. It holds files this repository would
    call tests that none of the patterns matched, and it exists because the
    guarantee "no convention is ever missed" cannot be kept by anyone, while
    "nothing is missed silently" can.
    """
    declared = declared_test_patterns(repo, files)
    patterns = declared["patterns"]

    matched: list[Path] = []
    for path in files:
        if TEST_FILE.match(path.name):
            matched.append(path)
        elif patterns and _matches_declared(repo, path, patterns):
            matched.append(path)
        elif (path.suffix.lower() in CODE_SUFFIXES
              and any(part.lower() in TEST_DIR_NAMES
                      for part in path.relative_to(repo).parts[:-1])):
            matched.append(path)

    found = set(matched)
    near_misses = sorted(str(p.relative_to(repo)) for p in files
                         if p not in found and _looks_test_adjacent(repo, p))
    return {
        "matched": sorted(str(p.relative_to(repo)) for p in matched),
        "declared_patterns": patterns,
        "declared_in": declared["sources"],
        "near_misses": near_misses,
    }


def _run(repo: Path, *args: str) -> str:
    try:
        out = subprocess.run(args, cwd=repo, capture_output=True, text=True, timeout=25)
        return out.stdout if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def detect(repo: Path, task: str = "") -> list[dict]:
    """Every oracle source this repo can actually supply, with the evidence."""
    found: list[dict] = []

    # -- rank 4 -----------------------------------------------------------------
    commits = _run(repo, "git", "log", "--oneline", "-200").strip().splitlines()
    if commits:
        fixes = [c for c in commits
                 if any(w in c.lower() for w in ("fix", "bug", "correct", "repair", "regress"))]
        found.append({
            "source": "diff-derived", "available": bool(fixes),
            "evidence": f"{len(commits)} recent commits, {len(fixes)} look like fixes",
            "how": "oracle_cli derive: turn a real before/after into relational predicates. "
                   "commit_miner ranks which commits are worth replaying.",
        })

    # One walk, one match, and the misses are reported. The earlier version ran
    # seven overlapping globs and summed their matches, so a file under tests/ was
    # counted twice and the evidence line reported 51 suites where 27 existed.
    files = list(walk(repo))
    scan = find_tests(repo, files)
    tests = scan["matched"]
    if tests:
        evidence = f"{len(tests)} test files, e.g. {tests[0]}"
        if scan["declared_in"]:
            evidence += (f"; patterns declared in {', '.join(scan['declared_in'])} "
                         f"were read, not guessed")
        found.append({
            "source": "repo-tests", "available": True,
            "evidence": evidence,
            "near_misses": scan["near_misses"],
            "declared_patterns": scan["declared_patterns"],
            "how": "run the repo's own suite; it was written before this task existed, "
                   "so it cannot have been shaped to agree with the work.",
        })

    data_markers = []
    for marker in (".env", "alembic.ini", "docker-compose.yml"):
        if (repo / marker).exists():
            data_markers.append(marker)
    schema_like = [p for p in files
                   if p.suffix.lower() in {".sql"} and "schema" in p.name.lower()
                   or "migrations" in {part.lower() for part in p.parts}]
    if schema_like:
        data_markers.append(str(schema_like[0].relative_to(repo)))
    if data_markers:
        found.append({
            "source": "data", "available": True,
            "evidence": "store reachable: " + ", ".join(sorted(set(data_markers))[:4]),
            "how": "fact_ledger.py: register each fact with the query that produces it, then "
                   "audit BACKWARDS — every number in the output must trace to a derivation. "
                   "An unledgered number was typed in by the author.",
        })

    # -- rank 3 -----------------------------------------------------------------
    # A host file states what the values ARE. A test file merely exercises them,
    # and handing one to the extractor produces rules that describe the test.
    # `e2e/theme-toggle.spec.ts` matched an earlier `startswith("theme")` probe on
    # a real repository and was offered as that repository's design conventions.
    candidates = [p for p in files if not TEST_FILE.match(p.name)]
    host_markers = []
    for probe in (lambda n: n.startswith("tokens") and n.endswith(".json"),
                  lambda n: n.startswith(("theme.", "theme-config", "themes.")) and
                            n.endswith((".js", ".ts", ".json", ".css")),
                  lambda n: "brandbook" in n or "brand-book" in n,
                  lambda n: n.startswith("design-system") or n.startswith("design-tokens"),
                  lambda n: n.startswith("tailwind.config."),
                  lambda n: ".tokens." in n,
                  lambda n: n in {"conventions.md", "styleguide.md", "style-guide.md"}):
        hit = next((p for p in candidates if probe(p.name.lower())), None)
        if hit:
            host_markers.append(str(hit.relative_to(repo)))
    if host_markers:
        found.append({
            "source": "host", "available": True,
            "evidence": "conventions in the repo: " + ", ".join(host_markers[:3]),
            "how": "host_rules.py --file <path>: extract the rules mechanically. Transcribing "
                   "them by hand turns rank 3 into rank 2, which is the rung that saturates, "
                   "and a transcription stops tracking the file the moment it changes.",
        })

    # -- rank 2 and below: always available, and that is the problem ------------
    found.append({
        "source": "spec", "available": True,
        "evidence": "a task description exists" if task else "no task text supplied",
        "how": "render the requirements as predicates. Cheap, and it saturates: on the one "
               "from-scratch family measured, a fully spec-derived instrument scored two "
               "builds near-identically and missed every defect a human then found by eye.",
    })
    return found


def plan(repo: Path, task: str = "") -> dict:
    sources = detect(repo, task)
    usable = [s for s in sources if s["available"]]
    best = max((RANK.get(s["source"], 0) for s in usable), default=0)
    strongest = [s["source"] for s in usable if RANK.get(s["source"], 0) == best]
    independent = [s for s in usable if RANK.get(s["source"], 0) >= 3]

    if best >= 4:
        verdict = "STRONG"
        advice = (f"Build the oracle from {strongest[0]!r} before writing any code. This is the "
                  f"rung the two positive campaigns ran on.")
    elif best == 3:
        verdict = "WORKABLE"
        advice = (f"Extract from {strongest[0]!r} mechanically. Do not transcribe it: a "
                  f"hand-copied rule is spec-derived and saturates.")
    else:
        verdict = "WEAK"
        advice = ("Only spec-derived predicates are available. The work can proceed, but a "
                  "green will mean the work agrees with its own description. Say so in the "
                  "report, and consider whether a hollow fixture can serve as the admission "
                  "surface instead of an absent baseline.")

    return {
        "schema_version": 1,
        "asked_before_mode": True,
        "verdict": verdict,
        "strongest_available": strongest,
        "independence_ceiling": round(len(independent) / len(usable), 2) if usable else 0.0,
        "advice": advice,
        "sources": sources,
        "rule": ("everything the agent authors about its own correctness has measured zero; "
                 "everything from outside the agent has carried the wins"),
    }


def render(result: dict) -> str:
    lines = [f"ORACLE PLAN: {result['verdict']}  "
             f"(strongest available: {', '.join(result['strongest_available']) or 'none'})",
             "", f"  {result['advice']}", ""]
    for row in sorted(result["sources"], key=lambda r: -RANK.get(r["source"], 0)):
        mark = "yes" if row["available"] else "no "
        lines.append(f"  [{mark}] rank {RANK.get(row['source'], 0)}  {row['source']}")
        lines.append(f"          {row['evidence']}")
        # NEAR MISSES ARE PRINTED, NOT FILED. No list of conventions is ever
        # complete, so the promise this tool can actually keep is not "nothing is
        # missed" but "nothing is missed quietly". Two silent under-reports on one
        # unfamiliar repository are the reason these four lines exist.
        misses = row.get("near_misses") or []
        if misses:
            lines.append(f"          {len(misses)} file(s) look like tests and did NOT match "
                         f"any pattern - check whether they belong:")
            for miss in misses[:5]:
                lines.append(f"            ? {miss}")
            if len(misses) > 5:
                lines.append(f"            ... and {len(misses) - 5} more (--out for the full list)")
        if row["available"]:
            lines.append(f"          -> {row['how']}")
    return "\n".join(lines)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--task-file", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    task = args.task_file.read_text(encoding="utf-8-sig") if (
        args.task_file and args.task_file.exists()) else ""
    result = plan(args.repo.resolve(), task)
    if args.out:
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(render(result))
    raise SystemExit(0)


if __name__ == "__main__":
    main()
