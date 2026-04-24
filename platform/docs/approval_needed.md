# Approval Needed

The following design decisions should be approved before provisioning or hardening the shared environment.

## 1. Access Pattern

Choose one:

- `IAP + OS Login + tunneled services`
- `HTTPS reverse proxy + browser access to services`

Recommendation:

- Use `IAP + OS Login` if your team is comfortable with Google Cloud tooling and wants the safer default.
- Use the HTTPS reverse proxy pattern only if “no local installs” is more important than tighter control-plane security.

## 2. Interactive Desktop Technology

Choose one primary path:

- `Amazon DCV`
- `TurboVNC + VirtualGL`

Recommendation:

- If paid licensing is acceptable, use `Amazon DCV` as the primary path and keep `TurboVNC + VirtualGL` as the no-license fallback.
- If you want to avoid licensing from day one, standardize directly on `TurboVNC + VirtualGL`.

## 3. Shared Storage

Choose one:

- `Persistent Disk + Cloud Storage only`
- `Persistent Disk + Cloud Storage + Filestore`

Recommendation:

- Start with Persistent Disk plus Cloud Storage.
- Add Filestore only if you hit a real multi-writer dataset or checkpoint coordination problem.

## 4. Scope Of The First Shared VM

Choose one:

- `single interactive VM only`
- `interactive VM plus separate headless batch runner`

Recommendation:

- Start with a single interactive VM if the team is still converging on the workflow.
- Plan a second headless node once training jobs become frequent enough to disrupt interactive use.

## 5. Experiment Tracking

Choose one:

- `TensorBoard only`
- `MLflow + optional TensorBoard`

Recommendation:

- Use `MLflow` as the team-visible system of record and allow TensorBoard as a per-run convenience UI.

## 6. Submission Hygiene

Confirm this team rule:

- all submission candidates must pass a remote smoke test with unique run artifacts before anyone tags and pushes a submission image

Recommendation:

- Approve this as mandatory. The challenge’s one-submission-per-day limit makes ad hoc submission discipline too expensive.
