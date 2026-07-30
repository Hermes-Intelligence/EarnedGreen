#!/usr/bin/env python3
"""Candidate adaptive mode selector and precision knowledge router."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
MODE_RANK = {"lite": 0, "standard": 1, "critical": 2}
# Historical mode/arm ids (schema <= 3 runs, saved campaign evidence). Analyzers
# that parse old run manifests map them through this table; new selection never
# produces them.
LEGACY_MODE_RANK = {"vanilla": 0, "mode-1-lean": 0, "mode-2-routed": 1, "mode-3-assured": 1, "full": 2}

# A "single-token" phrase is one contiguous word (letters/digits/underscore) with no
# spaces or hyphens. Those are matched with word boundaries so short anchors like
# ``ttl``/``auth``/``kind``/``field`` no longer match inside ``battle``/``author``/
# ``unkind``/``subfield``. Multi-word / hyphenated phrases keep cheap substring matching.
_SINGLE_TOKEN = re.compile(r"^\w+$")


def repo_root() -> Path:
    for parent in (HERE, *HERE.parents):
        if (parent / "Runtime/stable/manifest.json").exists():
            return parent
    raise RuntimeError("AgenticWorkBestPractices root not found")


REPO = repo_root()


def policy_path(local_name: str, stable_name: str) -> Path:
    local = HERE / local_name
    return local if local.exists() else REPO / stable_name


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def contains(text: str, phrases: list[str]) -> list[str]:
    hits: list[str] = []
    for phrase in phrases:
        if _SINGLE_TOKEN.match(phrase):
            if re.search(rf"\b{re.escape(phrase)}\b", text):
                hits.append(phrase)
        elif phrase in text:
            hits.append(phrase)
    return hits


def requirement_count(task: str) -> int:
    bullets = sum(1 for line in task.splitlines() if re.match(r"^\s*(?:[-*]|\d+[.)])\s+\S", line))
    musts = len(re.findall(r"\b(?:must|shall|required|requires)\b", task, re.I))
    return max(bullets, musts, 1)


# --- Specification clarity (fourth axis) ---------------------------------------
# A task is UNDERSPECIFIED when it implies a real scope (build a new
# product/source/adapter/integration, "like the existing X", "consistent with how
# the existing ... work") while pinning almost none of its own acceptance
# criteria: the real requirements live in the codebase's implicit conventions.
# This is the demonstrated Hermes failure class (DC WIRE, NY Medicaid adapter):
# the task text contained almost none of the load-bearing requirements.
_IMPLIED_SCOPE_PHRASES = [
    "new product", "new adapter", "new integration", "new pipeline", "new source",
    "new connector", "new feed", "new state adapter", "like the existing",
    "same as the existing", "consistent with how", "the same product",
    "the same way the existing", "works like the", "mirror the existing",
    "adapt the", "port the",
]
_BREADTH_IMPACT_PHRASES = ["across", "end to end", "end-to-end", "production", "the whole system"]
# Behavioral pinning markers: sentences that nail an edge case or an exact
# contract. Their presence is evidence the author DID write the spec down.
_PINNED_BEHAVIOR = re.compile(
    r"\b(?:exactly|must not|never|verbatim|raises?\s+[A-Z]\w*|returns?\s+exactly|"
    r"returning\s+exactly|increments?\s+`|exit\s+code)\b",
    re.I,
)


def specification_clarity(text: str, reqs: int, ambiguous: list[str], matched: dict[str, list[str]],
                          doc_only: bool) -> dict[str, Any]:
    """Classify the task as well-specified or underspecified.

    Bias: precision over recall. Underspecified REQUIRES an implied-scope phrase,
    so mechanical, read-only, doc-only and explicitly pinned tasks never buy the
    planning phase; a false negative degrades to today's behavior, while a false
    positive would put a completion-blocking spec gate in front of work that
    never needed one.
    """
    scope_hits = contains(text, _IMPLIED_SCOPE_PHRASES)
    breadth_hits = contains(text, _BREADTH_IMPACT_PHRASES)
    pinned = len(_PINNED_BEHAVIOR.findall(text))
    non_mutating = bool(matched["read_only"] or matched["non_executing_action"])
    thin_spec = pinned == 0 and (reqs <= 4 or (bool(ambiguous) and reqs <= 8) or bool(breadth_hits))
    underspecified = (not non_mutating and not matched["mechanical"] and not doc_only
                      and bool(scope_hits) and thin_spec)
    return {
        "clarity": "underspecified" if underspecified else "well-specified",
        "implied_scope": scope_hits,
        "breadth_impact": breadth_hits,
        "pinned_behavior_count": pinned,
        "requirement_count": reqs,
        "ambiguity_count": len(ambiguous),
    }


# --- Decision-type detection (decision-time research surfacing) ------------------
# When the task is itself a DESIGN DECISION - designing a benchmark, choosing an
# architecture, deciding whether to adopt a component - the Context Pack must
# surface the research findings that bear on it. This is JIT retrieval for
# decisions: the corpus already contained "the full multi-agent harness cost
# ~20x a solo agent" and "strip scaffolding as models improve" (findings-index
# F-2026-07-12-021) before the mode ladder and benchmark program were designed,
# and nothing routed those claims into the design. Detection is deliberately
# phrase-anchored: implementation tasks that merely say a consumer "must adopt
# the new contract" are execution, not decisions, and must NOT receive research
# findings (benchmark arm contexts stay uncontaminated).
_DECISION_TYPE_PHRASES = {
    "design": ["design the", "design a", "design an", "should we add", "should we adopt",
               "should we build", "should we use", "choose between", "trade-off", "tradeoff",
               "adopt or", "decide whether", "is it worth adding", "worth the complexity"],
    "benchmark": ["benchmark", "compare modes", "comparing modes", "eval plan", "ablation",
                  "a/b test", "measure the lift", "eval protocol", "how many trials"],
    "architecture": ["architecture", "architectural", "system design", "orchestration tier",
                     "multi-agent design", "harness design", "mode ladder"],
}


def detect_decision_type(text: str) -> dict[str, Any]:
    kinds: list[str] = []
    signals: list[str] = []
    for kind, phrases in _DECISION_TYPE_PHRASES.items():
        hits = contains(text, phrases)
        if hits:
            kinds.append(kind)
            signals.extend(hits)
    return {"detected": bool(kinds), "kinds": kinds, "signals": signals}


def surface_relevant_findings(text: str, decision_type: dict[str, Any], limit: int = 5) -> dict[str, Any]:
    """Match findings-index entries against the task text by topic keywords.

    Returns the top findings for a detected design/benchmark/architecture
    decision so the Context Pack carries the research that bears on it. Never
    raises on a missing index: surfacing is additive and must not break routing.
    """
    if not decision_type["detected"]:
        return {"decision_type": None, "findings": []}
    index_path = policy_path("findings-index.json", "Research/knowledge-base/findings-index.json")
    if not index_path.exists():
        return {"decision_type": decision_type["kinds"], "findings": [],
                "note": f"findings index not found: {index_path.name}"}
    index = load_json(index_path)
    scored: list[dict[str, Any]] = []
    for finding in index.get("findings", []):
        hits = contains(text, finding.get("match_terms", []))
        if not hits:
            continue
        scored.append({
            "id": finding["id"],
            "claim": finding["claim"],
            "topic_tags": finding.get("topic_tags", []),
            "sources": finding.get("sources", []),
            "origin": finding.get("origin"),
            "matched_terms": hits,
            "score": len(hits),
        })
    scored.sort(key=lambda row: (-row["score"], row["id"]))
    return {"decision_type": decision_type["kinds"], "index": index_path.name, "findings": scored[:limit]}


def analyze(task: str, changed_paths: list[str]) -> dict[str, Any]:
    text = task.lower()
    phrases = {
        "read_only": ["explain only", "answer only", "report status", "read-only", "do not change", "just tell me"],
        "mechanical": ["mechanical", "typo", "format only", "private local variable", "rename a private"],
        "public_contract": ["public api", "versioned api", "response schema", "function signature", "backward-compatible", "every consumer", "serialization contract"],
        "open_world": ["open-world", "unseen values", "without an allowlist", "mapping can grow", "runtime additions", "new kinds"],
        "reliability": ["misleading green", "stale data", "temporarybackenderror", "retry policy", "cache identity", "idempotent", "resume after failure"],
        "security": ["prompt injection", "credential handling", "secret handling", "authentication", "authorization", "untrusted repository", "command injection", "data exfiltration"],
        "migration": ["database migration", "schema rollout", "expand-migrate-contract", "backfill", "zero-downtime migration"],
        "multi_session": ["multi-session", "fresh session", "cold resume", "continue tomorrow", "session handoff", "checkpoint and resume"],
        "research": ["research candidate", "candidate package", "source registry", "weekly research", "academic papers"],
        "external_action": ["deploy to production", "publish the", "send the email", "send a message", "push to remote", "delete production", "rotate credentials"],
        "non_executing_action": ["do not execute", "do not deploy", "without deploying", "plan only", "draft a plan", "write a runbook", "document how to", "explain how to", "simulate only", "dry-run only", "dry run only", "review the plan"],
        "cross_system": ["cross-system", "multiple repositories", "frontend and backend", "code, migration, documentation and observability"],
    }
    matched = {key: contains(text, values) for key, values in phrases.items()}
    suffixes = {Path(path).suffix.lower() for path in changed_paths}
    multi_file = len(changed_paths) > 2 or bool(matched["cross_system"]) or "every consumer" in text or "across runtime code" in text
    doc_only = bool(changed_paths) and suffixes <= {".md", ".txt", ".rst"}
    ambiguous = []
    if "non-empty string" in text and "whitespace" not in text and "non-blank" not in text:
        ambiguous.append("non-empty does not define whitespace-only behavior")
    for phrase in ("appropriate", "as needed", "etc.", "and so on"):
        if phrase in text:
            ambiguous.append(f"subjective scope term: {phrase}")
    reqs = requirement_count(task)

    # Selection (modes.json schema 4). Consequence (blast radius) is the only
    # axis that changes the mode: critical consequence with execution intent
    # selects the critical mode and its human gate. High/medium consequence
    # stays in standard - the verification loop's independently executed checks
    # cover it; the measured benchmarks showed heavier prompt scaffolding never
    # bought correctness. Clarity and continuity add conditional capabilities
    # inside the selected mode; breadth is telemetry only.
    # A high-blast-radius phrase is not itself authorization to perform the action.
    # Planning, explanation and dry-run tasks must not acquire the human gate merely
    # because they mention deployment or credential rotation. Execution intent and
    # consequence are recorded separately so the decision remains auditable.
    non_executing_action = bool(matched["read_only"] or matched["non_executing_action"])
    critical_action = bool(matched["external_action"]) and not non_executing_action
    migration_rollout = len(matched["migration"]) >= 2 and not non_executing_action
    if critical_action or migration_rollout:
        consequence = "critical"
    elif matched["security"] or matched["migration"]:
        consequence = "high"
    elif any(matched[key] for key in ("public_contract", "open_world", "reliability")):
        consequence = "medium"
    else:
        consequence = "low"

    if multi_file or reqs > 8:
        breadth = "wide"
    elif reqs > 4 or len(changed_paths) > 2:
        breadth = "moderate"
    else:
        breadth = "narrow"

    continuity = "multi-session" if matched["multi_session"] else "single-session"

    # Clarity axis: an underspecified mutating task receives the spec-synthesis
    # capability inside its selected mode (spec synthesis needs the objective
    # ledger and gate, so it never activates in lite). Clarity never changes
    # the mode and never touches the human gate.
    clarity_signals = specification_clarity(text, reqs, ambiguous, matched, doc_only)
    clarity = clarity_signals["clarity"]

    advisory = bool(matched["read_only"]) and consequence == "low" and not changed_paths
    if advisory:
        mode, selection_reason = "lite", "advisory read-only work"
    elif matched["non_executing_action"] and matched["external_action"]:
        # A plan/runbook is real work and should receive routed topical guidance,
        # but it is not the outward-facing action itself: no human gate.
        mode, selection_reason = "standard", "plan/runbook about a critical action (non-executing)"
    elif consequence == "critical":
        mode, selection_reason = "critical", "critical consequence with execution intent"
    elif (matched["mechanical"] or doc_only) and breadth == "narrow" and reqs <= 4:
        mode, selection_reason = "lite", "trivial narrow mechanical/documentation change"
    else:
        mode, selection_reason = "standard", "default: non-trivial mutating work"

    risk = consequence

    return {
        "requirement_count": reqs,
        "changed_path_count": len(changed_paths),
        "multi_file": multi_file,
        "documentation_only": doc_only,
        "ambiguities": ambiguous,
        "matched_signals": {key: value for key, value in matched.items() if value},
        "decision_type": detect_decision_type(text),
        "axes": {"consequence": consequence, "breadth": breadth, "continuity": continuity, "clarity": clarity},
        "clarity_signals": clarity_signals,
        "action_intent": "non-executing" if non_executing_action else ("execution" if matched["external_action"] or migration_rollout else "not-applicable"),
        "advisory": advisory,
        "selection_reason": selection_reason,
        "risk": risk,
        "mode": mode,
    }


def route(task: str, changed_paths: list[str] | None = None, forced_mode: str | None = None, minimum_mode: str | None = None) -> dict[str, Any]:
    changed_paths = changed_paths or []
    analysis = analyze(task, changed_paths)
    modes = load_json(policy_path("modes.json", "Runtime/adaptive-modes.json"))
    catalog = load_json(policy_path("router-catalog.json", "Router/catalog/modules.json"))
    policy_mode = analysis["mode"]
    mode_escalations = []
    if forced_mode:
        if forced_mode not in MODE_RANK:
            raise ValueError(f"unknown forced benchmark mode: {forced_mode}")
        analysis["mode"] = forced_mode
    elif minimum_mode and MODE_RANK[minimum_mode] > MODE_RANK[analysis["mode"]]:
        mode_escalations.append({"from": analysis["mode"], "to": minimum_mode, "reason": "compiled scope exceeded the initial mode ceiling"})
        analysis["mode"] = minimum_mode
    mode_def = next(item for item in modes["modes"] if item["id"] == analysis["mode"])
    text = task.lower()
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for module in catalog["modules"]:
        if MODE_RANK[analysis["mode"]] < MODE_RANK[module["minimum_mode"]]:
            rejected.append({"id": module["id"], "reason": "mode floor"})
            continue
        always = module.get("always_from_mode") and MODE_RANK[analysis["mode"]] >= MODE_RANK[module["always_from_mode"]]
        positives = contains(text, module.get("positive_phrases", []))
        anchors = contains(text, module.get("topical_anchors", []))
        negatives = contains(text, module.get("negative_phrases", []))
        score = (100 if always else 0) + 6 * len(positives) + 2 * len(anchors) - 8 * len(negatives)
        relevant = always or bool(positives) or (len(anchors) >= 2 and not negatives)
        record = {
            "id": module["id"],
            "path": module["path"],
            "score": score,
            "reasons": [f"strong phrase: {value}" for value in positives] + [f"anchor: {value}" for value in anchors],
            "negative_matches": negatives,
            "outcome_markers": module.get("outcome_markers", []),
        }
        if relevant and score > 0:
            selected.append(record)
        else:
            rejected.append({"id": module["id"], "reason": "insufficient contextual evidence", "negative_matches": negatives})

    budget = catalog["context_budget_by_mode"][analysis["mode"]]
    selected.sort(key=lambda item: (-item["score"], item["id"]))
    selected = selected[: budget["max_modules"]]
    strong_signals = sum(len(values) for values in analysis["matched_signals"].values())
    if analysis["ambiguities"]:
        confidence = "medium"
    elif strong_signals >= 2 or analysis["mode"] == "lite":
        confidence = "high"
    else:
        confidence = "medium"
    # Conditional capabilities (modes.json schema 4): clarity and continuity
    # add capabilities INSIDE the selected mode instead of changing it.
    # Spec synthesis needs the objective ledger and gate, so it never activates
    # in lite (including benchmark-forced lite arms).
    capabilities = list(mode_def["capabilities"])
    if analysis["axes"].get("clarity") == "underspecified" and MODE_RANK[analysis["mode"]] >= 1:
        capabilities.append("spec-synthesis")
    if analysis["axes"].get("continuity") == "multi-session" and MODE_RANK[analysis["mode"]] >= 1:
        capabilities += ["durable-checkpoints", "session-handoff-state"]
    # Decision-time research surfacing: a design/benchmark/architecture decision
    # gets the top topic-matched findings from the knowledge-base index attached
    # to the Context Pack, so prior research is load-bearing at decision time.
    relevant_findings = surface_relevant_findings(text, analysis["decision_type"])
    return {
        "schema_version": 2,
        "status": "candidate-not-authoritative",
        "mode": analysis["mode"],
        "policy_selected_mode": policy_mode,
        "selection_source": "benchmark-forced" if forced_mode else ("adaptive-policy-escalated" if mode_escalations else "adaptive-policy"),
        "mode_escalations": mode_escalations,
        "mode_rank": mode_def["rank"],
        "risk": analysis["risk"],
        "routing_confidence": confidence,
        "analysis": analysis,
        "selected_modules": selected,
        "rejected_modules": rejected,
        "relevant_findings": relevant_findings,
        "context_budget": budget,
        "capabilities": capabilities,
        "model_routing": {
            "provider_independent": True,
            "primary_profile": mode_def["primary_profile"],
            "verifier_profile": mode_def["verifier_profile"],
            "human_gate": mode_def["human_gate"],
            "selector_resolution": "weekly expiring provider catalog"
        },
        "escalation_triggers": modes["escalation_triggers"],
        "downgrade_policy": modes["downgrade_policy"]
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--task")
    source.add_argument("--task-file", type=Path)
    parser.add_argument("--changed-path", action="append", default=[])
    parser.add_argument("--force-mode", choices=sorted(MODE_RANK))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    task = args.task if args.task is not None else args.task_file.read_text(encoding="utf-8-sig")
    result = route(task, args.changed_path, args.force_mode)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
