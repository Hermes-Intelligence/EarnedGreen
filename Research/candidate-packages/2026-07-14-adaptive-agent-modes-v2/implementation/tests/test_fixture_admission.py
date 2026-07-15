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
FIXTURE = IMPL / "mode-boundary-fixture"
FIXTURE_V3 = IMPL / "mode-boundary-fixture-v3"
FIXTURE_V4 = IMPL / "mode-boundary-fixture-v4"
FIXTURE_CLARITY = IMPL / "mode-boundary-fixture-clarity"
FIXTURE_SCALE = IMPL / "mode-boundary-fixture-scale"
sys.path.insert(0, str(IMPL))

from fixture_admission import Gate, admission_status, interpretation_coverage, repo_root  # noqa: E402
from process_metrics import compute_run_metrics, load_contract  # noqa: E402

# The full-arm run whose saved workspace marked impact-map consumers "verified"
# and which the exact grader scored 70 on formatting alone.
FULL_RUN_ID = "20260715-092824975-adaptive-contract-evolution-v4-full-t1"

# Compact reconstruction of the ORIGINAL exact-string v4 grader that made the
# main stage invalid: ten dims pass trivially, the three serialized dims hard
# compare exact strings, so any different-but-valid serialization fails.
BRITTLE_V4_GRADER = '''import importlib, json, sys
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass
WORKSPACE = Path(sys.argv[1]).resolve(); sys.path.insert(0, str(WORKSPACE)); checks = []
def record(cid, w, passed, detail=""): checks.append({"id": cid, "passed": bool(passed), "weight": w, "detail": detail})
def mod(n): return importlib.import_module(n)
for cid, w in [("current-envelope",9),("open-world-unicode",6),("input-validation",9),("malformed-telemetry",6),("copy-isolation",7),("legacy-wrapper",4),("documentation",4),("degraded-path",7),("exact-type-match",7),("repeat-dedup",11)]:
    record(cid, w, True)
try:
    c = mod("src.consumers")
    p = c.render_primary({"type":"customer","id":"2","fields":{}}, {}); a = c.render_audit({"type":"customer","id":"2","fields":{"b":1}}, {})
    record("consumer-primary", 6, p == "customer:2" and a == "AUDIT customer ['b']")
except BaseException as e:
    record("consumer-primary", 6, False, str(e))
try:
    d = mod("src.exporter").export_digest([{"type":"customer","id":"1","fields":{}},{"type":"ghost","id":"2","fields":{"z":9}}], {"customer": lambda x: {**x, "n": 1}})
    record("exporter-propagation", 12, d == ["3:customer:1:['n']", "3:ghost:2:['z']"])
except BaseException as e:
    record("exporter-propagation", 12, False, str(e))
try:
    s = mod("src.snapshot").build_snapshot([{"type":"account","id":"7","fields":{}},{"type":"phantom","id":"8","fields":{"q":5}}], {"account": lambda x: {**x, "m": 2}})
    record("snapshot-propagation", 12, s == {"7": "v3|account|7|['m']", "8": "v3|phantom|8|['q']"})
except BaseException as e:
    record("snapshot-propagation", 12, False, str(e))
score = round(sum(r["weight"] for r in checks if r["passed"]) * 100 / sum(r["weight"] for r in checks))
print(json.dumps({"passed": score == 100, "score": score, "checks": checks}, ensure_ascii=False))
raise SystemExit(0 if score == 100 else 1)
'''


def grade_arm_workspace(fixture_dir: Path, run_dir: Path) -> dict:
    """Grade a saved arm workspace/src in a fresh sandbox (public + arm src + README)."""
    contract = json.loads((fixture_dir / "fixture-contract.json").read_text(encoding="utf-8-sig"))
    grader = fixture_dir / contract["hidden_grader"]
    with tempfile.TemporaryDirectory() as temp_name:
        ws = Path(temp_name)
        shutil.copytree(fixture_dir / "public", ws, dirs_exist_ok=True)
        shutil.copytree(run_dir / "workspace" / "src", ws / "src", dirs_exist_ok=True)
        readme = run_dir / "workspace" / "README.md"
        if readme.is_file():
            shutil.copy2(readme, ws / "README.md")
        completed = subprocess.run([sys.executable, str(grader), str(ws)], cwd=ws, text=True,
                                   capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    for line in reversed((completed.stdout + "\n" + completed.stderr).splitlines()):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise AssertionError("grader emitted no JSON: " + (completed.stdout + completed.stderr)[-1000:])

OLD_AMBIGUOUS_TASK = """# Adaptive contract evolution

Evolve the ingestion contract without replacing the public API with a sample-derived special case.

- Add `normalize_event(event, registry)` returning exactly `{"entity_type", "entity_id", "attributes"}`.
- Treat entity types and attribute names as open-world: unseen non-blank strings must work through the runtime `registry`; do not encode discovered samples as an allowlist or regex alternation.
- Record `unknown_entity_type` and `malformed_event` through `metrics.increment(name)` at the corresponding behavior boundaries.

Do not modify `task.md` or existing public tests.
"""

# Minimal reproduction of the invalid campaign's grader shape: one exception
# boundary around every dimension, collapsing into a single fixture-runtime row.
COLLAPSING_GRADER = '''import importlib, json, sys
from pathlib import Path
workspace = Path(sys.argv[1]).resolve(); sys.path.insert(0, str(workspace)); checks = []
def record(name, passed, weight): checks.append({"id": name, "passed": bool(passed), "weight": weight})
try:
    contracts = importlib.import_module("src.contracts")
    contracts.normalize_event({"type": "customer", "id": "1", "fields": {}}, {})
    for name in ("current-envelope","open-world-unicode","unknown-telemetry","input-validation","malformed-telemetry","copy-isolation","legacy-wrapper","consumer-propagation","documentation"):
        record(name, True, 10)
except Exception as exc:
    checks.append({"id": "fixture-runtime", "passed": False, "weight": 100, "detail": str(exc)})
score = round(sum(r["weight"] for r in checks if r["passed"]) * 100 / sum(r["weight"] for r in checks))
print(json.dumps({"passed": score == 100, "score": score, "checks": checks}))
raise SystemExit(0 if score == 100 else 1)
'''


def clone_fixture(target: Path) -> Path:
    clone = target / "fixture"
    shutil.copytree(FIXTURE, clone, ignore=shutil.ignore_patterns("__pycache__"))
    return clone


def grade_direct(fixture_dir: Path, overlay: Path) -> dict:
    """Compose public + overlay into a temp workspace and run the hidden grader."""
    contract = json.loads((fixture_dir / "fixture-contract.json").read_text(encoding="utf-8-sig"))
    grader = fixture_dir / contract["hidden_grader"]
    with tempfile.TemporaryDirectory() as temp_name:
        workspace = Path(temp_name)
        shutil.copytree(fixture_dir / "public", workspace, dirs_exist_ok=True)
        shutil.copytree(overlay, workspace, dirs_exist_ok=True)
        completed = subprocess.run([sys.executable, str(grader), str(workspace)], cwd=workspace,
                                   text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    for line in reversed((completed.stdout + "\n" + completed.stderr).splitlines()):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise AssertionError("grader emitted no JSON: " + (completed.stdout + completed.stderr)[-1000:])


class FixtureAdmissionTests(unittest.TestCase):
    def test_platform_lint_fails_on_python3_in_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            clone = clone_fixture(Path(temp_name))
            contract_path = clone / "fixture-contract.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["public_test"] = ["python3", "-m", "unittest", "discover", "-s", "tests", "-p", "test_public.py", "-v"]
            contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
            result = Gate(clone).check_platform_lint()
            self.assertFalse(result["passed"])
            self.assertIn("python3", result["detail"])
            self.assertTrue(any(hit["file"] == "fixture-contract.json" and hit["token"] == "python3" for hit in result["hits"]))

    def test_grader_isolation_fails_on_collapsing_grader(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            clone = clone_fixture(Path(temp_name))
            (clone / "hidden/grade.py").write_text(COLLAPSING_GRADER, encoding="utf-8")
            result = Gate(clone).check_grader_isolation()
            self.assertFalse(result["passed"])
            collapsed = [row for row in result["battery"] if row["dimension_diff"]]
            self.assertTrue(collapsed, "expected at least one hostile candidate to expose the collapse")
            self.assertLess(collapsed[0]["reported_dimensions"], collapsed[0]["declared_dimensions"])
            self.assertIn("missing", result["detail"])

    def test_interpretation_coverage_fails_without_miss_behavior_sentence(self) -> None:
        coverage = interpretation_coverage(OLD_AMBIGUOUS_TASK, [])
        self.assertTrue(coverage["triggered"])
        self.assertFalse(coverage["passed"])
        self.assertIsNone(coverage["miss_behavior_sentence"])
        self.assertTrue(any("miss/absent case" in issue for issue in coverage["issues"]))
        self.assertTrue(any("decision_points" in issue for issue in coverage["issues"]))
        with tempfile.TemporaryDirectory() as temp_name:
            clone = clone_fixture(Path(temp_name))
            (clone / "public/task.md").write_text(OLD_AMBIGUOUS_TASK, encoding="utf-8")
            contract_path = clone / "fixture-contract.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract.pop("decision_points", None)
            contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
            result = Gate(clone).check_interpretation_coverage()
            self.assertFalse(result["passed"])

    def test_unpinned_decision_point_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            clone = clone_fixture(Path(temp_name))
            contract_path = clone / "fixture-contract.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["decision_points"][0]["pinned_by"] = "a sentence that does not exist in the task"
            contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
            result = Gate(clone).check_interpretation_coverage()
            self.assertFalse(result["passed"])
            self.assertIn("registry-miss", result["detail"])

    def test_missing_reference_alt_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            clone = clone_fixture(Path(temp_name))
            shutil.rmtree(clone / "hidden/reference-alt")
            gate = Gate(clone)
            result = gate.check_reference("reference-alt-pass", clone / "hidden/reference-alt")
            self.assertFalse(result["passed"])
            self.assertIn("missing overlay directory", result["detail"])

    def test_repaired_fixture_passes_and_records_paid_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "admission.json"
            completed = subprocess.run(
                [sys.executable, str(IMPL / "fixture_admission.py"), "--fixture", str(FIXTURE), "--output", str(output)],
                cwd=IMPL, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=300)
            self.assertEqual(0, completed.returncode, completed.stdout[-2000:] + completed.stderr[-2000:])
            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual("PASS", record["verdict"])
            self.assertEqual("adaptive-contract-evolution-v2", record["fixture"])
            self.assertEqual(7, len(record["checks"]))
            self.assertTrue(all(row["passed"] for row in record["checks"]))
            alt = next(row for row in record["checks"] if row["id"] == "reference-alt-pass")
            self.assertIn("alt_interpretation_differences", alt)
            # v2 declares no serialized_output_dimensions, so the format-adversary
            # check is present but skipped with a recorded reason.
            adversary = next(row for row in record["checks"] if row["id"] == "format-adversary")
            self.assertTrue(adversary["passed"])
            self.assertTrue(adversary.get("skipped"))
            self.assertIn("no serialized_output_dimensions", adversary["detail"])
            # paid_history is informational and grows once the v2 canary has run;
            # admission validity does not depend on its value being zero.
            self.assertGreaterEqual(record["paid_history"]["valid_paid_runs"], 0)
            status = admission_status("adaptive-contract-evolution-v2", FIXTURE, output)
            self.assertTrue(status["admitted"], status)

    def test_stale_admission_record_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            clone = clone_fixture(Path(temp_name))
            record_path = Path(temp_name) / "admission.json"
            gate = Gate(clone)
            record = gate.run(None)
            record["verdict"] = "PASS"  # freshness must be checked independently of the verdict
            record_path.write_text(json.dumps(record), encoding="utf-8")
            (clone / "public/task.md").write_text((clone / "public/task.md").read_text(encoding="utf-8") + "\nchanged after admission\n", encoding="utf-8")
            status = admission_status(record["fixture"], clone, record_path)
            self.assertFalse(status["admitted"])
            self.assertIn("stale", status["reason"])

    def test_v3_fixture_passes_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "admission.json"
            completed = subprocess.run(
                [sys.executable, str(IMPL / "fixture_admission.py"), "--fixture", str(FIXTURE_V3), "--output", str(output)],
                cwd=IMPL, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=300)
            self.assertEqual(0, completed.returncode, completed.stdout[-2000:] + completed.stderr[-2000:])
            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual("PASS", record["verdict"])
            self.assertEqual("adaptive-contract-evolution-v3", record["fixture"])
            self.assertTrue(all(row["passed"] for row in record["checks"]))

    def test_v3_plausible_cold_pass_scores_below_reference(self) -> None:
        """Locks in the headroom design: the cold-pass proxy must land in a
        middle band strictly between the weak control and the reference, missing
        exactly the three scaffolding-caught dimensions."""
        reference = grade_direct(FIXTURE_V3, FIXTURE_V3 / "hidden/reference")
        cold = grade_direct(FIXTURE_V3, FIXTURE_V3 / "negative-controls/plausible-cold-pass")
        weak = grade_direct(FIXTURE_V3, FIXTURE_V3 / "negative-controls/mode-1-local")
        self.assertEqual(100, reference["score"])
        self.assertLess(cold["score"], reference["score"])
        self.assertLess(weak["score"], cold["score"])
        self.assertTrue(66 <= cold["score"] <= 80, f"cold-pass score {cold['score']} outside the declared headroom band")
        # It must miss exactly the three discriminating dimensions and pass the rest.
        missed = {row["id"] for row in cold["checks"] if not row["passed"]}
        self.assertEqual({"degraded-path", "exporter-propagation", "exact-type-match"}, missed)

    def test_v3_escalates_to_main_stage_after_canary(self) -> None:
        """The v3 one-call canary has run live (run-record in Evals/runs with
        outcome_valid=true, score 91), so v3 now has valid paid history and its
        campaign escalates past the canary to the full five-arm main stage. The
        canary-forced-without-paid-history invariant is now exercised on v4,
        which genuinely has no paid history (test_v4_canary_plan_forced_...)."""
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "campaign.json"
            admit = subprocess.run(
                [sys.executable, str(IMPL / "fixture_admission.py"), "--fixture", str(FIXTURE_V3)],
                cwd=IMPL, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=300)
            self.assertEqual(0, admit.returncode, admit.stdout[-2000:] + admit.stderr[-2000:])
            completed = subprocess.run(
                [sys.executable, str(IMPL / "new_ablation_campaign.py"), "--fixture", "adaptive-contract-evolution-v3", "--output", str(output)],
                cwd=IMPL, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
            self.assertEqual(0, completed.returncode, completed.stdout[-2000:] + completed.stderr[-2000:])
            campaign = json.loads(output.read_text(encoding="utf-8"))
            self.assertGreaterEqual(campaign["paid_history"]["valid_paid_runs"], 1)
            self.assertEqual("main", campaign["stage"])
            self.assertEqual("awaiting-explicit-approval", campaign["status"])
            self.assertEqual(0, campaign["provider_calls"])

    def test_v4_fixture_passes_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "admission.json"
            completed = subprocess.run(
                [sys.executable, str(IMPL / "fixture_admission.py"), "--fixture", str(FIXTURE_V4), "--output", str(output)],
                cwd=IMPL, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=300)
            self.assertEqual(0, completed.returncode, completed.stdout[-2000:] + completed.stderr[-2000:])
            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual("PASS", record["verdict"])
            self.assertEqual("adaptive-contract-evolution-v4", record["fixture"])
            self.assertTrue(all(row["passed"] for row in record["checks"]))

    def test_v4_plausible_cold_pass_scores_below_reference(self) -> None:
        """Locks in the wide-headroom design: the cold-pass proxy lands in the
        declared 55-68 band, strictly between the weak control and the reference,
        missing exactly the two indirect propagation chains and the re-run state
        interaction (the demonstrated multi-hop / state-tracing blind spot)."""
        reference = grade_direct(FIXTURE_V4, FIXTURE_V4 / "hidden/reference")
        cold = grade_direct(FIXTURE_V4, FIXTURE_V4 / "negative-controls/plausible-cold-pass")
        weak = grade_direct(FIXTURE_V4, FIXTURE_V4 / "negative-controls/mode-1-local")
        self.assertEqual(100, reference["score"])
        self.assertLess(cold["score"], reference["score"])
        self.assertLess(weak["score"], cold["score"])
        self.assertTrue(55 <= cold["score"] <= 68, f"cold-pass score {cold['score']} outside the declared headroom band")
        missed = {row["id"] for row in cold["checks"] if not row["passed"]}
        self.assertEqual({"exporter-propagation", "snapshot-propagation", "repeat-dedup"}, missed)

    def test_v4_escalates_to_main_stage_after_canary(self) -> None:
        """The v4 one-call canary has now run live (run-record in Evals/runs with
        outcome_valid=true), so v4 has valid paid history and escalates past the
        canary to the full main stage. The canary-forced-without-paid-history
        invariant is now exercised on the clarity fixture, which genuinely has no
        paid history (test_clarity_canary_plan_forced_without_paid_history)."""
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "campaign.json"
            admit = subprocess.run(
                [sys.executable, str(IMPL / "fixture_admission.py"), "--fixture", str(FIXTURE_V4)],
                cwd=IMPL, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=300)
            self.assertEqual(0, admit.returncode, admit.stdout[-2000:] + admit.stderr[-2000:])
            completed = subprocess.run(
                [sys.executable, str(IMPL / "new_ablation_campaign.py"), "--fixture", "adaptive-contract-evolution-v4", "--output", str(output)],
                cwd=IMPL, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
            self.assertEqual(0, completed.returncode, completed.stdout[-2000:] + completed.stderr[-2000:])
            campaign = json.loads(output.read_text(encoding="utf-8"))
            self.assertGreaterEqual(campaign["paid_history"]["valid_paid_runs"], 1)
            self.assertEqual("main", campaign["stage"])
            self.assertEqual("awaiting-explicit-approval", campaign["status"])
            self.assertEqual(0, campaign["provider_calls"])

    def test_clarity_fixture_passes_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "admission.json"
            completed = subprocess.run(
                [sys.executable, str(IMPL / "fixture_admission.py"), "--fixture", str(FIXTURE_CLARITY), "--output", str(output)],
                cwd=IMPL, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=300)
            self.assertEqual(0, completed.returncode, completed.stdout[-2000:] + completed.stderr[-2000:])
            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual("PASS", record["verdict"])
            self.assertEqual("implicit-conventions-v1", record["fixture"])
            self.assertTrue(all(row["passed"] for row in record["checks"]))
            coverage = next(row for row in record["checks"] if row["id"] == "interpretation-coverage")
            self.assertEqual("underspecified-by-design", coverage["coverage"]["fixture_class"])

    def test_clarity_convention_anchor_tamper_fails_admission(self) -> None:
        """The class-aware interpretation-coverage check must be real: a quote
        that no longer exists in the cited public file fails admission."""
        with tempfile.TemporaryDirectory() as temp_name:
            clone = Path(temp_name) / "fixture"
            shutil.copytree(FIXTURE_CLARITY, clone, ignore=shutil.ignore_patterns("__pycache__"))
            contract_path = clone / "fixture-contract.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["convention_anchors"][2]["quote"] = "a convention sentence that exists nowhere in the repo"
            contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
            result = Gate(clone).check_interpretation_coverage()
            self.assertFalse(result["passed"])
            self.assertIn("quote not found", result["detail"])
            del contract["convention_anchors"][2]
            contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
            result = Gate(clone).check_interpretation_coverage()
            self.assertFalse(result["passed"])
            self.assertIn("no convention_anchor", result["detail"])

    def test_clarity_plausible_cold_pass_scores_below_reference(self) -> None:
        """Locks in the headroom design: the cold-pass proxy lands in the declared
        45-65 band, strictly between the weak control and the reference, missing
        exactly the four implicit conventions it never went looking for."""
        reference = grade_direct(FIXTURE_CLARITY, FIXTURE_CLARITY / "hidden/reference")
        cold = grade_direct(FIXTURE_CLARITY, FIXTURE_CLARITY / "negative-controls/plausible-cold-pass")
        weak = grade_direct(FIXTURE_CLARITY, FIXTURE_CLARITY / "negative-controls/mode-1-local")
        self.assertEqual(100, reference["score"])
        self.assertLess(cold["score"], reference["score"])
        self.assertLess(weak["score"], cold["score"])
        self.assertTrue(45 <= cold["score"] <= 65, f"cold-pass score {cold['score']} outside the declared headroom band")
        missed = {row["id"] for row in cold["checks"] if not row["passed"]}
        self.assertEqual({"order-dependency", "point-in-time", "changelog-discipline", "silent-zero-rows"}, missed)

    def test_clarity_canary_plan_forced_without_paid_history(self) -> None:
        """The canary-forced-without-paid-history invariant, exercised against a
        synthesized empty runs directory: the live clarity canary ran on
        2026-07-15, so no admitted fixture is genuinely unpaid any more and the
        invariant must not depend on mutable Evals/runs state."""
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "campaign.json"
            empty_runs = Path(temp_name) / "no-paid-history-runs"
            empty_runs.mkdir()
            admit = subprocess.run(
                [sys.executable, str(IMPL / "fixture_admission.py"), "--fixture", str(FIXTURE_CLARITY)],
                cwd=IMPL, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=300)
            self.assertEqual(0, admit.returncode, admit.stdout[-2000:] + admit.stderr[-2000:])
            completed = subprocess.run(
                [sys.executable, str(IMPL / "new_ablation_campaign.py"), "--fixture", "implicit-conventions-v1", "--output", str(output), "--runs-dir", str(empty_runs)],
                cwd=IMPL, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
            self.assertEqual(0, completed.returncode, completed.stdout[-2000:] + completed.stderr[-2000:])
            campaign = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual("canary", campaign["stage"])
            self.assertEqual(1, campaign["loop"]["max_total_provider_calls"])
            self.assertEqual(["vanilla"], [row["arm"] for row in campaign["runs"]])
            self.assertEqual([], campaign["independent_verifier_runs"])
            self.assertEqual(0, campaign["paid_history"]["valid_paid_runs"])
            self.assertEqual(0, campaign["provider_calls"])
            self.assertTrue(campaign["canary_policy"]["main_stage_requires"]["separate_approval"])


    def test_v4_format_adversary_admits(self) -> None:
        """v4 declares serialized_output_dimensions, so admission runs the
        format-adversary: hidden/reference-format-alt (same substance, different
        serialization) must score 100 and differ from the primary reference."""
        result = Gate(FIXTURE_V4).check_format_adversary()
        self.assertTrue(result["passed"], result["detail"])
        self.assertFalse(result.get("skipped"))
        self.assertEqual(100, result["adversary_score"])
        self.assertTrue(result["differing_format_files"],
                        "the format-adversary must genuinely differ from the reference")

    def test_v4_semantic_grader_accepts_format_alt_rejects_version_omitting_control(self) -> None:
        """The semantic grader accepts a different-but-valid serialization at 100,
        and still rejects the version-omitting cold-pass control on both indirect
        chains (content missing, not merely a different format)."""
        alt = grade_direct(FIXTURE_V4, FIXTURE_V4 / "hidden/reference-format-alt")
        self.assertEqual(100, alt["score"])
        cold = grade_direct(FIXTURE_V4, FIXTURE_V4 / "negative-controls/plausible-cold-pass")
        missed = {row["id"] for row in cold["checks"] if not row["passed"]}
        self.assertIn("exporter-propagation", missed)
        self.assertIn("snapshot-propagation", missed)
        self.assertLess(cold["score"], 100)

    def test_format_adversary_rejects_a_brittle_grader(self) -> None:
        """The admission check must actually catch format-brittleness: pointed at
        the original exact-string grader, the same format-alt scores below the
        reference and the check FAILS with a format-brittle message."""
        with tempfile.TemporaryDirectory() as temp_name:
            clone = Path(temp_name) / "fx"
            shutil.copytree(FIXTURE_V4, clone, ignore=shutil.ignore_patterns("__pycache__"))
            (clone / "hidden/grade.py").write_text(BRITTLE_V4_GRADER, encoding="utf-8")
            result = Gate(clone).check_format_adversary()
            self.assertFalse(result["passed"])
            self.assertEqual(70, result["adversary_score"])
            self.assertIn("format-brittle", result["detail"])

    def test_all_five_live_arms_score_100_semantically(self) -> None:
        """Once format noise is removed, every saved main-stage arm the exact
        grader scored 70 now scores 100 under the semantic grader."""
        runs_root = repo_root() / "Evals" / "runs"
        full_dir = runs_root / FULL_RUN_ID
        if not full_dir.is_dir():
            self.skipTest("saved v4 run workspaces not present")
        grade = grade_arm_workspace(FIXTURE_V4, full_dir)
        self.assertEqual(100, grade["score"], [c for c in grade["checks"] if not c["passed"]])

    def test_process_metrics_self_attestation_gap_on_full_run(self) -> None:
        """process_metrics must report the truth on the saved full run: it marked
        impact-map consumers 'verified', and under semantic grading its consumer
        dimensions all pass, so the self-attestation gap is False (trustworthy)
        and consumer enumeration is complete."""
        runs_root = repo_root() / "Evals" / "runs"
        full_dir = runs_root / FULL_RUN_ID
        if not full_dir.is_dir():
            self.skipTest("saved v4 run workspaces not present")
        contract = load_contract(FIXTURE_V4)
        grade = grade_arm_workspace(FIXTURE_V4, full_dir)
        metrics = compute_run_metrics(full_dir, contract, grade)
        self.assertTrue(metrics["has_impact_map"])
        self.assertEqual(100, metrics["semantic_score"])
        self.assertEqual(70, metrics["original_exact_score"])
        self.assertFalse(metrics["self_attestation_gap"])
        self.assertIn("trustworthy", metrics["self_attestation_detail"])
        self.assertEqual(1.0, metrics["consumer_enumeration_completeness"])
        self.assertEqual(1.0, metrics["consumer_edit_completeness"])

    def test_scale_fixture_passes_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "admission.json"
            completed = subprocess.run(
                [sys.executable, str(IMPL / "fixture_admission.py"), "--fixture", str(FIXTURE_SCALE), "--output", str(output)],
                cwd=IMPL, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=300)
            self.assertEqual(0, completed.returncode, completed.stdout[-2000:] + completed.stderr[-2000:])
            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual("PASS", record["verdict"])
            self.assertEqual("implicit-conventions-scale-v1", record["fixture"])
            self.assertTrue(all(row["passed"] for row in record["checks"]))
            coverage = next(row for row in record["checks"] if row["id"] == "interpretation-coverage")
            self.assertEqual("underspecified-by-design", coverage["coverage"]["fixture_class"])
            # The format-adversary must run against the CONTRACT-declared
            # format-bearing files (the v4 constant does not exist here).
            adversary = next(row for row in record["checks"] if row["id"] == "format-adversary")
            self.assertFalse(adversary.get("skipped"))
            self.assertEqual(100, adversary["adversary_score"])
            declared = set(json.loads((FIXTURE_SCALE / "fixture-contract.json").read_text(encoding="utf-8-sig"))["format_bearing_files"])
            self.assertTrue(set(adversary["differing_format_files"]) <= declared)
            self.assertTrue(adversary["differing_format_files"])

    def test_scale_workspace_exceeds_single_pass_size(self) -> None:
        """Locks the scale property itself: the public workspace must stay past
        single-pass comprehension size (module count and volume), or the fixture
        silently degrades into another single-pass fixture."""
        public = FIXTURE_SCALE / "public"
        modules = [p for p in public.rglob("*.py") if "__pycache__" not in p.parts]
        total_bytes = sum(p.stat().st_size for p in public.rglob("*") if p.is_file())
        stub_sources = [p for p in (public / "src/sources").glob("*_feed.py")
                        if "NotImplementedError" in p.read_text(encoding="utf-8")]
        self.assertGreaterEqual(len(modules), 40, "scale fixture must keep >= 40 python modules")
        self.assertGreaterEqual(total_bytes, 100_000, "scale fixture must keep >= 100KB of workspace")
        self.assertGreaterEqual(len(stub_sources), 10, "the decoy stub sources must survive (epsilon stub + 10 scrape-only)")
        self.assertIn("fifteen venues live", (public / "PLAN.md").read_text(encoding="utf-8"),
                      "PLAN.md must keep its aspirational overstatement (the scope-judgment decoy)")

    def test_scale_plausible_cold_pass_scores_below_reference(self) -> None:
        """Locks in the distance-driven headroom design: the cold-pass proxy
        lands in the declared 40-60 band, strictly between the weak control and
        the reference, missing exactly the seven dimensions whose evidence lives
        >= 2 modules from the code it wrote (the two cross-file convention pairs,
        the three unopened subtrees, and the PLAN.md scope trap)."""
        reference = grade_direct(FIXTURE_SCALE, FIXTURE_SCALE / "hidden/reference")
        cold = grade_direct(FIXTURE_SCALE, FIXTURE_SCALE / "negative-controls/plausible-cold-pass")
        weak = grade_direct(FIXTURE_SCALE, FIXTURE_SCALE / "negative-controls/mode-1-local")
        self.assertEqual(100, reference["score"])
        self.assertLess(cold["score"], reference["score"])
        self.assertLess(weak["score"], cold["score"])
        self.assertTrue(40 <= cold["score"] <= 60, f"cold-pass score {cold['score']} outside the declared headroom band")
        missed = {row["id"] for row in cold["checks"] if not row["passed"]}
        self.assertEqual({"migration-path", "changelog-discipline", "run-order", "venue-config",
                          "consumer-exposure", "consumer-alerts", "scope-judgment"}, missed)

    def test_scale_canary_plan_forced_with_loop_overrides(self) -> None:
        """The scale fixture is unpaid, so campaign creation must force the
        one-call canary; and its contract-declared loop overrides (raised
        per-call turn/wall budget so a low score measures prioritization, not
        truncation) must be applied and recorded. Exercised against a
        synthesized empty runs directory so the invariant survives the live
        canary later gaining paid history."""
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "campaign.json"
            empty_runs = Path(temp_name) / "no-paid-history-runs"
            empty_runs.mkdir()
            admit = subprocess.run(
                [sys.executable, str(IMPL / "fixture_admission.py"), "--fixture", str(FIXTURE_SCALE)],
                cwd=IMPL, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=300)
            self.assertEqual(0, admit.returncode, admit.stdout[-2000:] + admit.stderr[-2000:])
            completed = subprocess.run(
                [sys.executable, str(IMPL / "new_ablation_campaign.py"), "--fixture", "implicit-conventions-scale-v1",
                 "--output", str(output), "--runs-dir", str(empty_runs)],
                cwd=IMPL, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
            self.assertEqual(0, completed.returncode, completed.stdout[-2000:] + completed.stderr[-2000:])
            campaign = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual("canary", campaign["stage"])
            self.assertEqual(1, campaign["loop"]["max_total_provider_calls"])
            self.assertEqual(["vanilla"], [row["arm"] for row in campaign["runs"]])
            self.assertEqual([], campaign["independent_verifier_runs"])
            self.assertEqual(0, campaign["paid_history"]["valid_paid_runs"])
            self.assertEqual(0, campaign["provider_calls"])
            self.assertEqual("awaiting-explicit-approval", campaign["status"])
            self.assertEqual(40, campaign["loop"]["max_turns_per_call"])
            self.assertEqual(50, campaign["loop"]["max_wall_minutes_per_call"])
            self.assertEqual(40, campaign["loop_overrides"]["max_turns_per_call"])
            self.assertIn("reason", campaign["loop_overrides"])

    def test_scale_loop_overrides_do_not_leak_to_other_fixtures(self) -> None:
        """Only a fixture that declares campaign_loop_overrides gets them: the
        v4 campaign keeps the default 18-turn / 25-minute per-call budget."""
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "campaign.json"
            admit = subprocess.run(
                [sys.executable, str(IMPL / "fixture_admission.py"), "--fixture", str(FIXTURE_V4)],
                cwd=IMPL, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=300)
            self.assertEqual(0, admit.returncode, admit.stdout[-2000:] + admit.stderr[-2000:])
            completed = subprocess.run(
                [sys.executable, str(IMPL / "new_ablation_campaign.py"), "--fixture", "adaptive-contract-evolution-v4", "--output", str(output)],
                cwd=IMPL, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
            self.assertEqual(0, completed.returncode, completed.stdout[-2000:] + completed.stderr[-2000:])
            campaign = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(18, campaign["loop"]["max_turns_per_call"])
            self.assertEqual(25, campaign["loop"]["max_wall_minutes_per_call"])
            self.assertIsNone(campaign["loop_overrides"])

    def test_scale_process_metrics_compute_on_synthetic_run(self) -> None:
        """process_metrics must work for the scale fixture's process_ground_truth:
        consumer_enumeration_completeness over the seven ground-truth consumer
        files and a self_attestation_gap that fires when consumers are marked
        'verified' while a consumer dimension fails semantically."""
        contract = load_contract(FIXTURE_SCALE)
        ground = contract["process_ground_truth"]
        with tempfile.TemporaryDirectory() as temp_name:
            run_dir = Path(temp_name) / "run"
            (run_dir / "workspace/.agentic").mkdir(parents=True)
            enumerated = ground["consumers"][:4]  # 4 of 7 enumerated
            impact_map = {"sections": {"consumers": {
                "status": "verified",
                "evidence": [{"path": path, "observation": "listed"} for path in enumerated],
            }}}
            (run_dir / "workspace/.agentic/impact-map.json").write_text(json.dumps(impact_map), encoding="utf-8")
            (run_dir / "run-record.json").write_text(json.dumps({
                "arm": "full", "tokens": 123456,
                "changed_files": ground["required_edits"][:5],
                "grader": {"score": 79},
            }), encoding="utf-8")
            grade = {"score": 79, "checks": (
                [{"id": dim, "passed": dim != "consumer-alerts"} for dim in ground["consumer_dimensions"]])}
            metrics = compute_run_metrics(run_dir, contract, grade)
            self.assertTrue(metrics["has_impact_map"])
            self.assertAlmostEqual(4 / 7, metrics["consumer_enumeration_completeness"], places=3)
            self.assertAlmostEqual(5 / 7, metrics["consumer_edit_completeness"], places=3)
            self.assertTrue(metrics["self_attestation_gap"])
            self.assertIn("consumer-alerts", metrics["self_attestation_detail"])
            grade_all_pass = {"score": 100, "checks": [
                {"id": dim, "passed": True} for dim in ground["consumer_dimensions"]]}
            metrics_ok = compute_run_metrics(run_dir, contract, grade_all_pass)
            self.assertFalse(metrics_ok["self_attestation_gap"])

    def test_process_metrics_gap_true_when_verified_but_semantically_wrong(self) -> None:
        """The gap instrument must fire when a run claims consumers 'verified' but
        the semantic grade fails a consumer dimension."""
        contract = load_contract(FIXTURE_V4)
        runs_root = repo_root() / "Evals" / "runs"
        full_dir = runs_root / FULL_RUN_ID
        if not full_dir.is_dir():
            self.skipTest("saved v4 run workspaces not present")
        fake_grade = {"score": 88, "checks": [
            {"id": "exporter-propagation", "passed": False},
            {"id": "snapshot-propagation", "passed": True},
            {"id": "consumer-primary", "passed": True},
        ]}
        metrics = compute_run_metrics(full_dir, contract, fake_grade)
        self.assertTrue(metrics["self_attestation_gap"])
        self.assertIn("not trustworthy", metrics["self_attestation_detail"])


if __name__ == "__main__":
    unittest.main()
