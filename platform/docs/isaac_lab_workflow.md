# Isaac Lab remote workflow

This workflow mirrors the platform Gazebo/Foxglove flow, but uses NVIDIA Isaac
Lab as the simulator and the Foxglove SDK as the live data bridge.

Isaac Lab does not publish the AIC ROS graph by default. The provided bridge
therefore streams benchmark telemetry directly to Foxglove on a separate
WebSocket port, `8766`, so it can run alongside the existing Gazebo
`foxglove_bridge` on `8765`.

## Remote setup

From the laptop, start the shared VM and run the Isaac setup helper:

```bash
platform/scripts/aic vm up
platform/scripts/aic vm ssh 'bash -s' < platform/scripts/aic-isaac-setup.sh
```

The helper creates this VM layout:

```text
/srv/aic/isaac/
  IsaacLab/                 # Isaac Lab checkout, default v2.3.2
    aic/                    # AIC checkout mounted into the container
    docker/docker-compose.aic.patch.yaml
  Intrinsic_assets.zip
```

It also downloads the NVIDIA `Intrinsic_assets` pack, writes
`docker/.container.cfg` with X11 disabled for headless SSH runs, starts the
`isaac-lab-base` container, installs Isaac Lab into the live container, applies
the `flatdict` no-build-isolation workaround needed by Isaac Lab 2.3.x, installs
`foxglove-sdk`, and installs `aic_task` in editable mode.

Useful overrides:

```bash
AIC_ISAAC_LAB_TAG=v2.3.2 \
AIC_REPO_URL=https://github.com/Hong-yiii/ai-industry-challenge.git \
platform/scripts/aic vm ssh 'bash -s' < platform/scripts/aic-isaac-setup.sh
```

## Run a benchmark

Run the physics/control benchmark inside the Isaac Lab container:

```bash
platform/scripts/aic vm ssh 'cd /srv/aic/isaac/IsaacLab && ./docker/container.py start base --files docker-compose.aic.patch.yaml'

platform/scripts/aic vm ssh \
  'docker exec isaac-lab-base bash -lc "cd /workspace/isaaclab && ./isaaclab.sh -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/foxglove_benchmark.py --headless --disable-cameras --sync-cuda --task AIC-Task-v0 --num_envs 1 --steps 600 --warmup 60 --foxglove --foxglove-port 8766 --keepalive-seconds 300 --output-json /workspace/isaaclab/logs/aic_isaac_benchmark.json"'
```

The summary JSON reports wall time, step Hz, aggregate env-step Hz, estimated
real-time factor, step latency percentiles, and CUDA peak allocation.

The task has three tiled cameras in its default observation config. For full
camera observations, remove `--disable-cameras` and add `--enable_cameras`.
On the shared L4 VM, first camera-enabled startup can spend several minutes in
RTX shader compilation before any measured steps run.

## Test cameras

Use a camera-first smoke before full policy/training runs. It keeps the AIC task
cameras in the scene, temporarily removes only the ResNet image-feature
observation terms, and checks the raw RGB tensors from `center_camera`,
`left_camera`, and `right_camera`.

Start small to validate the headless renderer and Foxglove image transport:

```bash
platform/scripts/aic vm ssh \
  'docker exec isaac-lab-base bash -lc "cd /workspace/isaaclab && timeout 600 ./isaaclab.sh -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/camera_smoke.py --headless --enable_cameras --rendering_mode performance --task AIC-Task-v0 --num_envs 1 --camera-height 64 --camera-width 64 --steps 5 --warmup 2 --sync-cuda --foxglove --foxglove-port 8766 --keepalive-seconds 300 --output-json /workspace/isaaclab/logs/aic_camera_smoke_64.json"'
```

Then repeat at the task's default camera resolution:

```bash
platform/scripts/aic vm ssh \
  'docker exec isaac-lab-base bash -lc "cd /workspace/isaaclab && timeout 900 ./isaaclab.sh -p aic/aic_utils/aic_isaac/aic_isaaclab/scripts/camera_smoke.py --headless --enable_cameras --rendering_mode performance --task AIC-Task-v0 --num_envs 1 --camera-height 224 --camera-width 224 --steps 20 --warmup 5 --sync-cuda --foxglove --foxglove-port 8766 --keepalive-seconds 300 --output-json /workspace/isaaclab/logs/aic_camera_smoke_224.json"'
```

Camera topics in Foxglove:

- `/isaac/cameras/center_camera/image`
- `/isaac/cameras/left_camera/image`
- `/isaac/cameras/right_camera/image`
- `/isaac/camera_smoke/perf`

Once raw camera tensors are healthy, run `foxglove_benchmark.py` without
`--disable-cameras` to test the full observation stack with image features.

## Open Foxglove

In a second laptop terminal:

```bash
platform/scripts/aic tunnel --isaac-foxglove
```

Then open [Foxglove](https://app.foxglove.dev), choose **Open connection**,
select **Foxglove WebSocket**, and connect to:

```text
ws://localhost:8766
```

If the hosted Foxglove app redirects to sign-in, log in or use Foxglove
Desktop. The server/tunnel can still be verified with the low-level probe below.

The current Foxglove SDK WebSocket subprotocol is `foxglove.sdk.v1`; the
Foxglove app handles this automatically. A low-level transport probe from the
laptop can verify the tunnel without the app:

```bash
node - <<'NODE'
const ws = new WebSocket("ws://localhost:8766", "foxglove.sdk.v1");
ws.addEventListener("open", () => console.log(`open ${ws.protocol}`));
ws.addEventListener("message", async (event) => {
  const data = event.data instanceof Blob ? Buffer.from(await event.data.arrayBuffer()) : Buffer.from(event.data);
  console.log(`message bytes=${data.length}`);
  ws.close();
});
NODE
```

Recommended panels:

- **Image** for `/isaac/cameras/center_camera/image`,
  `/isaac/cameras/left_camera/image`, or `/isaac/cameras/right_camera/image`
  during `camera_smoke.py` runs.
- **Raw Messages** for `/isaac/perf`.
- **Plot** for `/isaac/perf.rtf`, `/isaac/perf.step_hz`, and `/isaac/perf.env_step_hz`.
- **Raw Messages** for `/isaac/sysinfo`.

## Observed aic-dev performance

Measured on the shared `aic-dev` GCP `g2-standard-8` VM with an NVIDIA L4
24 GB GPU, Isaac Lab 2.3.2 / Isaac Sim 5.1, random actions, `--disable-cameras`,
and `--sync-cuda`.

| Envs | Steps | Step Hz | Env-step Hz | RTF | Mean step ms | p95 step ms |
|------|-------|---------|-------------|-----|--------------|-------------|
| 1 | 300 | 12.58 | 12.58 | 0.42 | 79.59 | 89.19 |
| 2 | 200 | 11.15 | 22.29 | 0.37 | 89.88 | 99.88 |
| 4 | 150 | 10.94 | 43.76 | 0.36 | 91.68 | 103.68 |

Use the 1-env result as the conservative correctness baseline. Multi-env runs
increase aggregate throughput, but Isaac/PhysX logs a rope collision-group
replication warning for this task, so validate task semantics before using
multi-env numbers for training decisions.

Camera smoke results, using the AIC task's three tiled RGB cameras with ResNet
image-feature observations temporarily disabled:

| Camera size | Steps | Startup s | Step Hz | Mean step ms | p95 step ms | Tensor shape |
|-------------|-------|-----------|---------|--------------|-------------|--------------|
| 64x64 | 5 | 42.23 | 11.01 | 90.87 | 96.48 | `[1, 64, 64, 3]` |
| 224x224 | 20 | 9.61 | 11.33 | 88.25 | 91.66 | `[1, 224, 224, 3]` |

The first camera run pays the heaviest RTX/render cache warmup. Later runs on
the same VM start much faster.

Known runtime warnings:

- The asset pack references several `.glb:SDF_FORMAT_ARGS:target=usd` visual
  assets that Isaac logs as unavailable; physics still starts and steps.
- The robot asset has 46 joints but only 6 configured actuators, matching the
  arm action space.
- Camera-enabled runs require `--enable_cameras`; without it, Isaac raises a
  tiled-camera runtime error.

## Relationship to the Gazebo stack

- Gazebo/eval flow: ROS 2 + Zenoh + `foxglove_bridge` on `8765`.
- Isaac Lab flow: Isaac Gym-style Python environment + Foxglove SDK on `8766`.

Use the Isaac flow for training throughput and simulator experimentation. Use
the Gazebo/eval flow for challenge-interface validation because submissions are
still evaluated through the official ROS 2 `aic_model` boundary.
