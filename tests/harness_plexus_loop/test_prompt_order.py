"""The part of the prompt that is the same on every attempt of a run comes first.

Ollama reuses the cached prefix of the previous prompt. Run 12 attempt 1 spent 709 of its
1,473 model seconds reading a 24,464-token prompt, and most of that prompt (the brief, the
contract, the frozen tests, the spec) is identical from attempt to attempt. So the header and
the context files lead, and the step, the last drop, handed-on files, the score and the metric
tail follow them.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from harness.plexus_loop.loop import Attempt, build_prompt
from harness.plexus_loop.mission import mission_from_dict
from harness.plexus_loop.workers import OLLAMA_KEEP_ALIVE, OllamaWorker
from harness.plexus_loop.mission import WorkerSpec
from harness.plexus_loop.profile import Profile

PY = sys.executable
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def _repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    (r / "docs").mkdir(parents=True)
    (r / "plexus").mkdir()
    (r / "tests" / "acceptance").mkdir(parents=True)
    (r / "tests" / "acceptance" / "f.txt").write_text("x")
    (r / "docs" / "brief.md").write_text("# Brief\n\n" + "A rule the worker reads every time.\n" * 40)
    (r / "plexus" / "kept.py").write_text("X = 1\n")
    for args in (["init", "-q", "-b", "master"], ["add", "-A"], ["commit", "-q", "-m", "s"]):
        subprocess.run([*GIT, *args], cwd=r, check=True, capture_output=True)
    return r


def _mission():
    return mission_from_dict({
        "mission": {"name": "demo", "goal": "g", "requires": ["tests/acceptance"], "focus": ["plexus/**"],
                    "frozen": ["tests/acceptance/**"], "context": ["docs/brief.md"]},
        "metric": {"kind": "command", "cmd": [PY, "-c", "print(5)"]},
        "gates": [{"name": "core", "cmd": [PY, "-c", "print('ok')"]}],
        "steps": [{"id": "S1", "targets": ["tests/acceptance/f.txt"], "text": "Do the first step."},
                  {"id": "S2", "targets": ["tests/acceptance/f.txt"], "text": "Do the second step."}],
        "router": {"kind": "first"},
    })


def _drop(n, reason, detail):
    return Attempt(n=n, started=0.0, houdini="off", device="cpu", reason=reason, route="S1 via first",
                   detail=detail)


def _files_end(p: str) -> int:
    """Where the context files stop: everything before this is the cacheable prefix."""
    return p.index("## This attempt")


def test_the_files_come_before_everything_that_changes_per_attempt(tmp_path):
    m, r = _mission(), _repo(tmp_path)
    p = build_prompt(m, r, 5, None, [_drop(1, "gate 'core' failed", "$ build\nerror: one")], 100000, step=m.steps[0])
    i_files = p.index("## Files")
    for later in ("## This attempt", "## Why the last attempt was dropped", "## Where it stands",
                  "## Recent attempts that were not kept", "## Your reply"):
        assert i_files < p.index(later), later
    assert p.index("file:docs/brief.md") < _files_end(p) and p.index("file:plexus/kept.py") < _files_end(p)


def test_two_attempts_share_their_prefix_up_to_the_step(tmp_path):
    m, r = _mission(), _repo(tmp_path)
    a = build_prompt(m, r, 5, None, [], 100000, step=m.steps[0])
    b = build_prompt(m, r, 4, None, [_drop(1, "gate 'core' failed", "$ build\nerror: two"),
                                      _drop(2, "no strict gain (5 vs best 5)", "tail")], 100000, step=m.steps[1])
    assert a[:_files_end(a)] == b[:_files_end(b)]
    assert _files_end(a) > 0.7 * len(a)  # the shared prefix is most of a first attempt's prompt


def test_the_budget_still_counts_the_parts_that_follow_the_files(tmp_path):
    m, r = _mission(), _repo(tmp_path)
    big = "$ build\n" + "error: noise\n" * 300
    p = build_prompt(m, r, 5, None, [_drop(1, "gate 'core' failed", big)], 4000, step=m.steps[0])
    assert "further files left out to fit the 4000-character budget" in p
    assert "## Why the last attempt was dropped" in p and p.rstrip().endswith("Nothing else inside either.")


def test_ollama_keeps_the_model_loaded_through_the_gates():
    body = OllamaWorker(WorkerSpec()).payload("hi", Profile(device="cpu", houdini="running"))
    assert body["keep_alive"] == OLLAMA_KEEP_ALIVE == "15m"
