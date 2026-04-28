#!/usr/bin/env bash
# Start the AIC dev VM. Safe to run when the instance is already running.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=aic-vm-config.env
source "${SCRIPT_DIR}/aic-vm-config.env"

status=$(gcloud compute instances describe "${AIC_VM_NAME}" \
  --project "${AIC_VM_PROJECT}" \
  --zone    "${AIC_VM_ZONE}" \
  --format  "value(status)" 2>&1)

if [[ "${status}" == "RUNNING" ]]; then
  echo "aic-dev is already running."
else
  echo "Starting ${AIC_VM_NAME} (${AIC_VM_ZONE})…"
  gcloud compute instances start "${AIC_VM_NAME}" \
    --project "${AIC_VM_PROJECT}" \
    --zone    "${AIC_VM_ZONE}"
  echo "Done. Connect with:  platform/scripts/aic-vm-ssh.sh"
fi

# Print the current external IP (may change on each start for Spot VMs)
ip=$(gcloud compute instances describe "${AIC_VM_NAME}" \
  --project "${AIC_VM_PROJECT}" \
  --zone    "${AIC_VM_ZONE}" \
  --format  "value(networkInterfaces[0].accessConfigs[0].natIP)")
echo "External IP: ${ip}"
