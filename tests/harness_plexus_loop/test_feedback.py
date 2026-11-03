"""The next attempt sees why the last one was dropped: the failing gate's output, or the metric's."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from harness.plexus_loop import MissionRun
from harness.plexus_loop.metrics import _clip, measure
from harness.plexus_loop.mission import Metric, mission_from_dict
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
    # The files come first so Ollama can reuse their cached prefix; the drop follows them.
    assert second.index("## Files") < second.index("## Why the last attempt was dropped")


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


def test_a_gate_output_with_an_undecodable_byte_still_reaches_the_prompt(tmp_path):
    # One lone 0x9D is undecodable under cp1252 and UTF-8 alike. Without errors="replace" the
    # reader thread dies, stdout comes back None, and the whole output is lost, not one character.
    r = _repo(tmp_path)
    odd = [PY, "-c", "import os,sys; bad=os.path.exists('plexus/bad.txt'); "
           "sys.stdout.buffer.write(b'RULE: plexus.core must stay free of pxr\\n' + b'\\x9d\\n' "
           "if bad else b'ok\\n'); sys.exit(1 if bad else 0)"]
    m = mission_from_dict({
        "mission": {"name": "demo", "goal": "g", "requires": ["tests/acceptance"], "focus": ["plexus/**"],
                    "frozen": ["tests/acceptance/**"]},
        "metric": {"kind": "command", "cmd": [PY, "-c", "print(open('plexus/score.txt').read().strip())"]},
        "gates": [{"name": "core", "cmd": odd}],
        "budget": {"attempts": 2, "hours": 1, "max_consecutive_failures": 5},
    })
    w = Steps(_write("plexus/bad.txt", "x"), _write("plexus/score.txt", "4\n"))
    report = MissionRun(m, r, worker=w, log=lambda s: None,
                        profile_fn=lambda: Profile(device="cpu", houdini="running")).run()
    assert report.attempts[0].reason == "gate 'core' failed"
    section = w.prompts[1].split("## Why the last attempt was dropped", 1)[1]
    # The "$ cmd" line echoes the gate's own source, so only a newline-bounded RULE line is
    # the gate's output.
    assert "\nRULE: plexus.core must stay free of pxr\n" in section


def test_a_command_metric_output_with_an_undecodable_byte_still_scores(tmp_path):
    # The same lone 0x9D on the metric's own stdout. Without errors="replace" the reader thread
    # dies and r.stdout is None, so _command's splitlines() raised AttributeError out of
    # measure(): _run catches only GitError, OSError and UnicodeError, so one stray byte ended
    # the run, not the attempt (and the baseline evaluation catches nothing).
    odd = [PY, "-c", "import sys; sys.stdout.buffer.write(b'\\x9d\\n4\\n')"]
    res = measure(Metric(kind="command", cmd=odd), tmp_path,
                  Profile(device="cpu", houdini="running"))
    assert res.value == 4.0 and res.error == "" and "4" in res.tail


def test_a_pytest_metric_output_with_an_undecodable_byte_keeps_its_tail(tmp_path, monkeypatch):
    # The real mission's metric. The junit report still counted, but the tail, which is what
    # the next prompt's "Latest metric output" and Jev's latest_test_output_tail are, lost all
    # of stdout. A test's own output is fd-captured and re-encoded by pytest, so the byte is
    # written from the terminal-summary hook, where capture is suspended and fd 1 is the
    # harness's pipe. Auto-loaded plugins are kept out of the child: their stderr warnings
    # share the 4000-character tail with "1 passed".
    acc = tmp_path / "tests" / "acceptance"
    acc.mkdir(parents=True)
    (acc / "test_t.py").write_text("def test_a(): pass\n")
    (acc / "conftest.py").write_text("import os\n\n\ndef pytest_terminal_summary(terminalreporter):\n"
                                     "    os.write(1, b'\\x9d\\n')\n")
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    res = measure(Metric(kind="pytest_failures", target="tests/acceptance"), tmp_path,
                  Profile(device="cpu", houdini="running"))
    assert res.value == 0.0 and res.total == 1 and res.error == ""
    assert "1 passed" in res.tail


def test_a_changed_path_with_a_non_ascii_name_still_reaches_the_ledger(tmp_path):
    # git status -z prints paths as raw UTF-8. Under cp1252 the second byte of 'Á' (0x81) killed
    # subprocess's reader thread, gitops.git returned None and changed_paths raised out of _run,
    # which catches only GitError, OSError and UnicodeError: no row, REVIEW.md left running.
    # Under a UTF-8 locale this holds on its own; under cp1252 it exercises the decode.
    r = _repo(tmp_path)
    w = Steps(_write("plexus/Ávila.txt", "x"))
    (a,) = _run(r, w, attempts=1).attempts
    assert a.reason.startswith("no strict gain") and a.changed == ["plexus/Ávila.txt"]


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
