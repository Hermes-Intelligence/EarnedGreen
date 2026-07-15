#!/usr/bin/env bash
set -euo pipefail

provider="${1:-}"
model="${2:-provider-default}"
effort="${3:-medium}"
max_turns="${4:-12}"
max_seconds="${5:-900}"
workspace=/srv/agenticbench/workspace

[[ "${WSL_DISTRO_NAME:-}" == "${AGENTICBENCH_DISTRO:-AgenticBench}" ]] || exit 77
[[ "$(id -un)" == "agenticbench" ]] || exit 78
[[ "$(realpath "$workspace")" == "$workspace" ]] || exit 79
[[ "$provider" =~ ^(codex|claude)$ ]] || exit 64
[[ "$model" =~ ^[A-Za-z0-9._:-]+$ ]] || exit 65
[[ "$effort" =~ ^(low|medium|high|xhigh)$ ]] || exit 66
[[ "$max_turns" =~ ^[1-9][0-9]?$ ]] || exit 67
[[ "$max_seconds" =~ ^[1-9][0-9]{1,4}$ ]] || exit 68

cd "$workspace"
[[ -f .agentic/BENCHMARK_PROMPT.txt ]] || exit 69

export HOME=/home/agenticbench
export PATH="$HOME/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
events=.agentic/provider-events.jsonl
stderr_log=.agentic/provider-stderr.log
: > "$events"
: > "$stderr_log"

if [[ "$provider" == codex ]]; then
  args=(exec --ephemeral --ignore-user-config --skip-git-repo-check --sandbox workspace-write --json -C .)
  if [[ "$model" != provider-default ]]; then args+=(-m "$model"); fi
  args+=(-c "model_reasoning_effort=\"$effort\"" -)
  timeout --signal=TERM --kill-after=15 "${max_seconds}s" \
    codex "${args[@]}" < .agentic/BENCHMARK_PROMPT.txt > "$events" 2> "$stderr_log"
else
  [[ "$effort" != xhigh ]] || { echo "Claude does not accept xhigh effort." >&2; exit 70; }
  printf '%s\n' '{"mcpServers":{}}' > .agentic/empty-mcp.json
  args=(--print --output-format stream-json --verbose --max-turns "$max_turns"
    --permission-mode auto --safe-mode --no-session-persistence
    --strict-mcp-config --mcp-config .agentic/empty-mcp.json --effort "$effort")
  if [[ "$model" != provider-default ]]; then args+=(--model "$model"); fi
  timeout --signal=TERM --kill-after=15 "${max_seconds}s" \
    claude "${args[@]}" "$(< .agentic/BENCHMARK_PROMPT.txt)" > "$events" 2> "$stderr_log"
fi
