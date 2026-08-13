#!/usr/bin/env python3
"""claude-sync — pack / unpack Claude Code state across machines.

Bundles (ALLOWLIST — nothing else is ever touched, secrets are never bundled):
  ~/.claude/CLAUDE.md, ~/.claude/settings.json
  ~/.claude/skills, ~/.claude/agents, ~/.claude/commands   (if present)
  ~/.claude/projects/*/                                     (ALL conversations *.jsonl + memory/)
  one or more workstreams folders                          (auto-detected + --workstreams)

NEVER bundled: ~/.claude/.credentials.json (auth) or any runtime junk (shell-snapshots, statsig,
tasks, session-env, sessions, ide, logs, backups). unpack always writes a safety backup of the
current machine's state first, and --dry-run shows every action without touching disk.

Usage:
  python sync_claude.py pack   --out sync.zip [--no-sessions] [--days N] [--workstreams DIR ...]
  python sync_claude.py unpack --zip sync.zip [--dry-run] [--yes] [--workstreams-dest DIR]
"""
import argparse, fnmatch, getpass, json, os, platform, re, shutil, sys, zipfile
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
CLAUDE = HOME / ".claude"
NOW = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

# secrets / runtime state that must never be bundled (belt-and-suspenders on top of the allowlist)
NEVER = {".credentials.json"}
JUNK = ["*.lock", "*.tmp", "*.pyc", "__pycache__", ".git", "node_modules", ".DS_Store", "*.log"]
# heavy / binary artifacts skipped from WORKSTREAMS by default (the .md logs are the state; artifacts ride OneDrive).
# Conversations + memory + config are NEVER capped or ext-filtered — a whole conversation must survive.
MEDIA_EXT = {".docx", ".xlsx", ".pptx", ".pdf", ".zip", ".7z", ".rar", ".png", ".jpg", ".jpeg", ".gif",
             ".webp", ".mp4", ".mov", ".webm", ".ico", ".woff", ".woff2", ".ttf", ".otf", ".psd", ".ai", ".mp3", ".wav"}

def log(*a): print("[claude-sync]", *a)
def is_junk(rel): return any(fnmatch.fnmatch(p, g) for p in Path(rel).parts for g in JUNK) or Path(rel).name in NEVER

def detect_onedrive():
    """The user's synced cloud root, from the environment — works for any user/locale, not hardcoded paths."""
    for k in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        v = os.environ.get(k)
        if v and Path(v).is_dir():
            return Path(v)
    for c in [HOME / "OneDrive", *sorted(HOME.glob("OneDrive*")), HOME / "Dropbox", HOME / "iCloudDrive"]:
        if c.is_dir():
            return c
    return None

def default_out():
    base = detect_onedrive() or HOME
    return base / "claude-sync" / f"claude-{platform.node()}-{datetime.now().strftime('%Y%m%d')}.zip"

def detect_workstreams(extra):
    """Find every folder literally named 'workstreams' under the synced root + home (bounded, junk-skipped) —
    environment-derived, so it works on any machine without hardcoding a user's paths."""
    roots = [r for r in (detect_onedrive(), HOME) if r]
    SKIP = {"node_modules", ".git", "AppData", ".cache", ".claude", ".vscode", "dist", "build", "__pycache__", ".next", "venv", ".venv"}
    found = []
    for root in roots:
        base_depth = len(root.parts)
        for dp, dirs, _ in os.walk(root):
            if len(Path(dp).parts) - base_depth >= 4:  # bounded depth keeps it fast
                dirs[:] = []; continue
            dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith(".")]
            for d in list(dirs):
                if d.lower() == "workstreams":
                    found.append(Path(dp) / d)
    seen, out = set(), []
    for c in found + [Path(p) for p in (extra or [])]:
        rc = c.resolve()
        if c.is_dir() and rc not in seen:
            seen.add(rc); out.append(c)
    return out

def add_tree(zf, src: Path, arc_base: str, since_ts=None, only_ext=None, cap_bytes=None, skip_ext=None, stats=None):
    n = 0
    if not src.exists(): return 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if not is_junk(d)]
        for f in files:
            fp = Path(root) / f
            rel = fp.relative_to(src)
            if is_junk(str(rel)): continue
            if only_ext and fp.suffix.lower() not in only_ext and "memory" not in rel.parts: continue
            if since_ts and fp.stat().st_mtime < since_ts and fp.suffix.lower() == ".jsonl":
                continue
            if skip_ext and fp.suffix.lower() in skip_ext:
                if stats is not None: stats["skipped"] = stats.get("skipped", 0) + 1
                continue
            try: sz = fp.stat().st_size
            except OSError: continue
            if cap_bytes and sz > cap_bytes:
                if stats is not None: stats["skipped"] = stats.get("skipped", 0) + 1
                continue
            try: zf.write(fp, f"{arc_base}/{rel.as_posix()}")
            except OSError as e: log(f"skip {fp}: {e}"); continue
            n += 1
    return n

def cmd_pack(args):
    out = Path(args.out).resolve() if getattr(args, "out", None) else default_out().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    log(f"output → {out}")
    ws_dirs = detect_workstreams(args.workstreams)
    since_ts = None
    if args.days: since_ts = datetime.now().timestamp() - args.days * 86400
    only_ext = None if args.sessions else {".md", ".json"}   # --no-sessions => skip *.jsonl, keep memory/config
    manifest = {
        "tool": "claude-sync", "format": 1, "created_at": NOW,
        "source": {"host": platform.node(), "user": getpass.getuser(), "os": platform.system(), "home": str(HOME)},
        "workstreams": [], "counts": {}, "includes_sessions": bool(args.sessions),
    }
    counts = {"config": 0, "projects": 0, "sessions": 0, "memory_files": 0, "workstreams_files": 0}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. config files + dirs
        for name in ("CLAUDE.md", "settings.json"):
            fp = CLAUDE / name
            if fp.is_file(): zf.write(fp, f"home/.claude/{name}"); counts["config"] += 1
        for d in ("skills", "agents", "commands"):
            counts["config"] += add_tree(zf, CLAUDE / d, f"home/.claude/{d}")
        # 2. ALL projects (conversations *.jsonl + memory/)
        pj = CLAUDE / "projects"
        if pj.is_dir():
            for proj in sorted(p for p in pj.iterdir() if p.is_dir()):
                counts["projects"] += 1
                counts["sessions"] += sum(1 for _ in proj.glob("*.jsonl")) if args.sessions else 0
                counts["memory_files"] += sum(1 for _ in (proj / "memory").glob("*")) if (proj / "memory").is_dir() else 0
                add_tree(zf, proj, f"home/.claude/projects/{proj.name}", since_ts=since_ts, only_ext=only_ext)
        # 3. workstreams (recorded with their absolute target so unpack restores them home). By default heavy
        #    media/artifacts are skipped (the .md logs are the state; artifacts already ride OneDrive) — --full-workstreams
        #    includes everything.
        ws_stats = {"skipped": 0}
        ws_skip_ext = None if args.full_workstreams else MEDIA_EXT
        ws_cap = None if args.full_workstreams else int(args.max_ws_mb * 1e6)
        for w in ws_dirs:
            key = w.parent.name + "__" + w.name  # a stable, collision-resistant key
            manifest["workstreams"].append({"name": key, "abs": str(w)})
            counts["workstreams_files"] += add_tree(zf, w, f"ws/{key}", cap_bytes=ws_cap, skip_ext=ws_skip_ext, stats=ws_stats)
        counts["workstreams_skipped_heavy"] = ws_stats["skipped"]
        manifest["counts"] = counts
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        # 4. self-copy of this script + a human README, so the zip unpacks on a machine that never had the skill
        me = Path(__file__)
        if me.is_file(): zf.write(me, "sync_claude.py")
        zf.writestr("README.txt",
            "Claude-sync bundle. To restore on THIS machine:\n"
            "  python sync_claude.py unpack --zip <this-file>.zip --dry-run   # preview\n"
            "  python sync_claude.py unpack --zip <this-file>.zip --yes       # apply (backs up current state first)\n"
            "Never contains credentials. Config+memory go to ~/.claude; workstreams to their recorded paths\n"
            "(redirect with --workstreams-dest if this machine uses different folders).\n")
    size_mb = out.stat().st_size / 1e6
    log(f"packed → {out} ({size_mb:.1f} MB)")
    log(f"  config: {counts['config']} | projects: {counts['projects']} | sessions: {counts['sessions']} | memory: {counts['memory_files']} | workstream files: {counts['workstreams_files']} (skipped {counts.get('workstreams_skipped_heavy', 0)} heavy — use --full-workstreams to include)")
    log(f"  workstreams: {', '.join(w['abs'] for w in manifest['workstreams']) or '(none found)'}")
    return 0

def _target_for(arc, manifest, ws_dest):
    if arc.startswith("home/"):
        return HOME / arc[len("home/"):]
    if arc.startswith("ws/"):
        key = arc.split("/", 2)[1]; rest = arc.split("/", 2)[2] if arc.count("/") >= 2 else ""
        if ws_dest: base = Path(ws_dest) / key
        else:
            rec = next((w for w in manifest.get("workstreams", []) if w["name"] == key), None)
            base = Path(rec["abs"]) if rec else (HOME / "claude-sync-restore" / "workstreams" / key)
        return base / rest if rest else base
    return None

def cmd_unpack(args):
    zpath = Path(args.zip).resolve()
    if not zpath.is_file(): log(f"no such zip: {zpath}"); return 2
    with zipfile.ZipFile(zpath) as zf:
        try: manifest = json.loads(zf.read("manifest.json"))
        except KeyError: log("not a claude-sync bundle (no manifest.json)"); return 2
        names = [n for n in zf.namelist() if not n.endswith("/") and n not in ("manifest.json", "sync_claude.py", "README.txt")]
        log(f"bundle from {manifest['source']['host']} ({manifest['source']['user']}) @ {manifest['created_at']} — {len(names)} files")
        # plan
        plan = []
        for arc in names:
            if arc.split("/")[-1] in NEVER: continue          # never restore a credential even if present
            tgt = _target_for(arc, manifest, args.workstreams_dest)
            if tgt is None: continue
            plan.append((arc, tgt))
        # show plan
        by_root = {}
        for _, t in plan:
            root = "workstreams" if "workstreams" in str(t) or "claude-sync-restore" in str(t) else ("~/.claude/projects" if ".claude" in str(t) and "projects" in str(t) else "~/.claude")
            by_root[root] = by_root.get(root, 0) + 1
        log("would restore:", ", ".join(f"{k}: {v}" for k, v in by_root.items()) or "(nothing)")
        if args.dry_run:
            for arc, t in plan[:12]: log("  ", arc, "→", t)
            if len(plan) > 12: log(f"   … +{len(plan)-12} more (run without --dry-run to apply)")
            return 0
        if not args.yes:
            log("refusing to overwrite without --yes (or use --dry-run to preview)"); return 3
        # safety backup of the CURRENT machine first (reuse pack)
        bdir = CLAUDE / "backups"; bdir.mkdir(parents=True, exist_ok=True)
        backup = bdir / f"pre-unpack-{NOW}.zip"
        log(f"backing up current state → {backup}")
        cmd_pack(argparse.Namespace(out=str(backup), workstreams=[w["abs"] for w in manifest.get("workstreams", [])], sessions=True, days=None, full_workstreams=False, max_ws_mb=3.0))
        # apply
        applied = 0
        for arc, tgt in plan:
            tgt.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(arc) as src, open(tgt, "wb") as dst:
                shutil.copyfileobj(src, dst); applied += 1
        log(f"restored {applied} files. Backup of your previous state: {backup}")
        log("Open Claude in the synced repo at the SAME path so memory + sessions map; restart Claude Code to pick up config.")
        return 0

def main():
    ap = argparse.ArgumentParser(prog="sync_claude", description="Sync Claude Code conversations/memory/config/workstreams across machines")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack"); p.add_argument("--out", default=None, help="zip path (default: <OneDrive>/claude-sync/claude-<host>-<date>.zip)"); p.add_argument("--no-sessions", dest="sessions", action="store_false"); p.set_defaults(sessions=True)
    p.add_argument("--days", type=int, default=None, help="only sessions modified in the last N days"); p.add_argument("--workstreams", nargs="*", default=[])
    p.add_argument("--full-workstreams", dest="full_workstreams", action="store_true", help="include heavy workstream artifacts (docx/xlsx/pdf/zip/media), not just the .md logs")
    p.add_argument("--max-ws-mb", dest="max_ws_mb", type=float, default=3.0, help="per-file size cap for workstream artifacts (default 3 MB; ignored with --full-workstreams)")
    u = sub.add_parser("unpack"); u.add_argument("--zip", required=True); u.add_argument("--dry-run", action="store_true"); u.add_argument("--yes", action="store_true"); u.add_argument("--workstreams-dest", default=None)
    args = ap.parse_args()
    return cmd_pack(args) if args.cmd == "pack" else cmd_unpack(args)

if __name__ == "__main__":
    sys.exit(main())
