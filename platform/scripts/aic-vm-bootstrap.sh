#!/usr/bin/env bash
# One-time bootstrap for the aic-dev GCP VM.
# Installs: NVIDIA driver, Docker Engine, NVIDIA Container Toolkit, Pixi,
#           and creates the /srv/aic working layout.
#
# Run from your LOCAL machine:
#   platform/scripts/aic vm ssh -- 'bash -s' < platform/scripts/aic-vm-bootstrap.sh
#
# A reboot is required at the end before the GPU driver is usable.
# After rebooting, run aic vm pull or pipe aic-vm-pull.sh to pull the aic_eval image and verify.
set -euo pipefail

# Git clone URL for /srv/aic/repo (challenge toolkit upstream by default).
# Override without editing the script, e.g.:
#   platform/scripts/aic vm ssh -- \
#     'AIC_REPO_URL=https://github.com/your-org/your-fork.git bash -s' \
#     < platform/scripts/aic-vm-bootstrap.sh
AIC_REPO_URL="${AIC_REPO_URL:-https://github.com/intrinsic-dev/aic.git}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[bootstrap]${NC} $*"; }
warn()  { echo -e "${YELLOW}[bootstrap]${NC} $*"; }
error() { echo -e "${RED}[bootstrap]${NC} $*" >&2; }

# ── 1. System update ──────────────────────────────────────────────────────────
info "Updating system packages…"
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

sudo apt-get install -y -qq \
  apt-transport-https ca-certificates curl gnupg \
  lsb-release software-properties-common \
  git wget unzip htop nvtop tmux

# ── 2. NVIDIA driver ──────────────────────────────────────────────────────────
if command -v nvidia-smi &>/dev/null; then
  info "NVIDIA driver already installed: $(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)"
else
  info "Installing NVIDIA driver via CUDA network repository…"

  # CUDA keyring
  CUDA_DEB="cuda-keyring_1.1-1_all.deb"
  wget -q "https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/${CUDA_DEB}"
  sudo dpkg -i "${CUDA_DEB}"
  rm -f "${CUDA_DEB}"

  sudo apt-get update -qq
  # Use open kernel modules (better compatibility with kernel ≥6.x, recommended for L4/Ada Lovelace).
  # Do NOT use nvidia-dkms / cuda-drivers-550 — those fail to build on kernel 6.17+.
  sudo apt-get install -y nvidia-open-580
  info "NVIDIA driver installed. A reboot is required."
fi

# ── 3. Docker Engine ──────────────────────────────────────────────────────────
if command -v docker &>/dev/null; then
  info "Docker already installed: $(docker --version)"
else
  info "Installing Docker Engine…"
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg

  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

  sudo apt-get update -qq
  sudo apt-get install -y \
    docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin

  # Allow the current user to run docker without sudo
  sudo usermod -aG docker "$USER"
  info "Docker installed."
fi

# ── 4. NVIDIA Container Toolkit ───────────────────────────────────────────────
if dpkg -l nvidia-container-toolkit &>/dev/null 2>&1; then
  info "NVIDIA Container Toolkit already installed."
else
  info "Installing NVIDIA Container Toolkit…"
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

  sudo apt-get update -qq
  sudo apt-get install -y nvidia-container-toolkit

  # Wire nvidia runtime into Docker and restart
  sudo nvidia-ctk runtime configure --runtime=docker
  sudo systemctl restart docker

  info "NVIDIA Container Toolkit installed."
fi

# ── 5. Pixi ───────────────────────────────────────────────────────────────────
if command -v pixi &>/dev/null; then
  info "Pixi already installed: $(pixi --version)"
else
  info "Installing Pixi…"
  curl -fsSL https://pixi.sh/install.sh | sh
  # Make immediately available in this session
  export PATH="${HOME}/.pixi/bin:${PATH}"
  info "Pixi installed. It will be available after your next login."
fi

# ── 6. /srv/aic working layout ────────────────────────────────────────────────
info "Creating /srv/aic working layout…"
sudo mkdir -p /srv/aic/{repo,worktrees,results,bags,checkpoints,caches}
sudo chown -R "$USER":"$USER" /srv/aic
info "/srv/aic layout ready."

# ── 7. Clone the repo ─────────────────────────────────────────────────────────
if [[ -d /srv/aic/repo/.git ]]; then
  info "Repo already cloned at /srv/aic/repo — skipping."
else
  info "Cloning toolkit repo (${AIC_REPO_URL}) → /srv/aic/repo…"
  git clone "${AIC_REPO_URL}" /srv/aic/repo
  info "Repo cloned to /srv/aic/repo."
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Bootstrap complete.${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
warn "ACTION REQUIRED: reboot the VM before continuing."
warn "  From your local machine:"
warn "    platform/scripts/aic vm down   # stop (this triggers a clean shutdown)"
warn "    platform/scripts/aic vm up     # start again"
warn ""
warn "After reboot, pull the eval image:"
warn "    platform/scripts/aic vm ssh -- 'bash -s' < platform/scripts/aic-vm-pull.sh"
