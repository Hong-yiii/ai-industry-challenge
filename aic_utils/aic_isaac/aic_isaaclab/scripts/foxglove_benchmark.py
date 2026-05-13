# Copyright (c) 2026, AI for Industry Challenge contributors.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Benchmark the AIC Isaac Lab task and optionally stream telemetry to Foxglove.

The script is intentionally middleware-light: Isaac Lab does not publish the AIC
ROS graph by default, so this uses the Foxglove SDK WebSocket server directly.
Connect Foxglove to ws://localhost:8766 after opening the SSH tunnel.
"""

from __future__ import annotations

"""Launch Isaac Sim before importing Isaac Lab runtime modules."""

import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="AIC Isaac Lab benchmark with optional Foxglove streaming.")
parser.add_argument("--task", type=str, default="AIC-Task-v0", help="Isaac Lab task name.")
parser.add_argument("--num_envs", type=int, default=1, help="Number of parallel environments.")
parser.add_argument("--steps", type=int, default=600, help="Measured simulation steps.")
parser.add_argument("--warmup", type=int, default=60, help="Warmup steps excluded from metrics.")
parser.add_argument("--agent", choices=("random", "zero"), default="random", help="Action source.")
parser.add_argument("--output-json", type=str, default="", help="Optional summary JSON path.")
parser.add_argument("--sync-cuda", action="store_true", help="Synchronize CUDA around measured steps.")
parser.add_argument(
    "--disable-cameras",
    action="store_true",
    help="Remove camera sensors and image observations for physics/control throughput runs.",
)
parser.add_argument("--foxglove", action="store_true", help="Start Foxglove SDK WebSocket server.")
parser.add_argument("--foxglove-host", type=str, default="127.0.0.1", help="Foxglove SDK bind host.")
parser.add_argument("--foxglove-port", type=int, default=8766, help="Foxglove SDK bind port.")
parser.add_argument("--foxglove-every", type=int, default=5, help="Publish every N measured steps.")
parser.add_argument("--keepalive-seconds", type=float, default=0.0, help="Keep Foxglove server open after run.")
parser.add_argument("--mcap", type=str, default="", help="Optional MCAP recording path.")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

"""Everything below runs after Isaac Sim is initialized."""

import json
import statistics
import time
from pathlib import Path
from typing import Any

import gymnasium as gym
import torch

import isaaclab_tasks  # noqa: F401
from isaaclab_tasks.utils import parse_env_cfg

import aic_task.tasks  # noqa: F401


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    idx = round((len(values) - 1) * pct)
    return sorted(values)[idx]


def _make_foxglove_channels() -> tuple[Any, Any, Any]:
    import foxglove
    from foxglove import Channel

    foxglove.set_log_level("WARNING")
    server = foxglove.start_server(
        name="aic-isaac-lab",
        host=args_cli.foxglove_host,
        port=args_cli.foxglove_port,
    )
    sysinfo = foxglove.start_sysinfo_publisher(topic="/isaac/sysinfo", refresh_interval=0.5)
    if args_cli.mcap:
        foxglove.open_mcap(args_cli.mcap, allow_overwrite=True)

    perf_schema = {
        "type": "object",
        "properties": {
            "step": {"type": "integer"},
            "step_hz": {"type": "number"},
            "env_step_hz": {"type": "number"},
            "rtf": {"type": "number"},
            "step_ms": {"type": "number"},
            "cuda_peak_allocated_mib": {"type": "number"},
        },
    }
    return server, sysinfo, Channel("/isaac/perf", schema=perf_schema)


def _disable_camera_observations(env_cfg: Any) -> None:
    for sensor_name in ("center_camera", "left_camera", "right_camera"):
        if hasattr(env_cfg.scene, sensor_name):
            setattr(env_cfg.scene, sensor_name, None)
    for obs_name in ("center_rgb", "left_rgb", "right_rgb"):
        if hasattr(env_cfg.observations.policy, obs_name):
            setattr(env_cfg.observations.policy, obs_name, None)


def _action_shape(env: gym.Env) -> tuple[int, ...]:
    shape = tuple(env.action_space.shape)
    if len(shape) == 1:
        return (env.unwrapped.num_envs, *shape)
    return shape


def _sample_actions(env: gym.Env) -> torch.Tensor:
    shape = _action_shape(env)
    if args_cli.agent == "zero":
        return torch.zeros(shape, device=env.unwrapped.device)
    return 2 * torch.rand(shape, device=env.unwrapped.device) - 1


def main() -> None:
    if args_cli.steps <= 0:
        raise ValueError("--steps must be positive")
    if args_cli.warmup < 0:
        raise ValueError("--warmup must be non-negative")

    env_cfg = parse_env_cfg(
        args_cli.task,
        device=args_cli.device,
        num_envs=args_cli.num_envs,
    )
    if args_cli.disable_cameras:
        _disable_camera_observations(env_cfg)
    env = gym.make(args_cli.task, cfg=env_cfg)
    env.reset()

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    foxglove_server = None
    foxglove_sysinfo = None
    perf_channel = None
    if args_cli.foxglove:
        foxglove_server, foxglove_sysinfo, perf_channel = _make_foxglove_channels()

    total_steps = args_cli.warmup + args_cli.steps
    measured_durations: list[float] = []
    measured_start = 0.0
    sim_dt = float(env_cfg.sim.dt * env_cfg.decimation)

    try:
        for step_idx in range(total_steps):
            actions = _sample_actions(env)
            if args_cli.sync_cuda and torch.cuda.is_available():
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            env.step(actions)
            if args_cli.sync_cuda and torch.cuda.is_available():
                torch.cuda.synchronize()
            step_s = time.perf_counter() - t0

            if step_idx == args_cli.warmup:
                measured_start = time.perf_counter()
            if step_idx >= args_cli.warmup:
                measured_durations.append(step_s)
                measured_count = len(measured_durations)
                wall_s = time.perf_counter() - measured_start
                if perf_channel is not None and measured_count % max(args_cli.foxglove_every, 1) == 0:
                    perf_channel.log(
                        {
                            "step": measured_count,
                            "step_hz": measured_count / wall_s,
                            "env_step_hz": (measured_count * args_cli.num_envs) / wall_s,
                            "rtf": (measured_count * sim_dt) / wall_s,
                            "step_ms": step_s * 1000.0,
                            "cuda_peak_allocated_mib": (
                                torch.cuda.max_memory_allocated() / (1024 * 1024)
                                if torch.cuda.is_available()
                                else 0.0
                            ),
                        }
                    )

        wall_seconds = time.perf_counter() - measured_start
        summary = {
            "task": args_cli.task,
            "agent": args_cli.agent,
            "num_envs": args_cli.num_envs,
            "warmup_steps": args_cli.warmup,
            "measured_steps": args_cli.steps,
            "wall_seconds": wall_seconds,
            "sim_dt_seconds": sim_dt,
            "step_hz": args_cli.steps / wall_seconds,
            "env_step_hz": (args_cli.steps * args_cli.num_envs) / wall_seconds,
            "rtf": (args_cli.steps * sim_dt) / wall_seconds,
            "mean_step_ms": statistics.fmean(measured_durations) * 1000.0,
            "median_step_ms": statistics.median(measured_durations) * 1000.0,
            "p95_step_ms": _percentile(measured_durations, 0.95) * 1000.0,
            "p99_step_ms": _percentile(measured_durations, 0.99) * 1000.0,
            "cuda_available": torch.cuda.is_available(),
            "cuda_peak_allocated_mib": (
                torch.cuda.max_memory_allocated() / (1024 * 1024) if torch.cuda.is_available() else 0.0
            ),
        }

        print(json.dumps(summary, indent=2, sort_keys=True))
        if args_cli.output_json:
            path = Path(args_cli.output_json)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args_cli.keepalive_seconds > 0:
            time.sleep(args_cli.keepalive_seconds)
    finally:
        if foxglove_sysinfo is not None:
            foxglove_sysinfo.stop()
        if foxglove_server is not None:
            foxglove_server.stop()
        env.close()


if __name__ == "__main__":
    try:
        main()
    finally:
        simulation_app.close()
