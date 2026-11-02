"""Each mission step lists the files it writes; a drop that leaves one out names it first.

Run 5 attempts 1 and 2 sent only the package __init__ files and axon.py for step S2, never
stagekit.py or exchange.py. The next prompt showed `cannot import name 'stagekit'` and the
worker left the files out again. Now the step lists its files, and the feedback says plainly
which of them the reply did not include.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from harness.plexus_loop import MissionRun
from harness.plexus_loop.loop import Attempt, build_prompt, missing_files
from harness.plexus_loop.mission import MissionError, Step, load_mission, mission_from_dict
from harness.plexus_loop.profile import Profile
from harness.plexus_loop.router import Route
from harness.plexus_loop.workers import WorkerResult

PY = sys.executable
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
REPO = Path(__file__).resolve().parents[2]
STEP_FILES = ["plexus/a.py", "plexus/b.py", "plexus/c.py"]


def _raw(files=None, focus=None, frozen=None):
    step = {"id": "S1", "targets": ["tests/acceptance/test_x.py"], "text": "Write a, b and c."}
    if files is not None:
        step["files"] = files
    return {
        "mission": {"name": "demo", "goal": "g", "requires": ["tests/acceptance"],
                    "focus": focus or ["plexus/**"], "frozen": frozen or ["tests/acceptance/**"]},
        "metric": {"kind": "command", "cmd": [PY, "-c", "print(5)"]},
        "gates": [{"name": "ok", "cmd": [PY, "-c", "print('ok')"]}],
        "steps": [step],
        "router": {"kind": "first"},
        "budget": {"attempts": 2, "hours": 1, "max_consecutive_failures": 5},
    }


def _repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    (r / "plexus").mkdir(parents=True)
    (r / "tests" / "acceptance").mkdir(parents=True)
    (r / "tests" / "acceptance" / "f.txt").write_text("x")
    (r / "plexus" / "a.py").write_text("A = 1\n")  # already in a kept commit
    for args in (["init", "-q", "-b", "master"], ["add", "-A"], ["commit", "-q", "-m", "s"]):
        subprocess.run([*GIT, *args], cwd=r, check=True, capture_output=True)
    return r


# -- the mission file --------------------------------------------------------

def test_files_parse_normalised_and_default_empty():
    m = mission_from_dict(_raw(files=["plexus\\a.py", "./plexus/b.py"]))
    assert m.steps[0].files == ["plexus/a.py", "plexus/b.py"]
    assert mission_from_dict(_raw()).steps[0].files == []
    assert Step("S1", ["t"], "x").files == []  # positional construction still works


@pytest.mark.parametrize("bad", [["/abs/a.py"], ["C:/x/a.py"], ["plexus/../harness/x.py"], [""],
                                 ["plexus/a.py", "plexus/a.py"]])
def test_bad_file_entries_are_refused(bad):
    with pytest.raises(MissionError):
        mission_from_dict(_raw(files=bad))


def test_a_file_the_worker_could_never_write_is_refused():
    with pytest.raises(MissionError, match="outside focus or frozen"):
        mission_from_dict(_raw(files=["harness/x.py"]))
    with pytest.raises(MissionError, match="outside focus or frozen"):
        mission_from_dict(_raw(files=["plexus/frozen.py"], frozen=["plexus/frozen.py"]))


def test_the_acceptance_mission_lists_files_for_every_step():
    m = load_mission(REPO / "harness" / "plexus_loop" / "missions" / "acceptance.toml")
    assert m.steps and all(s.files for s in m.steps)
    s2 = next(s for s in m.steps if s.id == "S2")
    assert {"plexus/core/stagekit.py", "plexus/membrane/exchange.py", "plexus/core/axon.py"} <= set(s2.files)


# -- the check ----------------------------------------------------------------

def test_missing_files_keeps_step_order_and_counts_existing_files_as_present(tmp_path):
    (tmp_path / "plexus").mkdir()
    (tmp_path / "plexus" / "b.py").write_text("")
    (tmp_path / "plexus" / "c.py").mkdir()  # a directory is not the file
    assert missing_files(tmp_path, STEP_FILES) == ["plexus/a.py", "plexus/c.py"]
    assert missing_files(tmp_path, []) == []


# -- the prompt ----------------------------------------------------------------

def test_step_section_lists_the_files(tmp_path):
    m = mission_from_dict(_raw(files=STEP_FILES))
    p = build_prompt(m, _repo(tmp_path), 5, None, [], 100000, step=m.steps[0])
    section = p.split("## This attempt", 1)[1].split("## Where it stands", 1)[0]
    assert "Files this step writes: plexus/a.py, plexus/b.py, plexus/c.py." in section


def test_missing_files_lead_the_feedback_above_syntax_and_output(tmp_path):
    m = mission_from_dict(_raw(files=STEP_FILES))
    a = Attempt(n=1, started=0.0, houdini="off", device="gpu", reason="no strict gain (5 vs best 5)",
                route="S1 via first", detail="E   ImportError: cannot import name 'b'",
                syntax=["plexus/a.py:1: invalid syntax"], missing=["plexus/b.py", "plexus/c.py"])
    p = build_prompt(m, _repo(tmp_path), 5, None, [a], 100000, step=m.steps[0])
    fb = p.split("## Why the last attempt was dropped", 1)[1]
    assert fb.index("- plexus/b.py") < fb.index("- plexus/c.py") < fb.index("invalid syntax") < fb.index("ImportError")
    assert "did not include them" in fb


def test_missing_alone_still_opens_the_feedback_section(tmp_path):
    m = mission_from_dict(_raw(files=STEP_FILES))
    a = Attempt(n=1, started=0.0, houdini="off", device="gpu", reason="worker: patch did not apply",
                missing=["plexus/c.py"])
    p = build_prompt(m, _repo(tmp_path), 5, None, [a], 100000, step=m.steps[0])
    assert "## Why the last attempt was dropped" in p and "- plexus/c.py" in p


# -- a whole run -------------------------------------------------------------

class Steps:
    def __init__(self, *steps):
        self.steps, self.prompts = list(steps), []

    def attempt(self, wt, prompt, profile):
        self.prompts.append(prompt)
        self.steps.pop(0)(wt)
        return WorkerResult(True, "ok")


def _route(mission, last, attempts):
    return Route(mission.steps[0], "first")


def test_run_names_the_files_a_drop_left_out(tmp_path):
    r = _repo(tmp_path)
    m = mission_from_dict(_raw(files=STEP_FILES))
    def both(wt):  # a dropped attempt's files are gone, so the second sends b and c again
        (wt / "plexus" / "b.py").write_text("B = 1\n")
        (wt / "plexus" / "c.py").write_text("C = 1\n")
    w = Steps(lambda wt: (wt / "plexus" / "b.py").write_text("B = 1\n"), both)  # first leaves out c.py
    report = MissionRun(m, r, worker=w, log=lambda s: None, route_fn=_route,
                        profile_fn=lambda: Profile(device="cpu", houdini="running")).run()
    first, second = report.attempts
    assert not first.kept and first.missing == ["plexus/c.py"]  # a.py is in the kept commit
    assert "- plexus/c.py" in w.prompts[1].split("## Why the last attempt was dropped", 1)[1]
    assert second.missing == []
    rows = [json.loads(x) for x in (r / ".plexus_loop" / "demo" / "attempts.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["missing"] == ["plexus/c.py"] and rows[1]["missing"] == []
