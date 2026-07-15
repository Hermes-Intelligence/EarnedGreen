#!/usr/bin/env bash
set -euo pipefail

EXPECTED_DISTRO="${AGENTICBENCH_DISTRO:-AgenticBench}"
BENCH_USER="${AGENTICBENCH_USER:-agenticbench}"

if [[ "$(id -u)" != "0" ]]; then
  echo "Run as root inside the dedicated WSL distribution." >&2
  exit 77
fi

if [[ "${WSL_DISTRO_NAME:-}" != "$EXPECTED_DISTRO" ]]; then
  echo "Refusing to provision '${WSL_DISTRO_NAME:-unknown}'; expected '$EXPECTED_DISTRO'." >&2
  exit 78
fi

if [[ -d "/home/$BENCH_USER" ]] && [[ -n "$(find "/home/$BENCH_USER" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
  echo "Refusing to provision a non-empty benchmark home." >&2
  exit 79
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates curl git jq nodejs npm python3 python3-venv \
  procps tar time util-linux
if dpkg-query -W -f='${Status}' sudo 2>/dev/null | grep -q 'install ok installed'; then
  SUDO_FORCE_REMOVE=yes apt-get purge -y sudo
fi
rm -rf /var/lib/apt/lists/*

if ! id "$BENCH_USER" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "$BENCH_USER"
fi
chmod 0700 "/home/$BENCH_USER"

if id -nG "$BENCH_USER" | grep -Eq '(^| )(sudo|adm|docker|disk|root)( |$)'; then
  echo "Benchmark user unexpectedly belongs to a privileged group." >&2
  exit 80
fi

install -d -m 0755 /opt/agenticbench/bin /srv/agenticbench
install -d -m 0700 -o "$BENCH_USER" -g "$BENCH_USER" "/home/$BENCH_USER/.agenticbench"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for script in agenticbench-reset-workspace.sh agenticbench-run-provider.sh agenticbench-validate-workspace.sh; do
  install -m 0755 "$SCRIPT_DIR/$script" "/opt/agenticbench/bin/$script"
done

printf '%s\n' \
  '[automount]' \
  'enabled=false' \
  '[interop]' \
  'enabled=false' \
  'appendWindowsPath=false' \
  '[user]' \
  "default=$BENCH_USER" \
  > /etc/wsl.conf
chmod 0644 /etc/wsl.conf

echo "Base provisioning complete. Restart the distribution before validation."
