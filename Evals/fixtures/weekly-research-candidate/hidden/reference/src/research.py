import json
from pathlib import Path

def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def build_candidate(root, run_id, sources, claims):
    root = Path(root)
    if not isinstance(run_id, str) or not run_id or "/" in run_id or "\\" in run_id or run_id in {".", ".."}:
        raise ValueError("run_id")
    candidate = root / "Research/candidate-packages" / run_id
    candidate.mkdir(parents=True, exist_ok=False)
    _write_json(candidate / "manifest.json", {"schema_version":1,"run_id":run_id,"status":"awaiting-eval","promoted":False})
    _write_json(candidate / "source-snapshot.json", {"sources":sources})
    _write_json(candidate / "claims.json", {"claims":claims})
    _write_json(candidate / "rejected-claims.json", {"claims":[]})
    (candidate / "proposed-guidance.patch").write_text("# Candidate proposal; no stable mutation\n", encoding="utf-8")
    (candidate / "eval-plan.md").write_text("# Eval plan\n\nRun controlled A/B outcome evaluations before promotion.\n", encoding="utf-8")
    (candidate / "impact-rollback.md").write_text("# Impact and rollback\n\nPromotion is separate; rollback restores the prior stable manifest.\n", encoding="utf-8")
    links = "\n".join("- [{0}]({1})".format(source.get("id", "source"), source["url"]) for source in sources)
    (candidate / "report.md").write_text("# Weekly research candidate\n\nStatus: awaiting-eval\n\n## Sources\n\n" + links + "\n", encoding="utf-8")
    return candidate
