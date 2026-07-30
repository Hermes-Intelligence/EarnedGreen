#!/usr/bin/env python3
"""Resolve a stable capability profile through the expiring provider catalog."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def repo_root() -> Path:
    for parent in (HERE, *HERE.parents):
        if (parent / "Runtime/stable/manifest.json").exists():
            return parent
    raise RuntimeError("AgenticWorkBestPractices root not found")


REPO = repo_root()
RISK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def resolve(provider: str, profile: str, risk: str, explicit_selector: str | None = None, now: datetime | None = None) -> dict:
    profiles = json.loads((REPO / "Models/profiles.json").read_text(encoding="utf-8-sig"))
    catalog = json.loads((REPO / "Models/providers.json").read_text(encoding="utf-8-sig"))
    profile_def = next((row for row in profiles["profiles"] if row["id"] == profile), None)
    provider_def = next((row for row in catalog["providers"] if row["id"] == provider), None)
    if not profile_def or not provider_def:
        raise ValueError("unknown provider or capability profile")
    if RISK[risk] > RISK[profile_def["max_risk"]]:
        raise ValueError("capability profile is below the task risk floor")
    eligible = [row for row in provider_def["selectors"] if profile in row["profiles"]]
    if explicit_selector:
        selected = next((row for row in provider_def["selectors"] if row["id"] == explicit_selector), None)
        if not selected or profile not in selected["profiles"]:
            raise ValueError("explicit selector does not satisfy the capability profile")
        source = "explicit-user-selector"
    else:
        selected = eligible[0] if eligible else None
        source = "current-catalog"
    if not selected:
        raise ValueError("no current selector satisfies the capability profile")
    now = now or datetime.now(timezone.utc)
    expires = datetime.fromisoformat(catalog["expires_at"])
    expired = now >= expires
    return {
        "schema_version": 2,
        "provider": provider,
        "capability_profile": profile,
        "risk": risk,
        "selector": selected["id"],
        "selector_kind": selected["kind"],
        "effort": profile_def["effort"],
        "human_gate": bool(profile_def.get("human_gate")),
        "catalog_generated_at": catalog["generated_at"],
        "catalog_expires_at": catalog["expires_at"],
        "catalog_expired": expired,
        "automation_allowed": not expired,
        "selection_source": source,
        "actual_model_must_be_logged_after_execution": True,
        "next_action": "create a model-catalog research candidate; do not mutate Stable" if expired else "execute only within the approved task/campaign scope",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--risk", choices=list(RISK), required=True)
    parser.add_argument("--explicit-selector")
    args = parser.parse_args()
    print(json.dumps(resolve(args.provider, args.profile, args.risk, args.explicit_selector), indent=2))


if __name__ == "__main__":
    main()
