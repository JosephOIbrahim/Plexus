"""A reply that leaves out any of its step's files is dropped before the gates.

Run 12 attempts 1 and 3 sent only predicate.rs. lib.rs existed as a stub at the run's base, so
the missing-files list never named it, nothing declared the module, the file was never compiled,
every gate passed in about a second, and the next prompt was told the file "passed every gate".
Now a step's `files` means every file the reply must send: one left out, sent or not before,
and the reply is dropped unbuilt with the names, and what it did send goes to the next prompt
with honest words.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from harness.plexus_loop import MissionRun
from harness.plexus_loop.loop import LEFT_OUT, left_out, left_out_of
from harness.plexus_loop.mission import Step, mission_from_dict
from harness.plexus_loop.profile import Profile
from harness.plexus_loop.router import Route
from harness.plexus_loop.workers import WorkerResult

PY = sys.executable
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
FILES = ["plexus/a.py", "plexus/b.py"]


def _repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    (r / "plexus").mkdir(parents=True)
    (r / "tests" / "acceptance").mkdir(parents=True)
    (r / "tests" / "acceptance" / "f.txt").write_text("x")
    (r / "plexus" / "score.txt").write_text("5\n")
    (r / "plexus" / "b.py").write_text("B = 0  # a stub at the base, like lib.rs in run 12\n")
    for args in (["init", "-q", "-b", "master"], ["add", "-A"], ["commit", "-q", "-m", "s"]):
        subprocess.run([*GIT, *args], cwd=r, check=True, capture_output=True)
    return r


def _mission(files, attempts=2):
    step = {"id": "S1", "targets": ["tests/acceptance/f.txt"], "text": "Write both files."}
    if files is not None:
        step["files"] = files
    return mission_from_dict({
        "mission": {"name": "demo", "goal": "g", "requires": ["tests/acceptance"], "focus": ["plexus/**"],
                    "frozen": ["tests/acceptance/**"]},
        "metric": {"kind": "command", "cmd": [PY, "-c", "print(open('plexus/score.txt').read().strip())"]},
        "gates": [{"name": "core", "cmd": [PY, "-c", "print('ok')"]}],
        "steps": [step],
        "router": {"kind": "first"},
        "budget": {"attempts": attempts, "hours": 1, "max_consecutive_failures": 5},
    })


class Steps:
    def __init__(self, *steps):
        self.steps, self.prompts = list(steps), []

    def attempt(self, wt, prompt, profile):
        self.prompts.append(prompt)
        return self.steps.pop(0)(wt)


def _write(files: dict[str, str]):
    def step(wt):
        for rel, text in files.items():
            (wt / rel).write_text(text)
        return WorkerResult(True, "ok", wrote=list(files))
    return step


def _run(m, r, worker):
    # A command metric reports no failing test ids, so the step is routed by hand, as the
    # other loop tests do; the real mission's junit metric routes it the same way.
    return MissionRun(m, r, worker=worker, log=lambda s: None,
                      route_fn=lambda mi, last, att: Route(mi.steps[0], "first"),
                      profile_fn=lambda: Profile(device="cpu", houdini="running")).run()


ONLY_A = {"plexus/a.py": "A = 1\n"}
BOTH = {"plexus/a.py": "A = 1\n", "plexus/b.py": "B = 2\n"}


def test_a_reply_that_leaves_out_a_step_file_never_reaches_the_gates(tmp_path):
    r = _repo(tmp_path)
    w = Steps(_write(ONLY_A), _write(BOTH))
    a, b = _run(_mission(FILES), r, w).attempts
    # b.py exists at the base, so the missing-files list is empty: only the sent list tells
    assert a.reason == f"{LEFT_OUT}: plexus/b.py" and a.missing == []
    assert a.gates == [] and a.metric is None and a.failed_gate == ""
    assert a.handed_on == ["plexus/a.py"]
    # the next attempt sent both, so it was built and measured as before
    assert [g["name"] for g in b.gates] == ["core"] and b.metric is not None


def test_the_next_prompt_names_what_was_left_out_and_never_says_it_passed(tmp_path):
    r = _repo(tmp_path)
    w = Steps(_write(ONLY_A), _write(BOTH))
    _run(_mission(FILES), r, w)
    second = w.prompts[1]
    assert "## Why the last attempt was dropped" in second and f"{LEFT_OUT}: plexus/b.py" in second
    assert "## Your last attempt's files" in second and "A = 1" in second
    assert "left out plexus/b.py, so nothing it sent was built or tested" in second
    assert "together with every file still missing: plexus/b.py." in second
    assert "passed every gate" not in second


def test_a_complete_reply_is_built_and_can_be_kept(tmp_path):
    r = _repo(tmp_path)
    w = Steps(_write({**BOTH, "plexus/score.txt": "4\n"}))
    (a,) = _run(_mission(FILES, attempts=1), r, w).attempts
    assert a.kept and [g["name"] for g in a.gates] == ["core"]


def test_a_step_that_names_no_files_is_not_checked(tmp_path):
    r = _repo(tmp_path)
    w = Steps(_write({"plexus/score.txt": "4\n"}))
    (a,) = _run(_mission(None, attempts=1), r, w).attempts
    assert a.kept and not a.reason.startswith(LEFT_OUT)


def test_consecutive_left_out_drops_keep_the_last_full_attempt_in_view(tmp_path):
    # Run 18 attempts 1 and 2: after a left-out drop the worker edits its last draft, so each
    # reply sent one file and saw only that file handed back, and the T5 failure the full
    # attempt had vanished from the prompt. Now the prompt carries the union and the failure.
    r = _repo(tmp_path)
    w = Steps(_write(BOTH), _write({"plexus/a.py": "A = 2\n"}), _write({"plexus/b.py": "B = 3\n"}), _write(BOTH))
    a1, a2, a3, a4 = _run(_mission(FILES, attempts=4), r, w).attempts
    assert a1.reason.startswith("no strict gain") and a1.handed_on == FILES
    assert a2.reason == f"{LEFT_OUT}: plexus/b.py" and a2.handed_on == FILES  # b.py carried from attempt 1
    assert a3.reason == f"{LEFT_OUT}: plexus/a.py" and a3.handed_on == FILES  # a.py carried from attempt 2
    third, fourth = w.prompts[2], w.prompts[3]
    assert "A = 2" in third and "B = 2" in third  # attempt 2's a.py over attempt 1's b.py
    assert "sent only plexus/a.py and left out plexus/b.py" in third
    assert "The other files below (plexus/b.py) are your last full attempt's versions." in third
    assert "## Your last full attempt (1) was dropped: no strict gain (5 vs best 5)" in third
    assert "A = 2" in fourth and "B = 3" in fourth  # the union keeps composing
    assert "## Your last full attempt (1) was dropped" in fourth  # still attempt 1: 2 and 3 ran nothing


def test_a_keep_draws_the_line_for_what_a_left_out_drop_carries_and_shows(tmp_path):
    # Full drop, then a keep, then a one-file reply: nothing was carried for the keep, so the
    # left-out drop hands on its own file only, and the pre-keep failure is not "still the
    # thing to fix" (reviewer, 28f1d16).
    r = _repo(tmp_path)
    w = Steps(_write(BOTH), _write({**BOTH, "plexus/score.txt": "4\n"}), _write({"plexus/a.py": "A = 5\n"}), _write(BOTH))
    a1, a2, a3, _a4 = _run(_mission(FILES, attempts=4), r, w).attempts
    assert a1.reason.startswith("no strict gain") and a2.kept
    assert a3.reason == f"{LEFT_OUT}: plexus/b.py" and a3.handed_on == ["plexus/a.py"]
    fourth = w.prompts[3]  # the prompt after the left-out drop
    assert "A = 5" in fourth and "together with every file still missing: plexus/b.py." in fourth
    assert "## Your last full attempt" not in fourth  # attempt 1's failure sits before the keep


def test_left_out_helpers():
    s = Step("S3", ["t.py"], "x", files=["crates/a.rs", "crates/lib.rs", "plexus/p.py"])
    assert left_out(s, ["crates/a.rs"]) == ["crates/lib.rs", "plexus/p.py"]
    assert left_out(s, ["plexus/p.py", "crates/lib.rs", "crates/a.rs"]) == []
    assert left_out(None, []) == []
    assert left_out_of(f"{LEFT_OUT}: crates/lib.rs, plexus/p.py") == ["crates/lib.rs", "plexus/p.py"]
    for other in ("gate 'core' failed", "no strict gain (9 vs best 9)", "worker: ollama call failed: x: y"):
        assert left_out_of(other) == []
