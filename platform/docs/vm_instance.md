# AIC Dev VM — Provisioned Instance Record

This document records the actual GCP instance that has been provisioned for the AIC project.
It is the authoritative reference for the current hardware shape, cost expectations, and operational scripts.

## Instance Summary

| Field            | Value                          |
|------------------|-------------------------------|
| **Name**         | `aic-dev`                     |
| **Project**      | `ai-for-industry`             |
| **Region/Zone**  | `asia-southeast1-a` (Singapore) |
| **Machine type** | `g2-standard-8`               |
| **vCPU**         | 8 (Intel Cascade Lake)        |
| **RAM**          | 32 GB                         |
| **GPU**          | 1× NVIDIA L4 (24 GB VRAM)     |
| **OS**           | Ubuntu 24.04 LTS (x86/64)     |
| **Boot disk**    | 150 GB balanced persistent disk |
| **Provisioning** | **Spot** (preemptible)        |
| **Network**      | Default VPC, Premium external NAT |

## Why This Shape

The challenge eval environment runs on 64 vCPU / 256 GiB RAM / 1× NVIDIA L4.
`g2-standard-8` is a deliberately undersized but cost-effective dev node for policy
iteration — a full 1:1 eval-env replica is not needed until submission smoke tests.

Key matches:
- GPU type (NVIDIA L4) is identical to the eval environment
- 24 GB VRAM is enough to iterate on inference workloads
- 8 vCPUs and 32 GB RAM are enough for headless Gazebo + policy node concurrently

If Gazebo becomes a throughput bottleneck, step up to `g2-standard-16` or `g2-standard-32`
before changing region or GPU type.

## Storage

| Volume             | Type                   | Size   | Persists when stopped? |
|--------------------|------------------------|--------|------------------------|
| Boot disk (`aic-dev`) | Balanced persistent disk | 150 GB | Yes                  |

150 GB is intentional headroom for:
- Ubuntu base + Docker + NVIDIA drivers (~8–10 GB)
- Docker image cache for `aic_eval` and related containers (~30–50 GB)
- Pixi / pip caches
- Short-lived run artifacts and rosbags before archiving to Cloud Storage

Cloud Storage is the durable archive tier for longer-term artifact retention.

## Cost Estimates

Pricing is Spot (preemptible) in `asia-southeast1`. Spot rates fluctuate;
these figures come from the GCP cost estimator at provisioning time.

### Per-resource Spot rates (monthly if running 24/7)

| Resource                    | Monthly estimate |
|-----------------------------|-----------------|
| 8 vCPU + 32 GB (Spot)       | ~$85.75         |
| 1× NVIDIA L4 (Spot)         | ~$162.86        |
| 150 GB balanced disk        | ~$15.00         |
| **Total (24/7)**            | **~$263/month** |

### Hourly approximation

~$0.36/hr when the VM is running.

### Realistic active-dev cost

The VM is stopped when not in use. Disk cost is always-on; compute only accrues while running.

| Dev hours/day | Est. compute/month | + Disk | Total/month |
|--------------|-------------------|--------|-------------|
| 2 hrs        | ~$22              | $15    | ~$37        |
| 4 hrs        | ~$43              | $15    | ~$58        |
| 8 hrs        | ~$87              | $15    | ~$102       |

**Always stop the VM when done.** Use `platform/scripts/aic-vm-down.sh`.

### Spot preemption

GCP may reclaim a Spot VM with 30 seconds notice. The instance action on preemption is
`STOP` (not delete), so the disk and IP reservation are retained. Simply re-run
`aic-vm-up.sh` to restart. The external IP may change on each start.

## Lifecycle Scripts

All scripts live in `platform/scripts/` and source their config from
`platform/scripts/aic-vm-config.env`.

```bash
# Start the VM (prints current external IP)
platform/scripts/aic-vm-up.sh

# SSH in (use this — browser SSH is unreliable due to OAuth loop)
platform/scripts/aic-vm-ssh.sh

# Run a single remote command without an interactive shell
platform/scripts/aic-vm-ssh.sh -- docker ps

# Stop the VM (disk preserved; compute billing stops)
platform/scripts/aic-vm-down.sh
```

Override project/zone without editing files:

```bash
AIC_VM_ZONE=asia-southeast1-b platform/scripts/aic-vm-up.sh
```

## Access

- **SSH**: `gcloud compute ssh` via `aic-vm-ssh.sh` (preferred)
- **Browser SSH**: Available in the GCP console but prone to OAuth loop hangs; use only as a fallback
- **External IP**: Dynamic on each start (printed by `aic-vm-up.sh`); last known value was `34.143.177.7`
- **Internal IP**: `10.148.0.2` (stable within the VPC)

## One-Time Setup

Run this from your local machine to bootstrap the VM.
The process takes ~5 minutes and requires one reboot.

### Phase 1 — bootstrap (installs everything)

```bash
platform/scripts/aic-vm-up.sh
platform/scripts/aic-vm-ssh.sh -- 'bash -s' < platform/scripts/aic-vm-bootstrap.sh
```

This installs:
- NVIDIA GPU driver 550 (via CUDA network repo)
- Docker Engine + post-install user group setup
- NVIDIA Container Toolkit + Docker runtime configuration
- Pixi
- `/srv/aic/` working directory layout
- Clones the challenge repo to `/srv/aic/repo`

### Phase 2 — reboot

```bash
platform/scripts/aic-vm-down.sh   # clean shutdown
platform/scripts/aic-vm-up.sh     # start again (driver active after reboot)
```

### Phase 3 — pull images and verify

```bash
platform/scripts/aic-vm-ssh.sh -- 'bash -s' < platform/scripts/aic-vm-pull.sh
```

This verifies `nvidia-smi`, tests Docker GPU passthrough, pulls
`ghcr.io/intrinsic-dev/aic/aic_eval:latest` (~10 GB), runs `pixi install`,
and does a quick container smoke test.

## Current Decisions Snapshot

- Access model: `IAP + OS Login + tunneled services`
- Interactive surface: `Foxglove` as default; remote desktop deferred
- Storage: `Persistent Disk + Cloud Storage`
- Scope: `single interactive VM`
- Experiment tracking: deferred, with preliminary MLflow preparation
