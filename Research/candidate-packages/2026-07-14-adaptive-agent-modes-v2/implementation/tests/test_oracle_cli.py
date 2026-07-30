#!/usr/bin/env python3
"""End-to-end test of oracle_cli on a FOREIGN repository (zero provider calls).

This is the portability proof behind Stable 0.6.0: a person clones AWBP, points
oracle_cli at THEIR OWN repo somewhere else on disk, writes a few-line capture,
and gets working pins. The test builds exactly that situation from scratch — a
fresh git repo with a bug->fix history that AWBP has never seen — and walks the
whole user path: derive from history, evaluate against trees, mine guards from
the working tree. If this test passes, the cloned-repo user story is real; when
it fails, 0.6.0 has no business shipping.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMPL = HERE.parent
sys.path.insert(0, str(IMPL))

APP_BUGGY = '''\
import json, sys
def dedupe(items):
    return items  # bug: duplicates pass through
if __name__ == "__main__":
    corpus = {"basic": ["a", "b", "a", "c"], "empty": [], "single": ["x"]}
    print(json.dumps({name: dedupe(items) for name, items in corpus.items()}))
'''

APP_FIXED = APP_BUGGY.replace(
    "    return items  # bug: duplicates pass through",
    "    seen = []\n"
    "    for item in items:\n"
    "        if item not in seen:\n"
    "            seen.append(item)\n"
    "    return seen")

CAPTURE = ["{python}", "app.py"]


def git(repo: Path, *args: str) -> None:
    completed = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=60)
    if completed.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {completed.stderr[-300:]}")


def cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(IMPL / "oracle_cli.py"), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)


class ForeignRepo(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(tempfile.mkdtemp(prefix="awbp-foreign-repo-"))
        cls.repo = cls.root / "their-project"
        cls.repo.mkdir()
        git(cls.repo, "init", "-q")
        git(cls.repo, "config", "user.email", "test@example.com")
        git(cls.repo, "config", "user.name", "Test")
        (cls.repo / "app.py").write_text(APP_BUGGY, encoding="utf-8")
        git(cls.repo, "add", "-A")
        git(cls.repo, "commit", "-qm", "initial: dedupe passes duplicates through")
        (cls.repo / "app.py").write_text(APP_FIXED, encoding="utf-8")
        git(cls.repo, "add", "-A")
        git(cls.repo, "commit", "-qm", "fix: dedupe keeps first occurrence only")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_the_whole_cloned_user_path(self) -> None:
        pins_path = self.root / "pins.json"
        completed = cli("derive", "--repo", str(self.repo),
                        "--before-ref", "HEAD^", "--after-ref", "HEAD",
                        "--output", str(pins_path), "--capture", *CAPTURE)
        self.assertEqual(completed.returncode, 0, completed.stderr[-500:])
        pins = json.loads(pins_path.read_text(encoding="utf-8"))
        self.assertTrue(pins["predicates"], "history with a real fix must yield predicates")
        self.assertIn("warning", pins, "no --valid-ref must carry the measured over-constraint warning")

        # the fixed tree is green; the buggy state is red — through the CLI only
        self.assertEqual(cli("evaluate", "--pins", str(pins_path), "--tree", str(self.repo)).returncode, 0)
        buggy = self.root / "buggy-tree"
        shutil.copytree(self.repo, buggy, ignore=shutil.ignore_patterns(".git"))
        (buggy / "app.py").write_text(APP_BUGGY, encoding="utf-8")
        outcome = cli("evaluate", "--pins", str(pins_path), "--tree", str(buggy))
        self.assertEqual(outcome.returncode, 1, "the pre-fix behaviour must go red under the derived pins")

        # and the user's repo history is untouched by the worktree machinery
        status = subprocess.run(["git", "-C", str(self.repo), "status", "--porcelain"],
                                capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(status.stdout.strip(), "", "derive must leave the user's repo pristine")

    def test_guards_pin_the_current_envelope_and_report_findings(self) -> None:
        guards_path = self.root / "guards.json"
        completed = cli("guards", "--tree", str(self.repo),
                        "--output", str(guards_path), "--capture", *CAPTURE)
        self.assertEqual(completed.returncode, 0, completed.stderr[-500:])
        guards = json.loads(guards_path.read_text(encoding="utf-8"))
        self.assertEqual(guards["findings"], [])
        self.assertEqual(len(guards["predicates"]), 3, "one guard per corpus input")
        self.assertEqual(cli("evaluate", "--pins", str(guards_path), "--tree", str(self.repo)).returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
