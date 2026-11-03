"""Each ledger row records what the design and the next harness decisions need.

Run 11 could not say whether its 30-minute attempts went on reading the prompt or writing
the reply (the Ollama reply carries both, and only the text was kept), named the failing
gate only inside the free-text reason, and saved only the step's own target failures.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from harness.plexus_loop import MissionRun
from harness.plexus_loop.loop import GATE_FAILED, Attempt
from harness.plexus_loop.mission import RouterSpec, Step, WorkerSpec, mission_from_dict
from harness.plexus_loop.profile import Profile
from harness.plexus_loop.workers import OllamaWorker, WorkerResult, ollama_stats

PY = sys.executable
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]

BODY = {"response": "", "total_duration": 1_843_100_000_000, "load_duration": 2_400_000_000,
        "prompt_eval_count": 23_512, "prompt_eval_duration": 1_101_260_000_000,
        "eval_count": 4_210, "eval_duration": 739_440_000_000, "done": True}


def test_ollama_stats_keeps_counts_and_turns_nanoseconds_into_seconds():
    assert ollama_stats(BODY) == {"prompt_eval_count": 23_512, "eval_count": 4_210, "total_s": 1843.1,
                                  "load_s": 2.4, "prompt_eval_s": 1101.3, "eval_s": 739.4}


def test_ollama_stats_skips_what_is_missing_or_malformed():
    assert ollama_stats({"response": "x"}) == {}
    assert ollama_stats({"eval_count": "many", "eval_duration": None, "load_duration": 0}) == {"load_s": 0.0}


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_the_worker_hands_the_stats_back_with_its_result(tmp_path, monkeypatch):
    body = dict(BODY, response="```file:plexus/a.txt\nhi\n```\n")
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: _Resp(json.dumps(body).encode()))
    (tmp_path / "plexus").mkdir()
    res = OllamaWorker(WorkerSpec()).attempt(tmp_path, "prompt", Profile(device="cpu", houdini="running"))
    assert res.ok and res.stats["prompt_eval_count"] == 23_512 and res.stats["eval_s"] == 739.4


def test_a_reply_that_is_not_an_object_is_a_failed_call(tmp_path, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: _Resp(b"[1, 2]"))
    res = OllamaWorker(WorkerSpec()).attempt(tmp_path, "prompt", Profile(device="cpu", houdini="running"))
    assert not res.ok and "not a JSON object" in res.note


def _repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    (r / "plexus").mkdir(parents=True)
    (r / "tests" / "acceptance").mkdir(parents=True)
    (r / "tests" / "acceptance" / "f.txt").write_text("x")
    (r / "plexus" / "score.txt").write_text("5\n")
    for args in (["init", "-q", "-b", "master"], ["add", "-A"], ["commit", "-q", "-m", "s"]):
        subprocess.run([*GIT, *args], cwd=r, check=True, capture_output=True)
    return r


def _mission():
    return mission_from_dict({
        "mission": {"name": "demo", "goal": "g", "requires": ["tests/acceptance"], "focus": ["plexus/**"],
                    "frozen": ["tests/acceptance/**"]},
        "metric": {"kind": "command", "cmd": [PY, "-c", "print(open('plexus/score.txt').read().strip())"]},
        "gates": [{"name": "first", "cmd": [PY, "-c", "print('ok')"]},
                  {"name": "second", "cmd": [PY, "-c", "import os,sys; sys.exit(1 if os.path.exists('plexus/bad.txt') else 0)"]}],
        "budget": {"attempts": 2, "hours": 1, "max_consecutive_failures": 5},
    })


class _Steps:
    def __init__(self, *steps):
        self.steps = list(steps)

    def attempt(self, wt, prompt, profile):
        return self.steps.pop(0)(wt)


def _write(rel, text, stats=None):
    def step(wt):
        (wt / rel).write_text(text)
        return WorkerResult(True, "ok", stats=dict(stats or {}))
    return step


def _run(r, *steps):
    return MissionRun(_mission(), r, worker=_Steps(*steps), log=lambda s: None,
                      profile_fn=lambda: Profile(device="cpu", houdini="running")).run()


def test_new_rows_default_to_nothing_recorded():
    a = Attempt(n=1, started=0.0, houdini="off", device="gpu")
    assert (a.failed_gate, a.failing, a.ollama) == ("", [], {})


def test_a_gate_drop_names_its_gate_and_keeps_its_reason(tmp_path):
    r = _repo(tmp_path)
    a, b = _run(r, _write("plexus/bad.txt", "x", {"eval_count": 7}), _write("plexus/score.txt", "4\n")).attempts
    assert (a.reason, a.failed_gate, a.failing) == ("gate 'second' failed", "second", [])
    # The next prompt quotes a failing gate's known fixes only for a reason GATE_FAILED
    # matches, so this wording and that pattern must change together.
    assert GATE_FAILED.match(a.reason)
    assert a.ollama == {"eval_count": 7}
    assert b.kept and b.failed_gate == "" and b.ollama == {}


def test_a_worker_failure_still_records_the_model_timing(tmp_path):
    # A reply with no block to apply cost the same model time, and its row must say where it went.
    r = _repo(tmp_path)

    def no_blocks(wt):
        return WorkerResult(False, "model reply held no unified diff and no file block", stats={"eval_count": 9})
    a, _ = _run(r, no_blocks, _write("plexus/score.txt", "4\n")).attempts
    assert a.reason.startswith("worker: ") and a.ollama == {"eval_count": 9}


def test_every_row_in_the_ledger_carries_the_new_fields(tmp_path):
    r = _repo(tmp_path)
    _run(r, _write("plexus/bad.txt", "x", {"eval_count": 7}), _write("plexus/score.txt", "4\n"))
    rows = [json.loads(x) for x in (r / ".plexus_loop" / "demo" / "attempts.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(row["failed_gate"], row["failing"], row["ollama"]) for row in rows] == [("second", [], {"eval_count": 7}), ("", [], {})]


def test_a_metric_run_keeps_every_failing_test_id(tmp_path, monkeypatch):
    from harness.plexus_loop import loop
    from harness.plexus_loop.metrics import MetricResult
    ids = ["tests.acceptance.phase1.test_t2::test_bad", "tests.acceptance.phase1.test_t6::test_truth"]
    monkeypatch.setattr(loop, "measure", lambda metric, wt, profile: MetricResult(5.0, failing=list(ids)))
    # A step aimed at the first id only: `failing` keeps both, `target_failures` only its own.
    m = replace(_mission(), steps=[Step("S1", ["tests/acceptance/phase1/test_t2.py"], "x")],
                router=RouterSpec(kind="first"))
    r = _repo(tmp_path)
    a, _ = MissionRun(m, r, worker=_Steps(_write("plexus/a.txt", "x"), _write("plexus/b.txt", "y")),
                      log=lambda s: None, profile_fn=lambda: Profile(device="cpu", houdini="running")).run().attempts
    assert a.route == "S1 via first" and a.reason.startswith("no strict gain") and a.failed_gate == ""
    assert a.failing == ids and [t.split("\n", 1)[0] for t in a.target_failures] == ids[:1]


def test_a_null_response_is_an_empty_reply_not_a_crash(tmp_path, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout: _Resp(json.dumps(dict(BODY, response=None)).encode()))
    res = OllamaWorker(WorkerSpec()).attempt(tmp_path, "prompt", Profile(device="cpu", houdini="running"))
    assert not res.ok and res.stats["eval_count"] == 4_210
