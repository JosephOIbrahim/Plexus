"""A dropped attempt's syntax errors sit above its output in the next prompt: file, line, reason, source line.

Run 4 attempt 1 wrote ``from_<id> = ...`` in a module. The layers guard crashed parsing it,
and the SyntaxError itself sat in the part of the gate output the prompt leaves out.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from harness.plexus_loop import MissionRun
from harness.plexus_loop.loop import SYNTAX_LINE_CHARS, SYNTAX_MAX, Attempt, build_prompt, syntax_errors
from harness.plexus_loop.mission import mission_from_dict
from harness.plexus_loop.profile import Profile
from harness.plexus_loop.workers import WorkerResult

PY = sys.executable
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
BAD = 'import os\n\nfrom_<id> = f"from_{participant_id}.usda"\n'


def test_reports_file_line_reason_and_source(tmp_path):
    (tmp_path / "plexus").mkdir()
    (tmp_path / "plexus" / "exchange.py").write_text(BAD, encoding="utf-8")
    (tmp_path / "plexus" / "ok.py").write_text("x = 1\n", encoding="utf-8")
    out = syntax_errors(tmp_path, ["plexus/exchange.py", "plexus/ok.py"])
    assert len(out) == 1
    assert out[0].startswith("plexus/exchange.py:3: invalid syntax")
    assert 'from_<id> = f"from_{participant_id}.usda"' in out[0]


def test_skips_non_python_missing_and_deleted_files(tmp_path):
    (tmp_path / "a.rs").write_text("fn main( {", encoding="utf-8")
    assert syntax_errors(tmp_path, ["a.rs", "gone.py", "plexus/"]) == []


def test_catches_indentation_null_bytes_and_bad_encoding(tmp_path):
    (tmp_path / "indent.py").write_text("def f():\nreturn 1\n", encoding="utf-8")
    (tmp_path / "nul.py").write_bytes(b"x = 1\x00\n")
    (tmp_path / "enc.py").write_bytes(b"s = '\xff\xfe'\n")
    (tmp_path / "outside.py").write_text("return 1\n", encoding="utf-8")  # compile-stage error
    out = syntax_errors(tmp_path, ["indent.py", "nul.py", "enc.py", "outside.py"])
    assert [o.split(":", 1)[0] for o in out] == ["indent.py", "nul.py", "enc.py", "outside.py"]


def test_warnings_are_not_errors_and_code_never_runs(tmp_path):
    marker = tmp_path / "ran"
    (tmp_path / "w.py").write_text(
        f"import pathlib\npathlib.Path({str(marker)!r}).write_text('x')\ns = '\\d'\n", encoding="utf-8")
    assert syntax_errors(tmp_path, ["w.py"]) == []
    assert not marker.exists()


def test_degenerate_files_are_reported_not_raised(tmp_path):
    # A model stuck repeating a token: the compiler raises MemoryError or RecursionError,
    # which must cost the attempt a line of feedback, never end the run.
    (tmp_path / "deep.py").write_text("x = " + "1+" * 30000 + "1\n", encoding="utf-8")
    (tmp_path / "neg.py").write_text("x = " + "-" * 10000 + "1\n", encoding="utf-8")
    (tmp_path / "attr.py").write_text("x = a" + ".b" * 30000 + "\n", encoding="utf-8")
    out = syntax_errors(tmp_path, ["deep.py", "neg.py", "attr.py"])
    assert [o.split(":", 1)[0] for o in out] == ["deep.py", "neg.py", "attr.py"]
    assert all("\n" not in o and len(o) <= SYNTAX_LINE_CHARS for o in out)


def test_syntax_only_feedback_points_at_the_files(tmp_path):
    a = Attempt(n=1, started=0.0, houdini="off", device="gpu", reason="gate 'layers' failed",
                syntax=["plexus/a.py:1: invalid syntax"])
    p = build_prompt(_mission(), _repo(tmp_path), 5, None, [a], 100000)
    assert "Fix those files first." in p and "near the top of that output" not in p


def test_long_source_lines_are_clipped(tmp_path):
    (tmp_path / "long.py").write_text("x = (" + "1 + " * 200 + "\n", encoding="utf-8")
    (out,) = syntax_errors(tmp_path, ["long.py"])
    assert len(out) <= SYNTAX_LINE_CHARS


def _mission():
    return mission_from_dict({
        "mission": {"name": "demo", "goal": "g", "requires": ["tests/acceptance"], "focus": ["plexus/**"],
                    "frozen": ["tests/acceptance/**"]},
        "metric": {"kind": "command", "cmd": [PY, "-c", "print(5)"]},
        "gates": [{"name": "layers", "cmd": [PY, "-c", "print('ok')"]}],
        "budget": {"attempts": 3, "hours": 1, "max_consecutive_failures": 5},
    })


def test_prompt_puts_syntax_errors_above_the_gate_output(tmp_path):
    long_output = "$ python -m pytest\n" + "traceback line\n" * 2000 + "4 failed"
    a = Attempt(n=1, started=0.0, houdini="running", device="cpu", reason="gate 'layers' failed",
                route="S2 via jev 0.98", detail=long_output,
                syntax=["plexus/membrane/exchange.py:34: invalid syntax: from_<id> = ..."])
    p = build_prompt(_mission(), _repo(tmp_path), 5, None, [a], 100000)
    section = p.split("## Why the last attempt was dropped", 1)[1]
    assert section.index("exchange.py:34: invalid syntax") < section.index("This is what it printed:")
    assert "4 failed" in section  # the clipped gate output still follows


def test_prompt_shows_syntax_even_without_gate_output_and_caps_the_list(tmp_path):
    errs = [f"plexus/m{i}.py:1: invalid syntax" for i in range(SYNTAX_MAX + 3)]
    a = Attempt(n=2, started=0.0, houdini="off", device="gpu", reason="no strict gain (5 vs best 5)",
                syntax=errs)
    p = build_prompt(_mission(), _repo(tmp_path), 5, None, [a], 100000)
    assert f"plexus/m{SYNTAX_MAX - 1}.py:1" in p and f"plexus/m{SYNTAX_MAX}.py:1" not in p
    assert "(and 3 more)" in p
    assert "This is what it printed:" not in p


def _repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    (r / "plexus").mkdir(parents=True)
    (r / "tests" / "acceptance").mkdir(parents=True)
    (r / "tests" / "acceptance" / "f.txt").write_text("x")
    (r / "plexus" / "score.txt").write_text("5\n")
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


def test_run_records_syntax_errors_and_the_next_prompt_shows_them(tmp_path):
    r = _repo(tmp_path)
    # The gate parses every plexus .py file, as the layers guard does, and fails on a bad one.
    gate = [PY, "-c", "import ast,pathlib,sys\n"
            "try:\n [ast.parse(p.read_text()) for p in pathlib.Path('plexus').rglob('*.py')]\n"
            "except SyntaxError: print('parse failed'); sys.exit(1)"]
    m = mission_from_dict({
        "mission": {"name": "demo", "goal": "g", "requires": ["tests/acceptance"], "focus": ["plexus/**"],
                    "frozen": ["tests/acceptance/**"]},
        "metric": {"kind": "command", "cmd": [PY, "-c", "print(open('plexus/score.txt').read().strip())"]},
        "gates": [{"name": "layers", "cmd": gate}],
        "budget": {"attempts": 2, "hours": 1, "max_consecutive_failures": 5},
    })
    w = Steps(lambda wt: (wt / "plexus" / "exchange.py").write_text(BAD, encoding="utf-8"),
              lambda wt: (wt / "plexus" / "score.txt").write_text("4\n"))
    report = MissionRun(m, r, worker=w, log=lambda s: None,
                        profile_fn=lambda: Profile(device="cpu", houdini="running")).run()
    first, second = report.attempts
    assert not first.kept and first.reason == "gate 'layers' failed"
    assert first.syntax and first.syntax[0].startswith("plexus/exchange.py:3: invalid syntax")
    assert second.kept and second.syntax == []
    assert "plexus/exchange.py:3: invalid syntax" in w.prompts[1]
    line = (r / ".plexus_loop" / "demo" / "attempts.jsonl").read_text(encoding="utf-8").splitlines()[0]
    assert json.loads(line)["syntax"] == first.syntax
