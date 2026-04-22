# Intrinsic AIC Hardware Evaluation

Date: 2026-04-23  
Host: remote Ubuntu 24.04 box over Tailscale  
Repo: `/home/hongyi-home-lab/ai-industry-challenge`

## Summary

The Intrinsic AIC eval stack does start on this machine, and all three example policies can be discovered and activated from the host Pixi environment. The limiting factor is not basic compatibility. It is simulation throughput.

On this server, Gazebo advances at roughly `0.85%` of real time once the trial starts. Across `WaveArm`, `CheatCode`, and `RunACT`, the engine consistently reaches:

1. eval container startup
2. model discovery
3. lifecycle configure
4. lifecycle activate
5. task board and cable spawn
6. `Waiting for robot arm to stabilize.`

It then effectively stalls because simulator time is barely moving. No scoring files were produced during the 5-minute benchmark windows.

## Hardware

- CPU: `AMD Ryzen 5 2600`, `6 cores / 12 threads`
- RAM: `15 GiB`
- GPU: `NVIDIA GeForce RTX 2070`, `8 GiB VRAM`
- NVIDIA driver: `580.126.09`

At benchmark time:

- Host free memory stayed above roughly `3.8 GiB`
- Swap was mostly unused
- Docker GPU passthrough was working correctly

## What Was Tested

Preferred supported topology:

- Eval: Docker container
- Model: host `pixi run`
- Middleware: `rmw_zenoh_cpp`
- Transport: Zenoh TCP to `127.0.0.1:7447`

Per-demo workflow:

```bash
docker run -d --name aic_eval_<demo> -p 7447:7447 --gpus all \
  -e AIC_RESULTS_DIR=/results \
  -v /tmp/aic_hostpixi/<demo>/results:/results \
  ghcr.io/intrinsic-dev/aic/aic_eval:latest \
  gazebo_gui:=false launch_rviz:=false ground_truth:=<true|false> \
  start_aic_engine:=true shutdown_on_aic_engine_exit:=true \
  model_discovery_timeout_seconds:=600

RMW_IMPLEMENTATION=rmw_zenoh_cpp \
ZENOH_ROUTER_CHECK_ATTEMPTS=-1 \
ZENOH_CONFIG_OVERRIDE='connect/endpoints=["tcp/127.0.0.1:7447"];transport/shared_memory/enabled=false' \
~/.pixi/bin/pixi run --as-is ros2 run aic_model aic_model \
  --ros-args -p use_sim_time:=true -p policy:=<policy>
```

Telemetry was sampled at `1 Hz` from:

- `docker stats` for the eval container
- `ps` for the host-side `aic_model` process tree
- `nvidia-smi` for GPU utilization and VRAM

## Results

| Demo | Ground Truth | Wall Window | Sim Clock Reached | Approx. Real-Time Factor | Eval CPU Avg / Max | Eval RAM Avg / Max | Model CPU Avg / Max | Model RSS Avg / Max | GPU Util Avg / Max | GPU VRAM Avg / Max | Outcome |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `WaveArm` | `false` | `302 s` | `2.552 s` | `0.0085` | `994% / 1196%` | `2.76 / 5.43 GiB` | `2.64% / 38.2%` | `343 / 456 MiB` | `0% / 0%` | `15 / 15 MiB` | Activated, spawned scene, then stalled at stabilization |
| `CheatCode` | `true` | `307 s` | `2.602 s` | `0.0085` | `975% / 1193%` | `2.59 / 5.19 GiB` | `4.23% / 180%` | `321 / 430 MiB` | `0% / 0%` | `15 / 15 MiB` | Activated, spawned scene, then stalled at stabilization |
| `RunACT` | `false` | `305 s` | `2.652 s` | `0.0087` | `969% / 1183%` | `2.28 / 5.26 GiB` | `21.24% / 174%` | `1212 / 1536 MiB` | `0.01% / 1%` | `188 / 344 MiB` | Activated, loaded ACT model on CUDA, then stalled at stabilization |

## Key Learnings

- The machine is functionally compatible with the Intrinsic stack, but not operationally fast enough for practical evaluation.
- The dominant bottleneck is CPU-side Gazebo simulation throughput, not NVIDIA setup, Docker, or basic dependency health.
- The eval container alone is heavy enough to saturate most of the available CPU budget on this host.
- GPU headroom exists, but Gazebo headless evaluation does not materially consume it on this setup.
- `RunACT` can successfully initialize on CUDA here, but model acceleration does not matter when the simulator is advancing at less than `1%` of real time.
- For this hardware class, smoke testing is realistic, but full local evaluation and performance comparison are not.

## Demo-Specific Notes

- `WaveArm` had the lightest model-side footprint. It is the best candidate for basic connectivity and lifecycle smoke tests.
- `CheatCode` did not materially change simulator throughput relative to `WaveArm`, which reinforces that the simulator is the limiting stage.
- `RunACT` showed the only meaningful GPU memory use and the highest model RSS, but the overall run still stalled in the same place as the simpler policies.
- All three demos converged on the same failure mode: successful initialization followed by extremely slow progress once the simulator had to execute the full scene.

## Interpretation

### What works

- NVIDIA on the host is fixed and usable.
- Docker GPU passthrough works.
- The eval container starts reliably.
- Host `pixi` policies can connect to the eval router.
- `RunACT` successfully loads its model on `cuda`.

### What does not work well

- Gazebo is overwhelmingly CPU-bound on this hardware.
- The eval container alone consumes roughly `9.7` to `10.0` CPU cores on average.
- Simulator time advances only about `2.6 s` during a `5 minute` wall-clock window.
- Because the simulator barely advances, the engine never gets past early trial readiness and no benchmark scoring completes.

### GPU behavior

- Gazebo did not meaningfully use the RTX 2070 in these runs.
- Headless eval runs stayed at effectively `0%` GPU utilization.
- `RunACT` did use CUDA memory and a small amount of GPU compute, but the dominant bottleneck was still the simulator on CPU.

## Screenshot

Gazebo GUI capture saved here:

- [`docs/assets/gazebo_xvfb_2026-04-23.png`](./assets/gazebo_xvfb_2026-04-23.png)

Notes:

- The GUI was launched successfully inside `Xvfb`.
- The window was present and viewable as `Gazebo Sim` at `1200x1000`.
- The captured viewport is mostly black. The Gazebo chrome is present, but the 3D scene did not render usefully through this virtual-display setup.

## Artifacts

Temporary benchmark artifacts:

- `/tmp/aic_hostpixi/wavearm/telemetry.csv`
- `/tmp/aic_hostpixi/wavearm/model.log`
- `/tmp/aic_hostpixi/cheatcode/telemetry.csv`
- `/tmp/aic_hostpixi/cheatcode/model.log`
- `/tmp/aic_hostpixi/cheatcode/eval.log`
- `/tmp/aic_hostpixi/cheatcode/clock.txt`
- `/tmp/aic_hostpixi/runact/telemetry.csv`
- `/tmp/aic_hostpixi/runact/model.log`
- `/tmp/aic_hostpixi/runact/eval.log`
- `/tmp/aic_hostpixi/runact/clock.txt`

## Conclusion

This server is compatible enough to boot the Intrinsic eval environment and load the provided demos, including CUDA-backed `RunACT`. It is not performant enough to run the simulation at a practical speed.

The hard limit on this machine is the CPU side of Gazebo and the physics/render stack, not basic dependency setup and not Docker GPU support.

For usable demo runs, the practical next steps are:

- move the eval container to a significantly faster CPU
- or run on a machine with materially higher single-thread and multi-core simulation performance
- optionally test whether disabling some camera streams or lowering sim fidelity is possible, though this repo does not expose an obvious low-fidelity benchmark mode

If this host must remain in use, the most realistic local workflow is:

- use `WaveArm` for smoke tests only
- keep all runs headless
- avoid treating local wall-clock timings as meaningful
- create a separate low-fidelity dev profile for cameras, GI, and controller frequency
- reserve full-fidelity benchmarking for a faster machine

With the current `Ryzen 5 2600 + 15 GiB RAM + RTX 2070` box, the demos initialize but do not progress through trials at a usable rate.
