#!/usr/bin/env bash
set -euo pipefail
: "${AGENTIC_MODEL:?resolved model is required}"
: "${AGENTIC_EFFORT:?reasoning effort is required}"
codex exec --ephemeral --ignore-user-config --skip-git-repo-check \
  --sandbox workspace-write --json -C . -m "$AGENTIC_MODEL" \
  -c "model_reasoning_effort=\"$AGENTIC_EFFORT\"" - \
  < .agentic/BENCHMARK_PROMPT.txt \
  > .agentic/provider-events.jsonl
