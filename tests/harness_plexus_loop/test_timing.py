"""Each ledger row says where the attempt's time went: route, worker, each gate, metric, wall.

Run 4 attempt 1 took about 24 minutes against an 11 minute mean, and the ledger could not say
whether the model or the gates grew. Durations in these tests are near zero, so they check
presence, order and that the parts never exceed the whole, never magnitudes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from harness.plexus_loop import MissionRun
from harness.plexus_loop.loop import Attempt
from harness.plexus_loop.mission import mission_from_dict
from harness.plexus_loop.profile import Profile
from harness.plexus_loop.workers import WorkerResult

PY = sys.executable
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
TIMING_KEYS = ("wall_s", "route_s", "worker_s", "gates", "metric_s")


def _repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    (r / "plexus").mkdir(parents=True)
    (r / "tests" / "acceptance").mkdir(parents=True)
    (r / "tests" / "acceptance" / "f.txt").write_text("x")
    (r / "plexus" / "score.txt").write_text("5\n")
    for args in (["init", "-q", "-b", "master"], ["add", "-A"], ["commit", "-q", "-m", "s"]):
        subprocess.run([*GIT, *args], cwd=r, check=True, capture_output=True)
    return r


def _mission(attempts):
    # Gate "first" always passes; gate "second" fails whenever plexus/bad.txt exists.
    return mission_from_dict({
        "mission": {"name": "demo", "goal": "g", "requires": ["tests/acceptance"], "focus": ["plexus/**"],
                    "frozen": ["tests/acceptance/**"]},
        "metric": {"kind": "command", "cmd": [PY, "-c", "print(open('plexus/score.txt').read().strip())"]},
        "gates": [{"name": "first", "cmd": [PY, "-c", "print('ok')"]},
                  {"name": "second", "cmd": [PY, "-c", "import os,sys; sys.exit(1 if os.path.exists('plexus/bad.txt') else 0)"]}],
        "budget": {"attempts": attempts, "hours": 1, "max_consecutive_failures": 5},
    })


class Steps:
    """Each step returns a WorkerResult, or raises, after acting on the worktree."""

    def __init__(self, *steps):
        self.steps = list(steps)

    def attempt(self, wt, prompt, profile):
        return self.steps.pop(0)(wt)


def _write(rel, text, ok=True):
    def step(wt):
        (wt / rel).write_text(text)
        return WorkerResult(ok, "ok" if ok else "model returned nothing usable")
    return step


def _run(r, worker, attempts):
    return MissionRun(_mission(attempts), r, worker=worker, log=lambda s: None,
                      profile_fn=lambda: Profile(device="cpu", houdini="running")).run()


def _parts(a: Attempt) -> float:
    return (a.route_s or 0) + (a.worker_s or 0) + sum(g["seconds"] for g in a.gates) + (a.metric_s or 0)


def test_new_rows_default_to_unmeasured_not_zero():
    a = Attempt(n=1, started=0.0, houdini="off", device="gpu")
    assert (a.wall_s, a.route_s, a.worker_s, a.gates, a.metric_s) == (None, None, None, [], None)


def test_kept_attempt_times_every_step(tmp_path):
    r = _repo(tmp_path)
    (a,) = _run(r, Steps(_write("plexus/score.txt", "4\n")), attempts=1).attempts
    assert a.kept
    for v in (a.wall_s, a.route_s, a.worker_s, a.metric_s):
        assert isinstance(v, float) and v >= 0
    assert [g["name"] for g in a.gates] == ["first", "second"]
    assert all(g["ok"] is True and isinstance(g["seconds"], float) for g in a.gates)
    assert a.wall_s >= _parts(a) - 0.2  # each part rounds to a tenth on its own


def test_gate_drop_times_gates_up_to_the_failure_and_skips_the_metric(tmp_path):
    r = _repo(tmp_path)
    (a,) = _run(r, Steps(_write("plexus/bad.txt", "x")), attempts=1).attempts
    assert not a.kept and a.reason == "gate 'second' failed"
    assert [(g["name"], g["ok"]) for g in a.gates] == [("first", True), ("second", False)]
    assert a.metric_s is None
    assert isinstance(a.worker_s, float) and isinstance(a.wall_s, float)


def test_worker_failure_times_the_worker_and_runs_no_gates(tmp_path):
    r = _repo(tmp_path)
    (a,) = _run(r, Steps(_write("plexus/x.txt", "x", ok=False)), attempts=1).attempts
    assert a.reason.startswith("worker:")
    assert isinstance(a.worker_s, float) and isinstance(a.wall_s, float)
    assert a.gates == [] and a.metric_s is None


def test_worker_that_raises_still_records_its_time(tmp_path):
    def boom(wt):
        raise OSError("disk full")
    r = _repo(tmp_path)
    (a,) = _run(r, Steps(boom), attempts=1).attempts
    assert a.reason.startswith("attempt error: OSError")
    assert isinstance(a.worker_s, float) and isinstance(a.wall_s, float)
    assert a.gates == []


def test_ledger_rows_carry_every_timing_key(tmp_path):
    r = _repo(tmp_path)
    _run(r, Steps(_write("plexus/bad.txt", "x"), _write("plexus/score.txt", "4\n")), attempts=2)
    rows = [json.loads(x) for x in
            (r / ".plexus_loop" / "demo" / "attempts.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    for row in rows:
        assert all(k in row for k in TIMING_KEYS)
    assert rows[0]["metric_s"] is None and rows[0]["gates"][-1] == {"name": "second", "seconds": rows[0]["gates"][-1]["seconds"], "ok": False}
    assert isinstance(rows[1]["metric_s"], float)
