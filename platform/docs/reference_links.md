# Reference Links

These external references informed the platform design.

## Google Cloud

- Compute Engine GPU machine types: https://cloud.google.com/compute/docs/gpus
- OS Login: https://cloud.google.com/compute/docs/oslogin
- IAP SSH: https://cloud.google.com/compute/docs/connect/ssh-using-iap
- Linux startup scripts: https://cloud.google.com/compute/docs/instances/startup-scripts/linux
- Machine images: https://cloud.google.com/compute/docs/machine-images
- Local SSD: https://cloud.google.com/compute/docs/disks/local-ssd
- Filestore overview: https://cloud.google.com/filestore/docs/overview
- Cloud Storage FUSE overview: https://cloud.google.com/storage/docs/cloud-storage-fuse/overview
- Cloud Storage hierarchical namespace: https://cloud.google.com/storage/docs/hns-overview
- Artifact Registry OCI support: https://cloud.google.com/artifact-registry/docs/supported-formats
- Ops Agent: https://cloud.google.com/logging/docs/agent/ops-agent
- Compute Engine container startup agent deprecation: https://cloud.google.com/compute/docs/deprecations/container-startup-agent-on-compute

## Remote GUI And ROS Observability

- Amazon DCV sessions: https://docs.aws.amazon.com/dcv/latest/adminguide/managing-sessions-intro.html
- Amazon DCV GPU management: https://docs.aws.amazon.com/dcv/latest/adminguide/manage-gpu.html
- Amazon DCV licensing: https://docs.aws.amazon.com/dcv/latest/adminguide/setting-up-license.html
- TurboVNC: https://turbovnc.org/About/Features
- VirtualGL: https://www.virtualgl.org/
- noVNC: https://novnc.com/noVNC/
- Foxglove ROS 2 docs: https://docs.foxglove.dev/docs/getting-started/frameworks/ros2
- Foxglove bridge (live ROS → WebSocket for app.foxglove.dev): https://docs.foxglove.dev/docs/visualization/ros-foxglove-bridge
- ROS 2 `foxglove_bridge` parameters (upstream): https://github.com/foxglove/foxglove-sdk/blob/main/ros/src/foxglove_bridge/README.md#configuration
- Foxglove Agent (monitors a directory for recordings — **not** the live bridge; do not confuse with `ros-kilted-foxglove-bridge`): https://docs.foxglove.dev/docs/foxglove-agent
- `web_video_server`: https://docs.ros.org/en/ros2_packages/rolling/api/web_video_server/

## SLURM And Containers

- SLURM containers: https://slurm.schedmd.com/containers.html
- SLURM job arrays: https://slurm.schedmd.com/job_array.html
- SLURM accounting: https://slurm.schedmd.com/accounting.html
- `sstat`: https://slurm.schedmd.com/sstat.html
- Apptainer OCI and Docker sources: https://apptainer.org/docs/user/latest/docker_and_oci.html
- Apptainer bind mounts: https://apptainer.org/docs/user/1.3/bind_paths_and_mounts.html

## Training Metrics

- MLflow tracking server: https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/
- TensorBoard: https://www.tensorflow.org/tensorboard/get_started
