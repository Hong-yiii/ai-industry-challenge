# Worklog

This document records what was reviewed and why the current platform design was chosen.

## Local Review

The following repo areas were reviewed first:

- challenge overview and getting started docs
- hardware evaluation report in `docs/hardware_eval_2026-04-23.md`
- bringup, teleoperation, policy, scoring, and submission docs
- Dockerfiles for `aic_eval` and `aic_model`
- training integrations for Gazebo, MuJoCo, Isaac Lab, and LeRobot

## Key Findings From Repo Review

- The existing local server is compatible but too slow for practical Gazebo throughput.
- The challenge already recommends a split between eval-in-container and model-from-host.
- `rmw_zenoh_cpp` and ROS 2 Kilted are not optional if the team wants predictable behavior.
- Shared result paths must be isolated because scoring files are overwritten by default.
- The policy and submission boundary is stable enough that the platform can optimize around it without guessing.

## External Research Areas

These external areas were researched to avoid building the wrong remote workflow:

- current GCP Compute Engine GPU machine families and access patterns
- browser-based and native remote visualization approaches that avoid X11 forwarding
- ROS observability with Foxglove
- monitoring stack components for host, container, and GPU visibility
- current SLURM container support and portability constraints

The strongest conclusions from that research were:

- do not depend on the deprecated Compute Engine container startup agent
- keep OCI images and direct commands as the runtime contract, not Docker Compose
- use Foxglove as the default observability surface
- defer remote desktop standardization until there is a clear non-Foxglove need

## Resulting Design Choices

### Chosen

- shared GCP GPU VM as the first remote dev node
- browser-first observability
- remote desktop only when RViz, Gazebo GUI, or keyboard teleop is needed
- per-user worktrees and per-run artifact directories
- OCI containers as the durable runtime boundary

### Explicitly not chosen

- X11 forwarding as the default interaction model
- one mutable shared repo checkout
- a GUI-only workflow
- Docker Compose as the only execution contract

## Why A Single `platform/` Directory

The request was to document everything and keep it in one top-level place if possible.

This directory centralizes:

- architecture
- operational runbooks
- monitoring config
- helper scripts

That keeps the workflow proposal out of the official challenge docs while still making it versioned and reviewable inside the repo.
