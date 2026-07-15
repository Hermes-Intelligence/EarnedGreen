#!/usr/bin/env bash
set -euo pipefail

workspace=/srv/agenticbench/workspace
max_files="${AGENTIC_MAX_FILES:-5000}"
max_bytes="${AGENTIC_MAX_BYTES:-52428800}"

[[ "${WSL_DISTRO_NAME:-}" == "${AGENTICBENCH_DISTRO:-AgenticBench}" ]] || exit 77
[[ "$(realpath "$workspace")" == "$workspace" ]] || exit 78

if find "$workspace" -type l -print -quit | grep -q .; then
  echo "Workspace contains a symbolic link." >&2
  exit 81
fi

if find "$workspace" ! -type d ! -type f -print -quit | grep -q .; then
  echo "Workspace contains a non-regular filesystem object." >&2
  exit 82
fi

if find "$workspace" -type f \( -name auth.json -o -name .credentials.json -o -name .claude.json \) -print -quit | grep -q .; then
  echo "Workspace contains a provider credential filename." >&2
  exit 85
fi

if grep -RIlE --exclude='*.pyc' --exclude='*.bin' \
  '(sk-ant-|sk-proj-|"accessToken"[[:space:]]*:|"refreshToken"[[:space:]]*:)' \
  "$workspace" | grep -q .; then
  echo "Workspace content resembles provider credentials." >&2
  exit 86
fi

file_count="$(find "$workspace" -type f -printf . | wc -c)"
byte_count="$(du -sb "$workspace" | awk '{print $1}')"
(( file_count <= max_files )) || { echo "Workspace file ceiling exceeded." >&2; exit 83; }
(( byte_count <= max_bytes )) || { echo "Workspace byte ceiling exceeded." >&2; exit 84; }

jq -n --argjson files "$file_count" --argjson bytes "$byte_count" \
  '{schema_version:1,passed:true,files:$files,bytes:$bytes}'
