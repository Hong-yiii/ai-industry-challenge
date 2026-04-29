#!/usr/bin/env bash
# Entrypoint for the foxglove_bridge sidecar container.
# Inherits the ROS + Zenoh environment from the aic_eval base image.
set -eo pipefail

# ament's setup.bash reads AMENT_TRACE_SETUP_FILES; default it to avoid
# 'unbound variable' errors when the image is run with set -u elsewhere.
export AMENT_TRACE_SETUP_FILES="${AMENT_TRACE_SETUP_FILES:-}"

# Source ROS base, then the AIC workspace so foxglove_bridge can decode
# all custom message types (aic_control_interfaces, aic_model_interfaces, etc.)
# shellcheck disable=SC1091
source /opt/ros/kilted/setup.bash
# shellcheck disable=SC1091
[[ -f /ws_aic/install/setup.bash ]] && source /ws_aic/install/setup.bash

# Use Zenoh as the RMW (same as aic_eval)
export RMW_IMPLEMENTATION=rmw_zenoh_cpp

# Allow overriding the Zenoh router endpoint at runtime.
ZENOH_ROUTER_ENDPOINT="${ZENOH_ROUTER_ENDPOINT:-tcp/aic_eval:7447}"

export ZENOH_ROUTER_CHECK_ATTEMPTS=-1
export ZENOH_CONFIG_OVERRIDE="connect/endpoints=[\"${ZENOH_ROUTER_ENDPOINT}\"];transport/shared_memory/enabled=false"

echo "[foxglove-bridge] Connecting to Zenoh router at ${ZENOH_ROUTER_ENDPOINT}"

# ── URDF rewrite for Foxglove WebSocket (file:// -> package://) ───────────────
# Browser-side Foxglove cannot load mesh URIs like file:///ws_aic/install/...
# Republish once (latched) on /robot_description_foxglove for URDF layer Topic.
python3 /rewrite_urdf_for_foxglove.py >>/tmp/urdf_rewrite.log 2>&1 &
echo "[foxglove-bridge] URDF rewrite helper PID $! (see /tmp/urdf_rewrite.log)"

# ── Start compressed image republishers ───────────────────────────────────────
# Raw camera images are ~3 MB each. JPEG-compressed versions are ~50-150 KB,
# reducing WebSocket bandwidth by 20-50x and eliminating the "backlog full"
# disconnects that cause Foxglove panel refreshes.
#
# Foxglove subscribes to /*/image/compressed instead of /*/image.
start_republisher() {
  local topic="$1"
  ros2 run image_transport republish raw compressed \
    --ros-args \
    -r "in:=${topic}" \
    -r "out/compressed:=${topic}/compressed" \
    > "/tmp/republish_$(basename "${topic}").log" 2>&1 &
  echo "[foxglove-bridge] Republishing ${topic} → ${topic}/compressed (PID $!)"
}

start_republisher /center_camera/image
start_republisher /left_camera/image
start_republisher /right_camera/image

# Give republishers a moment to register in the graph before the bridge starts
sleep 2

echo "[foxglove-bridge] WebSocket on ws://0.0.0.0:8765"
echo "[foxglove-bridge] Subscribe to /*/image/compressed in Foxglove Image panels"
echo "[foxglove-bridge] Connect from https://app.foxglove.dev using ws://localhost:8765"
echo "[foxglove-bridge] 3D URDF (web Foxglove): add URDF layer → Source=Topic → /robot_description_foxglove (not raw /robot_description)"
echo ""

# Use a YAML params file — reliable way to pass list parameters (capabilities,
# topic_regexes / topic_allowlist patterns) to the ROS 2 foxglove_bridge node.
exec ros2 run foxglove_bridge foxglove_bridge \
  --ros-args \
  --params-file /foxglove_bridge_params.yaml
