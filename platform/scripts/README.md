# Platform scripts

Operational tooling for the shared GCP **`aic-dev`** VM and compose-based dev stacks.

For how **`aic`**, the VM, Compose, tunnels, Pixi-hosted policies, and **`aic stack test`** fit together—including Mermaid diagrams—see [**`docs/aic_platform_workflow.md`**](../docs/aic_platform_workflow.md).

## Main entrypoint: `aic`

Run from repo root:

```bash
chmod +x platform/scripts/aic   # once
platform/scripts/aic --help
```

[`aic`](aic) is a small bash shim that loads [`aic-vm-config.env`](aic-vm-config.env), then executes [`aic_cli.py`](aic_cli.py) (Python 3).

### Prerequisites

- `bash`, Python 3, `docker`/`docker compose` (for **local** stack commands)
- `gcloud` (for **`vm`** / **`tunnel`** / **`--remote`** stack commands)
- Optional: ROS 2 CLI for [`aic diag ros`](aic-healthcheck.sh) wrappers

 Defaults in **`aic-vm-config.env`:**

- `AIC_VM_PROJECT`, `AIC_VM_NAME`, `AIC_VM_ZONE`
- **`AIC_VM_REPO_PATH`** (default `/srv/aic/repo`) — path **on the VM** used for SSH `compose`/`docker compose` commands

 Override per-invocation:

```bash
AIC_VM_ZONE=us-central1-a platform/scripts/aic vm up
```

---

## Commands (overview)

### VM lifecycle

```text
aic vm up | down | ssh [-- ARGS...]
aic vm bootstrap    # stdin: aic-vm-bootstrap.sh (usually piped from laptop)
aic vm pull        # stdin: aic-vm-pull.sh (usually piped after reboot)
```

 Bootstrap / pull piping (unchanged semantics):

```bash
platform/scripts/aic vm ssh -- 'bash -s' < platform/scripts/aic-vm-bootstrap.sh
platform/scripts/aic vm ssh -- 'bash -s' < platform/scripts/aic-vm-pull.sh
```

### Golden path (`dev` = `session`)

Starts the VM if needed, waits for SSH, brings up the **dev** stack (`aic_eval` + `foxglove_bridge`) **on the VM**, optionally observability, then opens **SSH tunnels** (blocking).

```bash
platform/scripts/aic dev
platform/scripts/aic session --sync-foxglove --ground-truth --with-observability
```

### Tunnels (`aic-vm-observe.sh` parity)

Forward localhost **3000** (Grafana), **9090** (Prometheus), **8080** (cAdvisor), **8765** (Foxglove WebSocket):

```bash
platform/scripts/aic tunnel
platform/scripts/aic tunnel --metrics-only
platform/scripts/aic tunnel --foxglove-only
platform/scripts/aic tunnel --isaac-foxglove
```

**Ctrl+C** opens an interactive teardown menu (tunnel only, compose down, stop `model`, or stop VM — see **`AIC_TEARDOWN`** in `aic_cli.py`).

### Docker Compose stacks

```text
aic stack dev up|down|logs [--remote] [--sync-foxglove] [--ground-truth] [-- EXTRA_LOG_ARGS]
aic stack observability up|down|logs [--remote] [-- EXTRA_LOG_ARGS]
aic stack test up|down|logs [--remote] [-- EXTRA_LOG_ARGS]
```

- **`stack dev`** — [`compose/dev.compose.yaml`](../compose/dev.compose.yaml) (`aic_eval` + Foxglove sidecar).
- **`stack observability`** — [`compose/observability.compose.yaml`](../compose/observability.compose.yaml).
- **`stack test`** — repo-root [`docker/docker-compose.yaml`](../../docker/docker-compose.yaml) (eval + **model**; build/tag `my-solution:v1` as in that file).

 **`--remote`** runs `docker compose` on the VM over SSH (`AIC_VM_REPO_PATH`).

 **`--sync-foxglove`** forces pull/build so the Foxglove image matches `aic_eval` (install-tree skew; see foxglove docs).

### Diagnostics

```bash
platform/scripts/aic diag ros   # ROS graph — runs aic-healthcheck.sh
platform/scripts/aic diag host  # Host snapshot — runs aic-session-report.sh
```

### Isaac Lab

NVIDIA Isaac Lab runs as a separate training workflow from the Gazebo eval
stack. Setup is remote-only for the shared VM:

```bash
platform/scripts/aic vm up
platform/scripts/aic vm ssh 'bash -s' < platform/scripts/aic-isaac-setup.sh
platform/scripts/aic tunnel --isaac-foxglove
```

Then connect Foxglove to `ws://localhost:8766`. See
[`../docs/isaac_lab_workflow.md`](../docs/isaac_lab_workflow.md).

---

## Compatibility shims (deprecated names)

Older script names forward to **`aic`**:

| Script | Equivalent |
|--------|------------|
| `aic-vm-up.sh`, `aic-vm-down.sh`, `aic-vm-ssh.sh` | `aic vm …` |
| `aic-vm-observe.sh` | `aic tunnel` |
| `aic-foxglove-bridge.sh` | `aic stack dev up` |

---

## Scripts kept standalone

- [`aic-vm-bootstrap.sh`](aic-vm-bootstrap.sh), [`aic-vm-pull.sh`](aic-vm-pull.sh) — long-form VM setup (piped via `aic vm ssh`).
- [`aic-healthcheck.sh`](aic-healthcheck.sh), [`aic-session-report.sh`](aic-session-report.sh) — invoked via `aic diag`.

---

## Troubleshooting

| Issue | Try |
|--------|-----|
| `gcloud` auth | `gcloud auth login`, `gcloud config set project …` |
| SSH after start | Retry; wait for sshd (~10–30s) |
| `docker` denied on VM | Re-login SSH after bootstrap usermod |
| Foxglove disconnected | Tunnel running; containers up on VM; see [`../docs/foxglove_urdf_handoff.md`](../docs/foxglove_urdf_handoff.md) |
