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
If the zip was received on a machine that never had the skill, it embeds its own copy — extract it and run the extracted `sync_claude.py unpack`. If that machine uses different folders, pass `--workstreams-dest <dir>`.

## Two facts to tell the user
1. **Same path = things map.** Conversations/memory live in a folder named after the project's absolute path. They auto-load only if the target opens the repos at the **same path** (same username + synced layout — the normal case). Different path → the restored `projects/*` names won't match; open at the same path.
2. **Restart Claude Code** after unpacking so it re-reads `CLAUDE.md`, `settings.json`, skills and the memory index.

## Agent procedure
1. Decide direction from the request (pack vs unpack). Locate `sync_claude.py` next to this SKILL.md.
2. PACK → run `pack` (no args); if it reports no synced root, fall back to home and say so. Report the zip path + counts.
3. UNPACK → run with `--dry-run`, summarize the plan + where the safety backup goes, confirm with the user, then `--yes`. Report the backup path.
4. Never pass `--yes` without explicit confirmation. Never include or restore credentials (the script already refuses).
