#!/usr/bin/env bash
set -euo pipefail

# Remote Isaac Lab setup helper.
#
# Usage from repo root:
#   platform/scripts/aic vm ssh 'bash -s' < platform/scripts/aic-isaac-setup.sh

AIC_ISAAC_ROOT="${AIC_ISAAC_ROOT:-/srv/aic/isaac}"
AIC_ISAAC_LAB_TAG="${AIC_ISAAC_LAB_TAG:-v2.3.2}"
AIC_ISAAC_REPO_URL="${AIC_ISAAC_REPO_URL:-https://github.com/isaac-sim/IsaacLab.git}"
AIC_REPO_URL="${AIC_REPO_URL:-https://github.com/Hong-yiii/ai-industry-challenge.git}"
AIC_ASSET_URL="${AIC_ASSET_URL:-https://developer.nvidia.com/downloads/Omniverse/learning/Events/Hackathons/Intrinsic_assets.zip}"

LAB="${AIC_ISAAC_ROOT}/IsaacLab"
AIC="${LAB}/aic"
ASSET_ZIP="${AIC_ISAAC_ROOT}/Intrinsic_assets.zip"
ASSET_DEST="${AIC}/aic_utils/aic_isaac/aic_isaaclab/source/aic_task/aic_task/tasks/manager_based/aic_task/Intrinsic_assets"

mkdir -p "${AIC_ISAAC_ROOT}"

if [[ ! -d "${LAB}/.git" ]]; then
  git clone --branch "${AIC_ISAAC_LAB_TAG}" --depth 1 "${AIC_ISAAC_REPO_URL}" "${LAB}"
else
  git -C "${LAB}" fetch --tags origin "${AIC_ISAAC_LAB_TAG}"
  git -C "${LAB}" checkout "${AIC_ISAAC_LAB_TAG}"
fi

if [[ ! -d "${AIC}/.git" ]]; then
  git clone "${AIC_REPO_URL}" "${AIC}"
else
  git -C "${AIC}" fetch origin
  git -C "${AIC}" checkout main
  git -C "${AIC}" pull --ff-only origin main || true
fi

mkdir -p "$(dirname "${ASSET_DEST}")"
if [[ ! -f "${ASSET_ZIP}" ]]; then
  curl -L --fail --retry 3 -o "${ASSET_ZIP}" "${AIC_ASSET_URL}"
fi

if [[ ! -d "${ASSET_DEST}" ]]; then
  tmpdir="$(mktemp -d)"
  unzip -q "${ASSET_ZIP}" -d "${tmpdir}"
  found="$(find "${tmpdir}" -type d -name Intrinsic_assets | head -1)"
  if [[ -z "${found}" ]]; then
    echo "Intrinsic_assets directory not found in ${ASSET_ZIP}" >&2
    exit 1
  fi
  mv "${found}" "${ASSET_DEST}"
  rm -rf "${tmpdir}"
fi

cat > "${LAB}/docker/.container.cfg" <<'CFG'
[X11]
x11_forwarding_enabled = 0
CFG

cat > "${LAB}/docker/docker-compose.aic.patch.yaml" <<'YAML'
services:
  isaac-lab-base:
    volumes:
      - type: bind
        source: ../aic
        target: /workspace/isaaclab/aic
YAML

cd "${LAB}"
./docker/container.py start base --files docker-compose.aic.patch.yaml
docker exec isaac-lab-base bash -lc \
  'cd /workspace/isaaclab &&
   ./isaaclab.sh -p -m pip install --no-build-isolation flatdict==4.0.1 &&
   ./isaaclab.sh --install &&
   ./isaaclab.sh -p -m pip install -q foxglove-sdk &&
   ./isaaclab.sh -p -m pip install -e aic/aic_utils/aic_isaac/aic_isaaclab/source/aic_task'
