#!/usr/bin/env python3
"""Tests for the commit miner's parsing and scoring (no git repo needed)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import commit_miner

F = "\x1f"


def log_line(sha: str, parents: str, subject: str) -> str:
    return f"{sha}{F}{parents}{F}2026-07-01{F}{subject}"


class Parsing(unittest.TestCase):
    def test_commits_and_numstat_rows_are_grouped(self) -> None:
        raw = "\n".join([
            log_line("a" * 40, "b" * 40, "fix: citation runs glued"),
            "12\t3\tsrc/editionPdf.js",
            "",
            log_line("c" * 40, "d" * 40, "docs update"),
            "5\t1\tREADME.md",
        ])
        commits = commit_miner.parse_log(raw)
        self.assertEqual(len(commits), 2)
        self.assertEqual(commits[0]["files"][0]["path"], "src/editionPdf.js")
        self.assertEqual(commits[0]["files"][0]["added"], 12)

    def test_binary_numstat_dashes_survive_as_none(self) -> None:
        raw = "\n".join([log_line("a" * 40, "b" * 40, "add image"), "-\t-\tlogo.png"])
        self.assertIsNone(commit_miner.parse_log(raw)[0]["files"][0]["added"])


class Scoring(unittest.TestCase):
    def commit(self, subject: str, files: list[tuple[int, int, str]], parents: int = 1) -> dict:
        return {"sha": "e" * 40, "parents": ["p"] * parents, "date": "2026-07-01",
                "subject": subject,
                "files": [{"path": path, "added": a, "deleted": d} for a, d, path in files]}

    def test_a_focused_fix_scores_highest(self) -> None:
        row = commit_miner.score(self.commit("fix broken citation dedupe", [(30, 10, "src/render.js")]))
        self.assertIsNotNone(row)
        self.assertTrue(row["fixish_message"])
        self.assertEqual(row["score"], 6)
        self.assertEqual(row["before_ref"], row["after_ref"] + "^")

    def test_merges_docs_and_sweeping_refactors_are_rejected(self) -> None:
        self.assertIsNone(commit_miner.score(self.commit("fix things", [(9, 1, "src/a.js")], parents=2)),
                          "a merge has no single before-state")
        self.assertIsNone(commit_miner.score(self.commit("fix docs", [(9, 1, "README.md")])),
                          "docs are not replayable behaviour")
        many = [(9, 1, f"src/f{k}.js") for k in range(9)]
        self.assertIsNone(commit_miner.score(self.commit("fix everything", many)),
                          "a 9-file sweep is an era, not a task")

    def test_lockfiles_and_one_liners_are_noise(self) -> None:
        self.assertIsNone(commit_miner.score(self.commit("fix deps", [(400, 400, "package-lock.json")])))
        self.assertIsNone(commit_miner.score(self.commit("fix typo", [(1, 1, "src/a.js")])),
                          "a one-line tweak is not a task")


if __name__ == "__main__":
    unittest.main(verbosity=2)
