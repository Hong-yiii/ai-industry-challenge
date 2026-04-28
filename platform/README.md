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

- [docs/vm_instance.md](./docs/vm_instance.md): **provisioned instance record** — actual specs, cost estimates, and lifecycle scripts
- [docs/project_constraints.md](./docs/project_constraints.md): repo and challenge constraints that shaped the design
- [docs/gcp_shared_devflow.md](./docs/gcp_shared_devflow.md): the proposed shared GCP development flow
- [docs/observability.md](./docs/observability.md): what to monitor and how to keep the system observable
- [docs/slurm_portability.md](./docs/slurm_portability.md): how to keep the GCP workflow portable to SLURM
- [docs/approval_needed.md](./docs/approval_needed.md): decisions that should be approved before provisioning
- [docs/worklog.md](./docs/worklog.md): what was reviewed and why the recommendations landed here
- [docs/reference_links.md](./docs/reference_links.md): external references consulted for GCP, observability, and SLURM portability
- [slurm/train.sbatch.example](./slurm/train.sbatch.example): example train job shape for a containerized workflow
- [slurm/eval.sbatch.example](./slurm/eval.sbatch.example): example eval job shape for a containerized workflow
- [compose/observability.compose.yaml](./compose/observability.compose.yaml): optional monitoring stack
- [monitoring/prometheus.yml](./monitoring/prometheus.yml): Prometheus scrape config for the monitoring stack
- [scripts/aic-vm-config.env](./scripts/aic-vm-config.env): shared project/zone variables for VM scripts
- [scripts/aic-vm-up.sh](./scripts/aic-vm-up.sh): start the GCP dev VM
- [scripts/aic-vm-down.sh](./scripts/aic-vm-down.sh): stop the GCP dev VM (disk preserved)
- [scripts/aic-vm-ssh.sh](./scripts/aic-vm-ssh.sh): SSH into the dev VM via gcloud
- [scripts/aic-vm-bootstrap.sh](./scripts/aic-vm-bootstrap.sh): one-time VM setup (NVIDIA driver, Docker, nvidia-ctk, Pixi, repo clone)
- [scripts/aic-vm-pull.sh](./scripts/aic-vm-pull.sh): post-reboot image pull and smoke test
- [scripts/aic-prepare-worktree.sh](./scripts/aic-prepare-worktree.sh): create or refresh a per-user remote worktree
- [scripts/aic-mk-results-dir.sh](./scripts/aic-mk-results-dir.sh): create a unique `AIC_RESULTS_DIR`
- [scripts/aic-healthcheck.sh](./scripts/aic-healthcheck.sh): inspect ROS graph and simulator liveness
- [scripts/aic-session-report.sh](./scripts/aic-session-report.sh): snapshot host, Docker, and GPU state

## Practical Recommendation

If you want the shortest path that satisfies the stated requirements:

1. Provision a single Ubuntu 24.04 GCP GPU VM on the G2 series.
2. Keep one shared base checkout plus per-user `git worktree` directories.
3. Run Gazebo headless by default and only open a remote desktop session when a developer actually needs GUI debugging or teleop.
4. Treat Foxglove and Grafana as always-on shared services.
5. Keep training and evaluation entrypoints containerized so they can later move to Slurm with minimal workflow changes.

For the remote desktop path:

- paid/polished path: Amazon DCV
- open-source path: TurboVNC + VirtualGL, optionally exposed through noVNC
