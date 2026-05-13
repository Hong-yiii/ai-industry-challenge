# Copyright (c) 2026, AI for Industry Challenge contributors.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Smoke-test AIC Isaac Lab cameras and optionally stream images to Foxglove."""

from __future__ import annotations

import argparse

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="AIC Isaac Lab headless camera smoke test.")
parser.add_argument("--task", type=str, default="AIC-Task-v0", help="Isaac Lab task name.")
parser.add_argument("--num_envs", type=int, default=1, help="Number of parallel environments.")
parser.add_argument("--steps", type=int, default=5, help="Measured simulation steps.")
parser.add_argument("--warmup", type=int, default=2, help="Warmup steps before metrics/images.")
parser.add_argument("--camera-height", type=int, default=224, help="Override task camera height.")
parser.add_argument("--camera-width", type=int, default=224, help="Override task camera width.")
parser.add_argument("--output-json", type=str, default="", help="Optional summary JSON path.")
parser.add_argument("--sync-cuda", action="store_true", help="Synchronize CUDA around measured steps.")
parser.add_argument("--foxglove", action="store_true", help="Start Foxglove SDK WebSocket server.")
parser.add_argument("--foxglove-host", type=str, default="127.0.0.1", help="Foxglove SDK bind host.")
parser.add_argument("--foxglove-port", type=int, default=8766, help="Foxglove SDK bind port.")
parser.add_argument("--foxglove-every", type=int, default=1, help="Publish images every N measured steps.")
parser.add_argument("--keepalive-seconds", type=float, default=0.0, help="Keep Foxglove server open after run.")
parser.add_argument("--mcap", type=str, default="", help="Optional MCAP recording path.")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

# Cameras are the point of this script. Match Isaac Lab's own camera benchmark behavior
# so the remote command is forgiving if --enable_cameras is omitted.
args_cli.enable_cameras = True

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

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

CAMERA_NAMES = ("center_camera", "left_camera", "right_camera")
CAMERA_OBSERVATION_NAMES = ("center_rgb", "left_rgb", "right_rgb")


def _disable_image_feature_observations(env_cfg: Any) -> None:
    """Keep cameras in the scene, but avoid ResNet feature extraction for this smoke test."""
    for obs_name in CAMERA_OBSERVATION_NAMES:
        if hasattr(env_cfg.observations.policy, obs_name):
            setattr(env_cfg.observations.policy, obs_name, None)


def _configure_camera_resolution(env_cfg: Any) -> None:
    for sensor_name in CAMERA_NAMES:
        sensor_cfg = getattr(env_cfg.scene, sensor_name, None)
        if sensor_cfg is not None:
            sensor_cfg.height = args_cli.camera_height
            sensor_cfg.width = args_cli.camera_width


def _action_shape(env: gym.Env) -> tuple[int, ...]:
    shape = tuple(env.action_space.shape)
    if len(shape) == 1:
        return (env.unwrapped.num_envs, *shape)
    return shape


def _zero_actions(env: gym.Env) -> torch.Tensor:
    return torch.zeros(_action_shape(env), device=env.unwrapped.device)


def _camera_sensor(env: gym.Env, name: str) -> Any:
    scene = env.unwrapped.scene
    try:
        return scene[name]
    except Exception:
        sensors = getattr(scene, "sensors", {})
        if name in sensors:
            return sensors[name]
        return getattr(scene, name)


def _camera_rgb(env: gym.Env, name: str) -> torch.Tensor | None:
    sensor = _camera_sensor(env, name)
    output = getattr(sensor.data, "output", {})
    rgb = output.get("rgb")
    return rgb if isinstance(rgb, torch.Tensor) else None


def _tensor_summary(tensor: torch.Tensor | None) -> dict[str, Any]:
    if tensor is None:
        return {"available": False}
    detached = tensor.detach()
    summary: dict[str, Any] = {
        "available": True,
        "shape": list(detached.shape),
        "dtype": str(detached.dtype),
        "device": str(detached.device),
    }
    if detached.numel() > 0:
        cpu = detached
        if cpu.is_cuda:
            cpu = cpu.cpu()
        summary["min"] = float(cpu.min().item())
        summary["max"] = float(cpu.max().item())
    return summary


def _as_raw_image(tensor: torch.Tensor, *, frame_id: str, env_index: int = 0) -> Any:
    from foxglove.messages import RawImage

    image = tensor.detach()
    if image.ndim == 4:
        image = image[env_index]
    if image.ndim != 3:
        raise ValueError(f"Expected HxWxC or NxHxWxC image tensor, got shape {tuple(tensor.shape)}")

    if image.is_cuda:
        image = image.cpu()
    if image.is_floating_point():
        max_value = float(image.max().item()) if image.numel() else 0.0
        if max_value <= 1.0:
            image = image * 255.0
        image = image.clamp(0, 255).to(torch.uint8)
    elif image.dtype != torch.uint8:
        image = image.clamp(0, 255).to(torch.uint8)

    image = image.contiguous()
    height, width, channels = image.shape
    if channels == 4:
        encoding = "rgba8"
    elif channels == 3:
        encoding = "rgb8"
    elif channels == 1:
        encoding = "mono8"
    else:
        raise ValueError(f"Unsupported channel count for Foxglove RawImage: {channels}")

    return RawImage(
        frame_id=frame_id,
        width=int(width),
        height=int(height),
        encoding=encoding,
        step=int(width * channels),
        data=image.numpy().tobytes(),
    )


def _make_foxglove_channels() -> tuple[Any, Any, dict[str, Any], Any]:
    import foxglove
    from foxglove import Channel
    from foxglove.channels import RawImageChannel

    foxglove.set_log_level("WARNING")
    server = foxglove.start_server(
        name="aic-isaac-cameras",
        host=args_cli.foxglove_host,
        port=args_cli.foxglove_port,
    )
    sysinfo = foxglove.start_sysinfo_publisher(topic="/isaac/sysinfo", refresh_interval=0.5)
    if args_cli.mcap:
        foxglove.open_mcap(args_cli.mcap, allow_overwrite=True)

    image_channels = {
        name: RawImageChannel(f"/isaac/cameras/{name}/image")
        for name in CAMERA_NAMES
    }
    perf_channel = Channel(
        "/isaac/camera_smoke/perf",
        schema={
            "type": "object",
            "properties": {
                "step": {"type": "integer"},
                "step_ms": {"type": "number"},
                "cuda_peak_allocated_mib": {"type": "number"},
            },
        },
    )
    return server, sysinfo, image_channels, perf_channel


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    idx = round((len(values) - 1) * pct)
    return sorted(values)[idx]


def main() -> None:
    if args_cli.steps <= 0:
        raise ValueError("--steps must be positive")
    if args_cli.warmup < 0:
        raise ValueError("--warmup must be non-negative")

    env = None
    foxglove_server = None
    foxglove_sysinfo = None

    try:
        t0 = time.perf_counter()
        env_cfg = parse_env_cfg(args_cli.task, device=args_cli.device, num_envs=args_cli.num_envs)
        _configure_camera_resolution(env_cfg)
        _disable_image_feature_observations(env_cfg)
        env = gym.make(args_cli.task, cfg=env_cfg)
        env.reset()
        startup_seconds = time.perf_counter() - t0

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()

        image_channels = {}
        perf_channel = None
        if args_cli.foxglove:
            foxglove_server, foxglove_sysinfo, image_channels, perf_channel = _make_foxglove_channels()

        durations: list[float] = []
        total_steps = args_cli.warmup + args_cli.steps
        for step_idx in range(total_steps):
            actions = _zero_actions(env)
            if args_cli.sync_cuda and torch.cuda.is_available():
                torch.cuda.synchronize()
            step_t0 = time.perf_counter()
            env.step(actions)
            if args_cli.sync_cuda and torch.cuda.is_available():
                torch.cuda.synchronize()
            step_s = time.perf_counter() - step_t0

            if step_idx >= args_cli.warmup:
                durations.append(step_s)
                measured_step = len(durations)
                if perf_channel is not None and measured_step % max(args_cli.foxglove_every, 1) == 0:
                    perf_channel.log(
                        {
                            "step": measured_step,
                            "step_ms": step_s * 1000.0,
                            "cuda_peak_allocated_mib": (
                                torch.cuda.max_memory_allocated() / (1024 * 1024)
                                if torch.cuda.is_available()
                                else 0.0
                            ),
                        }
                    )
                    for camera_name, channel in image_channels.items():
                        rgb = _camera_rgb(env, camera_name)
                        if rgb is not None:
                            channel.log(_as_raw_image(rgb, frame_id=camera_name))

        camera_summaries = {
            camera_name: _tensor_summary(_camera_rgb(env, camera_name))
            for camera_name in CAMERA_NAMES
        }
        wall_seconds = sum(durations)
        summary = {
            "task": args_cli.task,
            "num_envs": args_cli.num_envs,
            "camera_height": args_cli.camera_height,
            "camera_width": args_cli.camera_width,
            "warmup_steps": args_cli.warmup,
            "measured_steps": args_cli.steps,
            "startup_seconds": startup_seconds,
            "measured_wall_seconds": wall_seconds,
            "step_hz": args_cli.steps / wall_seconds if wall_seconds > 0 else 0.0,
            "mean_step_ms": statistics.fmean(durations) * 1000.0 if durations else 0.0,
            "median_step_ms": statistics.median(durations) * 1000.0 if durations else 0.0,
            "p95_step_ms": _percentile(durations, 0.95) * 1000.0,
            "p99_step_ms": _percentile(durations, 0.99) * 1000.0,
            "cuda_available": torch.cuda.is_available(),
            "cuda_peak_allocated_mib": (
                torch.cuda.max_memory_allocated() / (1024 * 1024) if torch.cuda.is_available() else 0.0
            ),
            "cameras": camera_summaries,
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
        if env is not None:
            env.close()


if __name__ == "__main__":
    try:
        main()
    finally:
        simulation_app.close()
