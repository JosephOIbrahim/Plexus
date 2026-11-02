"""The next attempt sees why the last one was dropped: the failing gate's output, or the metric's."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from harness.plexus_loop import MissionRun
from harness.plexus_loop.metrics import _clip
from harness.plexus_loop.mission import mission_from_dict
from harness.plexus_loop.profile import Profile
from harness.plexus_loop.workers import WorkerResult

PY = sys.executable
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def _repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    (r / "plexus").mkdir(parents=True)
    (r / "tests" / "acceptance").mkdir(parents=True)
    (r / "tests" / "acceptance" / "f.txt").write_text("x")
    (r / "plexus" / "score.txt").write_text("5\n")
    for args in (["init", "-q", "-b", "master"], ["add", "-A"], ["commit", "-q", "-m", "s"]):
        subprocess.run([*GIT, *args], cwd=r, check=True, capture_output=True)
    return r


# The gate fails, printing a rule, whenever plexus/bad.txt exists.
GATE = [PY, "-c", "import os,sys; bad=os.path.exists('plexus/bad.txt'); "
        "print('RULE: plexus.core must stay free of pxr' if bad else 'ok'); sys.exit(1 if bad else 0)"]


def _mission(attempts=3):
    return mission_from_dict({
        "mission": {"name": "demo", "goal": "g", "requires": ["tests/acceptance"], "focus": ["plexus/**"],
                    "frozen": ["tests/acceptance/**"]},
        "metric": {"kind": "command", "cmd": [PY, "-c", "print(open('plexus/score.txt').read().strip())"]},
        "gates": [{"name": "layers", "cmd": GATE}],
        "budget": {"attempts": attempts, "hours": 1, "max_consecutive_failures": 5},
    })


class Steps:
    def __init__(self, *steps):
        self.steps, self.prompts = list(steps), []

    def attempt(self, wt, prompt, profile):
        self.prompts.append(prompt)
        self.steps.pop(0)(wt)
        return WorkerResult(True, "ok")


def _write(rel, text):
    return lambda wt: (wt / rel).write_text(text)


def _run(r, worker, attempts=3):
    return MissionRun(_mission(attempts), r, worker=worker, log=lambda s: None,
                      profile_fn=lambda: Profile(device="cpu", houdini="running")).run()


def test_clip_keeps_both_ends_of_long_output():
    head, tail = "error[E0425]: first\n" + "x" * 3000, "y" * 3000 + "\nerror: could not compile"
    out = _clip(head, tail)
    assert out.startswith("error[E0425]: first") and out.endswith("could not compile")
    assert "left out" in out and len(out) < 4200
    assert _clip("short") == "short"


def test_a_failed_gate_shows_its_output_in_the_next_prompt(tmp_path):
    r = _repo(tmp_path)
    w = Steps(_write("plexus/bad.txt", "x"), _write("plexus/score.txt", "4\n"))
    report = _run(r, w, attempts=2)
    assert [a.kept for a in report.attempts] == [False, True]
    first, second = w.prompts
    assert "## Why the last attempt was dropped" not in first
    assert "## Why the last attempt was dropped" in second
    assert "gate 'layers' failed" in second and "RULE: plexus.core must stay free of pxr" in second
    assert second.index("## Why the last attempt was dropped") < second.index("## Files")


def test_a_long_gate_output_keeps_its_first_error_and_command_in_the_prompt(tmp_path):
    r = _repo(tmp_path)
    loud = [PY, "-c", "import os,sys; bad=os.path.exists('plexus/bad.txt'); "
            "sys.stderr.write(('FIRST-ERROR'+chr(10)+'x'*6000) if bad else ''); sys.exit(1 if bad else 0)"]
    m = mission_from_dict({
        "mission": {"name": "demo", "goal": "g", "requires": ["tests/acceptance"], "focus": ["plexus/**"],
                    "frozen": ["tests/acceptance/**"]},
        "metric": {"kind": "command", "cmd": [PY, "-c", "print(open('plexus/score.txt').read().strip())"]},
        "gates": [{"name": "core", "cmd": loud}],
        "budget": {"attempts": 2, "hours": 1, "max_consecutive_failures": 5},
    })
    w = Steps(_write("plexus/bad.txt", "x"), _write("plexus/score.txt", "4\n"))
    MissionRun(m, r, worker=w, log=lambda s: None,
               profile_fn=lambda: Profile(device="cpu", houdini="running")).run()
    section = w.prompts[1].split("## Why the last attempt was dropped", 1)[1]
    assert "FIRST-ERROR" in section and "\n$ " in section and "left out" in section


def test_no_strict_gain_shows_the_metric_output(tmp_path):
    r = _repo(tmp_path)
    # A real change to the file that leaves the score at 5: kept by no gate, judged by the metric.
    w = Steps(_write("plexus/score.txt", "5\n\n"), _write("plexus/score.txt", "4\n"))
    _run(r, w, attempts=2)
    assert "no strict gain" in w.prompts[1] and "This is what it printed:" in w.prompts[1]


def test_after_a_kept_attempt_there_is_nothing_to_explain(tmp_path):
    r = _repo(tmp_path)
    w = Steps(_write("plexus/score.txt", "4\n"), _write("plexus/score.txt", "3\n"))
    _run(r, w, attempts=2)
    assert "## Why the last attempt was dropped" not in w.prompts[1]


def test_the_ledger_records_the_detail(tmp_path):
    r = _repo(tmp_path)
    _run(r, Steps(_write("plexus/bad.txt", "x")), attempts=1)
    line = (r / ".plexus_loop" / "demo" / "attempts.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    assert "RULE: plexus.core must stay free of pxr" in json.loads(line)["detail"]
