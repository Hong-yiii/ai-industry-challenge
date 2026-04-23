# Project Constraints

This summary captures the repo and challenge constraints that materially affect remote development, observability, and future HPC portability.

## Runtime Boundary

- The project is explicitly split into an organizer-side evaluation component and a participant-side model component.
- The evaluation stack includes `aic_engine`, `aic_bringup`, `aic_controller`, and `aic_adapter`.
- The submission target is a ROS 2 lifecycle node named `aic_model`.

Implication:

- Do not build a workflow that depends on editing the evaluation stack as part of the normal development loop.
- Optimize the remote setup around rapid iteration of the policy package, not around forking the evaluator.

## OS, ROS, and Middleware

- Official evaluation uses Ubuntu 24.04.
- Official evaluation uses ROS 2 Kilted Kaiju.
- The challenge requires `rmw_zenoh_cpp`.
- The eval side must start first because it launches the Zenoh router and the engine expects to discover `aic_model` quickly.

Implication:

- Standardize the remote environment on Ubuntu 24.04 + ROS 2 Kilted.
- Keep Zenoh configuration explicit in every run path.
- Avoid local-only workflows that rely on a different ROS distro.

## What Should Run Where

The repo’s preferred development split is:

- eval side in Docker
- policy side from host Pixi

Implication:

- The shared GCP box should preserve that split instead of forcing everything into one opaque container.
- For later SLURM portability, keep the policy runtime callable both as `pixi run ...` and as an OCI container entrypoint.

## Multi-Developer Concerns

- `pixi reinstall <package>` is required after package changes.
- `AIC_RESULTS_DIR/scoring.yaml` is overwritten on repeated runs unless each run gets its own directory.
- The hardware evaluation report in this repo shows the current server is far too slow for practical Gazebo throughput.

Implication:

- A shared machine must isolate developer worktrees and run outputs.
- Result paths must be unique by user and run.
- Smoke tests and full benchmarks should be separated operationally.

## Allowed and Forbidden Interfaces

- During evaluation, access to internal simulator control or backend state is restricted.
- Zenoh ACLs are part of that enforcement model.
- Ground truth is acceptable for training and debugging, but not for evaluation.

Implication:

- Dev tooling must make it easy to switch between `ground_truth:=true` debug runs and evaluation-faithful runs with ACLs enabled.
- Observability should focus on official ROS topics, logs, and host metrics rather than simulator internals.

## Training Portability

- Gazebo scenes can be exported to `/tmp/aic.sdf`.
- The repo already supports MuJoCo and Isaac Lab as alternate training environments.
- The same policy contract should remain valid at the submission boundary.

Implication:

- Keep scenario generation, policy training, and submission packaging as separate stages.
- Store scenarios, checkpoints, and metrics outside the interactive VM’s local state whenever possible.
