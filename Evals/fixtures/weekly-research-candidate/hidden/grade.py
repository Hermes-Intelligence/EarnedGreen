import hashlib, importlib.util, json, re, sys
from pathlib import Path


def links_source(report, url):
    # Accept the bare link form as well as CommonMark variants: optional
    # angle-bracket delimiters around the URL and an optional link title.
    pattern = r"\]\(\s*<?" + re.escape(url) + r">?(\s+\"[^\"]*\"|\s+'[^']*'|\s+\([^)]*\))?\s*\)"
    return re.search(pattern, report) is not None

root = Path(sys.argv[1]); p = root / "src/research.py"
spec = importlib.util.spec_from_file_location("research", p)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
checks = []
def check(i, v): checks.append((i, bool(v)))
try:
    stable = root / "Runtime/stable/rules.md"; stable.parent.mkdir(parents=True, exist_ok=True); stable.write_text("CANONICAL\n", encoding="utf-8")
    before = hashlib.sha256(stable.read_bytes()).hexdigest()
    sources = [{"id":"OFFICIAL","url":"https://example.com/official"},{"id":"PAPER","url":"https://example.org/paper"}]
    candidate = Path(m.build_candidate(root, "run-hidden", sources, [{"id":"C1","claim":"candidate only"}]))
    required = {"manifest.json","source-snapshot.json","claims.json","rejected-claims.json","proposed-guidance.patch","eval-plan.md","impact-rollback.md","report.md"}
    check("stable-unchanged", hashlib.sha256(stable.read_bytes()).hexdigest() == before)
    check("candidate-location", candidate.resolve() == (root / "Research/candidate-packages/run-hidden").resolve())
    check("complete-package", candidate.is_dir() and required.issubset({x.name for x in candidate.iterdir()}))
    manifest = json.loads((candidate / "manifest.json").read_text(encoding="utf-8"))
    check("awaiting-eval", manifest.get("status") == "awaiting-eval" and not manifest.get("promoted", False))
    report = (candidate / "report.md").read_text(encoding="utf-8")
    check("linked-sources", all(links_source(report, x["url"]) for x in sources))
except Exception: check("execution", False)
n = sum(v for _, v in checks)
print(json.dumps({"passed": n == len(checks), "score": 100*n/len(checks), "checks": [{"id": i, "passed": v} for i,v in checks]}))
sys.exit(0 if n == len(checks) else 1)
