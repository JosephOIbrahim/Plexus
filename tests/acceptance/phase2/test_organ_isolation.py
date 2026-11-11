"""Isolation · Each ComfyUI that CozyLifecycle starts keeps to its own folders and its own process tree: CONTRACT's M3.1 sentences.

M3.1 closes what the first live run (D4, Nov 11) and the M3 review found. Given an instance folder, CozyLifecycle hands ComfyUI its own
user folder, database, temp folder and output, so a second ComfyUI started from the workspace another session runs on 8188 never takes,
shares or wipes that instance's files. A start that cannot make a folder or open its log fails as 'unavailable', never a stale
'starting'. A second start() waits while its own engine still loads. The tree is everything the root started, so a root that exits
early cannot leave main.py behind, and on Windows the engine ends with the host that started it.

Nothing here runs the real comfy-cli or ComfyUI, touches port 8188 or leaves this machine. FAKE_CLI stands in for `python -m comfy_cli`
as in test_organ_lifecycle.py, with two more modes: `orphan`, where the cli starts main.py, waits until it answers and exits, leaving it
running, and `orphan_early`, where the cli starts main.py and exits at once, before main.py binds. FAKE_MAIN models what ComfyUI does
with its folders, from G:/COMFY/ComfyUI as of Nov 11: --user-directory must be an existing folder (comfy/cli_args.py:256); with no
--database-url, a user folder other than the workspace's own takes the workspace's user/comfyui.db, renaming it to .bak
(app/database/db.py:86-108); the temp folder is deleted at start (main.py:488-491). Every workspace starts with the files of "the 8188
instance": user/comfyui.db, temp/keep.txt and output/keep.png. A workspace file `notyet` makes /system_stats answer 404, as a server that
is up but not yet ComfyUI does. Every fake main.py writes its pid to main_pid first and ends itself on a `die` file or after 120 s.

What this file pins: the six M3.1 sentences of CONTRACT under plexus.organs. The last case runs only on Windows, where the sentence it
reads applies. Left open on purpose: the words of every message past the path or port it names, the folder names' case, how the tree is
held (a Job Object on Windows, the process group on POSIX), and a start lock between hosts, which waits for a later mission.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from tests.acceptance._support import PY, child_env
from tests.acceptance.phase2.test_organ_lifecycle import (
    CHILD_S,
    CONSTRUCT_S,
    FORBIDDEN_PORT,
    POLL_S,
    START_S,
    STOP_S,
    Reports,
    cli_runs,
    free_port,
    lifecycle_class,
    organ_error,
    raised_organ_error,
    refused,
    stats_status,
    until,
    value_of,
    within,
)

FLAGS = ("--user-directory", "--database-url", "--temp-directory", "--output-directory")
DB_BYTES = b"the 8188 instance's database"

SENTENCE_I1 = (
    "CONTRACT: CozyLifecycle also takes instance: Path | None = None. Given a folder, it resolves it to an absolute path, and start() makes "
    "whichever of <instance>/user, <instance>/temp and <instance>/output is missing, keeping what they hold, and runs sentence 7's argv with '--user-directory', str(<instance>/user), "
    "'--database-url', 'sqlite:///' + (<instance>/user/comfyui.db).as_posix(), '--temp-directory', str(<instance>/temp), "
    "'--output-directory', str(<instance>/output) between str(port) and *extra, so this ComfyUI never takes, shares or wipes the "
    "workspace's own database, user folder, temp folder or output; with instance=None the argv is exactly sentence 7's."
)
SENTENCE_I2 = (
    "CONTRACT: the constructor raises ValueError before it measures or reports when instance resolves to the workspace itself, or when extra "
    "names --user-directory, --database-url, --temp-directory or --output-directory (alone or as flag=value) while instance is given."
)
SENTENCE_I3 = (
    "CONTRACT: when start() cannot make an instance folder, open log or run command, it reports 'unavailable' and raises OrganError naming "
    "that path, spawning nothing, so 'starting' is never the last state a start leaves."
)
SENTENCE_I4 = (
    "CONTRACT: while a process this lifecycle started is alive, start() takes any measurement but 'ready' as not yet, so a first start() whose "
    "own engine answers before it is ComfyUI keeps waiting, and a further start() made while its own engine still loads waits as the first one "
    "does and reports nothing before 'ready'."
)
SENTENCE_I5 = (
    "CONTRACT: the tree is everything the root started, including what it leaves running after it exits: when the root exits before 'ready', "
    "start() kills what it left, reports 'unavailable' and raises OrganError, and stop() ends the tree even after the root has exited. stop_s "
    "bounds the waits after the kill, not the kill itself, and a kill or a wait that fails raises OrganError and nothing else."
)
SENTENCE_I6 = (
    "CONTRACT: on Windows the tree also ends when the host process ends, however it ends, so an engine never outlives the host that started it."
)
HOW_TREE = (
    "On Windows, put the root in a Job Object right after Popen (JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE) and end the tree with "
    "TerminateJobObject, which reaches main.py after comfy-cli has exited; taskkill /T cannot, because it walks children from a root that is gone."
)

# Stands in for `python -m comfy_cli` in the foreground. Imports nothing from plexus.
FAKE_CLI = r'''
import json, os, socket, subprocess, sys, threading, time
argv = sys.argv[1:]
ws = next(a.split("=", 1)[1] for a in argv if a.startswith("--workspace="))
got = []
reader = threading.Thread(target=lambda: got.append(sys.stdin.read() if sys.stdin else None), daemon=True)
reader.start()
reader.join(1.0)
with open(os.path.join(ws, "cli_seen.jsonl"), "a", encoding="utf-8") as f:
    f.write(json.dumps({"argv": argv, "pid": os.getpid(), "stdin_eof": got == [""]}) + "\n")
mode_file = os.path.join(ws, "mode")
mode = open(mode_file).read().strip() if os.path.exists(mode_file) else "serve"
os.chdir(ws)
extra = argv[argv.index("--") + 1:]
if mode in ("orphan", "orphan_early"):
    subprocess.Popen([sys.executable, "main.py"] + extra)
    if mode == "orphan":
        port = int(extra[extra.index("--port") + 1])
        end = time.monotonic() + 60
        while time.monotonic() < end:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                time.sleep(0.1)
        time.sleep(2.0)
    os._exit(0)
sys.exit(subprocess.run([sys.executable, "main.py"] + extra).returncode)
'''

# Stands in for ComfyUI's main.py, with what ComfyUI does to its folders.
FAKE_MAIN = r'''
import json, os, shutil, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
with open("main_pid", "w") as f:
    f.write(str(os.getpid()))
end = time.monotonic() + 120
def watch():
    while time.monotonic() < end and not os.path.exists("die"):
        time.sleep(0.1)
    os._exit(0)
threading.Thread(target=watch, daemon=True).start()
args = sys.argv[1:]
def opt(name):
    return args[args.index(name) + 1] if name in args else None
listen, port = opt("--listen"), int(opt("--port"))
ws = os.getcwd()
user = opt("--user-directory") or os.path.join(ws, "user")
temp = opt("--temp-directory") or os.path.join(ws, "temp")
output = opt("--output-directory") or os.path.join(ws, "output")
url = opt("--database-url")
seen = {"argv": args, "existed": {"user": os.path.isdir(user), "temp": os.path.isdir(temp), "output": os.path.isdir(output)}}
with open("main_seen.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps(seen) + "\n")
if not os.path.isdir(user):
    print(f"main.py: error: argument --user-directory: {user} is not a valid directory", file=sys.stderr, flush=True)
    sys.exit(2)
db = url.split("///", 1)[1] if url else os.path.join(user, "comfyui.db")
legacy = os.path.join(ws, "user", "comfyui.db")
if url is None and os.path.abspath(legacy) != os.path.abspath(db) and not os.path.exists(db) and os.path.exists(legacy) \
        and not os.path.exists(legacy + ".bak"):
    os.replace(legacy, legacy + ".bak")
    shutil.copy(legacy + ".bak", db)
elif not os.path.exists(db):
    os.makedirs(os.path.dirname(db), exist_ok=True)
    open(db, "wb").close()
shutil.rmtree(temp, ignore_errors=True)
os.makedirs(temp, exist_ok=True)
mode = open("mode").read().strip() if os.path.exists("mode") else "serve"
if mode == "orphan_early":
    time.sleep(3.0)
STATS = {"system": {"os": "nt", "comfyui_version": "0.3.99", "python_version": "3.12.0", "pytorch_version": "2.9.0"}, "devices": []}
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_GET(self):
        if self.path.startswith("/system_stats") and os.path.exists("notyet"):
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = json.dumps(STATS if self.path.startswith("/system_stats") else {}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
server = ThreadingHTTPServer((listen, port), H)
print(f"To see the GUI go to: http://{listen}:{port}", flush=True)
server.serve_forever(poll_interval=0.05)
'''


def alive(pid):
    """True while process pid runs. Never signals it: os.kill on Windows would end it."""
    if os.name == "nt":
        import ctypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = ctypes.c_void_p
        k32.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
        k32.GetExitCodeProcess.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32))
        k32.CloseHandle.argtypes = (ctypes.c_void_p,)
        handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_uint32()
        try:
            ok = k32.GetExitCodeProcess(handle, ctypes.byref(code))
        finally:
            k32.CloseHandle(handle)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    # An exited child nobody has reaped still answers kill(pid, 0); its state letter is Z.
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        return stat[stat.rindex(")") + 2] != "Z"
    except (OSError, ValueError, IndexError):
        state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
        return bool(state) and not state.startswith("Z")


def main_pid(ws):
    p = ws / "main_pid"
    return int(p.read_text()) if p.exists() and p.read_text().strip() else None


def main_runs(ws):
    p = ws / "main_seen.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


class Rig:
    def __init__(self, tmp_path):
        self.root = tmp_path
        self.cli = tmp_path / "fake_cli.py"
        self.cli.write_text(FAKE_CLI, encoding="utf-8")
        self.command = [PY, str(self.cli)]
        self.spaces, self.lifes = [], []

    def workspace(self, name, mode=None):
        """A workspace with FAKE_MAIN and the 8188 instance's files in user/, temp/ and output/."""
        ws = self.root / f"ws_{name}"
        for d in ("user", "temp", "output"):
            (ws / d).mkdir(parents=True)
        (ws / "main.py").write_text(FAKE_MAIN, encoding="utf-8")
        (ws / "user" / "comfyui.db").write_bytes(DB_BYTES)
        (ws / "temp" / "keep.txt").write_text("the 8188 instance's temp file")
        (ws / "output" / "keep.png").write_bytes(b"the 8188 instance's output")
        if mode:
            (ws / "mode").write_text(mode)
        self.spaces.append(ws)
        return ws

    def life(self, ws, port, report, **kw):
        cls = lifecycle_class()
        assert port != FORBIDDEN_PORT
        kw.setdefault("poll_s", POLL_S)
        box = within(lambda: cls(ws, port, command=self.command, report=report, **kw), "CozyLifecycle(...)", CONSTRUCT_S)
        if "raised" in box:
            e = box["raised"]
            raise AssertionError(f"CozyLifecycle({ws.name}, {port}, {', '.join(f'{k}=...' for k in kw)}) raised {type(e).__name__}: {e}. {SENTENCE_I1}")
        self.lifes.append(box["value"])
        return box["value"]

    def close(self):
        for ws in self.spaces:
            try:
                (ws / "die").write_text("")
            except OSError:
                pass
        for life in self.lifes:
            within(life.stop, "teardown stop()", STOP_S, must_return=False)


@pytest.fixture(autouse=True)
def nothing_reaches_the_real_comfy(tmp_path, monkeypatch):
    """comfy-cli's config path follows USERPROFILE (HOME on POSIX); a socket in this process may not connect to port 8188."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    real = socket.socket.connect, socket.socket.connect_ex

    def guard(fn):
        def connect(self, address):
            if isinstance(address, tuple) and len(address) >= 2 and address[1] == FORBIDDEN_PORT:
                raise AssertionError(f"Something in this test connected to port {FORBIDDEN_PORT}, another session's ComfyUI. Use the port given.")
            return fn(self, address)
        return connect

    monkeypatch.setattr(socket.socket, "connect", guard(real[0]))
    monkeypatch.setattr(socket.socket, "connect_ex", guard(real[1]))
    yield


@pytest.fixture
def rig(tmp_path):
    r = Rig(tmp_path)
    yield r
    r.close()


def untouched(ws):
    """What changed among the 8188 instance's files in ws; empty when nothing did."""
    changed = []
    db = ws / "user" / "comfyui.db"
    if not db.exists():
        changed.append("user/comfyui.db is gone")
    elif db.read_bytes() != DB_BYTES:
        changed.append("user/comfyui.db was rewritten")
    if (ws / "user" / "comfyui.db.bak").exists():
        changed.append("user/comfyui.db.bak appeared: the database was taken")
    if not (ws / "temp" / "keep.txt").exists():
        changed.append("temp/keep.txt is gone: the temp folder was wiped")
    if not (ws / "output" / "keep.png").exists():
        changed.append("output/keep.png is gone")
    return changed


def started(life, ws, port, why):
    box = within(life.start, "start()", START_S)
    got = value_of(box, "start()", why)
    assert got == "ready", f"start() returned {got!r} on a free port with a workspace that has main.py, and it returns 'ready'. {why}"


# ---------- an instance folder ----------


def test_an_instance_keeps_comfyui_off_the_workspaces_own_files(rig, monkeypatch):
    """IS1. The instance is given relative to the host's working folder when the constructor runs, through a '..', and the host's working
    folder moves before start(); the command runs in the workspace, so only a path resolved in the constructor holds. An earlier session
    left a database and an output in the instance, and they are kept."""
    port = free_port()
    ws = rig.workspace("is1")
    home = (rig.root / "instances" / "is1").resolve()
    (home / "user").mkdir(parents=True)
    (home / "output").mkdir()
    earlier_db = b"the database an earlier session of this instance left"
    (home / "user" / "comfyui.db").write_bytes(earlier_db)
    (home / "output" / "earlier.png").write_bytes(b"an output an earlier session left")
    monkeypatch.chdir(rig.root)
    inst = Path("instances") / "x" / ".." / "is1"
    reports = Reports()
    life = rig.life(ws, port, reports, instance=inst, extra=["--cpu"], ready_s=START_S - 2)
    elsewhere = rig.root / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    started(life, ws, port, SENTENCE_I1)
    runs = cli_runs(ws)
    assert len(runs) == 1, f"The command ran {len(runs)} times for one start(): {runs}."
    want = ["--skip-prompt", f"--workspace={ws}", "launch", "--", "--listen", "127.0.0.1", "--port", str(port),
            "--user-directory", str(home / "user"), "--database-url", "sqlite:///" + (home / "user" / "comfyui.db").as_posix(),
            "--temp-directory", str(home / "temp"), "--output-directory", str(home / "output"), "--cpu"]
    assert runs[0]["argv"] == want, f"With instance={inst} and extra=['--cpu'], the command got {runs[0]['argv']}, and it gets {want}. {SENTENCE_I1}"
    seen = main_runs(ws)
    assert seen and all(seen[0]["existed"].values()), (
        f"When main.py started, the instance folders existed: {seen[0]['existed'] if seen else 'main.py never ran'}. ComfyUI refuses a "
        f"--user-directory that is not a folder (comfy/cli_args.py:256), so start() makes all three before it spawns. {SENTENCE_I1}"
    )
    db = home / "user" / "comfyui.db"
    assert db.exists() and db.read_bytes() == earlier_db, (
        f"The database an earlier session left at {db} is {'gone' if not db.exists() else 'rewritten'}: start() makes only the folders that "
        f"are missing and keeps what they hold. {SENTENCE_I1}"
    )
    assert (home / "output" / "earlier.png").exists(), f"The output an earlier session left in {home / 'output'} is gone. {SENTENCE_I1}"
    got = value_of(within(life.stop, "stop()", STOP_S), "stop()", SENTENCE_I1)
    assert got == "stopped", f"stop() returned {got!r}."
    changed = untouched(ws)
    assert not changed, (
        f"Starting and stopping a ComfyUI with its own instance folder changed the workspace's own files: {changed}. ComfyUI moves the workspace's "
        f"database into a new --user-directory unless --database-url is given (app/database/db.py:86-108), and deletes its temp folder at start "
        f"(main.py:488-491). {SENTENCE_I1}"
    )


# instance and extra that the constructor refuses: (instance, extra), the workspace written through a '..' so only a resolved path matches
REFUSED = {"the workspace itself, written ws/user/..": ("workspace", ["--cpu"])}
for _flag in FLAGS:
    REFUSED[f"extra also names {_flag}"] = ("own", ["--cpu", _flag, "elsewhere"])
    REFUSED[f"extra also names {_flag}=..."] = ("own", [f"{_flag}=elsewhere"])


@pytest.mark.parametrize("case", sorted(REFUSED))
def test_an_instance_that_is_the_workspace_or_clashes_with_extra_is_refused(rig, case):
    """IS2."""
    where, extra = REFUSED[case]
    port = free_port()
    ws = rig.workspace(f"is2_{len(rig.spaces)}")
    inst = ws / "user" / ".." if where == "workspace" else rig.root / "instances" / f"is2_{len(rig.spaces)}"
    reports = Reports()
    cls = lifecycle_class()
    box = within(lambda: cls(ws, port, command=rig.command, report=reports, instance=inst, extra=extra, poll_s=POLL_S),
                 "CozyLifecycle(...)", CONSTRUCT_S)
    if "value" in box:
        rig.lifes.append(box["value"])
    assert "raised" in box and isinstance(box["raised"], ValueError), (
        f"CozyLifecycle with {case} {'raised ' + type(box['raised']).__name__ + ': ' + str(box['raised']) if 'raised' in box else 'was built'}, "
        f"and it raises ValueError. {SENTENCE_I2}"
    )
    assert reports.states == [], f"The constructor reported {reports.states} before it raised, and it raises before it measures. {SENTENCE_I2}"
    assert not cli_runs(ws), f"The command ran: {cli_runs(ws)}. {SENTENCE_I2}"


def test_without_an_instance_extra_may_name_the_folders(rig):
    """IS2b. The four flags are refused only beside an instance: with instance=None, extra passes to ComfyUI as before."""
    port = free_port()
    ws = rig.workspace("is2b")
    reports = Reports()
    cls = lifecycle_class()
    extra = ["--temp-directory", str(rig.root / "own_temp"), "--output-directory=" + str(rig.root / "own_output")]
    box = within(lambda: cls(ws, port, command=rig.command, report=reports, extra=extra, poll_s=POLL_S), "CozyLifecycle(...)", CONSTRUCT_S)
    if "value" in box:
        rig.lifes.append(box["value"])
    value_of(box, "CozyLifecycle(..., extra naming --temp-directory and --output-directory, no instance)", SENTENCE_I2)
    assert reports.states == ["stopped"], f"The constructor reported {reports.states}. {SENTENCE_I2}"


# ---------- a start that cannot begin ----------

# What cannot be made, opened or run; the path the OrganError names is set per case.
CANNOT = ("log whose folder is a file", "instance is a file", "command does not exist")


@pytest.mark.parametrize("case", CANNOT)
def test_a_start_that_cannot_make_its_folders_or_open_its_log_is_unavailable_and_named(rig, case):
    """IS3. A log under main.py, a file, cannot be opened or made, whatever the lifecycle tries."""
    port = free_port()
    ws = rig.workspace(f"is3_{CANNOT.index(case)}")
    reports = Reports()
    if case == CANNOT[0]:
        log = ws / "main.py" / "comfy.log"
        life, named = rig.life(ws, port, reports, log=log), str(log)
    elif case == CANNOT[1]:
        inst = rig.root / "instance_is_a_file"
        inst.write_text("not a folder")
        life, named = rig.life(ws, port, reports, instance=inst), str(inst.resolve())
    else:
        missing = rig.root / "no_such_cli.exe"
        cls = lifecycle_class()
        box = within(lambda: cls(ws, port, command=[str(missing)], report=reports, poll_s=POLL_S), "CozyLifecycle(...)", CONSTRUCT_S)
        life, named = value_of(box, "CozyLifecycle(...) with a command that does not exist", SENTENCE_I3), str(missing)
        rig.lifes.append(life)
    e = raised_organ_error(within(life.start, "start()", START_S), f"start() where the {case}", SENTENCE_I3)
    assert named in str(e), f"The OrganError reads {str(e)!r}, without the path {named}. {SENTENCE_I3}"
    assert reports.states[-1:] == ["unavailable"], f"After a start where the {case}, report last saw {reports.states[-1:]}, so the stage keeps a stale state. {SENTENCE_I3}"
    assert not cli_runs(ws), f"start() ran the command although the {case}: {cli_runs(ws)}. {SENTENCE_I3}"
    assert refused(port), f"After a start where the {case}, port {port} accepts a connection. {SENTENCE_I3}"


# ---------- a second start while its own engine loads ----------


def test_a_second_start_waits_while_its_own_engine_still_loads(rig):
    """IS4. The engine answers 404 on /system_stats while `notyet` exists, as a server that is up but not yet ComfyUI does."""
    port = free_port()
    ws = rig.workspace("is4")
    reports = Reports()
    life = rig.life(ws, port, reports, ready_s=START_S - 2)
    started(life, ws, port, SENTENCE_I4)
    (ws / "notyet").write_text("")
    probed = value_of(within(life.probe, "probe()", CONSTRUCT_S), "probe()", SENTENCE_I4)
    assert probed == "unavailable", f"With /system_stats answering 404, probe() read {probed!r}; this test needs 'unavailable' to mean anything."
    n = len(reports.states)
    box = {}

    def again():
        try:
            box["value"] = life.start()
        except BaseException as e:  # noqa: BLE001 - handed back to the test's own thread
            box["raised"] = e

    second = threading.Thread(target=again, daemon=True)
    second.start()
    time.sleep(1.5)
    early = dict(box)
    (ws / "notyet").unlink()
    second.join(START_S)
    assert not early, (
        f"start(), called while this lifecycle's own engine was still loading, came back within 1.5 s with "
        f"{'raised ' + type(early['raised']).__name__ + ': ' + str(early['raised']) if 'raised' in early else repr(early.get('value'))}. {SENTENCE_I4}"
    )
    assert not second.is_alive(), f"start() had not returned {START_S:g} s after the engine became ComfyUI. {SENTENCE_I4}"
    got = value_of(box, "start() while its own engine was loading", SENTENCE_I4)
    assert got == "ready" and reports.states[n:] == ["ready"], (
        f"start() while its own engine was loading returned {got!r} and reported {reports.states[n:]}, and it returns 'ready' and reports "
        f"['ready']. {SENTENCE_I4}"
    )
    assert len(cli_runs(ws)) == 1, f"start() while its own engine was loading ran the command again: {cli_runs(ws)}. {SENTENCE_I4}"


def test_a_first_start_waits_while_its_own_engine_still_loads(rig):
    """IS4b. `notyet` is there before the first start(), so its own engine answers 404 until the test removes it."""
    port = free_port()
    ws = rig.workspace("is4b")
    (ws / "notyet").write_text("")
    reports = Reports()
    life = rig.life(ws, port, reports, ready_s=START_S - 2)
    box = {}

    def first():
        try:
            box["value"] = life.start()
        except BaseException as e:  # noqa: BLE001 - handed back to the test's own thread
            box["raised"] = e

    thread = threading.Thread(target=first, daemon=True)
    thread.start()
    answered = until(lambda: not refused(port), 15.0, every=0.2)
    time.sleep(1.5)
    early = dict(box)
    (ws / "notyet").unlink()
    thread.join(START_S)
    assert answered and not early, (
        f"start(), whose own engine answered 404 while it loaded, came back with "
        f"{'raised ' + type(early['raised']).__name__ + ': ' + str(early['raised']) if 'raised' in early else repr(early.get('value'))} "
        f"before the engine became ComfyUI. {SENTENCE_I4}"
    )
    got = value_of(box, "start() while its own engine was loading", SENTENCE_I4)
    assert got == "ready" and reports.states == ["stopped", "starting", "ready"], (
        f"start() returned {got!r} and report saw {reports.states}, and it is ['stopped', 'starting', 'ready']. {SENTENCE_I4}"
    )


# ---------- the tree, after its root ----------


def test_stop_ends_what_the_root_left_running(rig):
    """IS5. The cli starts main.py, waits until it answers and exits, leaving main.py holding the port."""
    port = free_port()
    ws = rig.workspace("is5", mode="orphan")
    reports = Reports()
    life = rig.life(ws, port, reports, ready_s=START_S - 2, stop_s=5.0)
    started(life, ws, port, SENTENCE_I5)
    runs = cli_runs(ws)
    assert runs, "The fake cli never ran."
    assert until(lambda: not alive(runs[0]["pid"]), 15.0, every=0.2), "The fake cli had not exited 15 s after main.py answered; this test needs it gone."
    pid = main_pid(ws)
    assert pid and alive(pid) and stats_status(life.endpoint) == 200, "main.py is not answering on its own after the cli exited; this test needs it to."
    got = value_of(within(life.stop, "stop()", STOP_S), "stop() after the root exited", SENTENCE_I5 + " " + HOW_TREE)
    assert got == "stopped", f"stop() after the root exited returned {got!r}. {SENTENCE_I5}"
    assert refused(port), f"stop() returned 'stopped', and main.py, which the root left running, still holds port {port}. {SENTENCE_I5} {HOW_TREE}"
    assert until(lambda: not alive(pid), 5.0, every=0.2), f"main.py (pid {pid}) is still running 5 s after stop(). {SENTENCE_I5} {HOW_TREE}"


def test_a_root_that_exits_before_ready_takes_what_it_left_with_it(rig):
    """IS6. The cli starts main.py and exits at once; main.py binds 3 s later."""
    port = free_port()
    ws = rig.workspace("is6", mode="orphan_early")
    reports = Reports()
    life = rig.life(ws, port, reports, ready_s=START_S - 2)
    raised_organ_error(within(life.start, "start()", START_S), "start() whose root exited before main.py answered", SENTENCE_I5)
    assert reports.states[-1:] == ["unavailable"], f"After a root that exited first, report last saw {reports.states[-1:]}. {SENTENCE_I5}"
    time.sleep(5.0)
    pid = main_pid(ws)
    assert refused(port), (
        f"5 s after start() raised, main.py, which the exited root had started, holds port {port}: start() left it running. {SENTENCE_I5} {HOW_TREE}"
    )
    assert pid is None or not alive(pid), f"main.py (pid {pid}) is still running 5 s after start() raised. {SENTENCE_I5} {HOW_TREE}"


def test_a_stop_with_too_little_time_still_kills_the_tree_and_raises_only_organ_error(rig):
    """IS7. stop_s=0.01: no kill and no wait fits, and the tree still ends."""
    port = free_port()
    ws = rig.workspace("is7")
    reports = Reports()
    life = rig.life(ws, port, reports, ready_s=START_S - 2, stop_s=0.01)
    started(life, ws, port, SENTENCE_I5)
    pid = main_pid(ws)
    box = within(life.stop, "stop() with stop_s=0.01", STOP_S)
    if "raised" in box:
        e = box["raised"]
        assert isinstance(e, organ_error()), (
            f"stop() with stop_s=0.01 raised {type(e).__name__}: {e}, and a kill or its wait that fails raises OrganError and nothing else. "
            f"{SENTENCE_I5} {HOW_TREE}"
        )
    else:
        assert box.get("value") == "stopped", f"stop() with stop_s=0.01 returned {box.get('value')!r}. {SENTENCE_I5}"
    assert until(lambda: refused(port), 10.0, every=0.2), f"10 s after stop() with stop_s=0.01, port {port} still accepts a connection: the tree was not killed. {SENTENCE_I5}"
    assert pid is None or until(lambda: not alive(pid), 5.0, every=0.2), f"main.py (pid {pid}) is still running after stop() with stop_s=0.01. {SENTENCE_I5}"


# ---------- the host ----------

HOST = r"""
import json, os, sys
from pathlib import Path
ws, port, cli = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
try:
    from plexus.organs.cozy import CozyLifecycle
    life = CozyLifecycle(ws, port, command=[sys.executable, cli], report=lambda s: None, ready_s=18.0, poll_s=0.25)
    state = life.start()
    pid = int((ws / "main_pid").read_text())
    print("OUT " + json.dumps({"state": state, "main_pid": pid}), flush=True)
except Exception as e:
    print("RAISED " + type(e).__name__ + ": " + " ".join(str(e).split())[:400], flush=True)
os._exit(0)
"""


@pytest.mark.skipif(sys.platform != "win32", reason="sentence I6 is Windows' only; on POSIX the host's exit does not end the tree")
def test_the_engine_ends_with_the_host_that_started_it(rig):
    """IS8. A child interpreter starts the engine and exits without stop()."""
    port = free_port()
    ws = rig.workspace("is8")
    try:
        run = subprocess.run([PY, "-c", HOST, str(ws), str(port), str(rig.cli)], capture_output=True, text=True, errors="replace",
                             env=child_env(), timeout=CHILD_S)
    except subprocess.TimeoutExpired as e:
        raise AssertionError(f"The host had not finished after {CHILD_S:g} s. Its stderr ends: {str(e.stderr)[-400:]}") from None
    raised = next((x for x in run.stdout.splitlines() if x.startswith("RAISED ")), "")
    assert not raised, f"In the host, start() {raised[len('RAISED '):]}."
    line = next((x for x in run.stdout.splitlines() if x.startswith("OUT ")), "")
    assert line, f"The host never started the engine. Its stderr ends: {run.stderr[-600:]}"
    got = json.loads(line[len("OUT "):])
    assert got["state"] == "ready", f"In the host, start() returned {got['state']!r}."
    pid = got["main_pid"]
    gone = until(lambda: refused(port) and not alive(pid), 15.0, every=0.25)
    assert gone, (
        f"The host that started the engine exited 15 s ago without stop(), and main.py (pid {pid}) "
        f"{'still runs' if alive(pid) else 'is gone'} and port {port} {'is closed' if refused(port) else 'still answers'}. {SENTENCE_I6} {HOW_TREE}"
    )
