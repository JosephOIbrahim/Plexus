"""Lifecycle · One ComfyUI started, stopped and measured through comfy-cli: CONTRACT's CozyLifecycle, beside Spec §8.1's organ contract.

M3 lets a host start, stop and measure one local ComfyUI through comfy-cli, and puts each measurement on the stage through a report
callback the host points at NeuronRuntime.publish_organ_state (test_organ_state.py pins that method). This file reads
plexus.organs.cozy.CozyLifecycle through CONTRACT's surface: its constructor, .endpoint, probe(), start(), stop() and the report list.

Nothing here runs the real comfy-cli or ComfyUI, touches port 8188 or leaves this machine. The command is [sys.executable, FAKE_CLI],
a script this file writes into tmp_path. FAKE_CLI stands in for `python -m comfy_cli`: it records its argv, nine environment keys, its
pid and whether stdin read end of file at once, one JSON line per run in <workspace>/cli_seen.jsonl, then does what comfy-cli's
foreground launch does, chdir into the workspace and run [python, "main.py"] + the arguments after "--", so a grandchild holds the port.
The workspace's main.py is FAKE_MAIN, which, before it binds, writes about 250 KB to stdout and 260 KB to stderr, more than a pipe
holds, as ComfyUI loading its nodes does, and then answers /system_stats and /object_info like ComfyUI. A workspace file `mode` picks `serve`,
`exit` (the cli exits 3 at once), `silent` (main.py holds the port and never answers) or `reboot` (the cli starts main.py again after
each exit, as comfy-cli's reboot loop does). A file `die` ends main.py, a file `pause` ends it and keeps the next one unbound, and every
fake main.py ends itself after 120 s. Engines that are already running are test_organ_malformed.py's Engine, imported read-only.
An autouse fixture points USERPROFILE and HOME into tmp_path, so a lifecycle that ignored `command` and ran the real comfy-cli would
write its config there, and makes any connect to port 8188 from this process fail the test.

What this file pins: CONTRACT sentences 4 to 11 under plexus.organs, and, in its last case, sentence 1's wake end to end through the
host bridge. Clauses only the exact code holds (stdin at end of file, which under pytest's capture an inherited stdin also reads; the wait for
the port after the kill, which the fake's port closes with its process; the proxy-free opener, cwd, PYTHONUNBUFFERED, the process-group flags, the POSIX kill,
what happens when Popen or a kill itself fails) are not in CONTRACT and nothing here reads them.

Every call into CozyLifecycle runs on a daemon thread joined under a limit (CONSTRUCT_S, START_S, STOP_S), so a wrong lifecycle fails
one test and leaves the run going. Teardown writes `die` into every workspace, calls stop() on every lifecycle built (its OrganError
when it holds nothing is swallowed), kills every bystander and closes every in-test engine, so no fake outlives its test. Ports come
from 127.0.0.1:0: an in-test engine keeps its socket; a spawned fake gets a port this file bound, read and let go, and in the rare race
where something else takes it first, the failure names it.

Left open on purpose: the words of every message (past the port and the path where CONTRACT says a message names them); how often
start() polls; whether report runs before or after a kill; liveness between calls, a watcher, a start lock between hosts, adopting an
engine a dead host left, cancel and engine pools, which wait for later missions; and cross-process wakes, which wait for T1b.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from tests.acceptance._support import PY, child_env
from tests.acceptance.phase2.test_organ_malformed import STATS, Engine

ORGAN = "/Plexus/Organs/cozy"
LIFECYCLE = f"{ORGAN}.plexus:lifecycle"
ENDPOINT_ATTR = f"{ORGAN}.plexus:endpoint"
READY = f'changed({LIFECYCLE}) AND attr({LIFECYCLE}) == "ready"'
FORBIDDEN_PORT = 8188  # the ComfyUI another session runs; no case here may touch it

CONSTRUCT_S = 10.0  # the constructor: one measurement, 1 s on a closed port
START_S = 20.0  # one start(): a fake answers in about 2 s
STOP_S = 20.0  # one stop(): a kill and a closed port in about 3 s
IDLE_S = 10.0  # a runtime going idle
CHILD_S = 60.0  # one child interpreter
POLL_S = 0.25  # the lifecycle's poll_s here, so a start opens a few dozen sockets, not hundreds

DROPPED = ("COMFY_CLI_BACKGROUND", "COMFY_OUTPUT", "VIRTUAL_ENV", "CONDA_PREFIX", "PYTHONPATH", "PYTHONHOME", "PXR_PLUGINPATH_NAME")

SENTENCE_4 = (
    "CONTRACT: plexus.organs.cozy.CozyLifecycle(workspace: Path, port: int, *, command: Sequence[str], report: Callable[[str], object], "
    "extra: Sequence[str] = (), log: Path | None = None, ready_s: float = 300.0, stop_s: float = 30.0, poll_s: float = 0.5) starts, stops "
    "and measures one ComfyUI on 127.0.0.1:<port> through comfy-cli; it sits beside the organ contract (Organ gains nothing); .endpoint is "
    "http://127.0.0.1:<port>."
)
SENTENCE_5 = (
    "CONTRACT: a measurement reads 'ready' when the port answers GET /system_stats with a JSON object holding a system object, 'unavailable' "
    "when anything else answers there, and, when nothing accepts a connection, 'starting' while a process this lifecycle started is alive "
    "and 'stopped' otherwise; probe() measures, calls report(state) and returns the state, and the constructor probes once."
)
SENTENCE_6 = (
    "CONTRACT: start() reports and returns 'ready' when the port already answers as ComfyUI, spawning nothing; when something else answers "
    "on the port, or <workspace>/main.py is not a file, it reports 'unavailable' and raises OrganError naming the port or the path, spawning nothing."
)
SENTENCE_7 = (
    "CONTRACT: otherwise start() reports 'starting', runs [*command, '--skip-prompt', f'--workspace={workspace}', 'launch', '--', '--listen', "
    "'127.0.0.1', '--port', str(port), *extra] in the foreground with stdin at end of file and stdout and stderr appended to log (discarded "
    "when log is None), and returns 'ready' once a measurement reads it; when that process exits first, or ready_s passes, after which it "
    "kills the tree, it reports 'unavailable' and raises OrganError; while a process this lifecycle started is still alive, a further "
    "start() spawns nothing more and waits on that process the same way."
)
SPAWN = (
    "Spawn with stdin=subprocess.DEVNULL, stdout the log opened with 'ab' (subprocess.DEVNULL when log is None) and stderr=subprocess.STDOUT; "
    "never an unread subprocess.PIPE, which fills while the engine loads and stops it before it binds the port."
)
SENTENCE_8 = (
    "CONTRACT: the child's environment sets COMFY_NO_TELEMETRY and DO_NOT_TRACK to 1 and leaves out COMFY_CLI_BACKGROUND, COMFY_OUTPUT, "
    "VIRTUAL_ENV, CONDA_PREFIX, PYTHONPATH, PYTHONHOME and PXR_PLUGINPATH_NAME, and the lifecycle runs command once per start and never for "
    "comfy-cli's --background launch or comfy stop."
)
SENTENCE_9 = (
    "CONTRACT: stop() kills the process tree its own start() spawned, root and descendants together and nothing else, returns once the port "
    "no longer accepts a connection, and reports and returns 'stopped'; with no such tree it raises OrganError and touches nothing. On "
    "Windows run taskkill /T /F /PID <root>, which ends main.py with the root."
)
SENTENCE_10 = (
    "CONTRACT: report runs on the thread that called the constructor, probe(), start() or stop(), and no thread of the lifecycle's own writes "
    "anything; an exception from report reaches that caller, and a tree already spawned stays this lifecycle's, so stop() still ends it."
)
SENTENCE_11 = (
    "CONTRACT: a host bridges the two with report=lambda state: runtime.publish_organ_state(organ_id, state) after runtime.publish_organ(profile)."
)

# Stands in for `python -m comfy_cli` in the foreground. Imports nothing from plexus.
FAKE_CLI = r'''
import json, os, subprocess, sys, threading, time
argv = sys.argv[1:]
ws = next(a.split("=", 1)[1] for a in argv if a.startswith("--workspace="))
keys = ["COMFY_NO_TELEMETRY", "DO_NOT_TRACK", "COMFY_CLI_BACKGROUND", "COMFY_OUTPUT", "VIRTUAL_ENV", "CONDA_PREFIX",
        "PYTHONPATH", "PYTHONHOME", "PXR_PLUGINPATH_NAME"]
got = []
reader = threading.Thread(target=lambda: got.append(sys.stdin.read() if sys.stdin else None), daemon=True)
reader.start()
reader.join(1.0)
seen = {"argv": argv, "env": {k: os.environ.get(k) for k in keys}, "pid": os.getpid(), "stdin_eof": got == [""]}
with open(os.path.join(ws, "cli_seen.jsonl"), "a", encoding="utf-8") as f:
    f.write(json.dumps(seen) + "\n")
mode_file = os.path.join(ws, "mode")
mode = open(mode_file).read().strip() if os.path.exists(mode_file) else "serve"
if mode == "exit":
    sys.exit(3)
os.chdir(ws)
extra = argv[argv.index("--") + 1:]
while True:
    code = subprocess.run([sys.executable, "main.py"] + extra).returncode
    if mode != "reboot" or os.path.exists("die"):
        sys.exit(code)
    time.sleep(0.2)
'''

# Stands in for ComfyUI's main.py.
FAKE_MAIN = r'''
import json, os, socket, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
args = sys.argv[1:]
listen, port = args[args.index("--listen") + 1], int(args[args.index("--port") + 1])
end =time.monotonic() + 120
while os.path.exists("pause"):
    if os.path.exists("die") or time.monotonic() > end:
        os._exit(0)
    time.sleep(0.1)
with open("main_pid", "w") as f:
    f.write(str(os.getpid()))
def watch():
    while time.monotonic() < end and not os.path.exists("die") and not os.path.exists("pause"):
        time.sleep(0.1)
    os._exit(0)
threading.Thread(target=watch, daemon=True).start()
# More than a pipe holds, on both streams, before the port is bound, as ComfyUI loading its nodes writes: an unread PIPE stops it here.
sys.stdout.write("fake main.py starts up, as loud as ComfyUI loading its nodes\n" * 4096)
sys.stdout.flush()
sys.stderr.write("fake main.py: stderr reaches the log\n" + ("e" * 1023 + "\n") * 256)
sys.stderr.flush()
mode =open("mode").read().strip() if os.path.exists("mode") else "serve"
if mode == "silent":
    held = socket.create_server((listen, port))
    while True:
        time.sleep(1)
STATS = {"system": {"os": "nt", "comfyui_version": "0.3.99", "python_version": "3.12.0", "pytorch_version": "2.9.0"}, "devices": []}
NODES = {"FakeNode": {"input": {"required": {}}, "output": [], "name": "FakeNode"}}
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_GET(self):
        if self.path.startswith("/system_stats"):
            body = json.dumps(STATS).encode()
        elif self.path.startswith("/object_info"):
            body = json.dumps(NODES).encode()
        else:
            body = b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
server = ThreadingHTTPServer((listen, port), H)
print(f"To see the GUI go to: http://{listen}:{port}", flush=True)
server.serve_forever(poll_interval=0.05)
'''

DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def lifecycle_class():
    try:
        from plexus.organs.cozy import CozyLifecycle
    except ImportError as e:
        raise AssertionError(f"plexus.organs.cozy has no CozyLifecycle ({e}). {SENTENCE_4} Append the class to plexus/organs/cozy.py.") from None
    return CozyLifecycle


def organ_error():
    from plexus.organs.protocol import OrganError

    return OrganError


def free_port():
    """A port the operating system handed out, let go again for a spawned fake to bind."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert port != FORBIDDEN_PORT
    return port


def refused(port):
    try:
        socket.create_connection(("127.0.0.1", port), timeout=5).close()
        return False
    except OSError:
        return True


def stats_status(endpoint):
    with DIRECT.open(endpoint + "/system_stats", timeout=5) as r:
        return r.status


def engine_port(engine):
    return int(engine.url.rsplit(":", 1)[1])


class Reports:
    """A report callback that records each state and the thread it ran on."""

    def __init__(self, fail_on=None, then=None):
        self.states, self.threads = [], []
        self._fail_on, self._then, self._failed = fail_on, then, False

    def arm(self, state):
        """From now on, raise once when report sees state."""
        self._fail_on, self._failed = state, False

    def __call__(self, state):
        self.states.append(state)
        self.threads.append(threading.get_ident())
        if self._then is not None:
            self._then(state)
        if state == self._fail_on and not self._failed:
            self._failed = True
            raise RuntimeError("the bridge broke on purpose")


class Rig:
    def __init__(self, tmp_path):
        self.root = tmp_path
        self.cli = tmp_path / "fake_cli.py"
        self.cli.write_text(FAKE_CLI, encoding="utf-8")
        self.command = [PY, str(self.cli)]
        self.spaces, self.lifes, self.bystanders, self.engines, self.runtimes = [], [], [], [], []

    def workspace(self, name, mode=None, main=True):
        ws = self.root / f"ws_{name}"
        ws.mkdir()
        self.spaces.append(ws)
        if main:
            (ws / "main.py").write_text(FAKE_MAIN, encoding="utf-8")
        if mode:
            (ws / "mode").write_text(mode)
        return ws

    def engine(self, stats=None):
        """test_organ_malformed.py's Engine on its own port; stats, (status, body, content type), replaces its /system_stats reply."""
        e = Engine()
        self.engines.append(e)
        if stats is not None:
            e.replies["/system_stats"] = stats
        return e

    def bystander(self):
        p = subprocess.Popen([PY, "-c", "import time; time.sleep(60)"])
        self.bystanders.append(p)
        return p

    def life(self, ws, port, report, **kw):
        """CozyLifecycle(ws, port, command=FAKE_CLI's command, report=report, poll_s=POLL_S, **kw) on a daemon thread under CONSTRUCT_S."""
        cls = lifecycle_class()
        assert port != FORBIDDEN_PORT
        kw.setdefault("poll_s", POLL_S)
        box = within(lambda: cls(ws, port, command=self.command, report=report, **kw), "CozyLifecycle(...)", CONSTRUCT_S)
        if "raised" in box:
            e = box["raised"]
            raise AssertionError(f"CozyLifecycle({ws.name}, {port}, ...) raised {type(e).__name__}: {e}. {SENTENCE_4} {SENTENCE_5}")
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
        for p in self.bystanders:
            if p.poll() is None:
                p.kill()
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        for e in self.engines:
            e.close()
        for rt in self.runtimes:
            try:
                rt.stop()
            except Exception:  # noqa: BLE001 - teardown must reach everything
                pass


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


def within(call, what, limit, must_return=True):
    """call() on a daemon thread joined under limit. Returns {'value': ...} or {'raised': ...}, and {'thread': ident} either way."""
    box = {}

    def run():
        box["thread"] = threading.get_ident()
        try:
            box["value"] = call()
        except BaseException as e:  # noqa: BLE001 - handed back to the test's own thread
            box["raised"] = e

    t = threading.Thread(target=run, daemon=True)
    started = time.monotonic()
    t.start()
    t.join(limit)
    box["took"] = time.monotonic() - started
    if t.is_alive() and must_return:
        which = SENTENCE_9 if "stop()" in what else SENTENCE_7 + " " + SPAWN if "start()" in what else SENTENCE_5
        raise AssertionError(
            f"{what} had not returned after {limit:g} s. A measurement is one connect capped at 1 s and one GET capped at 5 s; start() ends "
            "within ready_s plus one poll, one measurement and the kill; stop() within twice stop_s plus one measurement, and a stop() whose "
            f"kill left main.py holding the port waits out stop_s, 30 s here. {which}"
        )
    return box


def value_of(box, what, why):
    if "raised" in box:
        e = box["raised"]
        raise AssertionError(f"{what} raised {type(e).__name__}: {e}. {why}")
    return box.get("value")


def raised_organ_error(box, what, why):
    error = organ_error()
    assert "raised" in box, f"{what} returned {box.get('value')!r} and raised nothing. {why}"
    e = box["raised"]
    assert isinstance(e, error), f"{what} raised {type(e).__name__}: {e}, and it raises plexus.organs.protocol.OrganError. {why}"
    return e


def cli_runs(ws):
    p = ws / "cli_seen.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


def until(read, limit, every=0.5):
    end = time.monotonic() + limit
    while True:
        value = read()
        if value or time.monotonic() > end:
            return value
        time.sleep(every)


def port_race(port, ws):
    """The port-race note, only when the fake cli never ran in ws."""
    if cli_runs(ws):
        return ""
    return (f" (If the fake never ran, something else may have taken port {port} between this test letting it go and the fake binding it; "
            "that race is rare, and a rerun tells it apart.)")


def started(rig, life, ws, port):
    """life.start() under START_S, and it has to come back 'ready'."""
    box = within(life.start, "start()", START_S)
    got = value_of(box, "start()", SENTENCE_7 + " " + SPAWN + port_race(port, ws))
    assert got == "ready", f"start() returned {got!r} on a free port with a workspace that has main.py, and it returns 'ready' once a measurement reads it. {SENTENCE_7}"
    return got


# ---------- what an earlier process left ----------

CHILD = r"""
import json, os, sys
from pathlib import Path
from plexus.core.neuron import NeuronRuntime
x, ws, port, cli = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
rt = NeuronRuntime(x, "host")
A = "/Plexus/Organs/cozy.plexus:lifecycle"
before = rt.stage.GetAttributeAtPath(A).Get()
seen = []
def report(s):
    seen.append(s)
    rt.publish_organ_state("cozy", s)
try:
    from plexus.organs.cozy import CozyLifecycle
    life = CozyLifecycle(ws, port, command=[sys.executable, cli], report=report, poll_s=0.25)
    after = rt.stage.GetAttributeAtPath(A).Get()
    print("OUT " + json.dumps({"before": before, "after": after, "seen": seen}), flush=True)
except Exception as e:
    print("RAISED " + type(e).__name__ + ": " + " ".join(str(e).split())[:400], flush=True)
os._exit(0)
"""


def test_the_constructor_replaces_a_state_an_earlier_process_saved(rig, tmp_path):
    """LB1. A child interpreter of the same participant reads the 'ready' this process saved, and its constructor measures a closed port."""
    from plexus.core.neuron import NeuronRuntime
    from plexus.membrane.exchange import create_exchange
    from plexus.organs.protocol import OrganProfile

    exchange = create_exchange(tmp_path / "lb1" / "shared" / "exchange")
    rt = NeuronRuntime(exchange, "host")
    rig.runtimes.append(rt)
    rt.publish_organ(OrganProfile("cozy", "comfyui", "http://127.0.0.1:1", ["A"], "free"))
    if not hasattr(rt, "publish_organ_state"):
        raise AssertionError(f"NeuronRuntime has no method publish_organ_state, which the host bridge calls. {SENTENCE_11}")
    box = within(lambda: rt.publish_organ_state("cozy", "ready"), "publish_organ_state('cozy', 'ready')", 10.0)
    value_of(box, "publish_organ_state('cozy', 'ready')", "test_organ_state.py pins it.")
    port = free_port()
    ws = rig.workspace("lb1")
    try:
        run = subprocess.run([PY, "-c", CHILD, str(exchange), str(ws), str(port), str(rig.cli)], capture_output=True, text=True,
                             errors="replace", env=child_env(), timeout=CHILD_S)
    except subprocess.TimeoutExpired as e:
        raise AssertionError(f"The child had not finished after {CHILD_S:g} s. Its stderr ends: {str(e.stderr)[-400:]}") from None
    raised = next((x for x in run.stdout.splitlines() if x.startswith("RAISED ")), "")
    assert not raised, f"In a child interpreter, building CozyLifecycle with the host bridge {raised[len('RAISED '):]}. {SENTENCE_4} {SENTENCE_5}"
    line = next((x for x in run.stdout.splitlines() if x.startswith("OUT ")), "")
    assert line, f"The child never reached CozyLifecycle. Its stderr ends: {run.stderr[-600:]}"
    got = json.loads(line[len("OUT "):])
    assert got["before"] == "ready", f"The child read {got['before']!r} on the stage before building the lifecycle, so this test cannot tell a measurement from a read. It reads the 'ready' this process saved."
    assert got["seen"] == ["stopped"] and got["after"] == "stopped", (
        f"On a closed port, the constructor reported {got['seen']} and left {got['after']!r} on the stage, and it reports ['stopped'] once, so "
        f"the 'ready' an earlier process saved is replaced before the constructor returns. {SENTENCE_5} Call self.probe() at the end of __init__; "
        "never read the stage."
    )
    from tests.acceptance.phase2.test_organ_state import in_file

    held = in_file(rt)
    assert held and held["attrs"].get("plexus:lifecycle") == ("token", "stopped"), f"The file this process reads says {held and held['attrs'].get('plexus:lifecycle')!r} after the child, and the child's report saved ('token', 'stopped')."
    assert not cli_runs(ws), f"The constructor ran the command: {cli_runs(ws)}. {SENTENCE_5} It measures and spawns nothing."


# ---------- a start, and what the child is given ----------


def test_a_start_runs_the_command_once_with_the_argv_the_env_and_the_log(rig, monkeypatch):
    """LB2."""
    monkeypatch.setenv("COMFY_CLI_BACKGROUND", "true")
    monkeypatch.setenv("VIRTUAL_ENV", str(rig.root / "venv"))
    monkeypatch.setenv("PYTHONPATH", str(rig.root / "nowhere"))
    port = free_port()
    ws = rig.workspace("lb2")
    log = ws / "comfy.log"
    log.write_text("a line an earlier run left\n", encoding="utf-8")
    reports = Reports()
    cls = lifecycle_class()
    holder = {}

    def build_and_start():
        holder["life"] = cls(ws, port, command=rig.command, report=reports, extra=["--cpu"], log=log, ready_s=START_S - 2, poll_s=POLL_S)
        rig.lifes.append(holder["life"])
        return holder["life"].start()

    box = within(build_and_start, "CozyLifecycle(...) then start()", CONSTRUCT_S + START_S)
    got = value_of(box, "CozyLifecycle(...) then start()", SENTENCE_7 + " " + SPAWN + port_race(port, ws))
    life = holder["life"]
    assert life.endpoint == f"http://127.0.0.1:{port}", f".endpoint is {life.endpoint!r}. {SENTENCE_4}"
    assert got == "ready" and reports.states == ["stopped", "starting", "ready"], (
        f"start() returned {got!r} and report saw {reports.states}, and on a free port it is ['stopped', 'starting', 'ready']: the constructor "
        f"measures 'stopped', start() reports 'starting' before it spawns and 'ready' once a measurement reads it. {SENTENCE_5} {SENTENCE_7}"
    )
    assert set(reports.threads) == {box["thread"]}, f"report ran on threads {set(reports.threads)}, and the caller's thread was {box['thread']}. {SENTENCE_10}"
    runs = cli_runs(ws)
    assert len(runs) == 1, f"The command ran {len(runs)} times for one start(): {runs}. {SENTENCE_8}"
    want = ["--skip-prompt", f"--workspace={ws}", "launch", "--", "--listen", "127.0.0.1", "--port", str(port), "--cpu"]
    assert runs[0]["argv"] == want, f"The command got the arguments {runs[0]['argv']}, and with extra=['--cpu'] they are {want}. {SENTENCE_7}"
    assert runs[0]["stdin_eof"] is True, f"The command's stdin did not read end of file within 1 s. {SENTENCE_7} Pass stdin=subprocess.DEVNULL."
    env = runs[0]["env"]
    assert env.get("COMFY_NO_TELEMETRY") == "1" and env.get("DO_NOT_TRACK") == "1", f"The command's environment holds COMFY_NO_TELEMETRY {env.get('COMFY_NO_TELEMETRY')!r} and DO_NOT_TRACK {env.get('DO_NOT_TRACK')!r}. {SENTENCE_8}"
    leaked = {k: env.get(k) for k in DROPPED if env.get(k) is not None}
    assert not leaked, (
        f"The command's environment holds {leaked}, which this test set in its own (COMFY_CLI_BACKGROUND, VIRTUAL_ENV, PYTHONPATH) or the host "
        f"had. {SENTENCE_8} Copy os.environ without those seven keys, compared upper-cased, then set the two to '1'."
    )
    assert stats_status(life.endpoint) == 200, f"GET {life.endpoint}/system_stats did not answer 200 after start() returned 'ready'."
    text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    assert "a line an earlier run left" in text and "fake main.py: stderr reaches the log" in text, (
        f"The log at {log} lost the line written before start() or never got main.py's stderr: {text[:200]!r}. {SENTENCE_7} {SPAWN}"
    )
    assert "To see the GUI go to:" in text, f"The log at {log} does not hold the engine's own line 'To see the GUI go to:'; it holds {text[-300:]!r}. {SENTENCE_7} {SPAWN}"


def test_a_stop_ends_its_own_tree_and_nothing_else(rig):
    """LB3."""
    port = free_port()
    ws = rig.workspace("lb3")
    reports = Reports()
    life = rig.life(ws, port, reports, ready_s=START_S - 2)
    started(rig, life, ws, port)
    bystander = rig.bystander()
    probed = value_of(within(life.probe, "probe()", CONSTRUCT_S), "probe()", SENTENCE_5)
    assert probed == "ready" and reports.states[-1] == "ready", f"probe() on a running engine returned {probed!r} and reported {reports.states[-1]!r}. {SENTENCE_5}"
    got = value_of(within(life.stop, "stop()", STOP_S), "stop()", SENTENCE_9)
    assert got == "stopped" and reports.states[-1] == "stopped", f"stop() returned {got!r} and last reported {reports.states[-1]!r}. {SENTENCE_9}"
    assert refused(port), (
        f"stop() returned, and port {port} still accepts a connection. Only main.py, the command's grandchild, held it, so the tree was not "
        f"killed whole. {SENTENCE_9}"
    )
    assert len(cli_runs(ws)) == 1, f"The command ran again during stop(): {cli_runs(ws)}. {SENTENCE_8} Never run it for comfy stop."
    assert bystander.poll() is None, f"A process this test started, outside the lifecycle's tree, ended during stop(). {SENTENCE_9}"
    n = len(reports.states)
    raised_organ_error(within(life.stop, "a second stop()", STOP_S), "A second stop()", SENTENCE_9)
    assert len(reports.states) == n, f"A second stop() reported {reports.states[n:]} before it raised, and it touches nothing. {SENTENCE_9}"


# ---------- an engine already there ----------


def test_an_engine_already_answering_is_ready_and_never_stopped(rig):
    """LB4."""
    engine = rig.engine()
    port = engine_port(engine)
    ws = rig.workspace("lb4")
    reports = Reports()
    life = rig.life(ws, port, reports)
    assert reports.states == ["ready"], f"The constructor, on a port where ComfyUI already answers {STATS}, reported {reports.states}. {SENTENCE_5}"
    got = value_of(within(life.start, "start()", START_S), "start()", SENTENCE_6)
    assert got == "ready" and reports.states == ["ready", "ready"], f"start() returned {got!r} and report saw {reports.states}. {SENTENCE_6}"
    assert not cli_runs(ws), f"start() ran the command although ComfyUI already answered: {cli_runs(ws)}. {SENTENCE_6}"
    raised_organ_error(within(life.stop, "stop()", STOP_S), "stop() of an engine this lifecycle did not start", SENTENCE_9)
    assert reports.states == ["ready", "ready"], f"stop() of an engine it did not start reported {reports.states[2:]}, and it touches nothing. {SENTENCE_9}"
    assert stats_status(engine.url) == 200, f"stop() refused, and the engine already there no longer answers. {SENTENCE_9}"


# case: the /system_stats reply of something that is not ComfyUI, (status, body, content type)
NOT_COMFY = {
    "a 404": (404, b"not here", "text/plain"),
    "a JSON object without system": (200, json.dumps({"devices": []}).encode(), "application/json"),
    "a system that is not an object": (200, json.dumps({"system": "nt", "devices": []}).encode(), "application/json"),
    "a JSON list": (200, json.dumps([STATS]).encode(), "application/json"),
    "a body that is not JSON": (200, b"<html>hello</html>", "text/html"),
}


@pytest.mark.parametrize("case", sorted(NOT_COMFY))
def test_something_else_on_the_port_is_unavailable_and_named(rig, case):
    """LB5."""
    engine = rig.engine(stats=NOT_COMFY[case])
    port = engine_port(engine)
    ws = rig.workspace("lb5")
    reports = Reports()
    life = rig.life(ws, port, reports)
    e = raised_organ_error(within(life.start, "start()", START_S), f"start() on a port that answers /system_stats with {case}", SENTENCE_6)
    assert reports.states == ["unavailable", "unavailable"], (
        f"With {case} on /system_stats the constructor and start() reported {reports.states}, and each reads 'unavailable': only a JSON "
        f"object whose system is an object reads 'ready'. {SENTENCE_5} {SENTENCE_6}"
    )
    assert str(port) in str(e), f"The OrganError reads {str(e)!r}, without the port {port}. {SENTENCE_6}"
    assert not cli_runs(ws), f"start() ran the command although something else holds the port: {cli_runs(ws)}. {SENTENCE_6}"


def test_a_workspace_without_main_py_is_unavailable_and_named(rig):
    """LB6."""
    port = free_port()
    ws = rig.workspace("lb6", main=False)
    reports = Reports()
    life = rig.life(ws, port, reports)
    e = raised_organ_error(within(life.start, "start()", START_S), "start() in a workspace without main.py", SENTENCE_6)
    assert str(ws / "main.py") in str(e), f"The OrganError reads {str(e)!r}, without the path {ws / 'main.py'}. {SENTENCE_6} Name the path, as Blueprint 5.2 rule 1 does: Unavailable names what is missing."
    assert not cli_runs(ws), f"start() ran the command in a workspace without main.py: {cli_runs(ws)}. {SENTENCE_6}"
    assert reports.states[-1:] == ["unavailable"], f"After a start without main.py, report last saw {reports.states[-1:]}. {SENTENCE_6}"


# ---------- a start that fails ----------

# mode: (lifecycle keyword arguments, what happened)
FAILED = {
    "exit": ({}, "the command exits 3 before anything answers"),
    "silent": ({"ready_s": 3.0}, "main.py holds the port and never answers, and ready_s is 3 s"),
}


@pytest.mark.parametrize("mode", sorted(FAILED))
def test_a_start_that_never_reads_ready_is_unavailable(rig, mode):
    """LB7."""
    kw, what = FAILED[mode]
    port = free_port()
    ws = rig.workspace(f"lb7_{mode}", mode=mode)
    reports = Reports()
    life = rig.life(ws, port, reports, **kw)
    raised_organ_error(within(life.start, "start()", START_S), f"start() where {what}", SENTENCE_7)
    assert reports.states[-1:] == ["unavailable"], f"After a start where {what}, report last saw {reports.states[-1:]}. {SENTENCE_7}"
    assert "starting" in reports.states, f"A start that spawned reported {reports.states}, without 'starting' before the spawn. {SENTENCE_7}"
    assert refused(port), f"After a start where {what}, port {port} still accepts a connection. {SENTENCE_7} Kill the tree once ready_s passes, then wait for the port to close."


# ---------- probe ----------


def test_probe_measures_an_engine_that_died_as_stopped(rig):
    """LB8."""
    port = free_port()
    ws = rig.workspace("lb8")
    reports = Reports()
    life = rig.life(ws, port, reports, ready_s=START_S - 2)
    started(rig, life, ws, port)
    (ws / "die").write_text("")
    read = until(lambda: value_of(within(life.probe, "probe()", CONSTRUCT_S), "probe()", SENTENCE_5) == "stopped", 10.0)
    assert read and reports.states[-1] == "stopped", f"The engine ended and its command with it, and probe() still reads {reports.states[-1]!r} 10 s later. {SENTENCE_5}"


def test_starting_while_its_own_process_lives_and_a_stop_ends_the_reboot_loop(rig):
    """LB9. The fake cli starts main.py again after each exit, as comfy-cli does. While its own process is starting, start() spawns nothing
    more and waits on it (sentence 7); stop() has to end the loop, not one main.py."""
    port = free_port()
    ws = rig.workspace("lb9", mode="reboot")
    reports = Reports()
    life = rig.life(ws, port, reports, ready_s=START_S - 2)
    started(rig, life, ws, port)
    (ws / "pause").write_text("")
    probe = lambda: value_of(within(life.probe, "probe()", CONSTRUCT_S), "probe()", SENTENCE_5)  # noqa: E731
    assert until(lambda: probe() == "starting", 15.0), (
        f"main.py ended and the command it runs under lives on, unbound, and probe() never read 'starting' within 15 s: {reports.states}. {SENTENCE_5}"
    )
    box = {}

    def again():
        try:
            box["value"] = life.start()
        except BaseException as e:  # noqa: BLE001 - handed back to the test's own thread
            box["raised"] = e

    second = threading.Thread(target=again, daemon=True)
    second.start()
    time.sleep(1.0)
    (ws / "pause").unlink()
    second.join(START_S)
    assert not second.is_alive(), (
        f"start(), called while this lifecycle's own process was still starting, had not returned {START_S:g} s after main.py came back. {SENTENCE_7}"
    )
    got = value_of(box, "start() while its own process was still starting", SENTENCE_7)
    assert got == "ready", f"start(), called while this lifecycle's own process was still starting, returned {got!r}. {SENTENCE_7}"
    runs = len(cli_runs(ws))
    assert runs == 1, (
        f"start(), called while this lifecycle's own process was still starting, ran the command again: {runs} runs in cli_seen.jsonl. "
        f"{SENTENCE_7} Spawn only when the measurement reads 'stopped'; on 'starting', wait on self._proc."
    )
    assert until(lambda: probe() == "ready", 15.0), f"main.py came back, and probe() never read 'ready' within 15 s: {reports.states}. {SENTENCE_5}"
    got = value_of(within(life.stop, "stop()", STOP_S), "stop()", SENTENCE_9)
    assert got == "stopped", f"stop() returned {got!r}. {SENTENCE_9}"
    time.sleep(2.0)
    assert refused(port), f"2 s after stop() returned, port {port} accepts a connection again: the reboot loop started main.py anew. {SENTENCE_9}"


# ---------- report ----------


def test_an_error_from_report_reaches_the_caller_and_the_tree_stays_owned(rig):
    """LB10."""
    port = free_port()
    ws = rig.workspace("lb10")
    reports = Reports(fail_on="ready")
    life = rig.life(ws, port, reports, ready_s=START_S - 2)
    box = within(life.start, "start()", START_S)
    assert "raised" in box and isinstance(box["raised"], RuntimeError) and "on purpose" in str(box["raised"]), (
        f"report raised RuntimeError on 'ready', and start() {'raised ' + type(box['raised']).__name__ + ': ' + str(box['raised']) if 'raised' in box else 'returned ' + repr(box.get('value'))}. "
        f"{SENTENCE_10} Let it propagate; never catch it.{port_race(port, ws)}"
    )
    got = value_of(within(life.stop, "stop()", STOP_S), "stop() after report raised", SENTENCE_10)
    assert got == "stopped" and reports.states[-1] == "stopped", f"stop() after the raised report returned {got!r} and reported {reports.states[-1]!r}. {SENTENCE_10}"
    assert refused(port), f"stop() after the raised report returned, and port {port} still accepts a connection. {SENTENCE_10} Keep self._proc set until the kill."


# ---------- the host bridge, end to end ----------


def test_the_host_bridge_wakes_a_neuron_that_reaches_the_engine(rig, tmp_path):
    """LB11. The host order of sentence 11: publish, construct, register, start the runtime, start the engine, republish."""
    from plexus.core.neuron import NeuronRuntime
    from plexus.membrane.exchange import create_exchange
    from plexus.organs.cozy import CozyOrgan
    from plexus.organs.protocol import OrganProfile

    exchange = create_exchange(tmp_path / "lb11" / "shared" / "exchange")
    rt = NeuronRuntime(exchange, "host")
    rig.runtimes.append(rt)
    port = free_port()
    ws = rig.workspace("lb11")
    out = tmp_path / "lb11_out"
    rt.publish_organ(OrganProfile("cozy", "comfyui", f"http://127.0.0.1:{port}", [], "free"))
    if not hasattr(rt, "publish_organ_state"):
        raise AssertionError(f"NeuronRuntime has no method publish_organ_state, which the host bridge calls. {SENTENCE_11}")
    got, errors = [], []

    def act(ctx):
        try:
            endpoint = rt.stage.GetAttributeAtPath(ENDPOINT_ATTR).Get()
            got.append(CozyOrgan(endpoint, out).capabilities())
        except Exception as e:  # noqa: BLE001 - read back below
            errors.append(f"{type(e).__name__}: {e}")

    handle = rt.register("render", scope=ORGAN, predicate=READY, action=act, budget_wakes=10, budget_window=10.0)
    rt.start()

    def settle():
        time.sleep(0.15)
        assert rt.wait_idle(IDLE_S), f"The runtime had not gone idle {IDLE_S:g} s after a report."

    reports = Reports(then=lambda state: rt.publish_organ_state("cozy", state))
    life = rig.life(ws, port, reports, ready_s=START_S - 2)
    settle()
    assert handle.wakes == 0 and rt.stage.GetAttributeAtPath(LIFECYCLE).Get() == "stopped", (
        f"After the constructor the stage reads {rt.stage.GetAttributeAtPath(LIFECYCLE).Get()!r} and the ready-neuron woke {handle.wakes} times; "
        f"it reads 'stopped' and wakes none. {SENTENCE_11} {SENTENCE_5}"
    )
    started(rig, life, ws, port)
    settle()
    assert handle.wakes == 1 and got == [["FakeNode"]], (
        f"start() through the bridge woke the ready-neuron {handle.wakes} times, and its action read {got} from the engine (errors: {errors}); "
        f"one wake, and CozyOrgan at the endpoint on the stage names ['FakeNode']. {SENTENCE_11}"
    )
    rt.publish_organ(CozyOrgan(life.endpoint, out).profile())
    settle()
    caps = list(rt.stage.GetAttributeAtPath(f"{ORGAN}.plexus:capabilities").Get() or [])
    assert caps == ["FakeNode"] and handle.wakes == 1, f"After the host republished the organ's profile the stage lists {caps} and the neuron woke {handle.wakes} times; ['FakeNode'], and still once."
    got_stop = value_of(within(life.stop, "stop()", STOP_S), "stop()", SENTENCE_9)
    settle()
    assert got_stop == "stopped" and rt.stage.GetAttributeAtPath(LIFECYCLE).Get() == "stopped" and handle.wakes == 1, (
        f"stop() returned {got_stop!r}, the stage reads {rt.stage.GetAttributeAtPath(LIFECYCLE).Get()!r} and the neuron woke {handle.wakes} times; "
        f"'stopped', 'stopped' and still once. {SENTENCE_9} {SENTENCE_11}"
    )


def outcome(box):
    """What a call did, in words: 'returned ...' or 'raised Type: text'."""
    if "raised" in box:
        return f"raised {type(box['raised']).__name__}: {box['raised']}"
    return f"returned {box.get('value')!r}"


def raised_the_report_error(box):
    e = box.get("raised")
    return isinstance(e, RuntimeError) and "on purpose" in str(e)


@pytest.mark.parametrize("when", ["constructor", "starting", "stop"])
def test_an_error_from_report_reaches_every_caller(rig, when):
    """LB12. Sentence 10 for the constructor, for a 'starting' report and for stop(); sentence 7's order, 'starting' reported before
    anything is spawned; and sentence 9's stop() that ends the tree even when its report raises."""
    port = free_port()
    ws = rig.workspace(f"lb12_{when}")
    cls = lifecycle_class()
    if when == "constructor":
        reports = Reports(fail_on="stopped")
        box = within(lambda: cls(ws, port, command=rig.command, report=reports, poll_s=POLL_S), "CozyLifecycle(...)", CONSTRUCT_S)
        assert raised_the_report_error(box), (
            f"report raised RuntimeError('the bridge broke on purpose') on the constructor's 'stopped', and the constructor {outcome(box)}. "
            f"{SENTENCE_10} Let it propagate out of __init__; never catch it, so a host whose bridge is broken learns it at once."
        )
        assert not cli_runs(ws), f"The constructor ran the command: {cli_runs(ws)}. {SENTENCE_5}"
        return
    reports = Reports(fail_on="starting" if when == "starting" else None)
    life = rig.life(ws, port, reports, ready_s=START_S - 2)
    if when == "starting":
        box = within(life.start, "start()", START_S)
        assert raised_the_report_error(box), (
            f"report raised RuntimeError('the bridge broke on purpose') on 'starting', and start() {outcome(box)}. {SENTENCE_10} Let it propagate."
        )
        time.sleep(2.0)
        assert not cli_runs(ws), (
            f"report raised on 'starting', and the command ran anyway: {cli_runs(ws)}. {SENTENCE_7} Report 'starting' before Popen, so an "
            "error from report leaves nothing spawned."
        )
        raised_organ_error(within(life.stop, "stop()", STOP_S), "stop() after a start whose 'starting' report raised and spawned nothing", SENTENCE_9)
        return
    started(rig, life, ws, port)
    reports.arm("stopped")
    box = within(life.stop, "stop()", STOP_S)
    assert raised_the_report_error(box), (
        f"report raised RuntimeError('the bridge broke on purpose') on 'stopped', and stop() {outcome(box)}. {SENTENCE_10} Let it propagate."
    )
    assert refused(port), (
        f"stop() raised the report's error, and port {port} still accepts a connection. {SENTENCE_9} Kill the tree and wait for the port first; "
        "report the measurement after, in a finally."
    )
