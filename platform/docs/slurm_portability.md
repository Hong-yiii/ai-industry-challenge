# SLURM Portability

The easiest way to make the current GCP workflow portable to SLURM later is to decide now where the boundaries are.

## Preserve These Boundaries

### Interactive dev

- branch checkout or worktree
- short smoke tests
- occasional GUI inspection

### Batch train

- long-running training jobs
- checkpointing
- periodic metrics logging

### Batch eval

- repeatable model evaluation runs
- fixed configs
- artifact collection

### Analyze

- post-run report generation
- bag inspection
- checkpoint comparison

If those become separate commands or entrypoints now, they map cleanly into SLURM job types later.

## Container Strategy

Do not make Docker Compose the core contract.

Use OCI images as the runtime boundary and keep Compose as a convenience layer for the GCP VM.

That keeps you compatible with common SLURM container approaches such as:

- native SLURM OCI support
- Enroot/Pyxis
- Apptainer/Singularity

Prefer image digests over mutable tags for anything that matters operationally.

Practical rule:

- every important action should have a direct command form that can run inside a container without Compose orchestration

Examples:

- `train`
- `eval`
- `replay`
- `export-world`
- `analyze`

The sample files in [../slurm](../slurm) intentionally use generic commands such as `run-train` and `run-batch-eval` to reinforce that the scheduler contract should be an image entrypoint, not an ad hoc interactive shell recipe.

## What To Avoid

Avoid designs that depend on:

- hard-coded Docker bridge network names
- local interactive shell state as part of the runtime contract
- hand-created shared directories with no naming convention
- GUI-only observability
- local laptop-specific binaries in the critical path

Those choices are cheap on a single VM and painful on SLURM.

## Portable Artifact Layout

Use run directories that can live on:

- GCP Persistent Disk
- Filestore
- Cloud Storage
- an HPC shared filesystem

Recommended run structure:

```text
runs/<project>/<date>/<run_id>/
  config/
  logs/
  metrics/
  checkpoints/
  results/
  bags/
```

This layout is portable across cloud VMs and HPC shared storage.

## Storage Mapping

Map storage by intent:

- source code: Git
- immutable containers: OCI registry or cluster image store
- checkpoints and reports: object storage or shared filesystem
- scratch space: node-local SSD or temporary job directory

On GCP:

- use Persistent Disk for interactive work
- use Cloud Storage for durable artifacts

On SLURM:

- use the cluster filesystem for shared inputs and outputs
- use node-local scratch for temporary high-IO phases if the cluster provides it

## Observability Mapping

Keep observability tools that survive both environments:

- Prometheus-compatible exporters for system metrics
- Grafana for dashboards
- MLflow or TensorBoard for training runs
- ROS bags or MCAP for replay

GUI access will change between GCP and SLURM, but artifacts and metrics should not.

## Job Shape Recommendation

Design your training and evaluation commands so they can be called by a job scheduler with only:

- input config path
- output directory
- container image
- resource request

That is the scheduling contract that matters.

Everything else should be optional convenience.

## Suggested Migration Path

### Now on GCP

- shared interactive VM
- headless eval by default
- observability services always on
- long runs limited or moved off the interactive node

### Later on SLURM

- login node or dev node for code and orchestration
- `sbatch` for train and eval
- same OCI images
- same result directory conventions
- same dashboards pointed at cluster exporters

If you hold that line, the SLURM migration becomes an operational rewrite rather than a workflow rewrite.
