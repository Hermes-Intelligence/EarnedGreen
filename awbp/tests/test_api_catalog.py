#!/usr/bin/env python3
"""The mounted-endpoint catalog, extracted from any FastAPI repo.

Generalised out of a campaign artifact on the owner's correction. Two regressions
are pinned here because both shipped, minutes apart, in the first generic draft:

  - a lazy `[\\w.]+?` with nothing anchoring its end matched a single character,
    and a 152-endpoint service catalogued as 1 — a regex that believed it had
    succeeded;
  - `from app.routes.vextrum import router as vextrum_router` resolved the alias
    to the literal word "router", and a service mounting six hundred endpoints
    catalogued as 6.

Every layout below is one of the real mount shapes in this estate.

    python tests/test_api_catalog.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api_catalog          # noqa: E402

PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(f"{name}{' — ' + detail if detail else ''}")


def build(root: Path, files: dict[str, str]) -> Path:
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def paths_of(catalog: dict) -> set[tuple[str, str]]:
    return {(row["method"], row["path"]) for row in catalog["endpoints"]}


def test_module_alias_shape(tmp: Path) -> None:
    """`import app.routes.auth as auth_routes` — the VextrumBackend shape."""
    repo = build(tmp / "alias", {
        "app/main.py": (
            "import app.routes.auth as auth_routes\n"
            "from fastapi import FastAPI\napp = FastAPI()\n"
            'app.include_router(auth_routes.router, prefix="/v0/auth", tags=["Auth"])\n'),
        "app/routes/auth.py": (
            "from fastapi import APIRouter\nrouter = APIRouter()\n"
            '@router.post("/login")\ndef login(): ...\n'
            '@router.get("/me")\ndef me(): ...\n'),
    })
    catalog = api_catalog.extract(repo)
    check("module-alias mounts resolve", catalog["count"] == 2, str(catalog["count"]))
    check("prefix is applied", ("POST", "/v0/auth/login") in paths_of(catalog),
          str(sorted(paths_of(catalog))))


def test_router_object_alias_shape(tmp: Path) -> None:
    """`from .routes.vextrum import router as vextrum_router` — the portal shape.

    The imported NAME is `router`; the module lives in the `from` clause. The
    first draft resolved this to the word "router" and found six endpoints in a
    service that mounts six hundred.
    """
    repo = build(tmp / "object", {
        "app/main.py": (
            "from app.routes.vextrum import router as vextrum_router\n"
            "from fastapi import FastAPI\napp = FastAPI()\n"
            "app.include_router(vextrum_router)\n"),
        "app/routes/vextrum.py": (
            "from fastapi import APIRouter\n"
            'router = APIRouter(\n    prefix="/vextrum",\n    tags=["vextrum"],\n)\n'
            '@router.get("/ideas")\ndef ideas(): ...\n'
            '@router.delete("/ideas/{idea_id}")\ndef drop(idea_id): ...\n'),
    })
    catalog = api_catalog.extract(repo)
    check("router-object aliases resolve through the from-clause",
          catalog["count"] == 2, str(catalog["count"]))
    check("the router's OWN prefix is applied",
          ("GET", "/vextrum/ideas") in paths_of(catalog), str(sorted(paths_of(catalog))))


def test_mount_call_is_parsed_whole(tmp: Path) -> None:
    """The lazy-regex regression: extra kwargs must not truncate the target."""
    repo = build(tmp / "kwargs", {
        "main.py": (
            "import routes.items as items_routes\n"
            "from fastapi import FastAPI\napp = FastAPI()\n"
            "app.include_router(\n    items_routes.router,\n"
            '    prefix="/api/items",\n    tags=["items"],\n'
            "    dependencies=[],\n)\n"),
        "routes/items.py": (
            "from fastapi import APIRouter\nrouter = APIRouter()\n"
            '@router.get("")\ndef all_items(): ...\n'),
    })
    catalog = api_catalog.extract(repo)
    check("a multi-line mount with kwargs still resolves",
          catalog["count"] == 1 and ("GET", "/api/items") in paths_of(catalog),
          str(sorted(paths_of(catalog))))


def test_single_file_app(tmp: Path) -> None:
    repo = build(tmp / "single", {
        "server.py": (
            "from fastapi import FastAPI\napp = FastAPI()\n"
            '@app.get("/health")\ndef health(): ...\n'
            '@app.post("/items")\ndef create(): ...\n'),
    })
    catalog = api_catalog.extract(repo)
    check("a single-file app with no include_router is catalogued",
          paths_of(catalog) == {("GET", "/health"), ("POST", "/items")},
          str(sorted(paths_of(catalog))))


def test_real_backend_exact_count() -> None:
    """The number the bespoke extractor measured, now required of the generic one."""
    backend = Path(__file__).resolve().parents[3] / "VextrumBackend"
    if not backend.is_dir():
        check("VextrumBackend present for the live check", True, "skipped: repo absent")
        return
    catalog = api_catalog.extract(backend)
    check("VextrumBackend catalogues at exactly 152", catalog["count"] == 152,
          str(catalog["count"]))
    check("workspace-scoped endpoints dominate",
          sum(1 for r in catalog["endpoints"]
              if r["mounted_prefix"] == "/v0/workspaces") == 75)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        test_module_alias_shape(tmp)
        test_router_object_alias_shape(tmp)
        test_mount_call_is_parsed_whole(tmp)
        test_single_file_app(tmp)
    test_real_backend_exact_count()

    for line in PASS:
        print(f"  ok    {line}")
    for line in FAIL:
        print(f"  FAIL  {line}")
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
