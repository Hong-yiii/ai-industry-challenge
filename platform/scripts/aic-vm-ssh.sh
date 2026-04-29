#!/usr/bin/env bash
# Compatibility shim — use `platform/scripts/aic vm ssh [--] <remote command>`.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/aic" vm ssh "$@"
