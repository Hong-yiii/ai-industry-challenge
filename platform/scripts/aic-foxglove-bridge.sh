#!/usr/bin/env bash
# Compatibility shim — use `platform/scripts/aic stack dev up`.
# Runs from repo root on the VM with the same semantics as docker compose up -d foxglove_bridge / aic_eval.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/aic" stack dev up "$@"
