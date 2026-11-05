"""A dropped attempt's feedback leads with its own step's target-test failures.

Run 5 attempt 4 sent every S2 file. T1, S2's target, then failed on one line in axon.py
(`Tf.Notice.ObjectsChanged` does not exist), but the feedback showed the end of the whole test
run: with ten tests failing, that was T6's failure, a later step's test, and T1's error sat in
the part left out. The junit report already holds each test's own failure.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from harness.plexus_loop import MissionRun
from harness.plexus_loop.loop import TARGET_FAILURES_MAX, Attempt, build_prompt, target_failures
from harness.plexus_loop.metrics import TEST_MESSAGE_CHARS, MetricResult, measure
from harness.plexus_loop.mission import Metric, Step, mission_from_dict
from harness.plexus_loop.profile import Profile
from harness.plexus_loop.router import Route, failing_targets
from harness.plexus_loop.workers import WorkerResult

PY = sys.executable
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
PROFILE = Profile(device="cpu", houdini="running")

# Target test (step S1) fails early with a distinctive error; a later step's test fails last,
# with a long traceback, so the end of the run's output is about it, not the target.
T_TARGET = '''
def test_target():
    import plexus.core as c
    c.Notice.ObjectsChanged
'''
T_LATER = '''
import pytest

@pytest.mark.parametrize("i", range(30))
def test_later(i):
    raise RuntimeError("LATER-STEP-NOISE " + "x" * 200)
'''


def _repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    (r / "plexus" / "core").mkdir(parents=True)
    (r / "plexus" / "__init__.py").write_text("")
    (r / "plexus" / "core" / "__init__.py").write_text("class Notice:\n    pass\n")
    t = r / "tests" / "acceptance" / "phase1"
    t.mkdir(parents=True)
    (r / "tests" / "__init__.py").write_text("")
    (r / "tests" / "acceptance" / "__init__.py").write_text("")
    (t / "__init__.py").write_text("")
    (t / "test_t1_target.py").write_text(T_TARGET)
    (t / "test_t9_later.py").write_text(T_LATER)
    for args in (["init", "-q", "-b", "master"], ["add", "-A"], ["commit", "-q", "-m", "s"]):
        subprocess.run([*GIT, *args], cwd=r, check=True, capture_output=True)
    return r


STEP = Step("S1", ["tests/acceptance/phase1/test_t1_target.py"], "Fix the target.", files=["plexus/core/__init__.py"])


# -- the metric keeps each test's own failure -------------------------------------

def test_metric_records_each_failing_tests_own_message(tmp_path):
    r = _repo(tmp_path)
    m = measure(Metric(kind="pytest_failures", target="tests/acceptance/phase1"), r, PROFILE)
    assert m.value == 31 and len(m.failing) == 31
    (tid,) = [f for f in m.failing if "test_t1_target" in f]
    msg = m.messages[tid]
    assert "AttributeError" in msg and "ObjectsChanged" in msg
    assert "LATER-STEP-NOISE" not in msg
    assert all(len(v) <= TEST_MESSAGE_CHARS for v in m.messages.values())
    assert "test_t1_target" not in m.tail[-300:]  # the end of the run is about the later tests


T_TEARDOWN = '''
import pytest

@pytest.fixture
def rt():
    yield 1
    raise ValueError("TEARDOWN-BOOM")

def test_call_and_teardown(rt):
    raise AttributeError("CALL-FAIL-FIRST")

def test_long_traceback():
    raise AssertionError("LONG-" + "y" * 5000 + "-END")
'''


def test_teardown_error_keeps_the_tests_own_failure_first_and_is_picked_once(tmp_path):
    r = _repo(tmp_path)
    (r / "tests" / "acceptance" / "phase1" / "test_t1_target.py").write_text(T_TEARDOWN)
    m = measure(Metric(kind="pytest_failures", target="tests/acceptance/phase1/test_t1_target.py"), r, PROFILE)
    (tid,) = {f for f in m.failing if f.endswith("::test_call_and_teardown")}
    assert m.failing.count(tid) == 2  # pytest's report repeats the id
    msg = m.messages[tid]
    assert "CALL-FAIL-FIRST" in msg and msg.index("CALL-FAIL-FIRST") < msg.index("TEARDOWN-BOOM")
    long_id = next(f for f in m.failing if f.endswith("::test_long_traceback"))
    assert "-END" in m.messages[long_id]  # a long traceback keeps its end, where the error is
    assert all(len(v) <= TEST_MESSAGE_CHARS for v in m.messages.values())
    picked = target_failures(m, STEP)
    assert [p.split("\n", 1)[0] for p in picked].count(tid) == 1
    # The score adds junit's failures and errors, so the test that fails both ways counts twice: 2 tests score 3.
    assert m.total == 2 and m.value == 3


# -- matching and selection --------------------------------------------------------

def test_failing_targets_matches_files_tests_and_parameters_in_report_order():
    failing = ["tests.acceptance.phase1.test_t9_later::test_later[0]",
               "tests.acceptance.phase1.test_t1_target::test_target",
               "tests.acceptance.phase1.test_t1_targetX::test_other",
               "tests.acceptance.phase1.test_t2::test_x[a-b]"]
    s = Step("S", ["tests/acceptance/phase1/test_t1_target.py", "tests/acceptance/phase1/test_t2.py::test_x"], "x")
    assert failing_targets(s, failing) == ["tests.acceptance.phase1.test_t1_target::test_target",
                                           "tests.acceptance.phase1.test_t2::test_x[a-b]"]
    assert failing_targets(s, failing + failing) == failing_targets(s, failing)  # once each


def test_target_failures_caps_the_count_and_marks_a_missing_message():
    ids = [f"tests.acceptance.phase1.test_t1_target::test_{i}" for i in range(TARGET_FAILURES_MAX + 2)]
    m = MetricResult(5.0, failing=ids, messages={ids[0]: "[failure] boom"})
    out = target_failures(m, STEP)
    assert len(out) == TARGET_FAILURES_MAX
    assert out[0] == f"{ids[0]}\n[failure] boom"
    assert out[1].endswith("(no message in the report)")
    assert target_failures(MetricResult(5.0, failing=["tests.other::t"], messages={}), STEP) == []


# -- the prompt --------------------------------------------------------------------

def _mission():
    return mission_from_dict({
        "mission": {"name": "demo", "goal": "g", "requires": ["tests/acceptance"], "focus": ["plexus/**"],
                    "frozen": ["tests/acceptance/**"]},
        "metric": {"kind": "pytest_failures", "target": "tests/acceptance/phase1"},
        "gates": [{"name": "ok", "cmd": [PY, "-c", "print('ok')"]}],
        "steps": [{"id": "S1", "targets": STEP.targets, "text": STEP.text, "files": STEP.files}],
        "router": {"kind": "first"},
        "budget": {"attempts": 2, "hours": 1, "max_consecutive_failures": 5},
    })


def _feedback(p):
    return p.split("## Why the last attempt was dropped", 1)[1].split("## Where it stands", 1)[0]


def test_target_failures_lead_the_feedback(tmp_path):
    m = _mission()
    a = Attempt(n=1, started=0.0, houdini="off", device="gpu", reason="no strict gain (31 vs best 31)",
                route="S1 via first", detail="...LATER-STEP-NOISE...\n31 failed",
                syntax=["plexus/x.py:1: invalid syntax"],
                target_failures=["tests.acceptance.phase1.test_t1_target::test_target\n[failure] AttributeError: ObjectsChanged"])
    fb = _feedback(build_prompt(m, _repo(tmp_path), 31, None, [a], 100000, step=m.steps[0]))
    assert fb.index("ObjectsChanged") < fb.index("invalid syntax") < fb.index("LATER-STEP-NOISE")
    assert "own target tests failed" in fb


def test_target_failures_alone_open_the_section_and_fence_safely(tmp_path):
    m = _mission()
    a = Attempt(n=1, started=0.0, houdini="off", device="gpu", reason="metric unavailable: x",
                target_failures=["t::x\n[failure] a ``` b ```` c"])
    fb = _feedback(build_prompt(m, _repo(tmp_path), 31, None, [a], 100000, step=m.steps[0]))
    assert "`````" in fb  # fence longer than the longest backtick run inside


# -- a whole run --------------------------------------------------------------------

class Steps:
    def __init__(self, *steps):
        self.steps, self.prompts = list(steps), []

    def attempt(self, wt, prompt, profile):
        self.prompts.append(prompt)
        self.steps.pop(0)(wt)
        return WorkerResult(True, "ok")


def test_run_leads_the_next_prompt_with_the_target_failure(tmp_path):
    r = _repo(tmp_path)
    touch = lambda wt: (wt / "plexus" / "core" / "__init__.py").write_text("class Notice:\n    x = 1\n")  # noqa: E731
    w = Steps(touch, touch)
    report = MissionRun(_mission(), r, worker=w, log=lambda s: None,
                        route_fn=lambda mi, last, att: Route(mi.steps[0], "first"),
                        profile_fn=lambda: PROFILE).run()
    first = report.attempts[0]
    assert not first.kept and first.target_failures
    assert "ObjectsChanged" in first.target_failures[0]
    fb = _feedback(w.prompts[1])
    assert fb.index("ObjectsChanged") < fb.index("This is what it printed:")
