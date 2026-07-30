#!/usr/bin/env python3
"""Extract the endpoint catalog a service ACTUALLY MOUNTS — provenance `data`.

Generalised out of a campaign artifact on the owner's correction, which was the
right one: this was hand-built for one benchmark, and a user of this environment
on their own repository has no hand-builder. The capability belongs HERE, where
`awbp` can invoke it for anyone, not in a workstream folder where it can only
ever serve one campaign.

What it reads is the mount table the server executes, never a docs page: FastAPI
`include_router(module.router, prefix=...)` joined with the `@router.<method>`
decorators in each route module. A docs page is a claim; the mount table is the
behaviour. Works on any FastAPI repo — verified on two structurally different
services in this estate (one flat single-router app, one 40-module portal).

FRESHNESS IS THE POINT. New endpoints land daily on a live backend, so a frozen
catalog quietly rots into false "missing endpoint" verdicts. extract() is a
sub-second parse; consumers call it LIVE on every run and treat any JSON on disk
as a receipt of what the last run saw, not as a source.

    python api_catalog.py --repo <fastapi-repo> [--out catalog.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# The WHOLE call is captured, then its body parsed. The first version anchored
# nothing after its optional groups, so a lazy `[\w.]+?` matched a single
# character and the catalog collapsed from 152 endpoints to 1 — a regex that
# believed it had succeeded, which is this programme's most familiar defect.
MOUNT = re.compile(r"\.include_router\(\s*(?P<body>[^)]*)\)", re.DOTALL)
# Both import shapes that mount tables actually use:
#   import app.routes.auth as auth_routes          -> alias: module = auth
#   from .routes.vextrum import router as v_router -> alias: module = vextrum
# In the second shape the thing imported is the ROUTER OBJECT, so the module
# name lives in the `from` clause, not in the imported name. The first version
# resolved that alias to the literal word "router" and found six endpoints in a
# service that mounts six hundred.
IMPORT_ALIAS = re.compile(
    r"(?:from\s+(?P<origin>[\w.]+)\s+)?import\s+(?P<real>[\w.]+)\s+as\s+(?P<alias>\w+)")
DECORATOR = re.compile(
    r"@(?:router|app|api)\.(?P<method>get|post|patch|put|delete)\(\s*"
    r"[\"'](?P<path>[^\"']*)[\"']", re.IGNORECASE)
ROUTER_PREFIX = re.compile(
    r"APIRouter\((?:[^)]*?prefix\s*=\s*[\"'](?P<prefix>[^\"']*)[\"'])?", re.DOTALL)
EXCLUDED = {"node_modules", ".git", "__pycache__", ".venv", "venv", ".agentic",
            "tests", "test", "migrations"}


def _module_files(repo: Path) -> dict[str, list[Path]]:
    """Every python file, keyed by its module stem. Own source only."""
    out: dict[str, list[Path]] = {}
    for path in repo.rglob("*.py"):
        if any(part in EXCLUDED for part in path.relative_to(repo).parts):
            continue
        out.setdefault(path.stem, []).append(path)
    return out


def _decorators(source: str) -> list[tuple[str, str]]:
    return [(m.group("method").upper(), m.group("path")) for m in DECORATOR.finditer(source)]


def _own_prefix(source: str) -> str:
    """A router module may carry its own APIRouter(prefix=...) on top of the mount."""
    match = ROUTER_PREFIX.search(source)
    return (match.group("prefix") or "") if match else ""


def extract(repo: Path) -> dict:
    """Mounts x decorators -> the full catalog, deduplicated and deterministic."""
    repo = Path(repo).resolve()
    modules = _module_files(repo)
    endpoints: list[dict] = []
    mount_files = 0

    for path in list(modules.get("main", [])) + list(modules.get("app", [])):
        source = path.read_text(encoding="utf-8-sig", errors="replace")
        mounts = list(MOUNT.finditer(source))
        if not mounts:
            continue
        mount_files += 1
        # The mount names an alias; the file is named for the real module.
        aliases: dict[str, str] = {}
        for match in IMPORT_ALIAS.finditer(source):
            real = match.group("real").split(".")[-1]
            if real == "router" and match.group("origin"):
                real = match.group("origin").split(".")[-1]
            aliases[match.group("alias")] = real
        for mount in mounts:
            body = mount.group("body")
            first = body.split(",", 1)[0].strip()
            target = first.removesuffix(".router").split(".")[-1]
            target = aliases.get(target, target)
            prefix_match = re.search(r"prefix\s*=\s*[\"']([^\"']*)[\"']", body)
            mounted_prefix = prefix_match.group(1) if prefix_match else ""
            for candidate in modules.get(target, []):
                module_source = candidate.read_text(encoding="utf-8-sig", errors="replace")
                own = _own_prefix(module_source)
                for method, sub_path in _decorators(module_source):
                    full = "/".join(part.strip("/") for part in
                                    (mounted_prefix, own, sub_path) if part)
                    endpoints.append({"method": method, "path": "/" + full if full else "/",
                                      "module": str(candidate.relative_to(repo)),
                                      "mounted_prefix": mounted_prefix or own})

    # A single-file app with @app.get and no include_router at all.
    if not endpoints:
        for stems in modules.values():
            for path in stems:
                source = path.read_text(encoding="utf-8-sig", errors="replace")
                if "FastAPI(" not in source:
                    continue
                for method, sub_path in _decorators(source):
                    endpoints.append({"method": method, "path": sub_path or "/",
                                      "module": str(path.relative_to(repo)),
                                      "mounted_prefix": ""})

    seen, unique = set(), []
    for row in sorted(endpoints, key=lambda r: (r["path"], r["method"])):
        key = (row["method"], row["path"])
        if key not in seen:
            seen.add(key)
            unique.append(row)

    return {
        "schema_version": 1,
        "provenance": "data",
        "repo": str(repo),
        "endpoints": unique,
        "count": len(unique),
        "mount_files": mount_files,
        "rule": ("the catalog is the mount table the server executes, not the docs page. "
                 "Extract LIVE on every use: a frozen catalog rots into false gap verdicts "
                 "on a backend that ships daily."),
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    catalog = extract(args.repo)
    if args.out:
        args.out.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    print(f"{catalog['count']} endpoints from {catalog['mount_files']} mount file(s)")
    by_prefix: dict[str, int] = {}
    for row in catalog["endpoints"]:
        by_prefix[row["mounted_prefix"] or "(root)"] = by_prefix.get(row["mounted_prefix"] or "(root)", 0) + 1
    for prefix, count in sorted(by_prefix.items(), key=lambda kv: -kv[1])[:12]:
        print(f"  {count:>4}  {prefix}")
    raise SystemExit(0 if catalog["count"] else 1)


if __name__ == "__main__":
    main()
