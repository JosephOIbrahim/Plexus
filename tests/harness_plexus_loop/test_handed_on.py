"""A dropped attempt that passed every gate hands its files to the next prompt, to resend in full.

Run 6 attempt 1 sent all five S2 files, passed every gate, and failed T1 on one missing import.
Attempts 2 and 3 then sent one and three files: the worker treats each attempt as an edit to its
last one, but every attempt starts from the last kept commit, where those files are gone.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from harness.plexus_loop import MissionRun
from harness.plexus_loop.loop import CARRY_CHARS, Attempt, build_prompt, carry_files
from harness.plexus_loop.mission import mission_from_dict
from harness.plexus_loop.profile import Profile
from harness.plexus_loop.router import Route
from harness.plexus_loop.workers import WorkerResult

PY = sys.executable
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
FILES = ["plexus/a.py", "plexus/b.py"]


def _raw(gate_fails_on=None, attempts=2):
    gate = [PY, "-c", "print('ok')"] if gate_fails_on is None else \
        [PY, "-c", f"import os,sys; sys.exit(1 if os.path.exists({gate_fails_on!r}) else 0)"]
    return {
        "mission": {"name": "demo", "goal": "g", "requires": ["tests/acceptance"], "focus": ["plexus/**"],
                    "frozen": ["tests/acceptance/**", "plexus/frozen.txt"]},
        "metric": {"kind": "command", "cmd": [PY, "-c", "print(5)"]},
        "gates": [{"name": "layers", "cmd": gate}, {"name": "unit", "cmd": [PY, "-c", "print('ok')"]}],
        "steps": [{"id": "S1", "targets": ["tests/acceptance/test_x.py"], "text": "Write a and b.", "files": FILES}],
        "router": {"kind": "first"},
        "budget": {"attempts": attempts, "hours": 1, "max_consecutive_failures": 5},
    }


def _repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    (r / "plexus").mkdir(parents=True)
    (r / "tests" / "acceptance").mkdir(parents=True)
    (r / "tests" / "acceptance" / "f.txt").write_text("x")
    (r / "plexus" / "keep.txt").write_text("k")
    for args in (["init", "-q", "-b", "master"], ["add", "-A"], ["commit", "-q", "-m", "s"]):
        subprocess.run([*GIT, *args], cwd=r, check=True, capture_output=True)
    return r


class Steps:
    def __init__(self, *steps):
        self.steps, self.prompts = list(steps), []

    def attempt(self, wt, prompt, profile):
        self.prompts.append(prompt)
        self.steps.pop(0)(wt)
        return WorkerResult(True, "ok")


def _run(r, raw, *steps):
    w = Steps(*steps)
    report = MissionRun(mission_from_dict(raw), r, worker=w, log=lambda s: None,
                        route_fn=lambda mi, last, att: Route(mi.steps[0], "first"),
                        profile_fn=lambda: Profile(device="cpu", houdini="running")).run()
    return report, w


def _write_both(wt):
    (wt / "plexus" / "a.py").write_text("A = 1  # ```` backticks inside\n")
    (wt / "plexus" / "b.py").write_text("B = 2\n")


def test_a_gate_passing_drop_hands_its_files_to_the_next_prompt(tmp_path):
    r = _repo(tmp_path)
    report, w = _run(r, _raw(), _write_both, _write_both)  # both complete: gate-passing, no-gain drops
    first, second = report.attempts
    assert first.reason == second.reason == "no strict gain (5 vs best 5)"
    assert not first.kept and first.handed_on == FILES
    section = w.prompts[1].split("## Your last attempt's files", 1)[1].split("## Where it stands", 1)[0]
    assert "file:plexus/a.py\nA = 1" in section and "file:plexus/b.py\nB = 2" in section
    assert "`````file:plexus/a.py" in section  # fence longer than the backticks inside
    assert "Resend every one of them in full" in section
    assert "## Your last attempt's files" not in w.prompts[0]


def test_a_gate_failure_hands_nothing_on(tmp_path):
    r = _repo(tmp_path)
    report, w = _run(r, _raw(gate_fails_on="plexus/b.py"), _write_both, _write_both)
    assert report.attempts[0].reason == "gate 'layers' failed" and report.attempts[0].handed_on == []
    assert "## Your last attempt's files" not in w.prompts[1]


def test_only_the_last_attempt_is_handed_on(tmp_path):
    # Attempt 1 passes the gates (handed on), attempt 2 fails a gate: attempt 3 must not see
    # attempt 1's files as if they were the last attempt's.
    r = _repo(tmp_path)
    raw = _raw(gate_fails_on="plexus/bad.txt", attempts=3)

    def both_and_bad(wt):  # sends the step's files too, so it reaches the gate and fails there
        _write_both(wt)
        (wt / "plexus" / "bad.txt").write_text("x")
    report, w = _run(r, raw, _write_both, both_and_bad, _write_both)
    assert report.attempts[0].handed_on and not report.attempts[1].handed_on
    assert report.attempts[1].reason == "gate 'layers' failed"
    assert "## Your last attempt's files" in w.prompts[1]
    assert "## Your last attempt's files" not in w.prompts[2]


def test_carry_files_orders_step_files_first_skips_frozen_unreadable_and_over_budget(tmp_path):
    m = mission_from_dict(_raw())
    (tmp_path / "plexus").mkdir()
    (tmp_path / "plexus" / "z.py").write_text("Z\n")
    (tmp_path / "plexus" / "b.py").write_text("B\n")
    (tmp_path / "plexus" / "a.py").write_text("A\n")
    (tmp_path / "plexus" / "frozen.txt").write_text("F\n")
    (tmp_path / "plexus" / "bin.dat").write_bytes(b"\xff\xfe\x00")
    (tmp_path / "plexus" / "big.py").write_text("x" * (CARRY_CHARS + 1))
    out = carry_files(tmp_path, ["plexus/z.py", "plexus/b.py", "plexus/a.py", "plexus/frozen.txt",
                                 "plexus/bin.dat", "plexus/big.py", "plexus/gone.py"], m, m.steps[0])
    assert list(out) == ["plexus/a.py", "plexus/b.py", "plexus/z.py"]


def test_a_handed_on_tracked_file_appears_once_in_the_attempts_version(tmp_path):
    # S3 and S7 edit lib.rs and py.rs, which the tip already tracks: the prompt must not also
    # show the tip version under Files, or the model may echo the wrong one.
    r = _repo(tmp_path)  # tracks plexus/keep.txt
    m = mission_from_dict(_raw())
    a = Attempt(n=1, started=0.0, houdini="off", device="gpu", reason="no strict gain (5 vs best 5)", detail="x")
    p = build_prompt(m, r, 5, None, [a], 100000, step=m.steps[0],
                     carried=(1, {"plexus/keep.txt": "EDITED\n"}))
    assert p.count("file:plexus/keep.txt") == 1
    assert "file:plexus/keep.txt\nEDITED" in p
    assert "back to its last kept version" in p
    p2 = build_prompt(m, r, 5, None, [a], 100000, step=m.steps[0])
    assert "file:plexus/keep.txt\nk" in p2  # without a hand-on, the tip version is shown as before


def test_prompt_ignores_a_carry_from_another_attempt(tmp_path):
    m = mission_from_dict(_raw())
    a = Attempt(n=4, started=0.0, houdini="off", device="gpu", reason="no strict gain (5 vs best 5)", detail="x")
    p = build_prompt(m, _repo(tmp_path), 5, None, [a], 100000, step=m.steps[0],
                     carried=(3, {"plexus/a.py": "A\n"}))
    assert "## Your last attempt's files" not in p
    p = build_prompt(m, _repo(tmp_path / "2"), 5, None, [a], 100000, step=m.steps[0],
                     carried=(4, {"plexus/a.py": "A\n"}))
    assert "## Your last attempt's files" in p
