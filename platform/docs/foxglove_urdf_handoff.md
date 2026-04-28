# Foxglove URDF rendering — best-practice runbook

**Status:** Web Foxglove over `foxglove_bridge` uses **Source = Topic**
`/robot_description_foxglove` so mesh `package://` URIs resolve on the VM
(`assets` + rewrite from install-time `file://` paths). Desktop native ROS can
still use **Parameter** per Foxglove docs.

This doc is the canonical setup and troubleshooting path. It intentionally
prioritizes Foxglove docs and operational best practice over speculative
workarounds.

---

## Architecture and data plane

**Base image (`aic_eval`).** `ghcr.io/intrinsic-dev/aic/aic_eval:latest` is the
challenge evaluation image: Ubuntu 24.04, ROS 2 Kilted, Gazebo, controllers,
`aic_engine`, and the Zenoh router on **7447** inside the container. The ROS
workspace is installed under **`/ws_aic/install`** (plus **`/opt/ros/.../share`**
for Debian-packaged stacks such as `ur_description`).

**Sidecar (`foxglove_bridge`).** `platform/docker/Dockerfile.foxglove` does
`FROM ghcr.io/intrinsic-dev/aic/aic_eval:latest`, installs
`ros-kilted-foxglove-bridge`, adds URL-encoded **symlink aliases** under
`/ws_aic/install/share/aic_assets/models` (Foxglove sends `%20` for spaces; the
bridge opens paths literally), copies `rewrite_urdf_for_foxglove.py`,
`foxglove-entrypoint.sh`, and `foxglove_bridge_params.yaml`. The entrypoint
sources `/opt/ros/kilted` + `/ws_aic/install`, sets **rmw_zenoh_cpp** and
**`ZENOH_ROUTER_ENDPOINT=tcp/aic_eval:7447`**, starts the URDF rewrite helper,
starts **JPEG republishers** for the three raw camera topics, then execs
`ros2 run foxglove_bridge foxglove_bridge` with the YAML params.

**Why a sidecar instead of `exec` into `aic_eval`?** Same ROS graph over Zenoh,
isolated WebSocket port **8765**, and a place to run bridge-specific helpers
without touching the eval entrypoint.

**URDF content.** `aic_description/urdf/ur_gz.urdf.xacro` passes
**`force_abs_paths="true"`** into the upstream `ur_robot` macro. That expands
every mesh URI to an absolute **`file:///…`** path inside the container (both
workspace and `/opt/ros/.../share/...`). That is correct for Gazebo and RViz,
but **wrong for web Foxglove**: the browser resolves `file://` on the laptop.
Upstream maintainers note that **Foxglove only requests `package://` assets
from the bridge**, not `file://`, even if the bridge could serve them. The
rewrite topic exists solely to turn those absolute paths into **`package://`**
so the bridge **assets** capability can open files **on the VM filesystem inside
the sidecar image**.

**Critical operational constraint — install-tree skew.** The sidecar image
embeds whatever **`FROM aic_eval`** contained at **`docker compose build`**
time. The running `aic_eval` container may be a **different digest** if you
pulled or recreated it later. Then TF and topics still work (Zenoh matches), but
`package://pkg/...` lookups inside `foxglove_bridge` can point at **missing or
older files** while `robot_state_publisher` in `aic_eval` emits URIs for the
**new** tree. Symptom: empty or partial robot in 3D, asset errors in bridge logs.
Fix: pull `aic_eval`, rebuild the sidecar with **`--pull`**, recreate both
containers (see `platform/scripts/aic-foxglove-bridge.sh` and
`AIC_FOXGLOVE_SYNC_BASE=1`).

---

## Goal

Render the AIC robot URDF (UR + Robotiq Hand‑E gripper + Axia80 F/T sensor +
cameras) in the **Foxglove 3D panel**, connected over the SSH IAP tunnel to the
`foxglove_bridge` sidecar running on the GCP VM.

---

## What is working

- `foxglove_bridge` Docker sidecar starts cleanly and advertises channels for TF, cameras, telemetry, **`/robot_description`**, and **`/robot_description_foxglove`**
- WebSocket connection on `ws://localhost:8765` is stable (no more "backlog full"
  disconnects since we whitelisted topics and added compressed image republishers)
- TF tree, `/clock`, `/joint_states`, `/dynamic_joint_states`, scoring events,
  diagnostics, FTS, contacts, AIC controller/model telemetry all flow into
  Foxglove correctly
- Compressed camera streams (`/<cam>_camera/image/compressed`) render in Image
  panels
- `parameters` capability is enabled — Foxglove can list params from
  `/robot_state_publisher` (and other nodes)
- `assets` capability is enabled — Foxglove can fetch arbitrary `package://`
  URIs from the bridge
- `/robot_description_foxglove` is the URDF topic intended for **web** Foxglove (rewritten meshes)

## Expected behavior

The 3D panel renders robot geometry after adding a URDF custom layer with:

- **Control mode = Transforms**

**Foxglove in the browser (WebSocket bridge):** with **`force_abs_paths="true"`**
on the UR arm macro, upstream URDF references meshes as absolute
`file:///ws_aic/install/share/<pkg>/...` and sometimes
`file:///opt/ros/<distro>/share/<pkg>/...`. The browser resolves `file://` on
your laptop, so those meshes **fail** even when the URDF string loads; the web
client also **requests `package://` from the bridge**, not `file://`. The
sidecar republishes on `/robot_description_foxglove` with those prefixes
rewritten to `package://<pkg>/…` so the bridge **`assets`** capability can open
files **inside the sidecar container**.

Use:

- **Source = Topic**
- **Topic = `/robot_description_foxglove`**

**Foxglove Desktop with a native ROS connection** can still use **Source =
Parameter** and `/robot_state_publisher.robot_description` per upstream docs.

---

## Per Foxglove docs (3D panel -> URDF custom layer)

> URDF robot models are loaded automatically if your data source supports
> parameters (i.e. a native ROS 1 or ROS 2 connection) and the
> `/robot_description` parameter is set to valid URDF XML.

For a WebSocket bridge connection, do not rely on auto-loading. Use an explicit
URDF custom layer:

- **Source: URL** → http(s) URL hosting the URDF
- **Source: Parameter** → bridge parameter (e.g. `/robot_state_publisher.robot_description`)
- **Source: Topic** → topic carrying the URDF body (use **`/robot_description_foxglove`** over the bridge in a browser)
- **Source: File path** → desktop app only

Resolving `package://` mesh URIs from a live bridge connection happens via the
bridge's **`assets`** capability over the WebSocket.

---

## Approaches (current)

### 1. Web Foxglove + bridge: Topic `/robot_description_foxglove`

**Outcome: recommended.** The sidecar runs `rewrite_urdf_for_foxglove.py`, which
subscribes to `/robot_description` and republishes the same XML with
`file:///ws_aic/install/share/<pkg>/...` **and**
`file:///opt/ros/<distro>/share/<pkg>/...` replaced by `package://<pkg>/...`.
Foxglove then requests meshes through the bridge **`assets`** API, which resolves
paths on the **sidecar** filesystem (must match the eval image digest; see
**Install-tree skew** above).

Use **Source = Topic** and topic **`/robot_description_foxglove`**, **Control mode = Transforms**.

### 2. Raw `/robot_description` or Parameter `/robot_state_publisher.robot_description`

**Outcome: poor fit for web Foxglove.** Those sources still embed **`file://`**
mesh URIs pointing at the container install tree. The browser tries to fetch
`file://` locally, so link errors like “Failed to fetch … `/ws_aic/install/...`”
are expected. Use section (1) instead, or change upstream xacro to emit
`package://` only.

### 3. `package://` mesh URIs containing encoded characters

**Outcome: compatibility shim applied for current assets; root cause remains upstream.**
The bridge can request URL-encoded path components (for example `%20`), while
asset trees may still contain unencoded names. This mismatch causes failed mesh
lookups unless aliases are present.

```
Failed to retrieve asset 'package://aic_assets/models/Axia80%20M20/axia_ft_sensor_visual.glb':
  Error retrieving file [/ws_aic/install/share/aic_assets/models/Axia80%20M20/...]:
  Failed to open file
```

Foxglove URL‑encodes spaces to `%20` before sending the asset request over the
WebSocket. `foxglove_bridge` does **not** URL‑decode before passing the path
to `resource_retriever` / the filesystem, so the literal string `Axia80%20M20`
is looked up and fails.

**Best practice order:**
1. **Canonical long-term fix:** normalize `aic_assets` directory names to ROS-safe
   package URI components (no spaces or special characters requiring encoding).
2. **Bridge-side fix (upstream):** URL-decode URI path components before
   filesystem/resource lookup.
3. **Current operational shim (in this repo):** create URL-encoded symlink
   aliases for all model files/directories during image build so encoded and
   unencoded paths both resolve.

### 4. Default `asset_uri_allowlist` regex

**Outcome: replaced.** The `foxglove_bridge` default allowlist
`^package://(?:[-\w%]+/)*[-\w%]+\.(?:dae|...|xacro)$` rejects path components
with spaces (`\w` does not match space). We replaced it with a more permissive
`[^/]+` per‑component regex in `foxglove_bridge_params.yaml`. The bridge still
rejects URIs containing `..` separately, so this remains safe.

### 5. Connection‑graph capability removed

**Outcome: kept removed.** With `connectionGraph` enabled the Foxglove UI
flickered/refreshed every second because `aic_engine` polls the ROS graph for
`aic_model`. Removing the capability stops the flicker.

### 6. `topic_whitelist` over the SSH IAP tunnel

**Outcome: working well.** Without it, raw 20 Hz camera images saturate the
WebSocket and Foxglove disconnects with "message backlog full". With it (plus
the compressed image republishers in `foxglove-entrypoint.sh`) the connection
is stable.

---

## Files in play

| File | Purpose |
|---|---|
| `platform/docker/Dockerfile.foxglove` | Builds the bridge sidecar; installs `ros-kilted-foxglove-bridge`; bakes in encoded-path symlinks under `aic_assets` |
| `platform/docker/rewrite_urdf_for_foxglove.py` | Republishes `/robot_description_foxglove` with `file:///ws_aic/install/share/...` → `package://...` for web Foxglove |
| `platform/docker/foxglove_bridge_params.yaml` | Bridge runtime config: `port`, `capabilities`, `asset_uri_allowlist`, `topic_whitelist`, `client_topic_whitelist` |
| `platform/docker/foxglove-entrypoint.sh` | Sources ROS + AIC workspace, starts URDF rewrite helper, `image_transport republish` for cameras, then `foxglove_bridge` |
| `platform/compose/dev.compose.yaml` | Brings up `aic_eval` + `foxglove_bridge` together on the same Docker network |
| `platform/scripts/aic-foxglove-bridge.sh` | One‑shot helper to build + start the sidecar |
| `platform/scripts/aic-vm-observe.sh` | Opens SSH port‑forwards (3000/9090/8080/8765) from laptop to VM |

---

## Concrete next steps

1. **Deploy the sidecar** (copy `platform/docker/*` for this stack, then rebuild
   with the same `aic_eval` digest the VM will run — on the VM prefer
   `AIC_FOXGLOVE_SYNC_BASE=1 platform/scripts/aic-foxglove-bridge.sh`):
   ```bash
   gcloud compute scp \
     platform/docker/Dockerfile.foxglove \
     platform/docker/foxglove-entrypoint.sh \
     platform/docker/foxglove_bridge_params.yaml \
     platform/docker/rewrite_urdf_for_foxglove.py \
     aic-dev:~/ai-industry-challenge/platform/docker/ \
     --project ai-for-industry --zone asia-southeast1-a
   gcloud compute ssh aic-dev --project ai-for-industry --zone asia-southeast1-a -- \
     "cd ~/ai-industry-challenge && \
      docker compose -f platform/compose/dev.compose.yaml build foxglove_bridge && \
      docker compose -f platform/compose/dev.compose.yaml up -d foxglove_bridge"
   ```
   Verify the rewrite helper ran:
   ```bash
   docker exec foxglove_bridge cat /tmp/urdf_rewrite.log
   ```
   Expect a line like `Republishing URDF on /robot_description_foxglove (N file:// path(s) rewritten)`.

2. **In Foxglove (browser)** — 3D panel:
   - Custom layers → **Add URDF**
   - **Source = Topic**
   - **Topic = `/robot_description_foxglove`**
   - **Control mode = Transforms**
   - **Save the layout** (cloud layouts can otherwise revert).

3. **Watch bridge logs** while the URDF layer loads meshes:
   ```bash
   docker logs -f foxglove_bridge 2>&1 | grep -iE 'asset|subscribe request for channel'
   ```
   Expect `subscribe request` for the `/robot_description_foxglove` channel and
   successful asset handling (no `Failed to retrieve asset` for rewritten URIs).

4. **If meshes still fail**, capture the failing `package://...` from logs and
   check the path under `/ws_aic/install/share/...` (encoded directory names,
   missing files, or allowlist regex).

5. **Long term**, prefer upstream URDF that uses `package://` mesh paths so the
   rewrite helper is unnecessary; normalize `aic_assets` directory names without
   spaces so stock bridge allowlists and fetches stay simple.

---

## Troubleshooting — “TF and topics work, but 3D shows nothing useful”

Work through this in order; most issues are client settings or image skew, not
“Foxglove is broken”.

1. **3D panel → Scene settings → Coordinate frame** — set **Z-up** (ROS / RViz
   convention). Foxglove defaults to **Blender Y-up**; with a UR robot the model
   can look wildly wrong or effectively vanish depending on camera framing.
   This matches upstream guidance on [ros-foxglove-bridge
   issues](https://github.com/foxglove/ros-foxglove-bridge/issues/264).

2. **Fixed frame** — pick a frame that actually exists on **`/tf`** or
   **`/tf_static`** (for this stack, **`world`** is a good default). If the
   fixed frame is unset or wrong, the URDF layer has nothing stable to attach to.

3. **URDF custom layer** — **Source = Topic**, topic **`/robot_description_foxglove`**
   (exact string), **Control mode = Transforms**. Remove extra URDF layers that
   still use **Parameter** or raw **`/robot_description`**; those keep **`file://`**
   meshes and the browser will never load them.

4. **Install-tree skew** — after `docker compose pull` or any new
   `aic_eval:latest` digest, rebuild the sidecar so **`FROM aic_eval`** matches:
   `AIC_FOXGLOVE_SYNC_BASE=1 platform/scripts/aic-foxglove-bridge.sh` on the VM,
   then restart or recreate **`aic_eval`** if needed so both containers see the
   same underlying files.

5. **Bridge logs while toggling the URDF layer** — on the VM:
   `docker logs foxglove_bridge 2>&1 | grep -iE 'asset|Failed to retrieve|allowlist'`.
   A single bad `package://` path should not hide *all* meshes, but allowlist
   rejections and missing files show up here.

6. **Save the Foxglove layout** after changes. Unsaved layouts revert on reload
   (especially with cloud-hosted layouts).

7. **`ros2 topic echo` gotcha** — from `docker exec foxglove_bridge`, Zenoh
   discovery often only shows `/parameter_events` and `/rosout`. For one-off
   CLI checks, run `ros2` **inside the `aic_eval` container** with the same
   Zenoh env, or rely on bridge logs and the rewrite log at
   `/tmp/urdf_rewrite.log` in the sidecar.

---

## Key facts to keep in mind

- `/robot_description` is published as **TRANSIENT_LOCAL, RELIABLE, depth 1** by
  `robot_state_publisher`.
- `/robot_description_foxglove` is the same payload with **`file://` → `package://`**
  for paths under `/ws_aic/install/share/` **and** `/opt/ros/*/share/`; the bridge
  advertises both topics.
- `parameters` and `assets` are both enabled in the bridge config.
- With **`use_sim_time: true`**, the bridge follows simulation time and `/clock`
  is on the topic whitelist so the **Time** path used for TF stays coherent.
- `aic_engine` polls for `aic_model` every second; this makes
  `connectionGraph` updates noisy and is why we keep that capability disabled.
- The Foxglove client URL‑encodes asset URIs before sending them to the bridge;
  the bridge does not URL‑decode them. Symlink aliases under `aic_assets` work
  around `%20` directory names.
