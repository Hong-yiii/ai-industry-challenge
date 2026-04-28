#!/usr/bin/env bash
# Build the foxglove_bridge sidecar image (first run only) and start it.
# The bridge connects to the Zenoh router inside aic_eval via Docker networking —
# no host-level ROS install or library path setup required.
#
# Prerequisites: aic_eval must already be running.
# The foxglove_bridge image is built FROM aic_eval, so it already has all
# AIC custom message schemas — no host-level ROS install needed.
#
# Usage (run on the VM):
#   cd ~/ai-industry-challenge
#   platform/scripts/aic-foxglove-bridge.sh
#
# CheatCode / other policies that need sim ground-truth TF:
#   AIC_GROUND_TRUTH=true platform/scripts/aic-foxglove-bridge.sh
#
# Then open the tunnel from your laptop:
#   platform/scripts/aic-vm-observe.sh
#
# And connect:
#   https://app.foxglove.dev → Open Connection → Foxglove WebSocket → ws://localhost:8765
set -euo pipefail

COMPOSE_FILE="platform/compose/dev.compose.yaml"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "${REPO_ROOT}"

# Sidecar image is `FROM aic_eval`; stale FROM layers cause missing meshes while
# TF/topics still work. See platform/compose/dev.compose.yaml and
# platform/docs/foxglove_urdf_handoff.md ("Install-tree skew").
if [[ "${AIC_FOXGLOVE_SYNC_BASE:-}" == "1" ]] || ! docker image inspect aic-foxglove-bridge:latest &>/dev/null; then
  echo "[foxglove-bridge] Pulling aic_eval + building sidecar with --pull (set AIC_FOXGLOVE_SYNC_BASE=1 to force)…"
  docker compose -f "${COMPOSE_FILE}" pull aic_eval
  docker compose -f "${COMPOSE_FILE}" build --pull foxglove_bridge
else
  echo "[foxglove-bridge] Incremental build (no --pull). For a fresh aic_eval digest: AIC_FOXGLOVE_SYNC_BASE=1 $0"
  docker compose -f "${COMPOSE_FILE}" build foxglove_bridge
fi

# Start (or restart) only the foxglove_bridge service
docker compose -f "${COMPOSE_FILE}" up -d foxglove_bridge

echo ""
echo "[foxglove-bridge] Container started."
echo "  Open tunnel:  platform/scripts/aic-vm-observe.sh"
echo "  Connect:      https://app.foxglove.dev  →  ws://localhost:8765"
echo "  3D URDF:      Custom layer → Source=Topic → /robot_description_foxglove"
echo "               (see platform/docs/foxglove_urdf_handoff.md)"
