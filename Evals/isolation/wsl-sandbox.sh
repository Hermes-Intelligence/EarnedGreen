#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 2 ]]; then echo "usage: wsl-sandbox.sh WORKSPACE COMMAND [ARG...]" >&2; exit 64; fi
workspace="$(realpath "$1")"; shift
[[ -d "$workspace" ]] || { echo "workspace missing" >&2; exit 66; }
root="$(mktemp -d /tmp/agentic-sandbox.XXXXXX)"
cleanup(){ rm -rf -- "$root"; }
trap cleanup EXIT
mkdir -p "$root/workspace" "$root/home/.codex" "$root/tmp" "$root/provider"
provider_source="${AGENTIC_PROVIDER_SOURCE:-$HOME/.local}"
[[ -d "$provider_source" ]] || { echo "provider runtime missing: $provider_source" >&2; exit 69; }
if [[ "${AGENTIC_COPY_CODEX_AUTH:-0}" == "1" ]]; then
  [[ -f "$HOME/.codex/auth.json" ]] || { echo "Codex is not logged in" >&2; exit 77; }
  cp "$HOME/.codex/auth.json" "$root/home/.codex/auth.json"
  chmod 600 "$root/home/.codex/auth.json"
fi
inner="$root/inner.sh"
cp "$(dirname "$(realpath "$0")")/wsl-sandbox-inner.sh" "$inner"
chmod 700 "$inner"
export AGENTIC_SANDBOX_ROOT="$root"
export AGENTIC_WORKSPACE_SOURCE="$workspace"
export AGENTIC_PROVIDER_SOURCE="$provider_source"
unshare --user --map-root-user --mount --pid --fork bash "$inner" "$@"
