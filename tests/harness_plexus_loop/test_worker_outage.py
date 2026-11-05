"""An outage of the model server: which calls count as one, and when the run stops. Nothing here reaches a real server."""

from __future__ import annotations

import http.client
import io
import json
import os
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

from harness.plexus_loop import MissionRun, RefuseToStart, loop
from harness.plexus_loop.__main__ import main as cli_main
from harness.plexus_loop.loop import WORKER_DOWN
from harness.plexus_loop.mission import WorkerSpec, mission_from_dict
from harness.plexus_loop.profile import Profile
from harness.plexus_loop.workers import HTTP_ERROR_BODY_CHARS, READY_TIMEOUT_S, OllamaWorker, WorkerResult

PY = sys.executable
CPU = Profile(device="cpu", houdini="running", ollama_options={"num_gpu": 0, "num_thread": 2})
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
sys.path.insert(0, str(Path(loop.__file__).parent / "tools"))


def _repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    (r / "plexus").mkdir(parents=True)
    (r / "fixed").mkdir(parents=True)
    (r / "plexus" / "score.txt").write_text("5\n")
    (r / "fixed" / "f.txt").write_text("x\n")
    for a in (["init", "-q", "-b", "master"], ["add", "-A"], ["commit", "-q", "-m", "s"]):
        subprocess.run([*GIT, *a], cwd=r, check=True, capture_output=True)
    return r


def _mission(metric_code="print(open('plexus/score.txt').read().strip())", gates=None, attempts=120, cap=30):
    d = {
        "mission": {"name": "demo", "goal": "g", "requires": ["fixed"], "focus": ["plexus/**"], "frozen": ["fixed/**"]},
        "metric": {"kind": "command", "cmd": [PY, "-c", metric_code]},
        "gates": gates or [{"name": "ok", "cmd": [PY, "-c", "pass"]}],
        "budget": {"attempts": attempts, "hours": 1, "max_consecutive_failures": cap},
    }
    return mission_from_dict(d)


class Worker:
    def __init__(self, *results):
        self.results, self.calls = list(results), 0

    def attempt(self, wt, prompt, profile):
        self.calls += 1
        step = self.results.pop(0)
        return step(wt) if callable(step) else step


def _score(n):
    def step(wt):
        (wt / "plexus" / "score.txt").write_text(f"{n}\n")
        return WorkerResult(True, "ok")
    return step


def _raises(e):
    def f(req, timeout):
        raise e
    return f


HTTP500 = urllib.error.HTTPError("u", 500, "Internal Server Error", {}, io.BytesIO(b'{"error":"llama-server binary not found"}'))


@pytest.mark.parametrize("error, unreachable, says", [
    (urllib.error.URLError("refused"), True, "URLError"),
    (http.client.RemoteDisconnected("closed"), True, "RemoteDisconnected"),
    (ConnectionResetError("reset"), True, "ConnectionResetError"),
    (HTTP500, True, "llama-server binary not found"),
    (http.client.IncompleteRead(b""), True, "IncompleteRead"),  # the server died in the middle of its reply
    (TimeoutError("timed out"), False, "TimeoutError"),  # the model had its 4800 s: a real attempt
    (ValueError("bad json"), False, "ValueError"),
])
def test_only_a_call_no_model_could_answer_is_unreachable(tmp_path, monkeypatch, error, unreachable, says):
    monkeypatch.setattr("urllib.request.urlopen", _raises(error))
    res = OllamaWorker(WorkerSpec()).attempt(tmp_path, "prompt", CPU)
    assert not res.ok and res.unreachable is unreachable and says in res.note
    assert res.note.startswith("ollama call failed: ")  # report_stats and test_tools read this prefix


class _BodyGone(io.BytesIO):
    def read(self, *a):
        raise http.client.IncompleteRead(b"")


@pytest.mark.parametrize("fp, tail", [
    (io.BytesIO(b'{"error":\n "out of\r\n memory"}\n'), ': {"error": "out of memory"}'),
    (io.BytesIO(b"x" * 5000), ": " + "x" * HTTP_ERROR_BODY_CHARS),
    (_BodyGone(), ""),
], ids=["on several lines", "past the limit", "cut off by the server"])
def test_an_http_errors_body_leaves_one_short_line_and_never_raises(tmp_path, monkeypatch, fp, tail):
    # The note becomes a ledger reason, a row of REVIEW.md's table and the stop line. IncompleteRead is no OSError, so
    # raised from here it would pass the loop's own except and end the run.
    monkeypatch.setattr("urllib.request.urlopen", _raises(urllib.error.HTTPError("u", 500, "Internal Server Error", {}, fp)))
    res = OllamaWorker(WorkerSpec()).attempt(tmp_path, "prompt", CPU)
    assert res.unreachable and res.note == f"ollama call failed: HTTPError: HTTP Error 500: Internal Server Error{tail}"


def test_an_outage_stops_the_run_on_its_second_row(tmp_path):
    r = _repo(tmp_path)
    routed = []

    def route(mi, last, attempts):
        routed.append(1)
        return loop.Route(None, "none")

    down = WorkerResult(False, "ollama call failed: URLError: refused", unreachable=True)
    w = Worker(down, down, _score(1))
    rep = MissionRun(_mission(), r, worker=w, profile_fn=lambda: CPU, log=lambda s: None, route_fn=route).run()
    assert w.calls == 2 and len(routed) == 2 and len(rep.attempts) == 2
    assert rep.stop_reason == f"{WORKER_DOWN}: worker: ollama call failed: URLError: refused"
    rows = [json.loads(x) for x in (r / ".plexus_loop" / "demo" / "attempts.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["unreachable"] for row in rows] == [True, True] and not rows[1]["kept"]
    assert f"Status: {WORKER_DOWN}" in (r / ".plexus_loop" / "demo" / "REVIEW.md").read_text(encoding="utf-8")
    assert not (r / ".plexus_loop" / "lock").exists()


def test_one_dropped_connection_costs_its_attempt_and_the_run_goes_on(tmp_path):
    r = _repo(tmp_path)
    w = Worker(WorkerResult(False, "ollama call failed: RemoteDisconnected: closed", unreachable=True), _score(4))
    rep = MissionRun(_mission(attempts=2), r, worker=w, profile_fn=lambda: CPU, log=lambda s: None).run()
    assert [a.kept for a in rep.attempts] == [False, True] and "attempt budget" in rep.stop_reason


def test_two_outage_rows_apart_do_not_stop_the_run(tmp_path):
    # In a row is the rule: a server that answered between two dropped calls can answer the next one.
    down = WorkerResult(False, "ollama call failed: RemoteDisconnected: closed", unreachable=True)
    other = WorkerResult(False, "model reply held no unified diff and no file block")
    w = Worker(down, other, down)
    rep = MissionRun(_mission(attempts=3), _repo(tmp_path), worker=w, profile_fn=lambda: CPU, log=lambda s: None).run()
    assert w.calls == 3 and "attempt budget" in rep.stop_reason


def test_an_ordinary_worker_failure_still_goes_on(tmp_path):
    r = _repo(tmp_path)
    w = Worker(WorkerResult(False, "model reply held no unified diff and no file block"), _score(4), _score(3))
    rep = MissionRun(_mission(attempts=3), r, worker=w, profile_fn=lambda: CPU, log=lambda s: None).run()
    assert [a.kept for a in rep.attempts] == [False, True, True] and "attempt budget" in rep.stop_reason


def test_an_outage_row_never_reaches_the_router(tmp_path, monkeypatch):
    # A 500's body can quote this machine's paths, and Jev is a third party. An outage says nothing about a step anyway.
    r = _repo(tmp_path)
    seen = []

    def choose(router, steps, failing, tail, recent):
        seen.append(list(recent))
        return loop.Route(None, "none")

    monkeypatch.setattr(loop, "choose_route", choose)
    down = WorkerResult(False, 'ollama call failed: HTTPError: HTTP Error 500: {"error":"C:/Users/me"}', unreachable=True)
    other = WorkerResult(False, "model reply held no unified diff and no file block")
    w = Worker(other, down, _score(4))
    MissionRun(_mission(attempts=3), r, worker=w, profile_fn=lambda: CPU, log=lambda s: None).run()
    assert [len(recent) for recent in seen] == [0, 1, 1]
    assert not any("C:/Users" in line for recent in seen for line in recent)


def test_the_new_rows_stay_out_of_the_means():
    import report_stats

    rows = [
        {"reason": "strict gain", "kept": True, "device": "cpu", "wall_s": 1800},
        {"reason": 'worker: ollama call failed: HTTPError: HTTP Error 500: {"error":"llama-server binary not found"}', "unreachable": True, "device": "cpu", "wall_s": 2},
        {"reason": "worker: ollama call failed: URLError: refused", "device": "cpu", "wall_s": 3},
        {"reason": "worker: ollama call failed: TimeoutError: timed out", "device": "cpu", "wall_s": 4800},
        {"reason": "git: worktree add failed", "route_s": None, "device": "cpu", "wall_s": 0.2},
    ]
    assert len(report_stats.real_attempts(rows)) == 2
    assert report_stats.drop_reasons(rows)["no server"] == 3


def test_an_outage_row_leaves_the_next_prompt_as_it_was(tmp_path):
    # Row 90 lost its connection at 199 s. No model answered that call, so the attempt after it still owes the failure
    # and the files of the attempt before it.
    prompts = []

    class Seeing(Worker):
        def attempt(self, wt, prompt, profile):
            prompts.append(prompt)
            return super().attempt(wt, prompt, profile)

    def draft(wt):
        (wt / "plexus" / "draft.py").write_text("DRAFT = 1\n")
        return WorkerResult(True, "ok")

    down = WorkerResult(False, "ollama call failed: RemoteDisconnected: closed", unreachable=True)
    w = Seeing(draft, down, WorkerResult(False, "model reply held no unified diff and no file block"))
    MissionRun(_mission(attempts=3), _repo(tmp_path), worker=w, profile_fn=lambda: CPU, log=lambda s: None).run()
    assert prompts[2] == prompts[1] and "DRAFT = 1" in prompts[2] and "RemoteDisconnected" not in prompts[2]


class Answers(Worker):
    """A stand-in with the real worker's check. ``why(i)`` says what the i-th ask of the load answers."""

    def __init__(self, *results, why=lambda i: ""):
        super().__init__(*results)
        self.why, self.asks = why, 0

    def cannot_run(self, profile):
        self.asks += 1
        return self.why(self.asks - 1)


DOWN = WorkerResult(False, "ollama call failed: URLError: refused", unreachable=True)


def _wait(monkeypatch, seconds=30.0):
    monkeypatch.setattr(loop, "WORKER_WAIT_S", seconds)
    monkeypatch.setattr(loop, "WORKER_POLL_S", 0.01)


def test_a_server_that_comes_back_costs_one_row_and_the_run_goes_on(tmp_path, monkeypatch):
    # Ask 0 is the load before the baseline. Asks 1 and 2 are the gap, a restart or an update taking its time.
    _wait(monkeypatch)
    w = Answers(DOWN, _score(4), why=lambda i: "refused" if i in (1, 2) else "")
    rep = MissionRun(_mission(attempts=2), _repo(tmp_path), worker=w, profile_fn=lambda: CPU, log=lambda s: None).run()
    assert [(a.kept, a.unreachable) for a in rep.attempts] == [(False, True), (True, False)]
    assert w.asks == 4 and "attempt budget" in rep.stop_reason


def test_an_engine_that_stays_gone_stops_after_the_wait_on_one_row(tmp_path, monkeypatch):
    _wait(monkeypatch, 0.05)
    routed = []

    def route(mi, last, attempts):
        routed.append(1)
        return loop.Route(None, "none")

    w = Answers(DOWN, _score(1), why=lambda i: "binary not found" if i else "")
    rep = MissionRun(_mission(), _repo(tmp_path), worker=w, profile_fn=lambda: CPU, log=lambda s: None, route_fn=route).run()
    assert w.calls == 1 and len(routed) == 1 and rep.stop_reason == f"{WORKER_DOWN}: binary not found"
    assert w.asks > 2  # it asked again during the wait


def test_two_rows_in_a_row_stop_even_when_the_load_answers(tmp_path, monkeypatch):
    # A server that loads and then drops every real call would otherwise spend the whole consecutive count.
    _wait(monkeypatch)
    w = Answers(DOWN, DOWN, _score(1))
    rep = MissionRun(_mission(), _repo(tmp_path), worker=w, profile_fn=lambda: CPU, log=lambda s: None).run()
    assert w.calls == 2 and rep.stop_reason == f"{WORKER_DOWN}: worker: {DOWN.note}"


def test_a_load_that_clears_during_the_wait_starts_the_run(tmp_path, monkeypatch):
    _wait(monkeypatch)
    w = Answers(why=lambda i: "busy" if i < 2 else "")
    rep = MissionRun(_mission(attempts=0), _repo(tmp_path), worker=w, profile_fn=lambda: CPU, log=lambda s: None).run()
    assert w.asks == 3 and rep.baseline == 5


def test_a_load_that_stays_down_refuses_only_after_the_wait(tmp_path, monkeypatch):
    _wait(monkeypatch, 0.05)
    w = Answers(why=lambda i: "binary not found")
    r = _repo(tmp_path)
    with pytest.raises(RefuseToStart, match=f"{WORKER_DOWN}: binary not found"):
        MissionRun(_mission(), r, worker=w, profile_fn=lambda: CPU, log=lambda s: None).run()
    assert w.asks > 2 and not (r / ".plexus_loop" / "lock").exists()


def test_a_stop_file_ends_the_wait_and_says_stop_file(tmp_path, monkeypatch):
    _wait(monkeypatch)
    r = _repo(tmp_path)

    def why(i):
        if i == 3:
            (r / ".plexus_loop" / "STOP").write_text("stop")
        return "refused" if i else ""

    w = Answers(DOWN, _score(1), why=why)
    rep = MissionRun(_mission(), r, worker=w, profile_fn=lambda: CPU, log=lambda s: None).run()
    assert w.calls == 1 and w.asks == 4 and rep.stop_reason == "stop file"


def _left_out_replies(tmp_path, *steps):
    d = {
        "mission": {"name": "demo", "goal": "g", "requires": ["fixed"], "focus": ["plexus/**"], "frozen": ["fixed/**"]},
        "metric": {"kind": "command", "cmd": [PY, "-c", "print(open('plexus/score.txt').read().strip())"]},
        "gates": [{"name": "ok", "cmd": [PY, "-c", "pass"]}],
        "steps": [{"id": "S1", "targets": ["fixed/f.txt"], "text": "Write the files.", "files": ["plexus/a.py", "plexus/b.py", "plexus/c.py"]}],
        "router": {"kind": "first"},
        "budget": {"attempts": len(steps), "hours": 1, "max_consecutive_failures": 30},
    }
    return MissionRun(mission_from_dict(d), _repo(tmp_path), worker=Worker(*steps), log=lambda s: None,
                      route_fn=lambda mi, last, att: loop.Route(mi.steps[0], "first"), profile_fn=lambda: CPU).run().attempts


def _writes(rel):
    def step(wt):
        (wt / rel).write_text(f"# {rel}\n")
        return WorkerResult(True, "ok", wrote=[rel])
    return step


DROPPED = WorkerResult(False, "ollama call failed: RemoteDisconnected: closed", unreachable=True)


def test_a_left_out_reply_after_an_outage_row_keeps_the_draft_from_before_it(tmp_path):
    # The draft from attempt 1 must survive the outage at attempt 2, or attempt 3 would hand on its own file alone.
    rows = _left_out_replies(tmp_path, _writes("plexus/a.py"), DROPPED, _writes("plexus/b.py"))
    assert [a.handed_on for a in rows] == [["plexus/a.py"], [], ["plexus/a.py", "plexus/b.py"]]


def test_a_left_out_reply_after_a_first_row_outage_has_no_draft_to_keep(tmp_path):
    rows = _left_out_replies(tmp_path, DROPPED, _writes("plexus/a.py"))
    assert [a.handed_on for a in rows] == [[], ["plexus/a.py"]]


def _recording(monkeypatch, error=None):
    sent = []

    def urlopen(req, timeout):
        sent.append((json.loads(req.data), timeout))
        if error is not None:
            raise error
        return io.BytesIO(b'{"response": "", "done": true, "done_reason": "load"}')

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    return sent


def test_a_model_that_cannot_load_refuses_the_run_before_its_baseline(tmp_path, monkeypatch):
    r = _repo(tmp_path)
    gone = urllib.error.HTTPError("u", 500, "Internal Server Error", {}, io.BytesIO(b'{"error":"llama-server binary not found"}'))
    sent = _recording(monkeypatch, gone)
    with pytest.raises(RefuseToStart, match=f"{WORKER_DOWN}: .*llama-server binary not found.*Nothing was run"):
        MissionRun(_mission(), r, profile_fn=lambda: CPU, log=lambda s: None).run()
    ((body, timeout),) = sent
    assert body["prompt"] == "" and body["options"] == {"num_gpu": 0, "num_thread": 2} and timeout == READY_TIMEOUT_S
    assert not (r / ".plexus_loop" / "demo").exists() and not (r / ".plexus_loop" / "lock").exists()
    assert "plexus-loop/demo" not in subprocess.run([*GIT, "branch"], cwd=r, capture_output=True, text=True, check=True).stdout


def test_a_model_that_loads_starts_the_run(tmp_path, monkeypatch):
    sent = _recording(monkeypatch)
    rep = MissionRun(_mission(attempts=0), _repo(tmp_path), profile_fn=lambda: CPU, log=lambda s: None).run()
    assert len(sent) == 1 and rep.baseline == 5 and rep.attempts == []


@pytest.mark.parametrize("error", [TimeoutError("timed out"), ValueError("bad json")])
def test_a_slow_load_or_an_odd_reply_is_no_refusal(monkeypatch, error):
    # The same line attempt() draws: the server took the call.
    _recording(monkeypatch, error)
    assert OllamaWorker(WorkerSpec()).cannot_run(CPU) == ""


def test_a_second_run_never_loads_a_model_beside_a_live_one(tmp_path, monkeypatch):
    r = _repo(tmp_path)
    (r / ".plexus_loop").mkdir()
    (r / ".plexus_loop" / "lock").write_text(json.dumps({"pid": os.getpid(), "mission": "other"}))
    sent = _recording(monkeypatch)
    with pytest.raises(RefuseToStart, match="holds the lock"):
        MissionRun(_mission(), r, profile_fn=lambda: CPU, log=lambda s: None).run()
    assert sent == []


def test_check_never_loads_the_model_and_keeps_ready_last_within_five_lines(tmp_path, monkeypatch, capsys):
    # /mission reads check through head -5, and the real mission prints the fix router's line too.
    sent = _recording(monkeypatch)
    r = _repo(tmp_path)
    assert cli_main(["check", str(Path(loop.__file__).parent / "missions" / "acceptance.toml"), "--repo", str(r)]) == 2
    lines = capsys.readouterr().out.splitlines()
    assert sent == [] and len(lines) <= 5 and lines[-1].startswith("not ready")
    monkeypatch.setattr("harness.plexus_loop.__main__.load_mission", lambda p: _mission())
    assert cli_main(["check", "any.toml", "--repo", str(r)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert sent == [] and "does not load" in lines[-2] and lines[-1] == "ready"
