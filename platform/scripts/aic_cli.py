#!/usr/bin/env python3
"""Unified AIC dev CLI — GCP VM lifecycle, tunnels, compose stacks, dev session."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from subprocess import CompletedProcess
from typing import Callable, Mapping, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
PLATFORM_ROOT = SCRIPT_DIR.parent
WORKSPACE_ROOT = PLATFORM_ROOT.parent
DEV_COMPOSE = PLATFORM_ROOT / "compose" / "dev.compose.yaml"
OBS_COMPOSE = PLATFORM_ROOT / "compose" / "observability.compose.yaml"
DOCKER_COMPOSE_TEST = WORKSPACE_ROOT / "docker" / "docker-compose.yaml"

REMOTE_DEV_COMPOSE = "platform/compose/dev.compose.yaml"
REMOTE_OBS_COMPOSE = "platform/compose/observability.compose.yaml"
REMOTE_TEST_COMPOSE_REL = "docker/docker-compose.yaml"


def getenv(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is not None and v != "":
        return v
    return default


def gcloud_ssh_base() -> list[str]:
    proj = getenv("AIC_VM_PROJECT") or getenv("GCP_PROJECT")
    zone = getenv("AIC_VM_ZONE")
    name = getenv("AIC_VM_NAME")
    for label, val in (
        ("AIC_VM_PROJECT", proj),
        ("AIC_VM_ZONE", zone),
        ("AIC_VM_NAME", name),
    ):
        if not val:
            cfg = SCRIPT_DIR / "aic-vm-config.env"
            print(f"[aic] error: unset {label} — set env or extend {cfg}", file=sys.stderr)
            sys.exit(2)
    assert proj and zone and name
    return [
        "gcloud",
        "compute",
        "ssh",
        name,
        "--project",
        proj,
        "--zone",
        zone,
    ]


def repo_root_local() -> Path:
    rr = getenv("AIC_REPO_ROOT")
    return Path(rr).resolve() if rr else WORKSPACE_ROOT


def remote_repo_path(default: str = "/srv/aic/repo") -> str:
    return getenv("AIC_VM_REPO_PATH") or default


def run(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
) -> CompletedProcess[str]:
    nenv = dict(os.environ)
    if env:
        nenv.update(env)
    kwargs = {
        "args": argv,
        "cwd": cwd,
        "env": nenv,
        "text": True,
    }
    if check:
        return subprocess.run(**kwargs, check=True)  # type: ignore[arg-type,misc]
    return subprocess.run(**kwargs)  # type: ignore[arg-type,misc]


def run_capture(argv: Sequence[str], *, cwd: Path | None = None) -> str:
    r = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        capture_output=True,
    )
    if r.returncode != 0:
        print(r.stderr or r.stdout or "", file=sys.stderr, end="")
        sys.exit(r.returncode or 1)
    return r.stdout.strip()


def vm_instance_status() -> str:
    name = getenv("AIC_VM_NAME")
    proj = getenv("AIC_VM_PROJECT")
    zone = getenv("AIC_VM_ZONE")
    return run_capture(
        [
            "gcloud",
            "compute",
            "instances",
            "describe",
            str(name),
            "--project",
            str(proj),
            "--zone",
            str(zone),
            "--format",
            "value(status)",
        ]
    )


def vm_external_ip() -> str:
    name = getenv("AIC_VM_NAME")
    proj = getenv("AIC_VM_PROJECT")
    zone = getenv("AIC_VM_ZONE")
    return run_capture(
        [
            "gcloud",
            "compute",
            "instances",
            "describe",
            str(name),
            "--project",
            str(proj),
            "--zone",
            str(zone),
            "--format",
            "value(networkInterfaces[0].accessConfigs[0].natIP)",
        ]
    )


def cmd_vm_up(_a: argparse.Namespace) -> None:
    status = vm_instance_status()
    name = getenv("AIC_VM_NAME")
    zone = getenv("AIC_VM_ZONE")
    proj = getenv("AIC_VM_PROJECT")
    if status != "RUNNING":
        print(f"Starting {name} ({zone})…")
        run(
            [
                "gcloud",
                "compute",
                "instances",
                "start",
                str(name),
                "--project",
                str(proj),
                "--zone",
                str(zone),
            ]
        )
        print("Done. Connect with:  platform/scripts/aic vm ssh")
    else:
        print("aic-dev is already running.")

    print(f"External IP: {vm_external_ip()}")


def cmd_vm_down(_a: argparse.Namespace) -> None:
    status = vm_instance_status()
    name = getenv("AIC_VM_NAME")
    proj = getenv("AIC_VM_PROJECT")
    zone = getenv("AIC_VM_ZONE")
    if status == "TERMINATED":
        print("aic-dev is already stopped.")
        return

    print(f"Stopping {name} ({zone})…")
    run(
        [
            "gcloud",
            "compute",
            "instances",
            "stop",
            str(name),
            "--project",
            str(proj),
            "--zone",
            str(zone),
        ]
    )
    print("Done. Disk is preserved; compute billing has stopped.")


def cmd_vm_ssh(ns: argparse.Namespace) -> None:
    argv = gcloud_ssh_base() + ["--", *ns.args]
    os.execvp(argv[0], list(argv))


def wait_for_ssh(*, attempts: int = 40, interval: float = 2.5) -> bool:
    ssh_args = [*gcloud_ssh_base(), "--", "bash", "-lc", "true"]
    for attempt in range(attempts):
        r = subprocess.run(ssh_args, capture_output=True, text=True)
        if r.returncode == 0:
            return True
        print(
            f"[aic] Waiting for SSH (attempt {attempt + 1}/{attempts})…",
            file=sys.stderr,
        )
        time.sleep(interval)
    return False


ForegroundStop = Callable[[], None]


# --- session tracking (SIGINT teardown) --------------------------------------

_foreground_stops: list[tuple[str, ForegroundStop]] = []
_tunnel_proc: subprocess.Popen[str] | None = None
_track_dev_remote = False
_track_obs_remote = False
_track_test_remote = False

_policy_kill_mode: str | None = None  # None | compose_model_on_test_stack


def register_foreground_stop(label: str, fn: ForegroundStop) -> None:
    _foreground_stops.append((label, fn))


def _exec_foreground_stops(verbose: bool) -> None:
    for label, fn in reversed(_foreground_stops):
        if verbose:
            print(f"[aic] teardown: {label}", file=sys.stderr)
        try:
            fn()
        except OSError as exc:
            print(f"[aic] teardown error ({label}): {exc}", file=sys.stderr)


def _stop_tunnel_process() -> None:
    proc = _tunnel_proc
    if proc is not None and proc.poll() is None:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
    subprocess.run(["stty", "sane"], check=False)


def compose_down_remote_dev_obs(kind: str) -> None:
    """SSH: compose down platform stacks under remote repo."""
    rp = remote_repo_path()
    compose_rel = REMOTE_DEV_COMPOSE if kind == "dev" else REMOTE_OBS_COMPOSE

    ssh = gcloud_ssh_base()
    rp_esc = rp.replace(chr(39), "'\"'\"'")
    compose_esc = compose_rel.replace(chr(39), "'\"'\"'")
    body = f"""
set -euo pipefail
cd '{rp_esc}'
if ! test -f '{compose_esc}'; then
  echo "[aic] error: missing compose on VM: ${{PWD}}/{compose_rel}" >&2
  exit 4
fi
docker compose -f '{compose_esc}' down
"""

    subprocess.run(
        ssh + ["--", "bash", "-lc", body.strip()],
        check=False,
    )


def compose_down_remote_test(rp_remote: str) -> None:
    """SSH: compose down docker/docker-compose.yaml (eval+model)."""
    rp_esc = rp_remote.replace(chr(39), "'\"'\"'")

    compose_rel = REMOTE_TEST_COMPOSE_REL
    compose_esc = compose_rel.replace(chr(39), "'\"'\"'")

    body = f"""
set -euo pipefail
cd '{rp_esc}'
if ! test -f '{compose_esc}'; then
  echo "[aic] error: missing on VM: {{PWD}}/{compose_rel}" >&2
  exit 4
fi
docker compose -f '{compose_esc}' down
"""

    subprocess.run(
        gcloud_ssh_base() + ["--", "bash", "-lc", body.strip()],
        check=False,
    )


def ssh_run_remote_script(remote_bash_body: str) -> int:
    return subprocess.run(gcloud_ssh_base() + ["--", "bash", "-lc", remote_bash_body]).returncode


def remote_stack_dev_up(sync_foxglove: bool, ground_truth: bool) -> None:
    """Match legacy aic-foxglove-bridge.sh on the VM (repo = AIC_VM_REPO_PATH)."""
    global _track_dev_remote  # noqa: PLW0603

    rp_esc = remote_repo_path().replace(chr(39), "'\"'\"'")

    prelude = ""
    if sync_foxglove:
        prelude = "export AIC_FOXGLOVE_SYNC_BASE=1;\n"

    gf = "export AIC_GROUND_TRUTH=true;\n" if ground_truth else ""

    compose_esc = REMOTE_DEV_COMPOSE.replace(chr(39), "'\"'\"'")

    body = """

set -euo pipefail
cd '%s'
%s%s

if [[ "${AIC_FOXGLOVE_SYNC_BASE:-}" == "1" ]] || ! docker image inspect aic-foxglove-bridge:latest >/dev/null 2>&1; then
  docker compose -f '%s' pull aic_eval
  docker compose -f '%s' build --pull foxglove_bridge
else
  docker compose -f '%s' build foxglove_bridge
fi
docker compose -f '%s' up -d foxglove_bridge
""" % (
        rp_esc,
        gf,
        prelude,
        compose_esc,
        compose_esc,
        compose_esc,
        compose_esc,
        compose_esc,
    )

    r = subprocess.run(
        gcloud_ssh_base() + ["--", "bash", "-lc", body.strip()],
    )
    if r.returncode != 0:
        sys.exit(r.returncode)
    _track_dev_remote = True


def remote_stack_obs_up() -> None:
    global _track_obs_remote  # noqa: PLW0603

    rp_esc = remote_repo_path().replace(chr(39), "'\"'\"'")

    body = """
set -euo pipefail
cd '%s'
OBS='platform/compose/observability.compose.yaml'
if ! test -f "$OBS"; then
  echo '[aic] missing Observability compose on VM:' "$(pwd)/$OBS" >&2
  exit 4
fi
docker compose -f "$OBS" up -d
""" % (
        rp_esc,
    )

    r = subprocess.run(gcloud_ssh_base() + ["--", "bash", "-lc", body.strip()])
    if r.returncode == 0:
        _track_obs_remote = True


def _require_path(p: Path, label: str) -> None:
    if not p.is_file():
        print(f"[aic] error: {label} missing: {p}", file=sys.stderr)
        sys.exit(3)


def preflight_gcloud() -> None:
    if not shutil.which("gcloud"):
        print("[aic] error: `gcloud` not on PATH.", file=sys.stderr)
        sys.exit(2)


def stack_dev_up_local(*, sync_foxglove: bool, ground_truth: bool) -> None:
    root = repo_root_local()
    env = dict(os.environ)
    if ground_truth:
        env["AIC_GROUND_TRUTH"] = "true"

    if sync_foxglove:
        env["AIC_FOXGLOVE_SYNC_BASE"] = "1"

    compose = DEV_COMPOSE
    if env.get("AIC_FOXGLOVE_SYNC_BASE") == "1" or subprocess.run(
        ["docker", "image", "inspect", "aic-foxglove-bridge:latest"],
        cwd=root,
        capture_output=True,
    ).returncode != 0:
        run(["docker", "compose", "-f", str(compose), "pull", "aic_eval"], cwd=root, env=env)
        run(
            ["docker", "compose", "-f", str(compose), "build", "--pull", "foxglove_bridge"],
            cwd=root,
            env=env,
        )
    else:
        run(["docker", "compose", "-f", str(compose), "build", "foxglove_bridge"], cwd=root, env=env)

    run(["docker", "compose", "-f", str(compose), "up", "-d", "foxglove_bridge"], cwd=root, env=env)


def stack_dev_down_local() -> None:
    root = repo_root_local()
    run(["docker", "compose", "-f", str(DEV_COMPOSE), "down"], cwd=root)


def stack_obs_cmd_local(action: str, log_args: list[str]) -> None:
    root = repo_root_local()
    cmd = ["docker", "compose", "-f", str(OBS_COMPOSE)]
    if action == "up":
        run(cmd + ["up", "-d"], cwd=root)
    elif action == "down":
        run(cmd + ["down"], cwd=root)
    else:
        run(cmd + ["logs", *log_args], cwd=root)


def remote_stack_obs_down() -> None:
    rp_esc = remote_repo_path().replace(chr(39), "'\"'\"'")
    body = """
set -euo pipefail
cd '%s'
OBS='platform/compose/observability.compose.yaml'
docker compose -f "$OBS" down
""" % (
        rp_esc,
    )

    subprocess.run(gcloud_ssh_base() + ["--", "bash", "-lc", body.strip()])


def tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def remote_stack_logs(compose_rel: str, log_args: list[str]) -> None:
    rp = shlex.quote(remote_repo_path())
    cf = shlex.quote(compose_rel)
    extras = " ".join(shlex.quote(a) for a in log_args)
    tail = extras if extras else "--tail=80"
    body = f"set -euo pipefail; cd {rp}; docker compose -f {cf} logs {tail}"
    subprocess.run(gcloud_ssh_base() + ["--", "bash", "-lc", body])


def remote_stack_eval_model_up(rp_override: str | None = None) -> None:
    global _track_test_remote
    global _policy_kill_mode

    rp = rp_override or getenv("AIC_VM_REPO_PATH") or "/srv/aic/repo"
    rp_esc = rp.replace(chr(39), "'\"'\"'")
    compose_esc = REMOTE_TEST_COMPOSE_REL.replace(chr(39), "'\"'\"'")

    body = """
set -euo pipefail
cd '%s'
DC='%s'
if ! test -f "$DC"; then
  echo '[aic] missing on VM:' "$(pwd)/$DC" >&2
  exit 4
fi
docker compose -f "$DC" up -d
""" % (
        rp_esc,
        compose_esc,
    )

    r = subprocess.run(gcloud_ssh_base() + ["--", "bash", "-lc", body.strip()])
    if r.returncode == 0:
        _track_test_remote = True
        _policy_kill_mode = "compose_model"


def remote_stop_model_container_only(rp_override: str | None = None) -> None:
    rp = rp_override or getenv("AIC_VM_REPO_PATH") or "/srv/aic/repo"
    rp_esc = rp.replace(chr(39), "'\"'\"'")
    compose_esc = REMOTE_TEST_COMPOSE_REL.replace(chr(39), "'\"'\"'")

    body = """
set -euo pipefail
cd '%s'
docker compose -f '%s' stop model
""" % (
        rp_esc,
        compose_esc,
    )

    subprocess.run(gcloud_ssh_base() + ["--", "bash", "-lc", body.strip()])


def stack_test_up_local() -> None:
    root = repo_root_local()
    run(["docker", "compose", "-f", str(DOCKER_COMPOSE_TEST), "up", "-d"], cwd=root)


def stack_test_down_local() -> None:
    root = repo_root_local()
    run(["docker", "compose", "-f", str(DOCKER_COMPOSE_TEST), "down"], cwd=root)


def teardown_menu() -> None:
    td = getenv("AIC_TEARDOWN", "").strip().lower()
    if td == "none":
        _exec_foreground_stops(verbose=False)
        return

    if getenv("CI") or not tty():
        _exec_foreground_stops(verbose=False)
        return

    if td in {"tunnel", "tunnel_only", "1"}:
        _exec_foreground_stops(verbose=True)
        return

    print(
        "[aic] choose teardown:\n"
        "  [1] Stop tunnel / foreground only\n"
        "  [2] Remote compose down (tracked stacks on VM)\n"
        "  [3] Stop model service only (docker compose stop model; if test stack was used)\n"
        "  [4] Stop VM (type YES) — compute stops, disk preserved\n"
        "  [Enter] skip",
        flush=True,
    )
    try:
        choice = input("[aic] choice [1-4]> ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = ""

    if choice == "1":
        _exec_foreground_stops(verbose=True)
    elif choice == "2":
        rp = remote_repo_path()
        if _track_dev_remote:
            compose_down_remote_dev_obs("dev")
        if _track_obs_remote:
            compose_down_remote_dev_obs("observability")
        if _track_test_remote:
            compose_down_remote_test(rp)
    elif choice == "3":
        if _policy_kill_mode == "compose_model":
            remote_stop_model_container_only()
        else:
            print("[aic] no tracked policy/container to stop.", file=sys.stderr)
    elif choice == "4":
        try:
            ans = input("[aic] Type YES to confirm VM stop: ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if ans == "YES":
            cmd_vm_down(argparse.Namespace())


def cmd_tunnel(ns: argparse.Namespace) -> None:
    global _tunnel_proc

    tunnels: list[tuple[str, str]]
    if ns.foxglove_only:
        tunnels = [("8765", "8765")]
    elif ns.metrics_only:
        tunnels = [
            ("3000", "3000"),
            ("9090", "9090"),
            ("8080", "8080"),
        ]
    else:
        tunnels = [
            ("3000", "3000"),
            ("9090", "9090"),
            ("8080", "8080"),
            ("8765", "8765"),
        ]

    ssh_args = gcloud_ssh_base() + ["--", "-N"]
    for lp, rport in tunnels:
        ssh_args += ["-L", f"{lp}:localhost:{rport}"]

    preflight_gcloud()
    print(
        "Opening tunnels…\n"
        "  Grafana → http://localhost:3000  Prometheus → http://localhost:9090\n"
        "  Foxglove → ws://localhost:8765  (visit https://app.foxglove.dev)\n"
        "\nCtrl+C opens teardown menu (see AIC_TEARDOWN for scripted behavior).",
        flush=True,
    )

    proc = subprocess.Popen(ssh_args)
    _tunnel_proc = proc
    register_foreground_stop("tunnel", _stop_tunnel_process)

    try:
        rc = proc.wait()
    except KeyboardInterrupt:
        teardown_menu()
        _stop_tunnel_process()
        return

    sys.exit(rc)


def cmd_stack_dev(ns: argparse.Namespace) -> None:
    la = getattr(ns, "log_args", None) or []
    if ns.action == "up":
        if ns.remote:
            preflight_gcloud()
            remote_stack_dev_up(ns.sync_foxglove, ns.ground_truth)
        else:
            stack_dev_up_local(sync_foxglove=ns.sync_foxglove, ground_truth=ns.ground_truth)
    elif ns.action == "down":
        if ns.remote:
            preflight_gcloud()
            compose_down_remote_dev_obs("dev")
        else:
            stack_dev_down_local()
    else:
        if ns.remote:
            preflight_gcloud()
            remote_stack_logs(REMOTE_DEV_COMPOSE, list(la))
        else:
            root = repo_root_local()
            run(["docker", "compose", "-f", str(DEV_COMPOSE), "logs", *la], cwd=root)


def cmd_stack_obs(ns: argparse.Namespace) -> None:
    la = getattr(ns, "log_args", None) or []
    if ns.action == "up":
        if ns.remote:
            preflight_gcloud()
            remote_stack_obs_up()
        else:
            stack_obs_cmd_local("up", [])
    elif ns.action == "down":
        if ns.remote:
            preflight_gcloud()
            remote_stack_obs_down()
        else:
            stack_obs_cmd_local("down", [])
    else:
        if ns.remote:
            preflight_gcloud()
            remote_stack_logs(REMOTE_OBS_COMPOSE, list(la))
        else:
            stack_obs_cmd_local("logs", list(la))


def cmd_stack_test(ns: argparse.Namespace) -> None:
    la = getattr(ns, "log_args", None) or []
    if ns.action == "up":
        if ns.remote:
            preflight_gcloud()
            remote_stack_eval_model_up()
        else:
            stack_test_up_local()
    elif ns.action == "down":
        if ns.remote:
            preflight_gcloud()
            compose_down_remote_test(remote_repo_path())
        else:
            stack_test_down_local()
    else:
        if ns.remote:
            preflight_gcloud()
            remote_stack_logs(REMOTE_TEST_COMPOSE_REL, list(la))
        else:
            root = repo_root_local()
            run(["docker", "compose", "-f", str(DOCKER_COMPOSE_TEST), "logs", *la], cwd=root)


def cmd_dev(ns: argparse.Namespace) -> None:
    preflight_gcloud()
    if vm_instance_status() != "RUNNING":
        cmd_vm_up(argparse.Namespace())
    if not wait_for_ssh():
        print("[aic] SSH did not become ready in time.", file=sys.stderr)
        sys.exit(1)
    remote_stack_dev_up(ns.sync_foxglove, ns.ground_truth)
    if ns.with_observability:
        remote_stack_obs_up()

    tunnel_ns = argparse.Namespace(foxglove_only=False, metrics_only=False)
    cmd_tunnel(tunnel_ns)


def cmd_vm_bootstrap(_ns: argparse.Namespace) -> None:
    script = SCRIPT_DIR / "aic-vm-bootstrap.sh"
    _require_path(script, "aic-vm-bootstrap.sh")
    preflight_gcloud()
    with open(script, encoding="utf-8") as f:
        subprocess.run(gcloud_ssh_base() + ["--", "bash", "-s"], stdin=f, check=True)


def cmd_vm_pull(_ns: argparse.Namespace) -> None:
    script = SCRIPT_DIR / "aic-vm-pull.sh"
    _require_path(script, "aic-vm-pull.sh")
    preflight_gcloud()
    with open(script, encoding="utf-8") as f:
        subprocess.run(gcloud_ssh_base() + ["--", "bash", "-s"], stdin=f, check=True)


def cmd_diag_ros(_ns: argparse.Namespace) -> None:
    hp = SCRIPT_DIR / "aic-healthcheck.sh"
    if hp.is_file():
        subprocess.run(["bash", str(hp)], check=False)
    else:
        print(f"[aic] missing {hp}", file=sys.stderr)
        sys.exit(3)


def cmd_diag_host(_ns: argparse.Namespace) -> None:
    sp = SCRIPT_DIR / "aic-session-report.sh"
    if sp.is_file():
        subprocess.run(["bash", str(sp)], check=False)
    else:
        print(f"[aic] missing {sp}", file=sys.stderr)
        sys.exit(3)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aic",
        description="AIC unified dev CLI (GCP VM, compose stacks, tunnels).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    vm = sub.add_parser("vm", help="VM lifecycle / SSH / onboarding")
    vm_s = vm.add_subparsers(dest="vm_cmd", required=True)
    vm_s.add_parser("up", help="Start GCP dev VM").set_defaults(func=cmd_vm_up)
    vm_s.add_parser("down", help="Stop GCP dev VM").set_defaults(func=cmd_vm_down)
    vssh = vm_s.add_parser("ssh", help="gcloud compute ssh passthrough")
    vssh.add_argument("args", nargs=argparse.REMAINDER, default=[], help='e.g. -- "uname -a"')
    vssh.set_defaults(func=cmd_vm_ssh)
    vm_s.add_parser("bootstrap", help="One-time VM setup (stdin script)").set_defaults(func=cmd_vm_bootstrap)
    vm_s.add_parser("pull", help="Post-reboot image pull / smoke").set_defaults(func=cmd_vm_pull)

    devp = sub.add_parser("dev", aliases=["session"], help="Golden path: VM up, dev stack, tunnel")
    devp.add_argument("--sync-foxglove", action="store_true", help="Force AIC_FOXGLOVE_SYNC_BASE pull+build")
    devp.add_argument("--ground-truth", action="store_true", help="AIC_GROUND_TRUTH for CheatCode-style runs")
    devp.add_argument(
        "--with-observability",
        action="store_true",
        help="Also start observability.compose on the VM",
    )
    devp.set_defaults(func=cmd_dev)

    tnp = sub.add_parser("tunnel", help="SSH port-forwards (Grafana/Prometheus/cAdvisor/Foxglove)")
    tnp.add_argument("--foxglove-only", action="store_true")
    tnp.add_argument("--metrics-only", action="store_true")
    tnp.set_defaults(func=cmd_tunnel)

    diag = sub.add_parser("diag", help="ROS / host diagnostics")
    dg = diag.add_subparsers(dest="diag_cmd", required=True)
    dg.add_parser("ros", help="ROS graph check (aic-healthcheck.sh)").set_defaults(func=cmd_diag_ros)
    dg.add_parser("host", help="Host/Docker snapshot (aic-session-report.sh)").set_defaults(func=cmd_diag_host)

    st = sub.add_parser("stack", help="Docker Compose stacks")
    st_s = st.add_subparsers(dest="stack_kind", required=True)

    def add_stack_p(
        name: str,
        helpt: str,
        fn: Callable[[argparse.Namespace], None],
    ) -> argparse.ArgumentParser:
        sp = st_s.add_parser(name, help=helpt)
        sp.add_argument("action", choices=["up", "down", "logs"])
        sp.add_argument("--remote", action="store_true", help="Run on VM via SSH (needs AIC_VM_REPO_PATH)")
        sp.add_argument("--sync-foxglove", action="store_true", help="(dev stack) sync sidecar FROM aic_eval")
        sp.add_argument("--ground-truth", action="store_true", help="(dev stack) ground truth TF")
        sp.add_argument("log_args", nargs=argparse.REMAINDER, default=[], help="args for `logs` action")
        sp.set_defaults(func=fn)
        return sp

    add_stack_p("dev", "platform/compose/dev — eval + Foxglove", cmd_stack_dev)
    add_stack_p("observability", "platform/compose/observability — metrics UI", cmd_stack_obs)
    add_stack_p("test", "docker/docker-compose — eval + model", cmd_stack_test)

    return p


def main() -> None:
    p = build_parser()
    ns = p.parse_args()
    if hasattr(ns, "func"):
        ns.func(ns)
    else:
        p.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()


