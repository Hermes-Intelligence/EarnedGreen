#!/usr/bin/env bash
set -euo pipefail

EXPECTED_DISTRO="${AGENTICBENCH_DISTRO:-AgenticBench}"
BENCH_USER="${AGENTICBENCH_USER:-agenticbench}"

if [[ "${WSL_DISTRO_NAME:-}" != "$EXPECTED_DISTRO" ]] || [[ "$(id -un)" != "$BENCH_USER" ]]; then
  echo "Run only as $BENCH_USER inside $EXPECTED_DISTRO." >&2
  exit 77
fi

install_root="$HOME/.local"
mkdir -p "$install_root"

if ! "$install_root/bin/node" --version >/dev/null 2>&1; then
  npm install --global --prefix "$install_root" n
  N_PREFIX="$install_root" "$install_root/bin/n" lts
fi

export PATH="$install_root/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
codex_version="$(npm view @openai/codex dist-tags.latest)"
claude_version="$(npm view @anthropic-ai/claude-code dist-tags.latest)"

npm install --global --prefix "$install_root" \
  "@openai/codex@$codex_version" \
  "@anthropic-ai/claude-code@$claude_version"

codex --version
claude --version

umask 077
jq -n \
  --arg generated_at "$(date --iso-8601=seconds)" \
  --arg node "$(node --version)" \
  --arg codex "$(codex --version)" \
  --arg claude "$(claude --version)" \
  '{schema_version:1,generated_at:$generated_at,node:$node,codex:$codex,claude:$claude}' \
  > "$HOME/.agenticbench/toolchain.json"

