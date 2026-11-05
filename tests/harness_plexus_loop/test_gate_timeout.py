"""A gate or metric that hangs costs its attempt: the timeout holds, and what it started does not stay behind."""

from __future__ import annotations

import subprocess
import sys
import time

import pytest

from harness.plexus_loop import metrics
from harness.plexus_loop.loop import _pid_alive
from harness.plexus_loop.metrics import GateResult, measure, run_gate
from harness.plexus_loop.mission import Gate, Metric
from harness.plexus_loop.profile import Profile

PY = sys.executable
CPU = Profile(device="cpu", houdini="running")


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="taskkill and the wait with no limit are Windows only")
def test_a_gate_timeout_holds_against_a_grandchild_and_leaves_nothing_behind(tmp_path):
    # The unit gate runs with -x beside a loaded CPU, and a flake there throws away an attempt, so the limits are wide on
    # purpose: 2 + 10 + 10 s is the worst the timeout path can take, the grandchild's 60 s is what a wait with no limit
    # takes, and a child too slow to write the pid file before the timeout must not fail the test.
    code = ("import pathlib, subprocess, sys\n"
            "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            "pathlib.Path('grandchild.pid').write_text(str(p.pid))\n"
            "p.wait()\n")
    t0 = time.monotonic()
    res = run_gate(Gate("hang", [PY, "-c", code], timeout_s=2), tmp_path, CPU)
    took = time.monotonic() - t0
    assert res == GateResult("hang", False, "timed out")
    assert took < 30
    pid_file = tmp_path / "grandchild.pid"
    pid = pid_file.read_text() if pid_file.exists() else ""  # empty when the kill landed between open and write
    if pid:
        deadline = time.monotonic() + 10
        while (alive := _pid_alive(int(pid))) is True and time.monotonic() < deadline:
            time.sleep(0.2)
        assert alive is not True


def test_a_gate_or_metric_that_hangs_or_cannot_start_returns_a_failure(tmp_path, monkeypatch):
    # _run catches only GitError, OSError and UnicodeError, and the baseline catches nothing, so a raise here ends the run with no row.
    res = run_gate(Gate("g", ["no-such-program-plexus"]), tmp_path, CPU)
    assert not res.passed and "could not start" in res.tail

    def hangs(*a, **kw):
        raise subprocess.TimeoutExpired("x", 1)

    monkeypatch.setattr(metrics, "_run_bounded", hangs)
    assert run_gate(Gate("g", ["x"]), tmp_path, CPU) == GateResult("g", False, "timed out")
    tests = measure(Metric(kind="pytest_failures", target="t"), tmp_path, CPU)
    assert tests.value is None and tests.error == "metric run timed out"
    command = measure(Metric(kind="command", cmd=["x"]), tmp_path, CPU)
    assert command.value is None and command.error == "metric command timed out"
