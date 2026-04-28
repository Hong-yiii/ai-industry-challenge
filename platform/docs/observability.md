# Observability

The user requirement here is clear: the system must not become opaque.

This design keeps observability in three layers:

1. ROS-level observability for topics, images, TF, actions, and controller state
2. Process-level observability for containers, CPU, RAM, and GPU usage
3. Run-level observability for logs, bags, scores, and training metrics

## Default Observation Surface

Most sessions should not require a full desktop.

Use these tools by default:

- Foxglove for ROS topics, images, TF, and graph inspection
- Prometheus + Grafana for host, Docker, and GPU metrics
- `ros2` CLI for targeted inspection and intervention
- per-run logs and result directories for postmortem analysis

Only open a remote desktop session when a developer truly needs:

- RViz rendering
- Gazebo GUI rendering
- keyboard teleoperation

## What To Monitor Continuously

### Host

- CPU utilization
- memory pressure
- disk space
- disk IO
- GPU utilization
- GPU memory

### Containers

- `aic_eval` CPU and RAM
- model process/container CPU and RAM
- container restart events
- per-run exit codes

### ROS

- `/clock` activity
- presence of `aic_model`
- presence of controller and adapter endpoints
- action server availability for `/insert_cable`
- controller state topics
- camera topic bandwidth

### Run artifacts

- scoring outputs
- rosbag or MCAP captures
- stdout and stderr logs
- training metrics
- checkpoints

## Browser-First Tooling

### Foxglove

Use Foxglove as the default live ROS UI.

What it gives you:

- camera streams
- TF tree and 3D visualization
- raw topic inspection
- plots for scalar topics
- sharable layouts

This should handle most “is the system alive?” and “what is the policy seeing?” questions without launching RViz.

Optional addition:

- `web_video_server` for low-friction browser access to image topics when someone only needs camera feeds and not the full Foxglove workspace

### Grafana

Use Grafana as the shared operational dashboard surface.

Recommended panels:

- host CPU, RAM, load, disk
- `aic_eval` container CPU and memory
- GPU utilization and VRAM
- top run directories by size
- most recent smoke test result

### Remote Desktop

Use a browser desktop only for:

- RViz
- Gazebo GUI
- keyboard teleop

Treat it as a scarce debugging seat, not as the default way to use the remote environment.

Current decision:

- Do not standardize a remote desktop stack yet.
- Use Foxglove as the interactive default and revisit desktop tooling only if required by specific debugging workflows.

## Health Checks

Two small repo-local scripts are included for day-to-day checks:

- [../scripts/aic-healthcheck.sh](../scripts/aic-healthcheck.sh)
- [../scripts/aic-session-report.sh](../scripts/aic-session-report.sh)

Typical use:

```bash
platform/scripts/aic-healthcheck.sh
platform/scripts/aic-session-report.sh
```

The first inspects ROS graph liveness. The second snapshots host, Docker, and GPU state.

## Run Isolation

Observability breaks down quickly on a shared machine if runs overwrite one another.

Always assign:

- a unique `AIC_RESULTS_DIR`
- a unique log path
- a unique bag path

Use:

```bash
export AIC_RESULTS_DIR="$(platform/scripts/aic-mk-results-dir.sh smoke)"
```

## Training Observability

For training, keep the stack simple and portable:

- TensorBoard now, with artifact layout prepared for MLflow adoption
- checkpoints stored outside ephemeral job directories
- system metrics collected the same way as eval runs

MLflow rollout is deferred, but run metadata should be structured so it can be onboarded later without reworking historical artifacts.

## Minimal Monitoring Stack

This directory includes an optional monitoring compose file:

- [../compose/observability.compose.yaml](../compose/observability.compose.yaml)
- [../monitoring/prometheus.yml](../monitoring/prometheus.yml)

It brings up:

- Prometheus
- Grafana
- node-exporter
- cAdvisor
- dcgm-exporter

This is intentionally generic. It can run on the GCP VM now and can later be re-pointed at SLURM nodes or login nodes.
