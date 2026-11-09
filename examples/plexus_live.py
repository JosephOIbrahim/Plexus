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
import contextlib
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
COMFYUI_PORT = 8188  # ComfyUI's own default, so its command stays the batch file's Stable line unless --url asks for another
COMFYUI_URL = f"http://127.0.0.1:{COMFYUI_PORT}"
START_TIMEOUT_S = 300.0  # every custom node in G:\COMFYUI_Database\Custom_Nodes loads before the port opens: 47 s on Nov 4, Houdini open
STOP_SETTLE_S = 10.0  # a killed process lets go of its port after taskkill returns: about 0.1 s on a small fake, not measured on a ComfyUI with a GPU to release
CHECKPOINT_SUFFIXES = (".safetensors", ".ckpt")  # fixed here so nothing reads G: to learn them, and a stray .txt or .yaml can never warn
FAILED_MARKER = "comfyui_failed"  # under state_folder(): ComfyUI's window writes it when the program in it fails
START_LOCK = "comfyui_start.json"  # under state_folder(): the one start in progress, and whose it is

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


def state_folder() -> Path:
    """The base plexus_session.py keeps its sessions under. Read when asked, because the tests move it."""
    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home()) / "Plexus"


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


def comfyui_command(root: Path, marker: Path, python: str = sys.executable, port: int = COMFYUI_PORT) -> str:
    """The Stable line of comfyui_launcher.bat, in a window that stays open if it fails, so its log can be read.
    That open window keeps poll() at None, so the marker is how the launcher learns of the failure."""
    port_arg = "" if port == COMFYUI_PORT else f" --port {port}"
    return f'cmd /c "title ComfyUI & chcp 65001 >nul & "{python}" -m comfy_cli --workspace="{root}" launch -- --reserve-vram 1.0{port_arg} || (echo failed>"{marker}" & pause)"'


def comfyui_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "PXR_PLUGINPATH_NAME")}
    return {**env, **COMFYUI_ENV}


def start_comfyui(root: Path, minimized: bool = False, port: int = COMFYUI_PORT) -> subprocess.Popen:
    """Its own console, so its log stays where Joe expects it."""
    startup = None
    if minimized:
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 7  # SW_SHOWMINNOACTIVE: it never takes the focus
    marker = state_folder() / FAILED_MARKER
    marker.parent.mkdir(parents=True, exist_ok=True)  # cmd's echo cannot make the folder, and it would fail with nobody watching
    marker.unlink(missing_ok=True)  # a stale one would fire at once
    return subprocess.Popen(comfyui_command(root, marker, port=port), cwd=root, env=comfyui_env(), startupinfo=startup, creationflags=subprocess.CREATE_NEW_CONSOLE)


def stop_tree(child: subprocess.Popen) -> None:
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(child.pid)], capture_output=True, check=False)


def wait_for_comfyui(url: str, child, timeout_s: float, *, marker: Path | None = None, timeout_note: str = "", say=print, poll_s: float = 1.0, clock=time.monotonic, sleep=time.sleep) -> dict:
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
            ended = "" if child.returncode is None else f" (exit {child.returncode})"  # a waiter never saw the other window's code
            raise LaunchError(f"ComfyUI's window closed before ComfyUI answered{ended}. Its log was in that window.")
        if marker is not None and marker.exists():  # after the window's own check, so a window closed since its failure is not called open
            raise LaunchError(f"ComfyUI failed in its window, which stays open so its log can be read. Close that window, then start again.{timeout_note}")
        if now >= next_note:
            say(f"[still waiting for ComfyUI: {now - start:.0f} s of {timeout_s:.0f}]")
            next_note += 15.0
        sleep(poll_s)
    raise LaunchError(f"ComfyUI did not answer at {url} in {timeout_s:.0f} s.{timeout_note}")


def pid_alive(pid: int) -> bool | None:
    """Whether a process has this pid, or None when the check cannot tell."""
    if pid <= 0:  # tasklist lists pid 0 as the System Idle Process
        return False
    try:
        listed = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True, errors="replace", timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if listed.returncode:  # a filter it rejects leaves stdout empty, and that is no proof the process is gone
        return None
    return f'"{pid}"' in listed.stdout


def _start_holder(lock: Path) -> int | None:
    """The pid the start file names, 0 when the file is gone, None when it cannot be read. A launcher writes
    the file in two steps, so an empty read is most likely a write in progress."""
    try:
        return int(json.loads(lock.read_text(encoding="utf-8"))["pid"])
    except FileNotFoundError:
        return 0
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        return None


def _claimed(lock: Path) -> bool:
    """Whether this launcher made the start file, naming itself until its window has a pid."""
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"pid": os.getpid()}, f)
    return True


def claim_start(lock: Path) -> int | None:
    """None when the one ComfyUI start is now this launcher's. Otherwise the pid that holds it, or 0 when its file
    cannot be read. A dead holder is taken over once; a live one, or one the check cannot tell about, keeps it."""
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
        if _claimed(lock):
            return None
        pid = _start_holder(lock)
        if pid is None or pid_alive(pid) is not False:
            return pid or 0
        if _start_holder(lock) == pid:  # tasklist takes most of a second, and another launcher can take over in that time
            lock.unlink(missing_ok=True)
        return None if _claimed(lock) else _start_holder(lock) or 0
    except OSError as e:
        raise LaunchError(f"Could not use {lock} ({e}), so this launcher cannot tell whether another start is still loading.") from None


class OtherStart:
    """Stands in for the window another launcher started. poll() reads the start file each time, because that
    launcher names itself first and its window after."""

    def __init__(self, lock: Path):
        self.lock = lock
        self.returncode = None

    def poll(self) -> int | None:
        pid = _start_holder(self.lock)
        # A file that is gone is no closed window: the other launcher removes it once the port answers, which
        # can land after this launcher's read of the port and before this read. The next read of the port says so.
        if not pid or pid_alive(pid) is not False:
            return None
        return 0


def ensure_comfyui(url: str, root: Path, *, start=start_comfyui, timeout_s: float = START_TIMEOUT_S, say=print, **wait) -> dict:
    """ComfyUI's stats. It starts ComfyUI only when nothing holds the port and no other launcher's start is
    loading, so it never touches one that is already up."""
    try:
        stats = comfyui_stats(url)
    except NotComfyUI as e:
        raise LaunchError(f"{e} ComfyUI cannot start on that port, and whatever holds it is not this launcher's to stop.") from None
    if stats:
        say(f"ComfyUI   already running at {url}, so it stays as it is: {describe(stats)}")
        return stats
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "http" or parts.hostname not in ("127.0.0.1", "localhost"):  # ComfyUI starts here on plain http, so the wait would run out on an address it never serves
        raise LaunchError(f"Nothing answers at {url}, and this launcher can start ComfyUI only at an http URL on this machine. Start it there, or leave --url out.")
    if not (root / "main.py").is_file():
        raise LaunchError(f"{root} has no main.py, so it is not a ComfyUI install.")
    marker, lock = state_folder() / FAILED_MARKER, state_folder() / START_LOCK
    holder = claim_start(lock)
    if holder is None:
        say(f"ComfyUI   starting from {root} in its own window")
        child = start(root)
        with contextlib.suppress(OSError):  # the window can outlive this launcher, so it is what the next one has to watch
            lock.write_text(json.dumps({"pid": child.pid}), encoding="utf-8")
        stats = wait_for_comfyui(url, child, timeout_s, marker=marker, say=say, **wait)
        with contextlib.suppress(OSError):  # only here: after a timeout that window can still be loading
            lock.unlink(missing_ok=True)
    else:
        say(f"ComfyUI   another launcher's start is still loading (pid {holder or 'unknown'}), so this one waits for it")
        stats = wait_for_comfyui(url, OtherStart(lock), timeout_s, marker=marker, timeout_note=f" If that window is gone, delete {lock}.", say=say, **wait)
    say(f"ComfyUI   up at {url}: {describe(stats)}")
    return stats


def models_line(url: str, models_root: Path) -> str:
    """Whether the checkpoints ComfyUI lists and the ones under Joe's model root agree, read from both sides."""
    try:
        names = _get_json(url, "/models/checkpoints", 30.0)
    except READ_ERRORS as e:
        return f"Models    WARNING: could not read ComfyUI's checkpoint list ({e})."
    folder = models_root / "checkpoints"
    listed = [str(name).replace("\\", "/") for name in names]
    on_disk = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.suffix.casefold() in CHECKPOINT_SUFFIXES and p.is_file())
    if not listed and not on_disk:
        return f"Models    ComfyUI lists no checkpoints and {folder} holds none."
    known = {name.casefold() for name in listed}
    unlisted = [name for name in on_disk if name.casefold() not in known]
    if unlisted:
        return f"Models    WARNING: ComfyUI does not list {len(unlisted)} of the {len(on_disk)} checkpoint files under {folder}, starting with {unlisted[0]}, so ComfyUI may not be reading that folder."
    here = sum((folder / name).is_file() for name in listed)
    if not here:
        return f"Models    WARNING: ComfyUI lists {len(names)} checkpoints and none are under {folder}, so it is not using your model root."
    return f"Models    {here} of the {len(names)} checkpoints ComfyUI lists are under {folder}"


def core_file(repo: Path) -> Path:
    return repo / "plexus" / ("_core.pyd" if os.name == "nt" else "_core.so")


def core_is_stale(repo: Path) -> bool:
    built = core_file(repo)
    if not built.is_file():
        return True
    sources = [*repo.glob("crates/**/*.rs"), *repo.glob("crates/**/Cargo.toml"), repo / "Cargo.lock", repo / "Cargo.toml"]  # the root file's profiles change what cargo builds
    return any(s.stat().st_mtime > built.stat().st_mtime for s in sources if s.is_file())


def build_core(repo: Path, say=print) -> None:
    """The first build here is cold. It stays out of the harness's shared target directory, because a build there could swap a library under a live attempt."""
    say("Core      the Rust core is missing or older than the crates, so it builds now")
    env = dict(os.environ, CARGO_BUILD_JOBS="8")
    env.pop("CARGO_TARGET_DIR", None)
    began = time.time()
    result = subprocess.run([sys.executable, str(repo / "harness" / "plexus_loop" / "build_core.py")], cwd=repo, env=env, check=False)
    if result.returncode:
        raise LaunchError(f"The Rust core did not build (exit {result.returncode}). If a Python process in {repo} is using plexus/_core.pyd, close it and start again.")
    # Cargo has nothing to do for a crate file with a new time and the same bytes, and the copy keeps the library's old
    # time, so that file would read as newer on every launch. The build's start, so an edit made during it still does.
    with contextlib.suppress(OSError):
        os.utime(core_file(repo), (began, began))


def live_run_pid(repo: Path) -> int | None:
    """The pid of a harness run that holds the lock and is alive, for the one-line note below."""
    try:
        pid = int(json.loads((repo / ".plexus_loop" / "lock").read_text(encoding="utf-8")).get("pid", 0))
    except (OSError, ValueError, AttributeError):
        return None
    return pid if pid_alive(pid) else None


def _url_is_usable(url: str) -> bool:
    try:  # urlsplit itself raises on a bad bracket, and .port on a bad port
        parts = urllib.parse.urlsplit(url)
        return parts.scheme in ("http", "https") and bool(parts.hostname and parts.port)
    except ValueError:
        return False


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
    p.add_argument("--workflow", type=Path, help="a ComfyUI API-format graph the neuron sends on each wake, instead of the swatch")
    p.add_argument("--no-organ", action="store_true", help="the neuron writes its grade hint only and sends ComfyUI nothing")
    args = p.parse_args(argv)
    if not _url_is_usable(args.url):  # without a scheme it reads as nothing listening, and ComfyUI would start beside one already up
        raise SystemExit(f"Plexus did not start: --url needs http or https, a host and a port, such as {COMFYUI_URL}. It got {args.url}.")
    args.comfyui_root = args.comfyui_root.absolute()  # the window starts inside this folder, where a relative path would point inside itself
    return args


def _still_answers_after_the_kill(url: str) -> bool:
    """One read right after taskkill said open on 2 of 3 kills that worked, so only a port that stays open counts."""
    deadline = time.monotonic() + STOP_SETTLE_S
    while _port_open(url):
        if time.monotonic() >= deadline:
            return True
        time.sleep(0.1)
    return False


def final_line(child, url: str, stop: bool) -> str:
    """The launcher's last word on the window it started. The window is read before any kill, because the kill
    closes it, and the port after. Taskkill's code is never read: a server that left the tree survives a kill that worked."""
    if child.poll() is not None:  # no kill: a closed window's pid can already belong to something else, and /T /F would take that down
        if _port_open(url):
            return f"ComfyUI's window has closed and something still answers at {url}. This launcher sent it no kill, so stop it by hand if it should not be running."
        return "ComfyUI's window had already closed, so there was nothing to stop." if stop else "ComfyUI's window has closed, so ComfyUI is not running."
    if (state_folder() / FAILED_MARKER).exists():  # no kill, flag or not: that window holds the only log of the failure, and the error above told the operator to read it there
        return "ComfyUI failed and its window stays open at its error. Close it after reading its log."
    if stop:
        stop_tree(child)
        if _still_answers_after_the_kill(url):
            return f"ComfyUI still answers at {url} after this launcher tried to stop it, so stop it by hand."
        return "ComfyUI stopped, because this launcher started it and --stop-comfyui-on-exit asked."
    if not _port_open(url):
        return f"ComfyUI keeps running in its own window and has not answered at {url}. Its log will say why."
    return "ComfyUI keeps running in its own window. Close that window to stop it."


def main(argv=None) -> int:
    args = parse_args(argv)
    started: list[subprocess.Popen] = []

    def start(root: Path) -> subprocess.Popen:
        started.append(start_comfyui(root, args.minimized, urllib.parse.urlsplit(args.url).port))  # here, so a start that times out can still be stopped
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
        if args.workflow:
            session_args += ["--workflow", str(args.workflow.absolute())]
        if args.no_organ:
            session_args += ["--no-organ"]
        code = plexus_session.main(session_args)
    except LaunchError as e:
        print(f"\nPlexus did not start: {e}", file=sys.stderr)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        if started:  # a launcher that waited on another start never enters this list, so that window stays the other's to describe
            print(final_line(started[0], args.url, args.stop_comfyui_on_exit))
    return code


if __name__ == "__main__":
    sys.exit(main())
