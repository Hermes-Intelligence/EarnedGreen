#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" != "0" ]] || [[ "${WSL_DISTRO_NAME:-}" != "${AGENTICBENCH_DISTRO:-AgenticBench}" ]]; then
  echo "Workspace reset is restricted to root in AgenticBench." >&2
  exit 77
fi

workspace=/srv/agenticbench/workspace
case "$workspace" in
  /srv/agenticbench/workspace) ;;
  *) echo "Unsafe workspace path." >&2; exit 78 ;;
esac

rm -rf -- "$workspace"
install -d -m 0700 -o agenticbench -g agenticbench "$workspace"

