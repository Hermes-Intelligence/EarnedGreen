"""Tests for the three research-utilization mechanisms.

1. Claims->rules traceability (claims_ledger.py + claims-rules-map.json)
2. Decision-time research surfacing (adaptive_router decision_type + relevant_findings)
3. Vault hygiene loop (vault_hygiene.py, report-only)
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMPL = HERE.parent
sys.path.insert(0, str(IMPL))

import claims_ledger  # noqa: E402
import vault_hygiene  # noqa: E402
from adaptive_router import detect_decision_type, route  # noqa: E402
from prepare_context import prepare  # noqa: E402

BENCHMARK_DESIGN_PROMPT = (
    "Design the benchmark protocol for comparing modes of the adaptive harness: "
    "should we add a multi-agent verifier arm, how many trials per arm, and which "
    "scaffolding levels justify their cost?"
)


class ClaimsLedgerTests(unittest.TestCase):
    def test_real_map_validates_with_honest_unsupported_inventory(self) -> None:
        result = claims_ledger.validate(IMPL / "claims-rules-map.json")
        self.assertEqual("PASS", result["verdict"], result["errors"])
        self.assertGreaterEqual(result["links_total"], 20)
        self.assertGreater(result["rules_unsupported"], 0, "the honest unsupported list must not be empty-washed")
        self.assertEqual(result["rules_unsupported"], len(result["unsupported_rule_ids"]))
        self.assertIn("RULE-MODE-TRIVIAL-BOUNDARY", result["unsupported_rule_ids"])
        self.assertIn("RULE-BENCH-MULTI-TRIAL", result["unsupported_rule_ids"])
        self.assertEqual(result["rules_total"], result["rules_supported"] + result["rules_partial"] + result["rules_unsupported"])

    def test_unknown_claim_reference_is_structural_failure(self) -> None:
        data = json.loads((IMPL / "claims-rules-map.json").read_text(encoding="utf-8-sig"))
        broken = copy.deepcopy(data)
        broken["rules"][0]["justified_by"] = ["NO-SUCH-CLAIM"]
        broken["rules"][0]["support"] = "supported"
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "map.json"
            path.write_text(json.dumps(broken), encoding="utf-8")
            result = claims_ledger.validate(path)
        self.assertEqual("FAIL", result["verdict"])
        self.assertTrue(any("unknown claim NO-SUCH-CLAIM" in row for row in result["errors"]))

    def test_missing_artifact_is_structural_failure(self) -> None:
        data = json.loads((IMPL / "claims-rules-map.json").read_text(encoding="utf-8-sig"))
        broken = copy.deepcopy(data)
        broken["rules"][0]["artifact"] = "Core/does-not-exist.md"
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "map.json"
            path.write_text(json.dumps(broken), encoding="utf-8")
            result = claims_ledger.validate(path)
        self.assertEqual("FAIL", result["verdict"])

    def test_unsupported_without_local_evidence_is_structural_failure(self) -> None:
        data = json.loads((IMPL / "claims-rules-map.json").read_text(encoding="utf-8-sig"))
        broken = copy.deepcopy(data)
        broken["rules"].append({"id": "RULE-TEST-BARE", "artifact": "Core/runtime.md",
                                "rule": "bare unsupported rule", "justified_by": [], "support": "unsupported"})
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "map.json"
            path.write_text(json.dumps(broken), encoding="utf-8")
            result = claims_ledger.validate(path)
        self.assertEqual("FAIL", result["verdict"])

    def test_expired_claims_warn_but_do_not_fail(self) -> None:
        result = claims_ledger.validate(IMPL / "claims-rules-map.json", today=date(2099, 1, 1))
        self.assertEqual("PASS", result["verdict"], result["errors"])
        self.assertGreater(len(result["expired_claims"]), 0)
        self.assertGreater(len(result["rules_with_expired_claims"]), 0, "expiry must flag dependent rules")


class DecisionSurfacingTests(unittest.TestCase):
    def test_benchmark_design_prompt_surfaces_scaffolding_cost_finding(self) -> None:
        result = route(BENCHMARK_DESIGN_PROMPT)
        section = result["relevant_findings"]
        self.assertIn("benchmark", section["decision_type"])
        surfaced = [row["id"] for row in section["findings"]]
        self.assertIn("F-2026-07-12-021", surfaced, "the ~20x scaffolding-cost finding must surface")
        self.assertEqual("F-2026-07-12-021", surfaced[0], "the scaffolding-cost finding should rank first for this prompt")
        top = section["findings"][0]
        self.assertIn("20x", top["claim"])
        self.assertTrue(top["sources"] and top["sources"][0]["url"].startswith("https://"))

    def test_security_architecture_prompt_surfaces_trifecta_finding(self) -> None:
        result = route("Design the architecture for handling untrusted input: choose between a "
                       "single agent with credential access and a split reader/doer to resist prompt injection.")
        surfaced = [row["id"] for row in result["relevant_findings"]["findings"]]
        self.assertIn("F-2026-07-12-020", surfaced)

    def test_implementation_adopt_phrase_is_not_a_decision(self) -> None:
        # Fixture-task style wording: execution, not a decision. Benchmark arm
        # contexts must stay uncontaminated by research findings.
        decision = detect_decision_type("the exporter must adopt the normalized contract and carry schema_version.")
        self.assertFalse(decision["detected"])
        result = route("The exporter must adopt the normalized contract, pass the registry through and carry schema_version in each serialized line.")
        self.assertEqual([], result["relevant_findings"]["findings"])

    def test_plain_feature_task_gets_no_findings_section_content(self) -> None:
        result = route("Build a normal product feature with tests.")
        self.assertFalse(result["analysis"]["decision_type"]["detected"])
        self.assertEqual([], result["relevant_findings"]["findings"])

    def test_context_pack_carries_relevant_findings_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            task = root / "task.md"
            task.write_text(BENCHMARK_DESIGN_PROMPT, encoding="utf-8")
            prepare(task, root, root / ".agentic", [], None)
            findings_path = root / ".agentic" / "relevant-findings.json"
            self.assertTrue(findings_path.exists(), "Context Pack must include the relevant_findings section")
            payload = json.loads(findings_path.read_text(encoding="utf-8"))
            self.assertIn("F-2026-07-12-021", [row["id"] for row in payload["findings"]])
            decision = json.loads((root / ".agentic" / "mode-decision.json").read_text(encoding="utf-8"))
            self.assertIn("relevant_findings", decision)

    def test_non_decision_context_pack_has_no_findings_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            task = root / "task.md"
            task.write_text("Build a normal product feature with tests.", encoding="utf-8")
            prepare(task, root, root / ".agentic", [], None)
            self.assertFalse((root / ".agentic" / "relevant-findings.json").exists())


class VaultHygieneTests(unittest.TestCase):
    def test_scan_reports_all_four_classes_and_modifies_nothing(self) -> None:
        repo = vault_hygiene.repo_root()
        sentinels = [repo / "Core/runtime.md", repo / "Router/catalog/modules.json",
                     repo / "Research/sources/registry.json", repo / "workstreams/current.json"]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in sentinels}
        report = vault_hygiene.run_scan(date(2026, 7, 15), max_workstream_age_days=7)
        after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in sentinels}
        self.assertEqual(before, after, "hygiene scan must never modify knowledge surfaces")
        self.assertEqual("report-only", report["mode"])
        self.assertEqual([], report["modified_files"])
        for section in ("cross_references", "staleness", "contradictions", "orphans"):
            self.assertIn(section, report)
        self.assertIn("limits", report["contradictions"], "heuristic limits must be stated in the report")

    def test_candidate_package_has_zero_broken_cross_references(self) -> None:
        report = vault_hygiene.run_scan(date(2026, 7, 15), max_workstream_age_days=7)
        self.assertEqual(0, report["cross_references"]["package_broken_count"],
                         report["cross_references"]["package_broken_references"])

    def test_staleness_fires_on_past_dates(self) -> None:
        # Far in the future everything is stale: the detector must fire.
        report = vault_hygiene.run_scan(date(2099, 1, 1), max_workstream_age_days=7)
        self.assertGreater(report["staleness"]["stale_count"], 0)
        artifacts = {row["artifact"] for row in report["staleness"]["stale_items"]}
        self.assertIn("Models/providers.json", artifacts)
        self.assertIn("Research/sources/registry.json", artifacts)

    def test_cli_writes_dated_json_and_markdown_reports(self) -> None:
        import subprocess
        with tempfile.TemporaryDirectory() as temp_name:
            completed = subprocess.run(
                [sys.executable, str(IMPL / "vault_hygiene.py"), "--output-dir", temp_name,
                 "--as-of", "2026-07-15", "--gate-package"],
                cwd=IMPL, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=300)
            self.assertEqual(0, completed.returncode, completed.stdout[-2000:] + completed.stderr[-2000:])
            json_path = Path(temp_name) / "vault-hygiene-report-20260715.json"
            md_path = Path(temp_name) / "vault-hygiene-report-20260715.md"
            self.assertTrue(json_path.exists() and md_path.exists())
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual("report-only", payload["mode"])
            self.assertIn("# Vault Hygiene Report", md_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
