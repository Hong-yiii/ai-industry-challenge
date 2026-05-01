# `aic-dev` collaborator IAM (full instance access)

**Role:** Document who gets **scoped full control of the `aic-dev` VM only**, which GCP roles are used, how **time-limited** access works, and how to **add or renew** collaborators.

For hardware, costs, and lifecycle commands, see [vm_instance.md](./vm_instance.md). For the broader access pattern (IAP, OS Login, tunnels), see [gcp_shared_devflow.md](./gcp_shared_devflow.md).

## What this access level allows

Collaborators listed below receive IAM meant for **one shared dev machine** (`aic-dev`), **not** project-wide admin:

| Binding | Scope | What it enables |
|--------|--------|------------------|
| `roles/compute.instanceAdmin.v1` | **Instance** `aic-dev` | Start/stop/reset the VM, change machine type, disks, metadata, and other **Compute API** operations on **this instance only**. Enough to run `gcloud compute instances start|stop …` / `platform/scripts/aic vm up|down` when project/zone/name are known. |
| `roles/compute.osAdminLogin` | **Instance** `aic-dev` | **OS Login** with **sudo** on the Linux guest (full shell access as an admin Linux user once SSH works). |
| `roles/iap.tunnelResourceAccessor` | **Project** with **IAM condition** | **IAP TCP forwarding** so SSH can use Identity-Aware Proxy. This role is **not** supported on the instance resource in IAM, so it is granted on project `ai-for-industry` with a condition that limits the grant to **only** the `aic-dev` resource name (see below). |

Together, these are “do anything **to this VM instance**” via GCP APIs and SSH-with-sudo. They do **not** by themselves grant Owner/Editor on the project, access to other VMs, or blanket IAP to unrelated resources—the IAP binding is conditioned on the instance resource name.

## Instance and project facts

| Field | Value |
|--------|--------|
| Project | `ai-for-industry` |
| Zone | `asia-southeast1-a` |
| Instance | `aic-dev` |

Canonical resource name used in the IAP condition:

`//compute.googleapis.com/projects/ai-for-industry/zones/asia-southeast1-a/instances/aic-dev`

## Time limits (expiry)

Bindings use an IAM **condition** so they **stop applying** after a fixed UTC time:

- **Expression (time part):** `request.time < timestamp("2027-05-01T00:00:00Z")`
- **Meaning:** Access is valid **before** 2027-05-01 00:00 UTC; after that instant the bindings are inactive.

The policy **rows may still appear** in the IAM UI after expiry; GCP does not always auto-delete them. **Removing** stale bindings later may require specifying the same `--condition` (or editing in Console)—see [GCP: IAM Conditions](https://cloud.google.com/iam/docs/conditions-overview).

**Renewals:** Extend or replace access by `remove-iam-policy-binding` (with matching condition) then `add-iam-policy-binding` with a new `timestamp(...)`, or add parallel bindings with a new expiry title and expression.

## Collaborators (current)

These principals are intended to match the bindings above (instance + conditional IAP). Update this table when you add or remove people.

| User | Notes |
|------|--------|
| `celes.chai@gmail.com` | Full `aic-dev` collaborator access; expiry aligned with condition above. |
| `frederick82004@gmail.com` | Same. |

*Project owners (e.g. billing and org-wide settings) are separate; they are not listed here.*

## Prerequisites for collaborators

- Google identity matching the `user:…@gmail.com` principal.
- **gcloud** installed and authenticated (`gcloud auth login` with that account).
- Optional: clone this repo and use `platform/scripts/aic vm up`, `vm ssh`, `vm down` with defaults from `platform/scripts/aic-vm-config.env`.

## How to add another collaborator

Run as a principal that can change IAM (e.g. project Owner). Replace `NEW_USER@example.com` and the `timestamp("…")` value if you extend access.

**Instance — instance admin + OS Login admin:**

```bash
gcloud compute instances add-iam-policy-binding aic-dev \
  --project=ai-for-industry \
  --zone=asia-southeast1-a \
  --member="user:NEW_USER@example.com" \
  --role="roles/compute.instanceAdmin.v1" \
  --condition='expression=request.time < timestamp("2027-05-01T00:00:00Z"),title=vm-admin-expires-2027-05-01,description=Instance admin time-limited'

gcloud compute instances add-iam-policy-binding aic-dev \
  --project=ai-for-industry \
  --zone=asia-southeast1-a \
  --member="user:NEW_USER@example.com" \
  --role="roles/compute.osAdminLogin" \
  --condition='expression=request.time < timestamp("2027-05-01T00:00:00Z"),title=oslogin-admin-expires-2027-05-01,description=OS Login admin time-limited'
```

**Project — IAP to `aic-dev` only** (this role cannot be set on the instance):

```bash
gcloud projects add-iam-policy-binding ai-for-industry \
  --member="user:NEW_USER@example.com" \
  --role="roles/iap.tunnelResourceAccessor" \
  --condition='expression=request.time < timestamp("2027-05-01T00:00:00Z") && resource.name == "//compute.googleapis.com/projects/ai-for-industry/zones/asia-southeast1-a/instances/aic-dev",title=iap-aic-dev-expires-2027-05-01,description=IAP tunnel to aic-dev only'
```

Then add the user to the **Collaborators** table in this doc.

## Verify bindings

**Instance:**

```bash
gcloud compute instances get-iam-policy aic-dev \
  --project=ai-for-industry \
  --zone=asia-southeast1-a
```

**Project** (filter in Console or inspect policy for `iap.tunnelResourceAccessor` and the member):

```bash
gcloud projects get-iam-policy ai-for-industry \
  --flatten="bindings[].members" \
  --filter="bindings.members:user:NEW_USER@example.com"
```

## gcloud caveat for conditional policies

After the first **conditional** binding is added to a resource, `add-iam-policy-binding` / `remove-iam-policy-binding` behavior can require an explicit `--condition` for some operations. Prefer **`get-iam-policy`** → edit → **`set-iam-policy`** for bulk edits, or use the Cloud Console IAM UI when unsure.
