#!/usr/bin/env python
"""Record the human's exact per-stage approval; never executes providers.

Stage-aware: a canary campaign is approvable only for exactly one call; a main
campaign only for its declared total. The approval count must match the
campaign's own hard ceiling, so a canary can never be silently widened.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--exact-calls", type=int, required=True)
    args = parser.parse_args()
    data = json.loads(args.campaign.read_text(encoding="utf-8-sig"))
    stage = data.get("stage", "main")
    ceiling = data["loop"]["max_total_provider_calls"]
    if stage == "canary" and ceiling != 1:
        raise SystemExit("canary campaign must plan exactly one call")
    if args.exact_calls != ceiling:
        raise SystemExit(f"approval must cover exactly {ceiling} call(s) for stage {stage!r}, got {args.exact_calls}")
    if not data.get("fixture_admission", {}).get("admitted"):
        raise SystemExit("campaign was created without an admitted fixture; refuse to approve")
    if data["status"] != "awaiting-explicit-approval" or data.get("provider_calls", 0) != 0:
        raise SystemExit("campaign is not an untouched approval-pending campaign")
    data["status"] = "approved"
    data["approval"] = {
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "approved_by": args.approved_by,
        "scope": data["approval"]["scope"],
        "exact_calls": ceiling,
        "stage": stage,
    }
    args.campaign.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"campaign_id":data["campaign_id"],"status":"approved","stage":stage,"exact_calls":ceiling,"provider_calls":0},indent=2))


if __name__ == "__main__":
    main()
