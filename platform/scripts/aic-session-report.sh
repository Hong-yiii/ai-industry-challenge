#!/usr/bin/env bash
set -euo pipefail

echo "== host =="
date -u +"%Y-%m-%dT%H:%M:%SZ"
uname -a
uptime

echo
echo "== memory =="
free -h || true

echo
echo "== disk =="
df -h || true

echo
echo "== docker ps =="
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' || true

echo
echo "== docker stats =="
docker stats --no-stream || true

echo
echo "== gpu =="
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi
else
  echo "nvidia-smi not found"
fi

echo
echo "== top ros and gazebo processes =="
ps -eo pid,ppid,%cpu,%mem,etime,cmd \
  | grep -E 'ros2|gz|gazebo|rviz|aic_' \
  | grep -v grep || true
