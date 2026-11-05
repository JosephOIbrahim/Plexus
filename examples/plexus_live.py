"""One click: ComfyUI the way Joe starts it, with his models, and then a Plexus session.

    python examples/plexus_live.py

It makes sure the Rust core matches the crates, starts G:\\COMFY\\ComfyUI in its own window, waits for
/system_stats, checks the checkpoints ComfyUI lists really sit under G:\\COMFYUI_Database, and then runs
plexus_session.py in this window. Joe's word, Nov 3: Claude may write this and a small driver outside
plexus/. It is not a worker file, and no frozen test covers it.

It runs the Stable command from comfyui_launcher.bat, with that file's environment, and not the file
itself: the file's countdown calls choice /c " qo", Windows rejects the space, and it always stops at
its Options menu waiting for a key, so a one-click start could never get past it.

Module level stays stdlib only, so the checks here work without pxr or the Rust core.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COMFYUI_ROOT = Path(r"G:\COMFY\ComfyUI")
MODELS_ROOT = Path(r"G:\COMFYUI_Database\Models")
COMFYUI_URL = "http://127.0.0.1:8188"
START_TIMEOUT_S = 300.0  # every custom node in G:\COMFYUI_Database\Custom_Nodes loads before the port opens: 47 s on Nov 4, Houdini open

# What comfyui_launcher.bat sets before it starts ComfyUI, kept in step with that file by hand.
COMFYUI_ENV = {
    "CUDA_MODULE_LOADING": "LAZY",
    "PYTORCH_ALLOC_CONF": "expandable_segments:True,garbage_collection_threshold:0.8",
    "CUDA_LAUNCH_BLOCKING": "0",
    "TF_ENABLE_ONEDNN_OPTS": "0",
    "PYTHONUNBUFFERED": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
    "PYTHONHASHSEED": "0",
}

READ_ERRORS = (OSError, ValueError, http.client.HTTPException)  # URLError is an OSError, and a bad JSON body a ValueError

# ComfyUI is on this machine, and a system proxy must never see a request to it.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class LaunchError(Exception):
    """Something the operator has to act on. The message says what."""


class NotComfyUI(Exception):
    """Something holds the port and does not answer as ComfyUI."""


def _get_json(url: str, path: str, timeout: float):
    with _OPENER.open(url.rstrip("/") + path, timeout=timeout) as reply:
        return json.loads(reply.read().decode("utf-8", "replace"))


def _port_open(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    try:
        with socket.create_connection((parts.hostname, parts.port or 80), timeout=1.0):
            return True
    except OSError:
        return False


def comfyui_stats(url: str, timeout: float = 5.0) -> dict | None:
    """ComfyUI's /system_stats, or None when nothing listens on the port."""
    try:
        stats = _get_json(url, "/system_stats", timeout)
    except READ_ERRORS as e:
        if _port_open(url):
            raise NotComfyUI(f"Something holds {url} and does not answer as ComfyUI ({e}).") from None
        return None
    if not (isinstance(stats, dict) and isinstance(stats.get("system"), dict)):
        raise NotComfyUI(f"Something holds {url} and does not answer as ComfyUI.")
    return stats


def describe(stats: dict) -> str:
    system = stats["system"]
    devices = stats.get("devices") or [{}]
    gpu = str(devices[0].get("name", "no device reported")).split(" : ")[0]
    return f"{system.get('comfyui_version', 'unknown version')}, Python {str(system.get('python_version', '?')).split()[0]}, {gpu}"


def comfyui_command(root: Path, python: str = sys.executable) -> str:
    """The Stable line of comfyui_launcher.bat, in a window that stays open if it fails, so its log can be read."""
    return f'cmd /c "title ComfyUI & chcp 65001 >nul & "{python}" -m comfy_cli --workspace="{root}" launch -- --reserve-vram 1.0 || pause"'


def comfyui_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "PXR_PLUGINPATH_NAME")}
    return {**env, **COMFYUI_ENV}


def start_comfyui(root: Path, minimized: bool = False) -> subprocess.Popen:
    """Its own console, so its log stays where Joe expects it."""
    startup = None
    if minimized:
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 7  # SW_SHOWMINNOACTIVE: it never takes the focus
    return subprocess.Popen(comfyui_command(root), cwd=root, env=comfyui_env(), startupinfo=startup, creationflags=subprocess.CREATE_NEW_CONSOLE)


def stop_tree(child: subprocess.Popen) -> None:
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(child.pid)], capture_output=True, check=False)


def wait_for_comfyui(url: str, child, timeout_s: float, *, say=print, poll_s: float = 1.0, clock=time.monotonic, sleep=time.sleep) -> dict:
    start = clock()
    next_note = start + 15.0
    while (now := clock()) - start < timeout_s:
        try:
            stats = comfyui_stats(url)
        except NotComfyUI:  # a server still finishing its start can hold the port before it answers
            stats = None
        if stats:
            return stats
        if child.poll() is not None:
            raise LaunchError(f"ComfyUI's window closed before ComfyUI answered (exit {child.returncode}). Its log was in that window.")
        if now >= next_note:
            say(f"[still waiting for ComfyUI: {now - start:.0f} s of {timeout_s:.0f}]")
            next_note += 15.0
        sleep(poll_s)
    raise LaunchError(f"ComfyUI did not answer at {url} in {timeout_s:.0f} s. Its window is still open and its log will say why.")


def ensure_comfyui(url: str, root: Path, *, start=start_comfyui, timeout_s: float = START_TIMEOUT_S, say=print, **wait) -> dict:
    """ComfyUI's stats. It starts ComfyUI only when nothing holds the port, so it never touches one that is already up."""
    try:
        stats = comfyui_stats(url)
    except NotComfyUI as e:
        raise LaunchError(f"{e} ComfyUI cannot start on that port, and whatever holds it is not this launcher's to stop.") from None
    if stats:
        say(f"ComfyUI   already running at {url}, so it stays as it is: {describe(stats)}")
        return stats
    if not (root / "main.py").is_file():
        raise LaunchError(f"{root} has no main.py, so it is not a ComfyUI install.")
    say(f"ComfyUI   starting from {root} in its own window")
    child = start(root)
    stats = wait_for_comfyui(url, child, timeout_s, say=say, **wait)
    say(f"ComfyUI   up at {url}: {describe(stats)}")
    return stats


def models_line(url: str, models_root: Path) -> str:
    """Whether the checkpoints ComfyUI lists are the ones under Joe's model root."""
    try:
        names = _get_json(url, "/models/checkpoints", 30.0)
    except READ_ERRORS as e:
        return f"Models    WARNING: could not read ComfyUI's checkpoint list ({e})."
    folder = models_root / "checkpoints"
    here = sum((folder / str(name).replace("\\", "/")).is_file() for name in names)
    if not here:
        return f"Models    WARNING: ComfyUI lists {len(names)} checkpoints and none are under {folder}, so it is not using your model root."
    return f"Models    {here} of the {len(names)} checkpoints ComfyUI lists are under {folder}"


def core_is_stale(repo: Path) -> bool:
    built = repo / "plexus" / ("_core.pyd" if os.name == "nt" else "_core.so")
    if not built.is_file():
        return True
    sources = [*repo.glob("crates/**/*.rs"), *repo.glob("crates/**/Cargo.toml"), repo / "Cargo.lock"]
    return any(s.stat().st_mtime > built.stat().st_mtime for s in sources if s.is_file())


def build_core(repo: Path, say=print) -> None:
    """The first build here is cold. It stays out of the harness's shared target directory, because a build there could swap a library under a live attempt."""
    say("Core      the Rust core is older than the crates, so it builds now")
    env = dict(os.environ, CARGO_BUILD_JOBS="8")
    env.pop("CARGO_TARGET_DIR", None)
    result = subprocess.run([sys.executable, str(repo / "harness" / "plexus_loop" / "build_core.py")], cwd=repo, env=env, check=False)
    if result.returncode:
        raise LaunchError(f"The Rust core did not build (exit {result.returncode}). If a Python process in {repo} is using plexus/_core.pyd, close it and start again.")


def live_run_pid(repo: Path) -> int | None:
    """The pid of a harness run that holds the lock and is alive, for the one-line note below."""
    try:
        pid = int(json.loads((repo / ".plexus_loop" / "lock").read_text(encoding="utf-8")).get("pid", 0))
    except (OSError, ValueError, AttributeError):
        return None
    if pid <= 0:
        return None
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True, errors="replace", timeout=10, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return pid if f'"{pid}"' in out else None


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Start ComfyUI the usual way, with your models, and then a Plexus session.")
    p.add_argument("--comfyui-root", type=Path, default=COMFYUI_ROOT)
    p.add_argument("--models-root", type=Path, default=MODELS_ROOT)
    p.add_argument("--url", default=COMFYUI_URL)
    p.add_argument("--timeout", type=float, default=START_TIMEOUT_S, help="seconds to wait for ComfyUI to answer")
    p.add_argument("--minimized", action="store_true", help="start ComfyUI's window minimized, without taking the focus")
    p.add_argument("--stop-comfyui-on-exit", action="store_true", help="stop ComfyUI when the session ends, only if this launcher started it")
    p.add_argument("--script", help="session commands separated by semicolons, instead of the prompt")
    p.add_argument("--sessions-root", type=Path, help="where the session folder goes")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    started: list[subprocess.Popen] = []

    def start(root: Path) -> subprocess.Popen:
        started.append(start_comfyui(root, args.minimized))  # here, so a start that times out can still be stopped
        return started[-1]

    code = 1
    try:
        print("Plexus Live\n\n[Step 1 of 3: the Rust core]")
        if core_is_stale(REPO):
            build_core(REPO)
        print("Core      matches the crates")

        print("\n[Step 2 of 3: ComfyUI]")
        if (pid := live_run_pid(REPO)) is not None:
            print(f"Note      harness run {pid} is live. ComfyUI's start is heavy for about a minute, and a busy box can cost that run a point on T1.")
        ensure_comfyui(args.url, args.comfyui_root, start=start, timeout_s=args.timeout)
        print(models_line(args.url, args.models_root))

        print("\n[Step 3 of 3: the session]")
        import plexus_session  # pxr and the Rust core load from here on

        session_args = ["--url", args.url]
        if args.script:
            session_args += ["--script", args.script]
        if args.sessions_root:
            session_args += ["--sessions-root", str(args.sessions_root)]
        code = plexus_session.main(session_args)
    except LaunchError as e:
        print(f"\nPlexus did not start: {e}", file=sys.stderr)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        if started and args.stop_comfyui_on_exit:
            stop_tree(started[0])
            print("ComfyUI stopped, because this launcher started it and --stop-comfyui-on-exit asked.")
        elif started:
            print("ComfyUI keeps running in its own window. Close that window to stop it.")
    return code


if __name__ == "__main__":
    sys.exit(main())
