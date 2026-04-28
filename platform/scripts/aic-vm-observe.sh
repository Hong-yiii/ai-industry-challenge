#!/usr/bin/env bash
# Open SSH port-forward tunnels to the observability stack on aic-dev.
#
# Usage:
#   platform/scripts/aic-vm-observe.sh
#
# Then open in a browser:
#   http://localhost:3000  →  Grafana  (admin / admin — change on first login)
#   http://localhost:9090  →  Prometheus
#
# Press Ctrl-C to close all tunnels.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=aic-vm-config.env
source "${SCRIPT_DIR}/aic-vm-config.env"

echo "Opening tunnels to ${AIC_VM_NAME} (${AIC_VM_ZONE})…"
echo "  Grafana    → http://localhost:3000  (admin / admin)"
echo "  Prometheus → http://localhost:9090"
echo "  Foxglove   → connect ws://localhost:8765 from https://app.foxglove.dev"
echo ""
echo "Press Ctrl-C to close."

exec gcloud compute ssh "${AIC_VM_NAME}" \
  --project "${AIC_VM_PROJECT}" \
  --zone    "${AIC_VM_ZONE}" \
  -- -N \
     -L 3000:localhost:3000 \
     -L 9090:localhost:9090 \
     -L 8080:localhost:8080 \
     -L 8765:localhost:8765
