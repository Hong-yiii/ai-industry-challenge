# Platform Scripts

Operational scripts for the shared GCP development VM and daily AIC workflows.

## Prerequisites

- `bash`
- `gcloud` CLI authenticated to the right project (for `aic-vm-*` scripts)
- Docker (for local/remote container scripts)
- ROS 2 CLI on PATH (for `aic-healthcheck.sh`)

Most VM scripts load defaults from `aic-vm-config.env`:

- `AIC_VM_PROJECT` (default: `ai-for-industry`)
- `AIC_VM_NAME` (default: `aic-dev`)
- `AIC_VM_ZONE` (default: `asia-southeast1-a`)

You can override these per command:

```bash
AIC_VM_ZONE=us-central1-a platform/scripts/aic-vm-up.sh
```

## Script Index

### VM lifecycle and access

- `aic-vm-up.sh`  
  Start the dev VM if it is stopped, then print the external IP.
- `aic-vm-down.sh`  
  Stop the dev VM (disk persists, compute billing stops).
- `aic-vm-ssh.sh`  
  SSH into the VM (interactive shell) or run one remote command.

Examples:

```bash
platform/scripts/aic-vm-up.sh
platform/scripts/aic-vm-ssh.sh
platform/scripts/aic-vm-ssh.sh -- 'hostname && nvidia-smi'
platform/scripts/aic-vm-down.sh
```

### VM setup and post-setup validation

- `aic-vm-bootstrap.sh`  
  One-time bootstrap on the VM (driver, Docker, NVIDIA toolkit, Pixi, `/srv/aic` layout, repo clone).
- `aic-vm-pull.sh`  
  Post-reboot validation and image prep (`aic_eval` pull, GPU smoke checks, Pixi check).

Run both from your local machine through SSH piping:

```bash
platform/scripts/aic-vm-ssh.sh -- 'bash -s' < platform/scripts/aic-vm-bootstrap.sh
# reboot VM, then:
platform/scripts/aic-vm-ssh.sh -- 'bash -s' < platform/scripts/aic-vm-pull.sh
```

### Observability and visualization

- `aic-vm-observe.sh`  
  Open SSH tunnels to VM services:
  - `localhost:3000` -> Grafana
  - `localhost:9090` -> Prometheus
  - `localhost:8765` -> Foxglove bridge websocket
- `aic-foxglove-bridge.sh`  
  Build and start the `foxglove_bridge` sidecar from `platform/compose/dev.compose.yaml`.
  First run (or when missing the local image) uses `docker compose build --pull`
  so the sidecar’s `FROM aic_eval` layer matches the registry. After updating
  `aic_eval:latest` on the VM, force the same with
  **`AIC_FOXGLOVE_SYNC_BASE=1 platform/scripts/aic-foxglove-bridge.sh`** so mesh
  `package://` paths resolve against the same tree as the running eval container.

Typical flow:

```bash
# On VM
platform/scripts/aic-foxglove-bridge.sh

# On laptop
platform/scripts/aic-vm-observe.sh
# Then connect Foxglove to ws://localhost:8765
# 3D panel URDF layer: Source=Topic, topic=/robot_description_foxglove (web; see foxglove_urdf_handoff.md)
```

### Runtime checks and diagnostics

- `aic-healthcheck.sh`  
  Quick ROS graph/liveness check (nodes, topics, actions, services, sample messages).
- `aic-session-report.sh`  
  Host diagnostics snapshot (time, memory, disk, Docker ps/stats, GPU, ROS/Gazebo-like processes).

Examples:

```bash
platform/scripts/aic-healthcheck.sh
platform/scripts/aic-session-report.sh
```

### Dev productivity helpers

- `aic-prepare-worktree.sh <branch> [remote]`  
  Create or refresh a per-user `git worktree` under `.worktrees/<user>/<branch>`.
- `aic-mk-results-dir.sh [label]`  
  Create a unique run directory and print the path. Path includes user, label, UTC timestamp, branch, and SHA.

Examples:

```bash
platform/scripts/aic-prepare-worktree.sh feat/new-policy
run_dir="$(platform/scripts/aic-mk-results-dir.sh eval)"
echo "$run_dir"
```

## Environment variables used by helper scripts

- `AIC_WORKTREE_ROOT`, `AIC_REPO_ROOT`, `AIC_REMOTE_USER` for `aic-prepare-worktree.sh`
- `AIC_RESULTS_ROOT`, `AIC_RUN_USER` for `aic-mk-results-dir.sh`
- `AIC_CLOCK_TOPIC`, `AIC_STATE_TOPIC`, `AIC_INSERT_ACTION`, `TIMEOUT_BIN` for `aic-healthcheck.sh`

## Troubleshooting

- `gcloud` auth errors:
  - Run `gcloud auth login`
  - Run `gcloud config set project <project-id>`
- SSH fails after VM restart:
  - Retry after ~10-30s while SSH service comes up
- `docker` permission denied on VM:
  - Re-login or open a fresh SSH session after bootstrap
- Foxglove cannot connect:
  - Verify bridge container is running
  - Keep `aic-vm-observe.sh` alive while connecting

