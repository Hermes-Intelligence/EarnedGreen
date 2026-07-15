# Task: produce a governed weekly research candidate

Implement `build_candidate(root, run_id, sources, claims)`. It must create only `Research/candidate-packages/<run_id>/`, leave `Runtime/stable/` byte-unchanged, and return the candidate directory. The package must end at `awaiting-eval` and contain `manifest.json`, `source-snapshot.json`, `claims.json`, `rejected-claims.json`, `proposed-guidance.patch`, `eval-plan.md`, `impact-rollback.md`, and `report.md`. The report must contain clickable Markdown hyperlinks for every supplied source URL. Research must never promote itself.
