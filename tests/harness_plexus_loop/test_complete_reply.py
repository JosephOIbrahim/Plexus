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
STUB = "B = 0  # a stub at the base, like lib.rs in run 12\n"


def _repo(tmp_path: Path, both_tracked: bool = False) -> Path:
    r = tmp_path / "repo"
    (r / "plexus").mkdir(parents=True)
    (r / "tests" / "acceptance").mkdir(parents=True)
    (r / "tests" / "acceptance" / "f.txt").write_text("x")
    (r / "plexus" / "score.txt").write_text("5\n")
    (r / "plexus" / "b.py").write_text(STUB)
    if both_tracked:  # S7's shape: every step file already at the tip (lib.rs and py.rs)
        (r / "plexus" / "a.py").write_text("A = 0\n")
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
    assert "together with every file it left out: plexus/b.py." in second
    assert "passed every gate" not in second
    # a.py is absent after the drop, and the list must not call a left-out reply's files "gone"
    assert "Its files are gone" not in second and "- plexus/a.py" in second
    assert "Every attempt starts from the last kept commit" in second  # the lead word after a left-out drop


def test_a_complete_reply_is_built_and_can_be_kept(tmp_path):
    r = _repo(tmp_path)
    w = Steps(_write({**BOTH, "plexus/score.txt": "4\n"}))
    (a,) = _run(_mission(FILES, attempts=1), r, w).attempts
    assert a.kept and [g["name"] for g in a.gates] == ["core"]


def test_a_left_out_reply_still_has_its_python_compile_checked(tmp_path):
    # compile() is not a build: a .py the dropped reply sent is named now, not handed back
    # verbatim and caught by a gate one attempt later.
    r = _repo(tmp_path)
    w = Steps(_write({"plexus/a.py": "A = (\n"}), _write(BOTH))
    a, _ = _run(_mission(FILES), r, w).attempts
    assert a.reason == f"{LEFT_OUT}: plexus/b.py" and a.gates == []
    assert len(a.syntax) == 1 and a.syntax[0].startswith("plexus/a.py:1:")
    second = w.prompts[1]
    assert "Python could not compile these files" in second and "Fix those files first." in second
    # handed on all the same, so the fix is one edit away (the syntax line quotes "A = (" too,
    # so only the whole-file block shows the file itself came along)
    assert a.handed_on == ["plexus/a.py"] and "file:plexus/a.py\nA = (\n" in second


def test_a_left_out_drop_is_explained_even_when_every_step_file_is_at_the_tip(tmp_path):
    # Nothing absent, no gate output, no syntax error: the reason alone must open the section.
    r = _repo(tmp_path, both_tracked=True)
    w = Steps(_write(ONLY_A), _write(BOTH))
    a, _ = _run(_mission(FILES), r, w).attempts
    assert a.reason == f"{LEFT_OUT}: plexus/b.py" and a.missing == [] and a.syntax == [] and a.detail == ""
    second = w.prompts[1]
    assert "## Why the last attempt was dropped" in second
    assert f"was dropped: {LEFT_OUT}: plexus/b.py." in second
    assert "needs these files" not in second  # nothing is absent, so there is no list to show


def test_a_file_resent_as_it_is_counts_as_sent(tmp_path):
    # The step section promises "including any you leave as it is": git sees no change in a
    # byte-identical b.py, so only the worker's own `wrote` list says the reply carried it.
    r = _repo(tmp_path)
    w = Steps(_write({"plexus/a.py": "A = 1\n", "plexus/b.py": STUB}))
    (a,) = _run(_mission(FILES, attempts=1), r, w).attempts
    assert not a.reason.startswith(LEFT_OUT) and [g["name"] for g in a.gates] == ["core"]
    assert a.changed == FILES and a.handed_on == FILES


def test_a_step_that_names_no_files_is_not_checked(tmp_path):
    r = _repo(tmp_path)
    w = Steps(_write({"plexus/score.txt": "4\n"}))
    (a,) = _run(_mission(None, attempts=1), r, w).attempts
    assert a.kept and not a.reason.startswith(LEFT_OUT)


def test_left_out_helpers():
    s = Step("S3", ["t.py"], "x", files=["crates/a.rs", "crates/lib.rs", "plexus/p.py"])
    assert left_out(s, ["crates/a.rs"]) == ["crates/lib.rs", "plexus/p.py"]
    assert left_out(s, ["plexus/p.py", "crates/lib.rs", "crates/a.rs"]) == []
    assert left_out(None, []) == []
    assert left_out_of(f"{LEFT_OUT}: crates/lib.rs, plexus/p.py") == ["crates/lib.rs", "plexus/p.py"]
    for other in ("gate 'core' failed", "no strict gain (9 vs best 9)", "worker: ollama call failed: x: y"):
        assert left_out_of(other) == []
