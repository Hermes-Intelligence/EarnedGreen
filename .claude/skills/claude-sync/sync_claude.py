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

unpack is env-robust:
  * console-encoding safe (no UnicodeEncodeError on legacy Windows code pages),
  * auto-remaps recorded paths to THIS machine (username / OneDrive known-folder redirection /
    different repo root), rewriting the project-folder slug AND every in-file path form,
  * merges MEMORY.md instead of clobbering machine-local notes,
  * registers restored conversations with the Claude desktop app so they actually show up.

Usage:
  python sync_claude.py pack   --out sync.zip [--no-sessions] [--days N] [--workstreams DIR ...]
  python sync_claude.py unpack --zip sync.zip [--dry-run] [--yes] [--workstreams-dest DIR]
                               [--remap "OLD=NEW" ...] [--no-remap] [--no-register-desktop]
  python sync_claude.py register [--project DIR] [--dry-run]   # (re)link projects into the desktop app
"""
import argparse, fnmatch, getpass, json, os, platform, re, shutil, sys, uuid, zipfile
from datetime import datetime, timezone
from pathlib import Path

# --- console encoding: never crash on a legacy code page (cp1250/cp437/etc.) -------------------
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

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
REWRITE_EXT = {".jsonl", ".md", ".json", ".txt"}   # files whose CONTENT may hold remappable paths

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
    log(f"output -> {out}")
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
            "(redirect with --workstreams-dest if this machine uses different folders). Paths are auto-remapped\n"
            "to this machine and restored conversations are registered with the Claude desktop app.\n")
    size_mb = out.stat().st_size / 1e6
    log(f"packed -> {out} ({size_mb:.1f} MB)")
    log(f"  config: {counts['config']} | projects: {counts['projects']} | sessions: {counts['sessions']} | memory: {counts['memory_files']} | workstream files: {counts['workstreams_files']} (skipped {counts.get('workstreams_skipped_heavy', 0)} heavy — use --full-workstreams to include)")
    log(f"  workstreams: {', '.join(w['abs'] for w in manifest['workstreams']) or '(none found)'}")
    return 0

# =============================================================================================
# PATH REMAP — make a bundle from any machine land on THIS one.
# A Windows path shows up inside the bundle in five encoded forms; a remap must fix all of them.
# =============================================================================================
def slugify(p):
    """Reproduce Claude Code's project-folder slug: every non-alphanumeric char becomes '-'."""
    return "".join(c if c.isalnum() else "-" for c in p)

def _canon(p):
    """Normalize a user-supplied path to a single-backslash Windows-style form for variant generation."""
    return p.strip().replace("/", "\\").rstrip("\\")

def path_forms(src, dst):
    """Every (search, replace) pair needed to swap src->dst across all on-disk encodings:
    a Windows path appears raw (1 backslash), JSON-encoded (2), or nested-JSON-encoded (4, 8, ...),
    plus forward-slash and the project-folder dash-slug. Most-escaped first so nothing partial-matches."""
    s, d = _canon(src), _canon(dst)
    pairs = []
    for n in (8, 4, 2, 1):                                            # backslash depth (nested JSON)
        pairs.append((s.replace("\\", "\\" * n), d.replace("\\", "\\" * n)))
    pairs.append((s.replace("\\", "/"), d.replace("\\", "/")))       # forward slash
    pairs.append((slugify(s), slugify(d)))                            # project-folder dash-slug
    # de-dup while preserving order; drop no-op pairs
    seen, out = set(), []
    for a, b in pairs:
        if a and a != b and a not in seen:
            seen.add(a); out.append((a, b))
    return out

def rewrite_text(text, remaps):
    for src, dst in remaps:
        for a, b in path_forms(src, dst):
            text = text.replace(a, b)
    return text

def apply_slug_remap(path_str, remaps):
    for src, dst in remaps:
        path_str = path_str.replace(slugify(_canon(src)), slugify(_canon(dst)))
    return path_str

def _first_cwd_from_lines(line_iter):
    n = 0
    for line in line_iter:
        n += 1
        if n > 60: break
        line = line.strip()
        if not line: continue
        try: o = json.loads(line)
        except Exception: continue
        if isinstance(o, dict) and o.get("cwd"):
            return o["cwd"]
    return None

def sample_source_roots(zf, project_arcs):
    """Distinct top-level cwd roots recorded in the bundle (read only each jsonl's head — fast)."""
    cwds = set()
    per_proj_seen = {}
    for arc in project_arcs:
        if not arc.endswith(".jsonl"): continue
        proj = arc.split("/")[3] if len(arc.split("/")) > 3 else arc
        if per_proj_seen.get(proj, 0) >= 3: continue      # a few files per project is plenty
        per_proj_seen[proj] = per_proj_seen.get(proj, 0) + 1
        try:
            with zf.open(arc) as fh:
                data = fh.read(65536).decode("utf-8", "replace")
        except Exception: continue
        c = _first_cwd_from_lines(data.splitlines())
        if c: cwds.add(c)
    # reduce to minimal roots: drop any path that has a shorter sibling as prefix
    roots, ordered = [], sorted(cwds, key=len)
    for c in ordered:
        cl = _canon(c).lower()
        if any(cl.startswith(_canon(r).lower() + "\\") or cl == _canon(r).lower() for r in roots):
            continue
        roots.append(c)
    return roots

def resolve_target(root, src_home):
    """Given a source cwd root that does NOT exist here, find its equivalent on this machine.
    Covers different usernames, OneDrive known-folder redirection, and Desktop<->home moves."""
    root_c = _canon(root)
    home = str(HOME)
    cands = []
    if src_home and root_c.lower().startswith(_canon(src_home).lower()):
        rel = root_c[len(_canon(src_home)):].lstrip("\\")
        parts = rel.split("\\") if rel else []
        cands.append(str(Path(home) / rel))                                   # same rel under this home
        cands.append(str(Path(home) / "Desktop" / rel))                       # ... under Desktop
        if parts and parts[0].lower().startswith("onedrive") and len(parts) > 2:
            deredir = "\\".join(parts[2:])                                    # strip OneDrive\<seg>\
            cands.append(str(Path(home) / deredir))
            cands.append(str(Path(home) / "Desktop" / deredir))
        for od in sorted(Path(home).glob("OneDrive*")):
            cands.append(str(od / rel))
            if parts: cands.append(str(od / "Pulpit" / parts[-1]))            # localized "Desktop" (pl)
    # last resort: match by basename under the usual roots
    base = root_c.split("\\")[-1]
    usual = [Path(home) / "Desktop", Path(home), Path(home) / "Documents",
             *sorted(Path(home).glob("OneDrive*")),
             *[od / "Pulpit" for od in sorted(Path(home).glob("OneDrive*"))],
             *[od / "Desktop" for od in sorted(Path(home).glob("OneDrive*"))]]
    for r in usual:
        cands.append(str(r / base))
    for c in cands:
        if c and Path(c).is_dir():
            return str(Path(c))
    return None

def registered_project_cwds():
    """cwds the Claude desktop app already uses for its projects — the authoritative target for a remap.
    Returns (set_of_normcase_cwds, {basename_lower: cwd} for basenames that map to exactly one cwd)."""
    base = desktop_registry_base()
    cwds = set()
    if base:
        for acct in base.iterdir():
            if not acct.is_dir(): continue
            for proj in acct.iterdir():
                if not proj.is_dir(): continue
                for lf in proj.glob("local_*.json"):
                    try: c = json.loads(lf.read_text(encoding="utf-8")).get("cwd")
                    except Exception: c = None
                    if c: cwds.add(c)
    norm = {os.path.normcase(os.path.normpath(c)) for c in cwds}
    by_base = {}
    for c in cwds:
        b = _canon(c).split("\\")[-1].lower()
        by_base.setdefault(b, set()).add(os.path.normpath(c))
    uniq_base = {b: next(iter(s)) for b, s in by_base.items() if len(s) == 1}
    return norm, uniq_base

def build_remaps(zf, project_arcs, explicit, manifest, auto):
    remaps = []
    for r in (explicit or []):
        s, _, d = r.partition("=")
        if s and d: remaps.append((s.strip(), d.strip()))
    if auto:
        src_home = (manifest.get("source") or {}).get("home")
        reg_cwds, reg_by_base = registered_project_cwds()
        for root in sample_source_roots(zf, project_arcs):
            rc = _canon(root)
            rc_norm = os.path.normcase(os.path.normpath(root))
            if any(rc.lower().startswith(_canon(s).lower()) for s, _ in remaps): continue
            if rc_norm in reg_cwds:                                            # already the app's project path
                continue
            base = rc.split("\\")[-1].lower()
            tgt = reg_by_base.get(base)                                        # PREFER the desktop app's cwd
            if tgt and os.path.normcase(tgt) != rc_norm:
                remaps.append((root, tgt)); continue
            if Path(root).exists():                                           # CLI machine, path valid as-is
                continue
            tgt = resolve_target(root, src_home)
            if tgt and _canon(tgt).lower() != rc.lower():
                remaps.append((root, tgt))
    return remaps

def merge_memory_index(incoming, current):
    """Keep the incoming MEMORY.md index; append machine-local pointer lines it doesn't already have."""
    extra = []
    for line in current.splitlines():
        ls = line.strip()
        if ls.startswith("- [") and "](" in ls:
            ref = ls.split("](", 1)[1].split(")", 1)[0]
            if ref not in incoming:
                extra.append(line)
    merged = incoming.rstrip("\n")
    return merged + ("\n" + "\n".join(extra) + "\n" if extra else "\n")

# =============================================================================================
# DESKTOP APP REGISTRY — the Claude desktop app lists conversations from its OWN registry,
# not from a live scan of ~/.claude/projects. Restored *.jsonl are invisible until registered.
# =============================================================================================
def desktop_registry_base():
    s = platform.system()
    if s == "Windows":
        ad = os.environ.get("APPDATA")
        cand = Path(ad) / "Claude" / "claude-code-sessions" if ad else None
    elif s == "Darwin":
        cand = HOME / "Library" / "Application Support" / "Claude" / "claude-code-sessions"
    else:
        cand = HOME / ".config" / "Claude" / "claude-code-sessions"
    return cand if cand and cand.is_dir() else None

def _iso_ms(s):
    try: return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)
    except Exception: return None

def _analyze_jsonl(path):
    title, first_ms, last_ms, model = None, None, None, "claude-opus-4-8"
    try: fh = open(path, encoding="utf-8")
    except OSError: return "Restored session", None, None, model
    with fh:
        for line in fh:
            line = line.strip()
            if not line: continue
            try: o = json.loads(line)
            except Exception: continue
            ts = o.get("timestamp")
            if ts:
                ms = _iso_ms(ts)
                if ms:
                    if first_ms is None: first_ms = ms
                    last_ms = ms
            if title is None and o.get("type") == "user" and not o.get("isSidechain"):
                c = (o.get("message") or {}).get("content")
                txt = c if isinstance(c, str) else ""
                if isinstance(c, list):
                    for b in c:
                        if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                            txt = b["text"]; break
                txt = " ".join((txt or "").split())
                if txt and txt[0] not in "<" and not txt.startswith("/") and not txt.startswith("Caveat"):
                    title = txt[:60]
            if o.get("type") == "assistant":
                m = (o.get("message") or {}).get("model")
                if m: model = m
    return (title or "Restored session"), first_ms, last_ms, model

def _desktop_project_dirs_by_cwd(base):
    """Map normalized cwd -> (project_dir, set of already-registered cliSessionIds)."""
    idx = {}
    for acct in base.iterdir():
        if not acct.is_dir(): continue
        for proj in acct.iterdir():
            if not proj.is_dir(): continue
            cwd, ids = None, set()
            for lf in proj.glob("local_*.json"):
                try: o = json.loads(lf.read_text(encoding="utf-8"))
                except Exception: continue
                if o.get("cliSessionId"): ids.add(o["cliSessionId"])
                if cwd is None and o.get("cwd"): cwd = o["cwd"]
            if cwd:
                idx[os.path.normcase(os.path.normpath(cwd))] = (proj, ids)
    return idx

def _fmt_register(created, unmatched, dry):
    if created < 0:   # sentinel: no desktop app
        return "desktop app not detected (CLI-only machine) — nothing to register"
    verb = "would register" if dry else "registered"
    msg = f"{verb} {created} conversation(s)"
    if unmatched:
        show = ", ".join(sorted(unmatched))
        msg += (f"; {len(unmatched)} project path(s) not yet known to the app "
                f"[{show}] — open each once in the desktop app, then run: python sync_claude.py register")
    return msg

def register_desktop(specs, dry=False):
    """specs: list of {cli, cwd, jsonl(Path or None)}. Creates missing local_*.json registry entries
    in the matching desktop project dir so the app lists the conversations. Best-effort & idempotent.
    Returns (created_count, unmatched_cwd_set); created_count is -1 when no desktop app is present."""
    base = desktop_registry_base()
    if not base:
        return -1, set()
    idx = _desktop_project_dirs_by_cwd(base)
    created, unmatched = 0, set()
    for sp in specs:
        key = os.path.normcase(os.path.normpath(sp["cwd"])) if sp.get("cwd") else None
        hit = idx.get(key)
        if not hit:
            if sp.get("cwd"): unmatched.add(sp["cwd"])
            continue
        proj_dir, ids = hit
        if sp["cli"] in ids: continue
        if dry:
            created += 1; continue
        title, first_ms, last_ms, model = _analyze_jsonl(sp["jsonl"]) if sp.get("jsonl") else ("Restored session", None, None, "claude-opus-4-8")
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        first_ms = first_ms or now_ms; last_ms = last_ms or first_ms
        local_id = "local_" + str(uuid.uuid4())
        entry = {
            "sessionId": local_id, "cliSessionId": sp["cli"],
            "cwd": sp["cwd"], "originCwd": sp["cwd"],
            "lastFocusedAt": last_ms, "createdAt": first_ms, "lastActivityAt": last_ms,
            "model": model, "effort": "high", "isArchived": False,
            "title": title, "titleSource": "auto", "permissionMode": "auto",
            "remoteMcpServersConfig": [], "chromePermissionMode": "skip_all_permission_checks",
            "completedTurns": 0, "alwaysAllowedReasons": [], "sessionPermissionUpdates": [],
            "classifierSummaryEnabled": True, "reportFindingsCard": True, "spawnSeed": {},
        }
        (proj_dir / (local_id + ".json")).write_text(json.dumps(entry, ensure_ascii=False, indent=1), encoding="utf-8")
        ids.add(sp["cli"]); created += 1
    return created, unmatched

def specs_from_disk(project_filter=None):
    """Build desktop-registration specs from what's already in ~/.claude/projects (post-restore)."""
    specs = []
    pj = CLAUDE / "projects"
    if not pj.is_dir(): return specs
    filt = os.path.normcase(os.path.normpath(project_filter)) if project_filter else None
    for proj in pj.iterdir():
        if not proj.is_dir(): continue
        for f in proj.glob("*.jsonl"):
            cwd = _first_cwd_from_lines_file(f)
            if not cwd: continue
            if filt and os.path.normcase(os.path.normpath(cwd)) != filt: continue
            specs.append({"cli": f.stem, "cwd": cwd, "jsonl": f})
    return specs

def _first_cwd_from_lines_file(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return _first_cwd_from_lines(fh)
    except OSError:
        return None

def _is_top_level_session_arc(arc):
    """A real conversation is projects/<slug>/<id>.jsonl — NOT a per-session sidecar under <slug>/<uuid>/."""
    return arc.startswith("home/.claude/projects/") and arc.endswith(".jsonl") and arc.count("/") == 4

def _project_root_of(path: Path):
    parts = path.parts
    if ".claude" not in parts or "projects" not in parts: return None
    i = parts.index("projects")
    return Path(*parts[:i + 2]) if i + 1 < len(parts) else None

# =============================================================================================
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

        project_arcs = [n for n in names if n.startswith("home/.claude/projects/")]
        remaps = build_remaps(zf, project_arcs, args.remap, manifest, auto=args.auto_remap)
        if remaps:
            log("path remaps (applied to slugs + file contents):")
            for s, d in remaps: log(f"    {s}  ->  {d}")
        else:
            log("path remaps: none (recorded paths already valid here)")

        # plan (targets already carry any slug remap)
        plan = []
        for arc in names:
            if arc.split("/")[-1] in NEVER: continue
            tgt = _target_for(arc, manifest, args.workstreams_dest)
            if tgt is None: continue
            if remaps: tgt = Path(apply_slug_remap(str(tgt), remaps))
            plan.append((arc, tgt))

        by_root = {}
        for _, t in plan:
            root = "workstreams" if "workstreams" in str(t) or "claude-sync-restore" in str(t) else ("~/.claude/projects" if ".claude" in str(t) and "projects" in str(t) else "~/.claude")
            by_root[root] = by_root.get(root, 0) + 1
        log("would restore:", ", ".join(f"{k}: {v}" for k, v in by_root.items()) or "(nothing)")

        if args.dry_run:
            for arc, t in plan[:12]: log("  ", arc, "->", t)
            if len(plan) > 12: log(f"   ... +{len(plan)-12} more (run without --dry-run to apply)")
            if args.register_desktop:
                specs = []
                for arc in project_arcs:
                    if not _is_top_level_session_arc(arc): continue
                    try:
                        with zf.open(arc) as fh:
                            cwd = _first_cwd_from_lines((fh.read(65536).decode("utf-8", "replace")).splitlines())
                    except Exception: cwd = None
                    if cwd and remaps: cwd = rewrite_text(cwd, remaps)
                    specs.append({"cli": Path(arc).stem, "cwd": cwd, "jsonl": None})
                created, unmatched = register_desktop(specs, dry=True)
                log(f"desktop app: {_fmt_register(created, unmatched, dry=True)}")
            return 0

        if not args.yes:
            log("refusing to overwrite without --yes (or use --dry-run to preview)"); return 3

        # safety backup of the CURRENT machine first (reuse pack)
        bdir = CLAUDE / "backups"; bdir.mkdir(parents=True, exist_ok=True)
        backup = bdir / f"pre-unpack-{NOW}.zip"
        log(f"backing up current state -> {backup}")
        cmd_pack(argparse.Namespace(out=str(backup), workstreams=[w["abs"] for w in manifest.get("workstreams", [])], sessions=True, days=None, full_workstreams=False, max_ws_mb=3.0))

        # apply (remap contents, merge MEMORY.md)
        applied, restored_projects = 0, set()
        for arc, tgt in plan:
            tgt.parent.mkdir(parents=True, exist_ok=True)
            do_rewrite = bool(remaps) and tgt.suffix.lower() in REWRITE_EXT
            is_mem_index = tgt.name == "MEMORY.md" and "memory" in tgt.parts and tgt.exists()
            if not do_rewrite and not is_mem_index:
                # large binaries / unmodified files: stream straight through (low memory)
                with zf.open(arc) as src, open(tgt, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            else:
                data = zf.read(arc)
                if do_rewrite:
                    try: data = rewrite_text(data.decode("utf-8"), remaps).encode("utf-8")
                    except UnicodeDecodeError: pass
                if is_mem_index:
                    try: data = merge_memory_index(data.decode("utf-8"), tgt.read_text(encoding="utf-8")).encode("utf-8")
                    except Exception: pass
                with open(tgt, "wb") as dst: dst.write(data)
            applied += 1
            pr = _project_root_of(tgt)
            if pr: restored_projects.add(pr)
        log(f"restored {applied} files. Backup of your previous state: {backup}")

        # register with the desktop app so conversations actually show up
        if args.register_desktop:
            specs = []
            for proj in restored_projects:
                for f in proj.glob("*.jsonl"):
                    cwd = _first_cwd_from_lines_file(f)
                    if cwd: specs.append({"cli": f.stem, "cwd": cwd, "jsonl": f})
            created, unmatched = register_desktop(specs)
            log(f"desktop app: {_fmt_register(created, unmatched, dry=False)}")

        log("Restart Claude Code (fully quit incl. tray) to pick up config, memory and the restored conversations.")
        return 0

def cmd_register(args):
    """Standalone: (re)link conversations already in ~/.claude/projects into the desktop app.
    Use after opening a project once in the app if it wasn't known at unpack time."""
    specs = specs_from_disk(args.project)
    if not specs:
        log("no conversations found in ~/.claude/projects" + (f" for {args.project}" if args.project else "")); return 0
    created, unmatched = register_desktop(specs, dry=args.dry_run)
    log(_fmt_register(created, unmatched, dry=args.dry_run))
    return 0

def main():
    ap = argparse.ArgumentParser(prog="sync_claude", description="Sync Claude Code conversations/memory/config/workstreams across machines")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack"); p.add_argument("--out", default=None, help="zip path (default: <OneDrive>/claude-sync/claude-<host>-<date>.zip)"); p.add_argument("--no-sessions", dest="sessions", action="store_false"); p.set_defaults(sessions=True)
    p.add_argument("--days", type=int, default=None, help="only sessions modified in the last N days"); p.add_argument("--workstreams", nargs="*", default=[])
    p.add_argument("--full-workstreams", dest="full_workstreams", action="store_true", help="include heavy workstream artifacts (docx/xlsx/pdf/zip/media), not just the .md logs")
    p.add_argument("--max-ws-mb", dest="max_ws_mb", type=float, default=3.0, help="per-file size cap for workstream artifacts (default 3 MB; ignored with --full-workstreams)")
    u = sub.add_parser("unpack"); u.add_argument("--zip", required=True); u.add_argument("--dry-run", action="store_true"); u.add_argument("--yes", action="store_true"); u.add_argument("--workstreams-dest", default=None)
    u.add_argument("--remap", action="append", default=[], help='force a path remap, e.g. --remap "C:\\old\\path=C:\\new\\path" (repeatable)')
    u.add_argument("--no-remap", dest="auto_remap", action="store_false", help="disable automatic path remapping to this machine")
    u.add_argument("--no-register-desktop", dest="register_desktop", action="store_false", help="do not create Claude desktop-app registry entries")
    u.set_defaults(auto_remap=True, register_desktop=True)
    r = sub.add_parser("register", help="(re)link conversations in ~/.claude/projects into the Claude desktop app")
    r.add_argument("--project", default=None, help="only this project cwd (absolute path)"); r.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    return {"pack": cmd_pack, "unpack": cmd_unpack, "register": cmd_register}[args.cmd](args)

if __name__ == "__main__":
    sys.exit(main())
