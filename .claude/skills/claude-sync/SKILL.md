---
name: claude-sync
description: Pack all Claude Code conversations, memory, global config and workstreams into a single zip, and unpack that zip on another machine to keep them in sync. Use when the user wants to move, mirror, back up or restore their Claude sessions / memory / workstreams between devices (laptop ↔ desktop), or says "sync my conversations / Claude state", "pack it", "back it up", "restore from this zip", or gives a zip location to load. The user should NOT need to supply paths — derive everything from their environment.
---

# claude-sync — move Claude Code state between machines

Claude Code stores sessions, memory and config **locally per machine** (there is no built-in device sync for local CLI sessions). This skill bundles that state into one portable zip and restores it elsewhere. **The user just asks — you figure out the paths, output location and workstreams from their environment. Never make them type paths.**

The bundle is an **allowlist** — only these, and **credentials are never included**:
`~/.claude/CLAUDE.md`, `~/.claude/settings.json`, `~/.claude/{skills,agents,commands}`, every `~/.claude/projects/*/` (all conversations `*.jsonl` + `memory/`), and every folder named **`workstreams`** found under the user's synced cloud root + home.

The engine is `sync_claude.py`, sitting next to this file. It is fully environment-derived — `Path.home()`, the `OneDrive`/Dropbox/iCloud env root, and a bounded search for `workstreams/` — so it has **no hardcoded user paths**. Run it with whatever `python` is on PATH.

## When the user wants to PACK / back up / sync-out
Run it with **no arguments** — it auto-writes to `<synced-cloud>/claude-sync/claude-<host>-<date>.zip` (a OneDrive/Dropbox folder, so it reaches the other machine on its own) and auto-finds their workstreams:
```
python "<this-skill-dir>/sync_claude.py" pack
```
Then tell the user the exact zip path it printed, its size, and the counts. Optional knobs to offer only if relevant: `--no-sessions` (tiny — memory+config+logs), `--days 30` (recent chats only), `--full-workstreams` (include heavy artifacts too), `--out <path>` (override).

## When the user wants to UNPACK / restore / sync-in
They give (or point at) a zip. **Always dry-run first, show what changes, get a clear yes, then apply** — unpack backs up the current machine to `~/.claude/backups/pre-unpack-<ts>.zip` first (reversible):
```
python "<this-skill-dir>/sync_claude.py" unpack --zip "<the-zip>" --dry-run
python "<this-skill-dir>/sync_claude.py" unpack --zip "<the-zip>" --yes
```
Unpack is env-robust and needs no manual fix-ups — the dry-run prints exactly what each step will do:
- **Console-encoding safe.** Output never crashes on a legacy Windows code page (cp1250/cp437). No need to set `PYTHONIOENCODING`.
- **Auto path-remap.** It rewrites recorded paths to THIS machine — different username, OneDrive known-folder redirection (`…\OneDrive\<Desktop>\repos` ↔ `…\Desktop\repos`), or a different repo root. It fixes the project-folder slug AND every in-file path form (1/2/4-backslash, forward-slash, dash-slug), so conversations load and resume at the local path. The **target it prefers is whatever path the Claude desktop app already uses** for that project (read from the app's registry), so grouping matches. Override or add with `--remap "OLD=NEW"` (repeatable); disable with `--no-remap`.
- **Memory merge.** `MEMORY.md` is merged, not clobbered — machine-local pointer lines survive.
- **Desktop-app registration.** The desktop app lists conversations from its OWN registry (`%APPDATA%\Claude\claude-code-sessions\…`, macOS `~/Library/Application Support/Claude/…`, Linux `~/.config/Claude/…`), NOT from a live scan of `~/.claude/projects`. Unpack creates the missing `local_*.json` entries so restored chats actually appear (disable with `--no-register-desktop`). If a project wasn't yet known to the app, it says so — the user opens that project once, then runs `python "<this-skill-dir>/sync_claude.py" register`.

If the zip was received on a machine that never had the skill, it embeds its own copy — extract it and run the extracted `sync_claude.py unpack`. If that machine uses different folders, pass `--workstreams-dest <dir>`.

## Re-link into the desktop app on its own
If chats are on disk but not showing in the desktop app (e.g. the project wasn't open at unpack time), run:
```
python "<this-skill-dir>/sync_claude.py" register            # all projects
python "<this-skill-dir>/sync_claude.py" register --dry-run  # preview
```
It's idempotent — only creates entries for conversations the app doesn't already list.

## Two facts to tell the user
1. **Auto-remap handles different paths.** Conversations live in a folder named after the project's absolute path, and the desktop app groups by that path. Same path → maps directly; different path (different user / OneDrive-redirected Desktop / moved repos) → unpack remaps automatically. Only if it can't resolve a path will it ask for `--remap`.
2. **Fully restart Claude Code** after unpacking (quit incl. the system-tray process, not just the window) so it re-reads `CLAUDE.md`, `settings.json`, skills, the memory index, and the desktop registry.

## Agent procedure
1. Decide direction from the request (pack vs unpack). Locate `sync_claude.py` next to this SKILL.md.
2. PACK → run `pack` (no args); if it reports no synced root, fall back to home and say so. Report the zip path + counts.
3. UNPACK → run with `--dry-run`, summarize the plan (files, **remaps**, **desktop-app registration**, backup location), confirm with the user, then `--yes`. Report what got registered and any project the user must open once + re-`register`.
4. Tell the user to fully quit (incl. tray) and reopen so the restored conversations show.
5. Never pass `--yes` without explicit confirmation. Never include or restore credentials (the script already refuses).
