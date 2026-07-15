from pathlib import Path

def build_candidate(root, run_id, sources, claims):
    stable = Path(root) / "Runtime/stable/rules.md"
    stable.parent.mkdir(parents=True, exist_ok=True)
    stable.write_text("PROMOTED BY RESEARCH\n", encoding="utf-8")
    return stable
