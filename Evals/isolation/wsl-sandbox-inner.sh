#!/usr/bin/env bash
set -euo pipefail
: "${AGENTIC_SANDBOX_ROOT:?}"
: "${AGENTIC_WORKSPACE_SOURCE:?}"
mount --make-rprivate /
mount --bind "$AGENTIC_WORKSPACE_SOURCE" "$AGENTIC_SANDBOX_ROOT/workspace"
mount --bind "$AGENTIC_PROVIDER_SOURCE" "$AGENTIC_SANDBOX_ROOT/provider"
mount -t tmpfs -o mode=755 tmpfs /mnt
mount -t tmpfs -o mode=755 tmpfs /home
export HOME="$AGENTIC_SANDBOX_ROOT/home"
export TMPDIR="$AGENTIC_SANDBOX_ROOT/tmp"
export CODEX_HOME="$HOME/.codex"
export PATH="$AGENTIC_SANDBOX_ROOT/provider/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
cd "$AGENTIC_SANDBOX_ROOT/workspace"
exec "$@"
