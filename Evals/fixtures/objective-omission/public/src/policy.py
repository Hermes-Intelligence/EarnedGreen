"""Incomplete starter. Read every document before changing this implementation."""


def build_policy(request):
    if not isinstance(request, dict) or not request.get("name"):
        raise ValueError("name is required")
    return {
        "name": request["name"].strip(),
        "targets": list(request.get("targets", [])),
        "timeout_seconds": request.get("timeout_seconds", 30),
        "retries": request.get("retries", 2),
        "dry_run": request.get("dry_run", True),
        "metadata": dict(request.get("metadata", {})),
    }
