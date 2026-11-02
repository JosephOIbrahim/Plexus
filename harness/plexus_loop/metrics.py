"""The number that decides whether an attempt is kept, and the gates around it."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .mission import Gate, Metric
from .profile import Profile

TAIL_CHARS = 4000


@dataclass
class MetricResult:
    value: float | None
    total: int | None = None  # tests collected, for pytest_failures
    tail: str = ""
    error: str = ""
    failing: list[str] = field(default_factory=list)  # junit "classname::name" of every bad test


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


def run_gate(gate: Gate, worktree: Path, profile: Profile) -> GateResult:
    try:
        r = subprocess.run(
            gate.cmd, cwd=worktree, env=profile.environ(), capture_output=True, text=True,
            timeout=gate.timeout_s, check=False)
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
    """Count tests under the target that did not pass.

    Failures, errors and skips all count, so a change can't score by skipping
    a test. A run that collects nothing is an error, never a score of zero.
    """
    with tempfile.TemporaryDirectory() as d:
        junit = Path(d) / "junit.xml"
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
               metric.target, f"--junitxml={junit}"]
        try:
            r = subprocess.run(cmd, cwd=worktree, env=profile.environ(), capture_output=True,
                               text=True, timeout=metric.timeout_s, check=False)
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
    total = bad = 0
    failing: list[str] = []
    for s in suites:
        total += int(s.get("tests", 0))
        bad += int(s.get("failures", 0)) + int(s.get("errors", 0)) + int(s.get("skipped", 0))
        for case in s.iter("testcase"):
            if any(child.tag in ("failure", "error", "skipped") for child in case):
                failing.append(f"{case.get('classname', '')}::{case.get('name', '')}")
    if total == 0:
        return MetricResult(None, total=0, tail=tail, error="no tests collected")
    return MetricResult(float(bad), total=total, tail=tail, failing=failing)


def _command(metric: Metric, worktree: Path, profile: Profile) -> MetricResult:
    """Run the mission's command and read a number from its last output line."""
    try:
        r = subprocess.run(metric.cmd, cwd=worktree, env=profile.environ(), capture_output=True,
                           text=True, timeout=metric.timeout_s, check=False)
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
