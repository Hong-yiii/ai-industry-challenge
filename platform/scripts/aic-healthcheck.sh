#!/usr/bin/env bash
set -euo pipefail

timeout_cmd="${TIMEOUT_BIN:-timeout}"
clock_topic="${AIC_CLOCK_TOPIC:-/clock}"
state_topic="${AIC_STATE_TOPIC:-/aic_controller/state}"
action_name="${AIC_INSERT_ACTION:-/insert_cable}"

if ! command -v ros2 >/dev/null 2>&1; then
  echo "ros2 is not on PATH" >&2
  exit 1
fi

echo "== env =="
echo "RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-unset}"
echo "ZENOH_CONFIG_OVERRIDE=${ZENOH_CONFIG_OVERRIDE:-unset}"

echo
echo "== nodes =="
ros2 node list || true

echo
echo "== topics =="
ros2 topic list || true

echo
echo "== actions =="
ros2 action list || true

echo
echo "== services =="
ros2 service list || true

echo
echo "== clock sample =="
if command -v "${timeout_cmd}" >/dev/null 2>&1; then
  "${timeout_cmd}" 5s ros2 topic echo --once "${clock_topic}" || echo "clock sample unavailable"
else
  ros2 topic echo --once "${clock_topic}" || echo "clock sample unavailable"
fi

echo
echo "== controller state sample =="
if command -v "${timeout_cmd}" >/dev/null 2>&1; then
  "${timeout_cmd}" 5s ros2 topic echo --once "${state_topic}" || echo "controller state unavailable"
else
  ros2 topic echo --once "${state_topic}" || echo "controller state unavailable"
fi

echo
echo "== action info =="
ros2 action info "${action_name}" || echo "action ${action_name} unavailable"
