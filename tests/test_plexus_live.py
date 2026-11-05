"""The launcher in examples/: what it starts, what it refuses, and one real session end to end. Nothing here starts ComfyUI."""

from __future__ import annotations

import itertools
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
WINDOWS = sys.platform.startswith("win")
DEAD_PID = 2**22 + 12345  # no process has this pid: Windows pids are multiples of 4, and Linux's stop at 2**22
STOP = "--stop-comfyui-on-exit"


@pytest.fixture(autouse=True)
def local_state(tmp_path, monkeypatch):
    """No test touches the real %LOCALAPPDATA%\\Plexus. This names the folder and does not make it, because a session test counts what sits in tmp_path."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))


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
    def __init__(self, code=None, pid=4242):
        self.returncode = code
        self.pid = pid

    def poll(self):
        return self.returncode


@pytest.fixture
def root(tmp_path):
    (tmp_path / "main.py").write_text("", encoding="utf-8")
    return tmp_path


def refuse_to_start(root):
    raise AssertionError("the launcher must not start ComfyUI here")


def refuse_to_sleep(seconds):
    raise AssertionError("the launcher must not wait here")


def quiet(line):
    pass


def lock_file() -> Path:
    return live.state_folder() / live.START_LOCK


def hold_the_start(pid) -> Path:
    lock = lock_file()
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({"pid": pid}), encoding="utf-8")
    return lock


def leave_the_marker() -> Path:
    marker = live.state_folder() / live.FAILED_MARKER
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("failed\n", encoding="utf-8")
    return marker


def named_in(lock: Path) -> int:
    return json.loads(lock.read_text(encoding="utf-8"))["pid"]


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
    assert not lock_file().exists(), "a folder that is not ComfyUI claims nothing"


def test_the_state_folder_is_the_base_the_sessions_use(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert live.state_folder() == tmp_path / "Plexus"
    monkeypatch.delenv("LOCALAPPDATA")
    assert live.state_folder() == Path.home() / "Plexus"


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
    marker = Path(r"C:\Users\Joe\AppData\Local\Plexus\comfyui_failed")
    command = live.comfyui_command(Path(r"G:\COMFY\ComfyUI"), marker, python=r"C:\Python314\python.exe")
    assert r'"C:\Python314\python.exe" -m comfy_cli --workspace="G:\COMFY\ComfyUI" launch -- --reserve-vram 1.0' in command
    assert command.startswith('cmd /c "') and command.endswith(f' || (echo failed>"{marker}" & pause)"')
    assert "--port" not in command
    assert f'--reserve-vram 1.0 --port 9000 || (echo failed>"{marker}"' in live.comfyui_command(Path(r"G:\COMFY\ComfyUI"), marker, port=9000)


@pytest.mark.skipif(not WINDOWS, reason="the command is cmd's")
@pytest.mark.parametrize("code, fails, port", [(3, True, live.COMFYUI_PORT), (0, False, live.COMFYUI_PORT), (3, True, 9000)])
def test_the_real_command_leaves_the_marker_only_when_the_program_in_it_fails(tmp_path, code, fails, port):
    # The workspace holds a shadow comfy_cli.py and python -m looks in the cwd first, so nothing real can start. With no
    # stdin, pause returns at once. A console of its own keeps title and chcp off the console running these tests.
    workspace = tmp_path / "with space"
    workspace.mkdir()
    (workspace / "comfy_cli.py").write_text(f"import sys\nprint('FAKE', *sys.argv[1:], sep='\\n')\nsys.exit({code})\n", encoding="utf-8")
    marker = tmp_path / "state folder" / "comfyui_failed"
    marker.parent.mkdir()
    r = subprocess.run(
        live.comfyui_command(workspace, marker, port=port),
        cwd=workspace,
        env=live.comfyui_env(),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    lines = r.stdout.splitlines()
    assert "FAKE" in lines and f"--workspace={workspace}" in lines, r.stdout + r.stderr  # the marker's absence means nothing unless the program ran
    assert marker.exists() is fails
    assert ("--port" in lines and "9000" in lines) is (port == 9000)


@pytest.mark.skipif(not WINDOWS, reason="CREATE_NEW_CONSOLE is Windows'")
def test_a_start_makes_the_state_folder_and_clears_a_stale_marker_before_the_window_opens(root, monkeypatch):
    marker = live.state_folder() / live.FAILED_MARKER
    seen = []

    def popen(command, **kw):
        seen.append((command, marker.parent.is_dir(), marker.exists()))
        return Child()

    monkeypatch.setattr(subprocess, "Popen", popen)
    live.start_comfyui(root)  # the first run on a machine: cmd's echo cannot make the folder
    leave_the_marker()
    live.start_comfyui(root)
    assert [(folder, stale) for _, folder, stale in seen] == [(True, False), (True, False)]
    assert f'echo failed>"{marker}"' in seen[0][0]


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
    monkeypatch.setattr(live, "start_comfyui", lambda root, minimized, port: child)
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


def launch_to_the_last_line(monkeypatch, capsys, url, root, child, *flags, failed=False, port="closed"):
    """main with a start that times out at once, so the launcher's last words are all that is left to read."""
    kills, port_reads = [], []

    def start(where, minimized, port):
        if child is None:
            refuse_to_start(where)
        child.port = port
        if failed:
            leave_the_marker()
        return child

    def kill(window):  # as the real one does: the window closes, and the port goes with it
        kills.append(window)
        window.returncode = 1

    def port_open(checked):
        port_reads.append(checked)
        return port == "open" or (port == "until the kill" and not kills)

    monkeypatch.setattr(live, "core_is_stale", lambda repo: False)
    monkeypatch.setattr(live, "live_run_pid", lambda repo: None)
    monkeypatch.setattr(live, "comfyui_stats", lambda checked: None)
    monkeypatch.setattr(live, "start_comfyui", start)
    monkeypatch.setattr(live, "stop_tree", kill)
    monkeypatch.setattr(live, "_port_open", port_open)
    monkeypatch.setattr(live, "STOP_SETTLE_S", 0.0)
    code = live.main(["--url", url, "--comfyui-root", str(root), "--timeout", "0", *flags])
    out, err = capsys.readouterr()
    return code, out.splitlines(), err.strip(), kills, port_reads


STILL_ANSWERS = "ComfyUI still answers at {url} after this launcher tried to stop it, so stop it by hand."
CLOSED_BUT_ANSWERS = "ComfyUI's window has closed and something still answers at {url}. This launcher sent it no kill, so stop it by hand if it should not be running."


@pytest.mark.parametrize(
    "flags, exit_code, failed, port, last",
    [
        ([STOP], None, False, "open", STILL_ANSWERS),
        ([STOP], 3, False, "open", CLOSED_BUT_ANSWERS),
        ([], 3, False, "open", CLOSED_BUT_ANSWERS),
        ([STOP], 3, False, "closed", "ComfyUI's window had already closed, so there was nothing to stop."),
        # The kill closes the window and frees the port, so reading either one on the wrong side of it gets this line wrong.
        ([STOP], None, False, "until the kill", "ComfyUI stopped, because this launcher started it and --stop-comfyui-on-exit asked."),
        ([], 3, False, "closed", "ComfyUI's window has closed, so ComfyUI is not running."),
        ([], None, True, "closed", "ComfyUI failed and its window stays open at its error. Close it after reading its log."),
        ([], None, False, "closed", "ComfyUI keeps running in its own window and has not answered at {url}. Its log will say why."),
        ([], None, False, "open", "ComfyUI keeps running in its own window. Close that window to stop it."),
    ],
    ids=["port still open", "closed and the port still open", "closed, no flag, the port still open", "already closed", "stopped", "closed without the flag", "marker", "port closed", "all well"],
)
def test_the_last_line_says_what_it_read(monkeypatch, capsys, closed_url, root, flags, exit_code, failed, port, last):
    child = Child(code=exit_code)
    code, lines, err, kills, port_reads = launch_to_the_last_line(monkeypatch, capsys, closed_url, root, child, *flags, failed=failed, port=port)
    assert code == 1
    assert lines[-1] == last.format(url=closed_url)
    assert kills == ([child] if flags and exit_code is None else [])  # a closed window's pid can already be something else's
    assert len(port_reads) <= 1


def test_the_stop_flag_keeps_the_failed_window_the_error_line_points_at(monkeypatch, capsys, closed_url, root):
    # That window holds the only log of the failure. --timeout 30 reaches the marker's error, not the timeout's.
    child = Child()
    _, lines, err, kills, _ = launch_to_the_last_line(monkeypatch, capsys, closed_url, root, child, STOP, "--timeout", "30", failed=True)
    assert "which stays open so its log can be read" in err
    assert kills == []
    assert lines[-1] == "ComfyUI failed and its window stays open at its error. Close it after reading its log."


def test_the_urls_port_reaches_the_start(monkeypatch, capsys, closed_url, root):
    child = Child()
    launch_to_the_last_line(monkeypatch, capsys, closed_url, root, child)
    assert child.port == int(closed_url.rsplit(":", 1)[1])


@pytest.mark.parametrize("url", ["http://192.0.2.1:8188", "https://127.0.0.1:8188"], ids=["another host", "https"])
def test_a_url_this_machine_cannot_serve_starts_nothing(root, monkeypatch, url):
    monkeypatch.setattr(live, "comfyui_stats", lambda checked: None)
    with pytest.raises(live.LaunchError, match="only at an http URL on this machine"):
        live.ensure_comfyui(url, root, start=refuse_to_start, say=quiet)
    assert not lock_file().exists()
    monkeypatch.setattr(live, "comfyui_stats", lambda checked: STATS)  # one that already answers there is still a use of --url
    assert live.ensure_comfyui(url, root, start=refuse_to_start, say=quiet) is STATS


def test_a_relative_root_is_made_absolute_before_the_window_starts_inside_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert live.parse_args(["--comfyui-root", "rel_root"]).comfyui_root == Path.cwd() / "rel_root"
    if WINDOWS:  # the default names a drive, which is a relative path anywhere else
        assert live.parse_args([]).comfyui_root == live.COMFYUI_ROOT


def settling_port(monkeypatch, answers):
    """A port that answers like this after the kill, on a clock only the launcher's naps move."""
    now, reads = [0.0], iter(answers)
    monkeypatch.setattr(live, "stop_tree", lambda window: None)
    monkeypatch.setattr(live, "_port_open", lambda url: next(reads))
    monkeypatch.setattr(live.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(live.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    return now


def test_a_port_that_lets_go_a_moment_after_the_kill_is_a_stop_that_worked(monkeypatch, closed_url):
    # On a fake server in a real window, one read right after taskkill said open on 2 of 3 tries, and the port was gone about 0.1 s later.
    now = settling_port(monkeypatch, [True, True, False])
    assert live.final_line(Child(), closed_url, True).startswith("ComfyUI stopped")
    assert now[0] > 0, "it waited, and did not conclude on the first read"


def test_a_port_that_stays_open_past_the_settling_time_still_answers(monkeypatch, closed_url):
    now = settling_port(monkeypatch, itertools.repeat(True))
    assert live.final_line(Child(), closed_url, True) == STILL_ANSWERS.format(url=closed_url)
    assert now[0] >= live.STOP_SETTLE_S


def test_the_timeout_message_never_calls_a_window_open_that_the_next_line_may_kill(monkeypatch, capsys, closed_url, root):
    _, _, err, _, _ = launch_to_the_last_line(monkeypatch, capsys, closed_url, root, Child(), STOP)
    assert err == f"Plexus did not start: ComfyUI did not answer at {closed_url} in 0 s."


def test_a_launcher_that_waited_neither_stops_nor_describes_the_other_window(monkeypatch, capsys, closed_url, root):
    lock = hold_the_start(os.getpid())
    code, lines, err, kills, port_reads = launch_to_the_last_line(monkeypatch, capsys, closed_url, root, None, STOP)
    assert code == 1
    assert kills == [] and port_reads == []
    assert lines[-1].startswith("ComfyUI   another launcher's start is still loading")
    assert err == f"Plexus did not start: ComfyUI did not answer at {closed_url} in 0 s. If that window is gone, delete {lock}."


def test_a_timeout_leaves_the_file_naming_the_window_because_it_can_still_be_loading(monkeypatch, capsys, closed_url, root):
    launch_to_the_last_line(monkeypatch, capsys, closed_url, root, Child(pid=4242))
    assert named_in(lock_file()) == 4242


def test_the_winner_names_itself_then_its_window_and_removes_the_file_once_the_port_answers(closed_url, root, monkeypatch):
    lock, held = lock_file(), []
    answers = iter([None, None, STATS])

    def stats(url):
        if lock.exists():
            held.append(named_in(lock))
        return next(answers)

    def start(where):
        held.append(named_in(lock))
        return Child(pid=4242)

    monkeypatch.setattr(live, "comfyui_stats", stats)
    assert live.ensure_comfyui(closed_url, root, start=start, say=quiet, sleep=lambda s: None) is STATS
    assert held == [os.getpid(), 4242, 4242]
    assert not lock.exists()


def test_a_second_launcher_waits_on_a_live_start_and_starts_nothing(closed_url, root, monkeypatch):
    lock = hold_the_start(os.getpid())
    answers = iter([None, None, STATS])
    monkeypatch.setattr(live, "comfyui_stats", lambda url: next(answers))
    notes = []
    assert live.ensure_comfyui(closed_url, root, start=refuse_to_start, say=notes.append, sleep=lambda s: None) is STATS
    assert f"ComfyUI   another launcher's start is still loading (pid {os.getpid()}), so this one waits for it" in notes
    assert any("up at" in n for n in notes)
    assert named_in(lock) == os.getpid(), "the file is the other launcher's to remove"


@pytest.mark.skipif(not WINDOWS, reason="the alive check is tasklist")
def test_a_dead_holder_is_taken_over_and_starts_once(closed_url, root, monkeypatch):
    lock = hold_the_start(DEAD_PID)
    answers = iter([None, None, STATS])
    monkeypatch.setattr(live, "comfyui_stats", lambda url: next(answers))
    started = []

    def start(where):
        started.append(named_in(lock))
        return Child()

    assert live.ensure_comfyui(closed_url, root, start=start, say=quiet, sleep=lambda s: None) is STATS
    assert started == [os.getpid()]
    assert not lock.exists()


def test_a_holder_the_check_cannot_tell_about_keeps_the_start(closed_url, root, monkeypatch):
    lock = hold_the_start(1111)
    answers = iter([None, None, STATS])
    monkeypatch.setattr(live, "comfyui_stats", lambda url: next(answers))
    monkeypatch.setattr(live, "pid_alive", lambda pid: None)
    assert live.ensure_comfyui(closed_url, root, start=refuse_to_start, say=quiet, sleep=lambda s: None) is STATS
    assert named_in(lock) == 1111


@pytest.mark.parametrize("text", ["", "not json", '{"pid": null}', "[1]"], ids=["empty", "not json", "null pid", "a list"])
def test_a_file_it_cannot_read_starts_nothing(closed_url, root, monkeypatch, text):
    # A launcher writes the file in two steps, so an empty read is most likely a write in progress.
    lock = hold_the_start(0)
    lock.write_text(text, encoding="utf-8")
    answers = iter([None, None, STATS])
    monkeypatch.setattr(live, "comfyui_stats", lambda url: next(answers))
    notes = []
    assert live.ensure_comfyui(closed_url, root, start=refuse_to_start, say=notes.append, sleep=lambda s: None) is STATS
    assert any("(pid unknown)" in n for n in notes)
    assert lock.read_text(encoding="utf-8") == text


def test_a_takeover_leaves_alone_a_claim_that_landed_during_its_check(closed_url, root, monkeypatch):
    # tasklist takes most of a second, long enough for another launcher to take the dead holder over first.
    lock = hold_the_start(1111)

    def alive(pid):
        if pid == 1111:
            lock.write_text(json.dumps({"pid": 2222}), encoding="utf-8")
            return False
        return True

    answers = iter([None, STATS])
    monkeypatch.setattr(live, "comfyui_stats", lambda url: next(answers))
    monkeypatch.setattr(live, "pid_alive", alive)
    notes = []
    assert live.ensure_comfyui(closed_url, root, start=refuse_to_start, say=notes.append, sleep=lambda s: None) is STATS
    assert named_in(lock) == 2222
    assert any("(pid 2222)" in n for n in notes)


def test_a_waiter_follows_the_file_from_the_launcher_to_its_window(closed_url, root, monkeypatch):
    # A launcher names itself first and its window after, and can then exit while that window loads.
    lock = hold_the_start(1111)
    alive_pids = {1111}
    reads = iter([None, None, "hand on", STATS])  # after its first read of the file, so a stand-in that keeps that pid fails here

    def stats(url):
        answer = next(reads)
        if answer == "hand on":
            lock.write_text(json.dumps({"pid": 2222}), encoding="utf-8")
            alive_pids.clear()
            alive_pids.add(2222)
            return None
        return answer

    monkeypatch.setattr(live, "comfyui_stats", stats)
    monkeypatch.setattr(live, "pid_alive", lambda pid: pid in alive_pids)
    assert live.ensure_comfyui(closed_url, root, start=refuse_to_start, say=quiet, sleep=lambda s: None) is STATS


def test_a_file_gone_because_the_port_answered_is_no_closed_window(closed_url, root, monkeypatch):
    # The other launcher removes the file once the port answers, which can land after this launcher's read of the port.
    lock = hold_the_start(1111)
    reads = iter([None, "removed", STATS])

    def stats(url):
        answer = next(reads)
        if answer == "removed":
            lock.unlink()
            return None
        return answer

    monkeypatch.setattr(live, "comfyui_stats", stats)
    monkeypatch.setattr(live, "pid_alive", lambda pid: pid == 1111)  # no other pid is alive, as the real check says of the 0 a gone file reads as
    assert live.ensure_comfyui(closed_url, root, start=refuse_to_start, say=quiet, sleep=lambda s: None) is STATS


def test_a_waiter_whose_holder_dies_says_the_window_closed(closed_url, root, monkeypatch):
    hold_the_start(1111)
    alive = iter([True, False])
    monkeypatch.setattr(live, "comfyui_stats", lambda url: None)
    monkeypatch.setattr(live, "pid_alive", lambda pid: next(alive))
    with pytest.raises(live.LaunchError, match="closed before") as e:
        live.ensure_comfyui(closed_url, root, start=refuse_to_start, say=quiet, sleep=refuse_to_sleep)
    assert "exit" not in str(e.value)  # a waiter never saw that window's code


def test_a_waiter_reads_the_same_marker(closed_url, root, monkeypatch):
    hold_the_start(1111)
    leave_the_marker()
    monkeypatch.setattr(live, "comfyui_stats", lambda url: None)
    monkeypatch.setattr(live, "pid_alive", lambda pid: True)
    with pytest.raises(live.LaunchError, match="failed in its window"):
        live.ensure_comfyui(closed_url, root, start=refuse_to_start, say=quiet, sleep=refuse_to_sleep)


def test_a_state_folder_it_cannot_write_stops_with_one_line(closed_url, root, tmp_path, monkeypatch):
    (tmp_path / "a file").write_text("", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "a file"))
    monkeypatch.setattr(live, "comfyui_stats", lambda url: None)
    with pytest.raises(live.LaunchError, match="Could not use"):
        live.ensure_comfyui(closed_url, root, start=refuse_to_start, say=quiet)


def test_the_alive_check_says_when_it_cannot_tell(monkeypatch):
    assert live.pid_alive(0) is False  # tasklist would list the System Idle Process under it
    if WINDOWS:
        assert live.pid_alive(os.getpid()) is True
        assert live.pid_alive(DEAD_PID) is False
        assert live.pid_alive(99999999999) is None  # tasklist rejects the filter and leaves stdout empty

    def hangs(*args, **kwargs):
        raise subprocess.TimeoutExpired("tasklist", 10)

    monkeypatch.setattr(subprocess, "run", hangs)
    assert live.pid_alive(4) is None


def test_a_start_that_fails_in_its_window_says_so_at_once(closed_url, root, monkeypatch):
    monkeypatch.setattr(live, "comfyui_stats", lambda url: None)

    def start(where):
        leave_the_marker()
        return Child()

    with pytest.raises(live.LaunchError, match="failed in its window"):
        live.ensure_comfyui(closed_url, root, start=start, say=quiet, sleep=refuse_to_sleep)
    assert lock_file().exists(), "that window stays open, and the next launcher has to find it"


def test_a_live_window_and_a_marker_raise_at_once_without_sleeping(closed_url, monkeypatch):
    monkeypatch.setattr(live, "comfyui_stats", lambda url: None)
    with pytest.raises(live.LaunchError, match="failed in its window, which stays open"):
        live.wait_for_comfyui(closed_url, Child(), 300.0, marker=leave_the_marker(), say=quiet, sleep=refuse_to_sleep)


def test_a_marker_from_a_window_that_has_since_closed_does_not_call_it_open(closed_url, monkeypatch):
    monkeypatch.setattr(live, "comfyui_stats", lambda url: None)
    with pytest.raises(live.LaunchError, match="closed before"):
        live.wait_for_comfyui(closed_url, Child(code=1), 300.0, marker=leave_the_marker(), say=quiet, sleep=refuse_to_sleep)


def test_the_port_is_read_before_the_marker(closed_url, monkeypatch):
    monkeypatch.setattr(live, "comfyui_stats", lambda url: STATS)
    assert live.wait_for_comfyui(closed_url, Child(), 300.0, marker=leave_the_marker(), say=quiet, sleep=refuse_to_sleep) is STATS


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


@pytest.fixture
def comfyui_listing():
    """A ComfyUI that lists these checkpoints."""
    servers = []

    def listing(names):
        server, url = serve({"/system_stats": STATS, "/models/checkpoints": names})
        servers.append(server)
        return url

    yield listing
    for server in servers:
        server.shutdown()
        server.server_close()


def checkpoints_on_disk(models_root, *names):
    folder = models_root / "checkpoints"
    for name in names:
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text("", encoding="utf-8")
    return folder


def test_models_line_warns_about_files_on_disk_that_comfyui_does_not_list(comfyui_listing, tmp_path):
    folder = checkpoints_on_disk(tmp_path, "e.safetensors", "a.safetensors", "b.ckpt", "sub/c.safetensors", "sub/d.SAFETENSORS")
    line = live.models_line(comfyui_listing(["a.safetensors"]), tmp_path)
    assert line.startswith("Models    WARNING:")
    assert "4 of the 5" in line and "b.ckpt" in line and str(folder) in line and "may not be reading that folder" in line


def test_models_line_warns_when_comfyui_lists_nothing_and_the_folder_has_files(comfyui_listing, tmp_path):
    checkpoints_on_disk(tmp_path, "sub/a.safetensors")
    line = live.models_line(comfyui_listing([]), tmp_path)
    assert line.startswith("Models    WARNING:") and "1 of the 1" in line and "sub/a.safetensors" in line


def test_models_line_matches_names_across_case_and_slashes(comfyui_listing, tmp_path):
    checkpoints_on_disk(tmp_path, "a.safetensors", "sub/B.ckpt")
    assert "does not list" not in live.models_line(comfyui_listing(["A.SAFETENSORS", "SUB\\b.CKPT"]), tmp_path)


def test_models_line_never_warns_about_a_stray_file(comfyui_listing, tmp_path):
    folder = checkpoints_on_disk(tmp_path, "a.safetensors", "notes.txt", "sub/config.yaml")
    (folder / "a folder.ckpt").mkdir()
    line = live.models_line(comfyui_listing(["a.safetensors"]), tmp_path)
    assert "WARNING" not in line and "1 of the 1" in line


def test_models_line_with_nothing_on_either_side_claims_nothing_about_the_root(comfyui_listing, tmp_path):
    line = live.models_line(comfyui_listing([]), tmp_path)
    assert line == f"Models    ComfyUI lists no checkpoints and {tmp_path / 'checkpoints'} holds none."


@pytest.mark.parametrize("url", ["127.0.0.1:8188", "localhost:8188", "http://127.0.0.1:abc", "http://127.0.0.1:99999", "http://127.0.0.1", "ftp://x:1", "http://127.0.0.1:0", "http://[bad"])
def test_a_url_it_cannot_use_stops_with_one_line(url):
    with pytest.raises(SystemExit, match="needs http or https") as stopped:  # match, because argparse's own errors are a SystemExit too
        live.parse_args(["--url", url])
    assert str(stopped.value) == f"Plexus did not start: --url needs http or https, a host and a port, such as http://127.0.0.1:8188. It got {url}."


def test_the_urls_it_can_use_still_parse():
    assert live.parse_args([]).url == live.COMFYUI_URL
    assert live.parse_args(["--url", "https://comfy.local:8443"]).url == "https://comfy.local:8443"


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
    os.utime(source, (1000, 1000))
    workspace = tmp_path / "Cargo.toml"
    workspace.write_text("", encoding="utf-8")
    os.utime(workspace, (3000, 3000))
    assert live.core_is_stale(tmp_path)  # a release profile there changes what cargo builds


@pytest.mark.parametrize("exit_code", [0, 3])
def test_only_a_build_that_worked_leaves_the_core_matching_the_crates(tmp_path, monkeypatch, exit_code):
    # Cargo finds nothing to do for a crate file with a new time and the same bytes, and build_core's copy keeps the
    # library's old time, so without this the core reads as stale on every launch.
    built = live.core_file(tmp_path)
    built.parent.mkdir()
    built.write_text("", encoding="utf-8")
    source = tmp_path / "Cargo.lock"
    source.write_text("", encoding="utf-8")
    os.utime(built, (1000, 1000))
    os.utime(source, (2000, 2000))
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, exit_code))
    if exit_code:
        with pytest.raises(live.LaunchError, match="did not build"):
            live.build_core(tmp_path, say=quiet)
    else:
        live.build_core(tmp_path, say=quiet)
    assert live.core_is_stale(tmp_path) is bool(exit_code)


def test_a_lock_with_a_dead_or_unreadable_pid_is_not_a_live_run(tmp_path):
    assert live.live_run_pid(tmp_path) is None
    (tmp_path / ".plexus_loop").mkdir()
    (tmp_path / ".plexus_loop" / "lock").write_text("not json", encoding="utf-8")
    assert live.live_run_pid(tmp_path) is None
    (tmp_path / ".plexus_loop" / "lock").write_text(json.dumps({"pid": DEAD_PID}), encoding="utf-8")
    assert live.live_run_pid(tmp_path) is None
    (tmp_path / ".plexus_loop" / "lock").write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    if sys.platform.startswith("win"):
        assert live.live_run_pid(tmp_path) == os.getpid()


def test_a_run_the_check_cannot_tell_about_is_not_called_live(tmp_path, monkeypatch):
    (tmp_path / ".plexus_loop").mkdir()
    (tmp_path / ".plexus_loop" / "lock").write_text(json.dumps({"pid": 4242}), encoding="utf-8")
    monkeypatch.setattr(live, "pid_alive", lambda pid: None)
    assert live.live_run_pid(tmp_path) is None
    monkeypatch.setattr(live, "pid_alive", lambda pid: True)
    assert live.live_run_pid(tmp_path) == 4242


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
