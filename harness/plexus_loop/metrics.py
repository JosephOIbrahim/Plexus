"""The number that decides whether an attempt is kept, and the gates around it."""

from __future__ import annotations

import contextlib
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .mission import Gate, Metric
from .profile import Profile

TAIL_CHARS = 4000
TEST_MESSAGE_CHARS = 1500  # one test's own failure, as the next prompt shows it
KILL_DRAIN_S = 10  # after a timeout: the limit on taskkill, then on the wait for the pipes


@dataclass
class MetricResult:
    value: float | None
    total: int | None = None  # tests collected, for pytest_failures
    tail: str = ""
    error: str = ""
    failing: list[str] = field(default_factory=list)  # junit "classname::name" of every bad test
    # junit id -> that test's own failure: the report's message line, then the end of its
    # traceback (where pytest puts the "E" lines and the file:line). Clipped per test.
    messages: dict[str, str] = field(default_factory=dict)


@dataclass
class GateResult:
    name: str
    passed: bool
    tail: str = ""


def _tail(*texts: str) -> str:
    return "\n".join(t for t in texts if t)[-TAIL_CHARS:]


GATE_HEAD_CHARS = 1500
GATE_TAIL_CHARS = 2500


def _clip(*texts: str) -> str:
    """A gate's output with both ends kept: compilers print the first error early, and test
    runners print their summary last."""
    text = "\n".join(t for t in texts if t)
    if len(text) <= GATE_HEAD_CHARS + GATE_TAIL_CHARS:
        return text
    return text[:GATE_HEAD_CHARS] + "\n[... middle of the output left out ...]\n" + text[-GATE_TAIL_CHARS:]


def _run_bounded(cmd: list[str], worktree: Path, profile: Profile,
                 timeout: float) -> subprocess.CompletedProcess:
    """subprocess.run with a timeout that holds on Windows, raising TimeoutExpired as it does.

    There subprocess.run kills only the direct child and then waits with no limit for the pipes,
    and a grandchild holds them (cargo under build_core.py, a test binary under cargo), so a stuck
    one never returns, past every budget and the stop file. So the whole tree goes first, and the
    wait for the pipes has a limit in case something left the tree. No ``with``: its exit closes a
    pipe a grandchild still holds, and that blocks until the grandchild exits.
    """
    # errors="replace": a byte the locale cannot decode (rustc echoing a worker's '”' or '←')
    # costs a replacement character (plus mojibake for that character's other bytes), never
    # the stream. Without it the reader thread dies and the output comes back None, so the
    # next prompt would show nothing of the error.
    p = subprocess.Popen(cmd, cwd=worktree, env=profile.environ(), stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, errors="replace")
    try:
        out, err = p.communicate(timeout=timeout)
    except BaseException:  # a timeout or Ctrl-C: subprocess.run also kills on any exception
        if sys.platform.startswith("win"):
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True,
                               timeout=KILL_DRAIN_S, check=False)
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            p.kill()
            p.communicate(timeout=KILL_DRAIN_S)
        raise
    return subprocess.CompletedProcess(cmd, p.returncode, out, err)


def run_gate(gate: Gate, worktree: Path, profile: Profile) -> GateResult:
    try:
        r = _run_bounded(gate.cmd, worktree, profile, gate.timeout_s)
    except subprocess.TimeoutExpired:
        return GateResult(gate.name, False, "timed out")
    except OSError as e:
        return GateResult(gate.name, False, f"could not start: {e}")
    return GateResult(gate.name, r.returncode == 0, _clip(r.stdout, r.stderr))


def measure(metric: Metric, worktree: Path, profile: Profile) -> MetricResult:
    if metric.kind == "pytest_failures":
        return _pytest_failures(metric, worktree, profile)
    return _command(metric, worktree, profile)


def _pytest_failures(metric: Metric, worktree: Path, profile: Profile) -> MetricResult:
    """Count what did not pass under the target, from the report's own totals.

    Failures, errors and skips all count, so a change can't score by skipping a test. The value counts
    report entries, not tests: a test that fails and then errors in teardown adds two, so it can pass
    ``total``. ``total`` counts test ids and not the report's own ``tests``, which adds a passing test
    with a teardown error twice, so the attempt that fixes that error would read as a test gone missing.
    A run that collects nothing is an error, never a score of zero.
    """
    with tempfile.TemporaryDirectory() as d:
        junit = Path(d) / "junit.xml"
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
               metric.target, f"--junitxml={junit}"]
        try:
            r = _run_bounded(cmd, worktree, profile, metric.timeout_s)
        except subprocess.TimeoutExpired:
            return MetricResult(None, error="metric run timed out")
        tail = _tail(r.stdout, r.stderr)
        if not junit.exists():
            return MetricResult(None, tail=tail, error="pytest wrote no report")
        try:
            root = ET.parse(junit).getroot()
        except ET.ParseError:
            return MetricResult(None, tail=tail, error="pytest report could not be read")
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    bad = 0
    tests: set[str] = set()
    failing: list[str] = []
    messages: dict[str, str] = {}
    for s in suites:
        bad += int(s.get("failures", 0)) + int(s.get("errors", 0)) + int(s.get("skipped", 0))
        for case in s.iter("testcase"):
            tid = f"{case.get('classname', '')}::{case.get('name', '')}"
            tests.add(tid)
            bad_children = [c for c in case if c.tag in ("failure", "error", "skipped")]
            if bad_children:
                failing.append(tid)
                # A test that fails and then errors in teardown appears twice under one id: keep
                # its own failure first and add the teardown after it, never replace it.
                text = "\n".join(_case_message(c) for c in bad_children)[-TEST_MESSAGE_CHARS:]
                if tid in messages:  # the first entry is whole (each is at most the cap); clip the rest
                    text = (messages[tid] + "\n" + text)[:TEST_MESSAGE_CHARS]
                messages[tid] = text
    if not tests:
        return MetricResult(None, total=0, tail=tail, error="no tests collected")
    return MetricResult(float(bad), total=len(tests), tail=tail, failing=failing, messages=messages)


def _case_message(el: ET.Element) -> str:
    """One junit failure, error or skip: its message line, then the end of its text."""
    msg = (el.get("message") or "").strip()
    text = (el.text or "").rstrip()
    body = text[-(TEST_MESSAGE_CHARS - min(len(msg), 300) - 20):] if text else ""
    head = f"[{el.tag}] {msg[:300]}" if msg else f"[{el.tag}]"
    return head + ("\n" + body if body else "")


def _command(metric: Metric, worktree: Path, profile: Profile) -> MetricResult:
    """Run the mission's command and read a number from its last output line."""
    try:
        r = _run_bounded(metric.cmd, worktree, profile, metric.timeout_s)
    except subprocess.TimeoutExpired:
        return MetricResult(None, error="metric command timed out")
    except OSError as e:
        return MetricResult(None, error=f"metric command could not start: {e}")
    tail = _tail(r.stdout, r.stderr)
    if r.returncode != 0:
        return MetricResult(None, tail=tail, error=f"metric command exited {r.returncode}")
    lines = [x.strip() for x in r.stdout.splitlines() if x.strip()]
    try:
        return MetricResult(float(lines[-1]), tail=tail)
    except (IndexError, ValueError):
        return MetricResult(None, tail=tail, error="metric command printed no number on its last line")
