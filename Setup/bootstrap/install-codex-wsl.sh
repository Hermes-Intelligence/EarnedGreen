#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$HOME/.local"
if ! "$HOME/.local/bin/node" --version >/dev/null 2>&1; then
  npm install -g --prefix "$HOME/.local" n
  N_PREFIX="$HOME/.local" "$HOME/.local/bin/n" lts
fi
export PATH="$HOME/.local/bin:$PATH"
version="$(npm view @openai/codex dist-tags.latest)"
npm install -g --prefix "$HOME/.local" "@openai/codex@$version"
codex --version
