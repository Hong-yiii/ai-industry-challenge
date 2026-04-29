#!/usr/bin/env bash
# Run on the VM AFTER rebooting post-bootstrap.
# Verifies the NVIDIA driver, pulls the aic_eval image, and runs a smoke test.
#
# Run from your LOCAL machine:
#   platform/scripts/aic vm ssh -- 'bash -s' < platform/scripts/aic-vm-pull.sh
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[pull]${NC} $*"; }
warn()  { echo -e "${YELLOW}[pull]${NC} $*"; }
fail()  { echo -e "${RED}[pull] FAIL:${NC} $*" >&2; exit 1; }

AIC_EVAL_IMAGE="ghcr.io/intrinsic-dev/aic/aic_eval:latest"
export PATH="${HOME}/.pixi/bin:${PATH}"

# ── 1. Verify NVIDIA driver ───────────────────────────────────────────────────
info "Checking NVIDIA driver…"
if ! command -v nvidia-smi &>/dev/null; then
  fail "nvidia-smi not found. Did the reboot complete and was the driver installed by bootstrap?"
fi
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
info "NVIDIA driver OK."

# ── 2. Verify Docker + GPU passthrough ────────────────────────────────────────
info "Checking Docker GPU passthrough…"
# Re-login to docker group in case this session predates the usermod
if ! groups | grep -q docker; then
  warn "Current session is not in the docker group yet — using sudo for this check."
  DOCKER="sudo docker"
else
  DOCKER="docker"
fi

${DOCKER} run --rm --gpus all nvidia/cuda:12.3.2-base-ubuntu22.04 \
  nvidia-smi --query-gpu=name --format=csv,noheader \
  && info "Docker GPU passthrough OK." \
  || fail "Docker GPU passthrough failed. Check 'sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker'."

# ── 3. Pull aic_eval ──────────────────────────────────────────────────────────
info "Pulling ${AIC_EVAL_IMAGE} (this may take several minutes — image is ~10 GB)…"
${DOCKER} pull "${AIC_EVAL_IMAGE}"
info "Image pulled."

# ── 4. Verify Pixi ────────────────────────────────────────────────────────────
info "Checking Pixi…"
if ! command -v pixi &>/dev/null; then
  fail "pixi not found. Run bootstrap first, then re-login so ~/.pixi/bin is on PATH."
fi
pixi --version
info "Pixi OK."

# ── 5. Pixi install in repo ───────────────────────────────────────────────────
if [[ -d /srv/aic/repo/pixi.toml ]] || [[ -f /srv/aic/repo/pixi.toml ]]; then
  info "Running 'pixi install' in /srv/aic/repo…"
  (cd /srv/aic/repo && pixi install)
  info "Pixi install complete."
else
  warn "/srv/aic/repo/pixi.toml not found — skipping pixi install."
  warn "The repo may not have been cloned by bootstrap. Clone it manually if needed:"
  warn "  git clone https://github.com/intrinsic-dev/aic /srv/aic/repo"
fi

# ── 6. Quick eval container smoke test ───────────────────────────────────────
info "Running eval container smoke test (prints image entrypoint help)…"
${DOCKER} run --rm --gpus all "${AIC_EVAL_IMAGE}" /entrypoint.sh --help 2>&1 | head -20 || true
info "Smoke test done."

# Note: Compose dev.stack uses shutdown_on_aic_engine_exit:=false (long Foxglove sessions).
# The printed docker-run example uses :=true — one-shot smoke exits when aic_engine stops.

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  VM is ready for development.${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
info "Useful next steps:"
echo "  # Start the eval container (headless)"
echo "  docker run --rm --name aic_eval -p 7447:7447 --gpus all \\"
echo "    -e AIC_RESULTS_DIR=/results -v /tmp/aic_results:/results \\"
echo "    ${AIC_EVAL_IMAGE} \\"
echo "    gazebo_gui:=false launch_rviz:=false ground_truth:=false \\"
echo "    start_aic_engine:=true shutdown_on_aic_engine_exit:=true \\"
echo "    model_discovery_timeout_seconds:=600"
echo ""
echo "  # From /srv/aic/repo, run an example policy"
echo "  cd /srv/aic/repo"
echo "  RMW_IMPLEMENTATION=rmw_zenoh_cpp \\"
echo "  ZENOH_ROUTER_CHECK_ATTEMPTS=-1 \\"
echo "  ZENOH_CONFIG_OVERRIDE='connect/endpoints=[\"tcp/127.0.0.1:7447\"];transport/shared_memory/enabled=false' \\"
echo "  pixi run --as-is ros2 run aic_model aic_model \\"
echo "    --ros-args -p use_sim_time:=true -p policy:=aic_example_policies.ros.WaveArm"
