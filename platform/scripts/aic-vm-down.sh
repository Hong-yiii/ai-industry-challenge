#!/usr/bin/env bash
# Stop the AIC dev VM. Disk is preserved; only compute billing stops.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=aic-vm-config.env
source "${SCRIPT_DIR}/aic-vm-config.env"

status=$(gcloud compute instances describe "${AIC_VM_NAME}" \
  --project "${AIC_VM_PROJECT}" \
  --zone    "${AIC_VM_ZONE}" \
  --format  "value(status)" 2>&1)

if [[ "${status}" == "TERMINATED" ]]; then
  echo "aic-dev is already stopped."
  exit 0
fi

echo "Stopping ${AIC_VM_NAME} (${AIC_VM_ZONE})…"
gcloud compute instances stop "${AIC_VM_NAME}" \
  --project "${AIC_VM_PROJECT}" \
  --zone    "${AIC_VM_ZONE}"
echo "Done. Disk is preserved; compute billing has stopped."
