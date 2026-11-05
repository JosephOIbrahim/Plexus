"""The launcher in examples/: what it starts, what it refuses, and one real session end to end. Nothing here starts ComfyUI."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "examples"))

import plexus_live as live  # noqa: E402

STATS = {
    "system": {"comfyui_version": "0.9.9", "python_version": "3.14.2 (tags/v3.14.2)", "argv": ["main.py"]},
    "devices": [{"name": "cuda:0 NVIDIA GeForce RTX 4090 : cudaMallocAsync"}],
}


def serve(routes: dict[str, object]):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = routes.get(self.path)
            payload = (body if isinstance(body, str) else json.dumps(body)).encode()
            self.send_response(200 if body is not None else 404)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


@pytest.fixture
def comfyui():
    server, url = serve({"/system_stats": STATS, "/models/checkpoints": ["a.safetensors", "sub\\b.safetensors", "elsewhere.safetensors"]})
    yield url
    server.shutdown()
    server.server_close()


@pytest.fixture
def other_server():
    server, url = serve({"/": "<html>not ComfyUI</html>"})
    yield url
    server.shutdown()
    server.server_close()


@pytest.fixture
def closed_url():
    """A port nothing listens on: bound, read and released."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"http://127.0.0.1:{port}"


class Child:
    def __init__(self, code=None):
        self.returncode = code

    def poll(self):
        return self.returncode


@pytest.fixture
def root(tmp_path):
    (tmp_path / "main.py").write_text("", encoding="utf-8")
    return tmp_path


def refuse_to_start(root):
    raise AssertionError("the launcher must not start ComfyUI here")


def test_stats_read_comfyui_and_tell_nothing_from_something_else(comfyui, closed_url, other_server):
    assert live.comfyui_stats(comfyui)["system"]["comfyui_version"] == "0.9.9"
    assert live.comfyui_stats(closed_url) is None
    with pytest.raises(live.NotComfyUI):
        live.comfyui_stats(other_server)


def test_a_running_comfyui_is_left_alone(comfyui, root):
    stats = live.ensure_comfyui(comfyui, root, start=refuse_to_start, say=lambda s: None)
    assert stats["system"]["comfyui_version"] == "0.9.9"


def test_something_else_on_the_port_stops_the_launcher_and_stays_running(other_server, root):
    with pytest.raises(live.LaunchError, match="not this launcher's to stop"):
        live.ensure_comfyui(other_server, root, start=refuse_to_start, say=lambda s: None)
    with pytest.raises(live.NotComfyUI):
        live.comfyui_stats(other_server)


def test_a_folder_that_is_not_comfyui_says_so(closed_url, tmp_path):
    with pytest.raises(live.LaunchError, match="no main.py"):
        live.ensure_comfyui(closed_url, tmp_path, start=refuse_to_start, say=lambda s: None)


def test_it_starts_comfyui_and_waits_until_it_answers(closed_url, root, monkeypatch):
    answers = iter([None, None, None, STATS])
    started = []
    monkeypatch.setattr(live, "comfyui_stats", lambda url: next(answers))
    notes = []

    def start(where):
        started.append(where)
        return Child()

    stats = live.ensure_comfyui(closed_url, root, start=start, say=notes.append, sleep=lambda s: None)
    assert started == [root]
    assert stats is STATS
    assert any("up at" in n for n in notes)


def test_the_command_is_the_stable_line_of_the_batch_file_and_keeps_a_failed_window_open():
    command = live.comfyui_command(Path(r"G:\COMFY\ComfyUI"), python=r"C:\Python314\python.exe")
    assert r'"C:\Python314\python.exe" -m comfy_cli --workspace="G:\COMFY\ComfyUI" launch -- --reserve-vram 1.0' in command
    assert command.startswith('cmd /c "') and command.endswith(' || pause"')


def test_the_environment_matches_the_batch_file_and_drops_this_repos_python_settings(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "E:/Plexus")
    monkeypatch.setenv("PXR_PLUGINPATH_NAME", "E:/Plexus/plexus/schema")
    env = live.comfyui_env()
    assert "PYTHONPATH" not in env
    assert "PXR_PLUGINPATH_NAME" not in env
    assert env["PYTORCH_ALLOC_CONF"] == "expandable_segments:True,garbage_collection_threshold:0.8"
    assert env["PYTHONHASHSEED"] == "0"


def launch_that_times_out(monkeypatch, closed_url, tmp_path, *flags):
    (tmp_path / "main.py").write_text("", encoding="utf-8")
    child, stopped = Child(), []
    monkeypatch.setattr(live, "core_is_stale", lambda repo: False)
    monkeypatch.setattr(live, "live_run_pid", lambda repo: None)
    monkeypatch.setattr(live, "start_comfyui", lambda root, minimized: child)
    monkeypatch.setattr(live, "stop_tree", stopped.append)
    code = live.main(["--url", closed_url, "--comfyui-root", str(tmp_path), "--timeout", "0.05", *flags])
    return code, child, stopped


def test_a_start_that_times_out_is_stopped_when_asked(monkeypatch, closed_url, tmp_path, capsys):
    code, child, stopped = launch_that_times_out(monkeypatch, closed_url, tmp_path, "--stop-comfyui-on-exit")
    assert code == 1
    assert stopped == [child]
    assert "did not answer" in capsys.readouterr().err


def test_a_start_that_times_out_keeps_its_window_otherwise(monkeypatch, closed_url, tmp_path, capsys):
    code, _, stopped = launch_that_times_out(monkeypatch, closed_url, tmp_path)
    assert code == 1
    assert stopped == []
    assert "keeps running in its own window" in capsys.readouterr().out


def test_a_window_closed_early_is_named_and_does_not_wait_out_the_timeout(closed_url):
    with pytest.raises(live.LaunchError, match="closed before"):
        live.wait_for_comfyui(closed_url, Child(code=3), 300.0, say=lambda s: None, sleep=lambda s: None)


def test_it_gives_up_at_the_timeout_and_reports_progress_on_the_way(closed_url):
    now = [0.0]

    def sleep(seconds):
        now[0] += seconds

    notes = []
    with pytest.raises(live.LaunchError, match="did not answer"):
        live.wait_for_comfyui(closed_url, Child(), 60.0, say=notes.append, poll_s=5.0, clock=lambda: now[0], sleep=sleep)
    assert len(notes) >= 3
    assert all(n.startswith("[still waiting") for n in notes)


def test_models_line_counts_what_sits_under_the_model_root(comfyui, tmp_path):
    folder = tmp_path / "checkpoints" / "sub"
    folder.mkdir(parents=True)
    (tmp_path / "checkpoints" / "a.safetensors").write_text("", encoding="utf-8")
    (folder / "b.safetensors").write_text("", encoding="utf-8")
    line = live.models_line(comfyui, tmp_path)
    assert "2 of the 3" in line
    assert "WARNING" not in line


def test_models_line_warns_when_none_of_them_are_there(comfyui, tmp_path):
    assert "not using your model root" in live.models_line(comfyui, tmp_path)


def test_models_line_warns_when_it_cannot_read_the_list(other_server, tmp_path):
    assert "could not read" in live.models_line(other_server, tmp_path)


def test_core_is_stale_when_missing_or_older_than_any_crate_file(tmp_path):
    (tmp_path / "plexus").mkdir()
    source = tmp_path / "crates" / "plexus-core" / "src" / "lib.rs"
    source.parent.mkdir(parents=True)
    source.write_text("", encoding="utf-8")
    assert live.core_is_stale(tmp_path)
    built = tmp_path / "plexus" / ("_core.pyd" if os.name == "nt" else "_core.so")
    built.write_text("", encoding="utf-8")
    os.utime(source, (1000, 1000))
    os.utime(built, (2000, 2000))
    assert not live.core_is_stale(tmp_path)
    os.utime(source, (3000, 3000))
    assert live.core_is_stale(tmp_path)


def test_a_lock_with_a_dead_or_unreadable_pid_is_not_a_live_run(tmp_path):
    assert live.live_run_pid(tmp_path) is None
    (tmp_path / ".plexus_loop").mkdir()
    (tmp_path / ".plexus_loop" / "lock").write_text("not json", encoding="utf-8")
    assert live.live_run_pid(tmp_path) is None
    (tmp_path / ".plexus_loop" / "lock").write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    if sys.platform.startswith("win"):
        assert live.live_run_pid(tmp_path) == os.getpid()


@pytest.fixture
def core_loads():
    env = dict(os.environ, PYTHONPATH=str(REPO))
    check = subprocess.run([sys.executable, "-c", "import plexus.core.neuron"], cwd=REPO, env=env, capture_output=True, check=False)
    if check.returncode:
        pytest.skip(f"the Plexus core does not load here: {check.stderr.decode(errors='replace')[-200:]}")


def run_session(sessions_root, closed_url, script, *more):
    return subprocess.run(
        [sys.executable, str(REPO / "examples" / "plexus_session.py"), "--url", closed_url, "--sessions-root", str(sessions_root), "--script", script, *more],
        cwd=REPO,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=120,
        check=False,
    )


def test_a_real_session_wakes_the_neuron_and_project_b_reads_the_hint(core_loads, tmp_path, closed_url):
    r = run_session(tmp_path, closed_url, "temp 1.05; temp 1.5; status; temp 0.5; status; bogus; temp x; quit; temp 9")
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "Project A wrote 1.05. The neuron stayed dormant." in out
    assert "Project A wrote 1.5. The neuron woke. Wakes so far: 1." in out
    assert "Project B temperature 1.5, grade_hint warmer" in out
    assert "Project A wrote 0.5. The neuron woke. Wakes so far: 2." in out
    assert "Project B temperature 0.5, grade_hint cooler" in out
    assert f"not running at {closed_url}" in out
    assert "Not a command: bogus" in out
    assert "x is not a number." in out
    assert "temp 9" not in out, "quit must end the session before the next command"
    assert len(list(tmp_path.iterdir())) == 1


def test_two_sessions_in_the_same_second_get_their_own_folders(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO))
    session = pytest.importorskip("plexus_session")

    class Frozen:
        @staticmethod
        def now():
            return Frozen

        @staticmethod
        def strftime(fmt):
            return "20261104-120000"

    monkeypatch.setattr(session, "datetime", Frozen)
    first = session.new_session_folder(tmp_path)
    second = session.new_session_folder(tmp_path)
    assert first != second
    assert first.is_dir() and second.is_dir()
