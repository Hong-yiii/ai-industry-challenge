# Platform Dev Flow

This directory defines a shared remote development and observability workflow for the AI for Industry Challenge project.

It is designed around three constraints from the repo and challenge docs:

1. The official submission boundary is a ROS 2 Kilted `aic_model` lifecycle node.
2. The evaluation stack is heavy enough that shared remote infrastructure is more realistic than asking every engineer to run Gazebo locally.
3. Training and evaluation workflows should stay portable to a later SLURM-based HPC environment.

## Recommended Architecture

Use one shared GCP GPU VM as the interactive development backend, and keep the runtime split that the challenge already recommends:

- `aic_eval` runs remotely in Docker and owns Gazebo, RViz, controllers, sensors, and `aic_engine`.
- Policy code lives in Git and is tested from a per-user remote worktree with Pixi or a model container.
- Observability is browser-first:
  - Foxglove for ROS topics, images, TF, and live debugging.
  - Prometheus + Grafana for host, container, and GPU metrics.
  - A remote desktop path only for the cases that genuinely need RViz, Gazebo GUI, or keyboard teleop.
- Artifacts are isolated per run so a shared machine does not overwrite previous results.

## What Is In Here

- [docs/aic_platform_workflow.md](./docs/aic_platform_workflow.md): end-to-end map of **`aic`**, VMs, Compose, tunnels, and policy execution (Pixi vs **`model`**, Zenoh topology)
- [docs/vm_instance.md](./docs/vm_instance.md): **provisioned instance record** — actual specs, cost estimates, and lifecycle scripts
- [docs/project_constraints.md](./docs/project_constraints.md): repo and challenge constraints that shaped the design
- [docs/gcp_shared_devflow.md](./docs/gcp_shared_devflow.md): the proposed shared GCP development flow
- [docs/observability.md](./docs/observability.md): what to monitor and how to keep the system observable
- [docs/slurm_portability.md](./docs/slurm_portability.md): how to keep the GCP workflow portable to SLURM
- [docs/worklog.md](./docs/worklog.md): historical design audit trail (see also [project_constraints.md](./docs/project_constraints.md))
- [docs/foxglove_urdf_handoff.md](./docs/foxglove_urdf_handoff.md): Foxglove web + bridge — URDF topic `/robot_description_foxglove` and troubleshooting
- [docs/isaac_lab_workflow.md](./docs/isaac_lab_workflow.md): remote NVIDIA Isaac Lab setup, benchmark, and Foxglove SDK streaming
- [docs/reference_links.md](./docs/reference_links.md): external references consulted for GCP, observability, and SLURM portability
- [slurm/train.sbatch.example](./slurm/train.sbatch.example): example train job shape for a containerized workflow
- [slurm/eval.sbatch.example](./slurm/eval.sbatch.example): example eval job shape for a containerized workflow
- [compose/dev.compose.yaml](./compose/dev.compose.yaml): eval + Foxglove bridge only (lighter than the full platform stack)
- [compose/observability.compose.yaml](./compose/observability.compose.yaml): includes dev stack (eval + Foxglove bridge) **and** Prometheus + Grafana + GPU/container metrics
- [compose/full.compose.yaml](./compose/full.compose.yaml): same services as observability compose, Compose project name `aic-platform` for a single default “bring everything up” entrypoint
- [docker/Dockerfile.foxglove](./docker/Dockerfile.foxglove): Foxglove bridge sidecar image (extends `aic_eval`)
- [monitoring/prometheus.yml](./monitoring/prometheus.yml): Prometheus scrape config for the monitoring stack
- [monitoring/grafana/provisioning/](./monitoring/grafana/provisioning): Grafana datasource and provisioning (mounted by observability compose)
- [scripts/aic](./scripts/aic): unified dev CLI (**`vm`** / **`tunnel`** / **`stack`** / **`dev`** / **`diag`**) — see [scripts/README.md](./scripts/README.md)
- [scripts/aic_cli.py](./scripts/aic_cli.py): Python implementation invoked by **`aic`**
- [scripts/aic-vm-config.env](./scripts/aic-vm-config.env): GCP project/zone/name and optional **`AIC_VM_REPO_PATH`**
- [scripts/aic-vm-up.sh](./scripts/aic-vm-up.sh) … [scripts/aic-foxglove-bridge.sh](./scripts/aic-foxglove-bridge.sh): thin **compatibility shims** that delegate to **`aic`**
- [scripts/aic-vm-bootstrap.sh](./scripts/aic-vm-bootstrap.sh): one-time VM setup (NVIDIA driver, Docker, nvidia-ctk, Pixi, repo clone; pipe via **`aic vm ssh`**)
- [scripts/aic-vm-pull.sh](./scripts/aic-vm-pull.sh): post-reboot image pull / smoke (**pipe via `aic vm ssh`**)
- [scripts/aic-isaac-setup.sh](./scripts/aic-isaac-setup.sh): remote Isaac Lab setup, assets, container start, and Foxglove SDK dependencies
- [scripts/aic-healthcheck.sh](./scripts/aic-healthcheck.sh): inspect ROS graph and simulator liveness
- [scripts/aic-session-report.sh](./scripts/aic-session-report.sh): snapshot host, Docker, and GPU state
- [scripts/README.md](./scripts/README.md): script usage guide with examples and troubleshooting

## Practical Recommendation

If you want the shortest path that satisfies the stated requirements:

1. Provision a single Ubuntu 24.04 GCP GPU VM on the G2 series.
2. Keep one shared base checkout plus per-user `git worktree` directories.
3. Run Gazebo headless by default and only open a remote desktop session when a developer actually needs GUI debugging or teleop.
4. Treat Foxglove and Grafana as always-on shared services.
5. Keep training and evaluation entrypoints containerized so they can later move to Slurm with minimal workflow changes.
