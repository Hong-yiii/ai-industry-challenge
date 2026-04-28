#!/usr/bin/env bash
# SSH into the AIC dev VM via gcloud (more reliable than the browser terminal).
# Usage:
#   platform/scripts/aic-vm-ssh.sh              # interactive shell
#   platform/scripts/aic-vm-ssh.sh -- <cmd>     # run a single command
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=aic-vm-config.env
source "${SCRIPT_DIR}/aic-vm-config.env"

exec gcloud compute ssh "${AIC_VM_NAME}" \
  --project "${AIC_VM_PROJECT}" \
  --zone    "${AIC_VM_ZONE}" \
  -- "$@"
