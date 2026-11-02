"""Tests for the plexus-loop build harness, using fake workers and a temp git repo."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from harness.plexus_loop import MissionRun, RefuseToStart
from harness.plexus_loop.__main__ import main as cli_main
from harness.plexus_loop.loop import Lock
from harness.plexus_loop.mission import HoudiniPolicy, MissionError, WorkerSpec, mission_from_dict
from harness.plexus_loop.profile import Profile, choose_profile, houdini_state
from harness.plexus_loop.workers import OllamaWorker, WorkerResult, extract_diff

PY = sys.executable


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    (r / "plexus").mkdir(parents=True)
    (r / "tests" / "acceptance").mkdir(parents=True)
    (r / "plexus" / "score.txt").write_text("5\n")
    (r / "tests" / "acceptance" / "frozen.txt").write_text("do not touch\n")
    (r / "README.md").write_text("outside focus\n")
    _git(r, "init", "-q", "-b", "master")
    _git(r, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    _git(r, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
         "commit", "-q", "-m", "seed")
    return r


def _mission(**over) -> dict:
    d = {
        "mission": {
            "name": "demo",
            "goal": "Lower the score.",
            "requires": ["tests/acceptance"],
            "focus": ["plexus/**"],
            "frozen": ["tests/acceptance/**"],
        },
        "metric": {"kind": "command", "direction": "lower", "min_delta": 1,
                   "cmd": [PY, "-c", "print(open('plexus/score.txt').read().strip())"]},
        "gates": [{"name": "ok", "cmd": [PY, "-c", "pass"]}],
        "budget": {"attempts": 3, "hours": 1, "max_consecutive_failures": 3},
    }
    for k, v in over.items():
        d[k] = v
    return d


CPU = Profile(device="cpu", houdini="running", env={"CUDA_VISIBLE_DEVICES": ""},
              ollama_options={"num_gpu": 0, "num_thread": 2})


class Scripted:
    """A fake worker that runs one function per attempt."""

    def __init__(self, *steps):
        self.steps = list(steps)
        self.prompts: list[str] = []
        self.profiles: list[Profile] = []

    def attempt(self, worktree: Path, prompt: str, profile: Profile) -> WorkerResult:
        self.prompts.append(prompt)
        self.profiles.append(profile)
        step = self.steps.pop(0) if self.steps else (lambda wt: None)
        out = step(worktree)
        return out if isinstance(out, WorkerResult) else WorkerResult(True, "ok")


def set_score(n):
    return lambda wt: (wt / "plexus" / "score.txt").write_text(f"{n}\n")


def run(repo, mission_dict, worker, profile=CPU):
    m = mission_from_dict(mission_dict)
    return MissionRun(m, repo, worker=worker, profile_fn=lambda: profile, log=lambda s: None).run()


# -- refusals -------------------------------------------------------------

def test_refuses_when_required_path_missing(repo):
    d = _mission()
    d["mission"]["requires"] = ["tests/acceptance", "PLEXUS_SPEC.md"]
    with pytest.raises(RefuseToStart, match="PLEXUS_SPEC.md"):
        run(repo, d, Scripted())
    assert "plexus-loop/demo" not in _git(repo, "branch")


def test_refuses_when_stop_file_present(repo):
    (repo / ".plexus_loop").mkdir()
    (repo / ".plexus_loop" / "STOP").touch()
    with pytest.raises(RefuseToStart, match="stop file"):
        run(repo, _mission(), Scripted())


def test_refuses_when_gates_fail_before_any_change(repo):
    d = _mission(gates=[{"name": "red", "cmd": [PY, "-c", "raise SystemExit(1)"]}])
    w = Scripted()
    with pytest.raises(RefuseToStart, match="gate 'red' failed"):
        run(repo, d, w)
    assert w.prompts == []


def test_lock_blocks_a_second_run(repo):
    state = repo / ".plexus_loop"
    Lock(state).acquire("other")  # held by this live process
    try:
        with pytest.raises(RefuseToStart, match="holds the lock"):
            run(repo, _mission(), Scripted())
    finally:
        Lock(state).release()


def test_stale_lock_from_dead_process_is_taken_over(repo):
    state = repo / ".plexus_loop"
    state.mkdir()
    (state / "lock").write_text(json.dumps({"pid": 2**22 + 12345, "mission": "old"}))
    report = run(repo, _mission(), Scripted(set_score(4)))
    assert report.best == 4
    assert not (state / "lock").exists()


# -- keeping and dropping -------------------------------------------------

def test_keeps_strict_gain_and_advances_branch(repo):
    master = _git(repo, "rev-parse", "master").strip()
    report = run(repo, _mission(), Scripted(set_score(3), set_score(3), set_score(1)))
    assert [a.kept for a in report.attempts] == [True, False, True]
    assert report.baseline == 5 and report.best == 1
    assert _git(repo, "show", "plexus-loop/demo:plexus/score.txt").strip() == "1"
    # Nothing else moved.
    assert _git(repo, "rev-parse", "master").strip() == master
    assert (repo / "plexus" / "score.txt").read_text().strip() == "5"
    review = (repo / ".plexus_loop" / "demo" / "REVIEW.md").read_text()
    assert "Promotion is yours" in review and "5 at start, 1 now" in review
    log = (repo / ".plexus_loop" / "demo" / "attempts.jsonl").read_text().splitlines()
    assert len(log) == 3
    assert _git(repo, "worktree", "list").count("\n") == 1  # only the main worktree is left


def test_attempt_starts_from_best_commit(repo):
    seen = []

    def look(wt):
        seen.append((wt / "plexus" / "score.txt").read_text().strip())
        (wt / "plexus" / "score.txt").write_text("2\n")

    run(repo, _mission(), Scripted(set_score(4), look))
    assert seen == ["4"]


def test_drops_frozen_path(repo):
    def touch_frozen(wt):
        (wt / "plexus" / "score.txt").write_text("0\n")
        (wt / "tests" / "acceptance" / "frozen.txt").write_text("changed\n")

    report = run(repo, _mission(), Scripted(touch_frozen))
    assert not report.attempts[0].kept
    assert "frozen" in report.attempts[0].reason
    assert report.best == 5


def test_drops_change_outside_focus(repo):
    def outside(wt):
        (wt / "plexus" / "score.txt").write_text("0\n")
        (wt / "new_top_level.py").write_text("x = 1\n")

    report = run(repo, _mission(), Scripted(outside))
    assert "outside focus" in report.attempts[0].reason


def test_drops_when_a_gate_fails_after_change(repo):
    gate = [PY, "-c", "import sys; sys.exit(0 if open('plexus/score.txt').read().strip() != '0' else 1)"]
    d = _mission(gates=[{"name": "guard", "cmd": gate}])
    report = run(repo, d, Scripted(set_score(0)))
    assert report.attempts[0].reason == "gate 'guard' failed"


def test_no_change_and_worker_failure_are_dropped(repo):
    report = run(repo, _mission(), Scripted(lambda wt: None, lambda wt: WorkerResult(False, "boom")))
    assert report.attempts[0].reason == "no change"
    assert report.attempts[1].reason == "worker: boom"


def test_min_delta_requires_strict_gain(repo):
    d = _mission()
    d["metric"]["min_delta"] = 2
    report = run(repo, d, Scripted(set_score(4), set_score(3)))
    assert [a.kept for a in report.attempts[:2]] == [False, True]


def test_higher_is_better(repo):
    d = _mission()
    d["metric"]["direction"] = "higher"
    report = run(repo, d, Scripted(set_score(4), set_score(9)))
    assert [a.kept for a in report.attempts[:2]] == [False, True]
    assert report.best == 9


# -- stopping -------------------------------------------------------------

def test_stops_after_consecutive_failures(repo):
    d = _mission()
    d["budget"] = {"attempts": 50, "hours": 1, "max_consecutive_failures": 2}
    report = run(repo, d, Scripted())
    assert len(report.attempts) == 2
    assert "in a row" in report.stop_reason


def test_stops_on_attempt_budget(repo):
    report = run(repo, _mission(), Scripted(set_score(4), set_score(3), set_score(2), set_score(1)))
    assert len(report.attempts) == 3
    assert "attempt budget" in report.stop_reason


def test_stops_on_hour_budget(repo):
    t = {"now": 1000.0}

    def clock():
        t["now"] += 1800  # half an hour per tick
        return t["now"]

    m = mission_from_dict(_mission())
    report = MissionRun(m, repo, worker=Scripted(set_score(4), set_score(3)), profile_fn=lambda: CPU,
                        clock=clock, log=lambda s: None).run()
    assert "hour budget" in report.stop_reason


def test_stop_file_halts_after_current_attempt(repo):
    def then_stop(wt):
        (wt / "plexus" / "score.txt").write_text("4\n")
        (repo / ".plexus_loop" / "STOP").touch()

    report = run(repo, _mission(), Scripted(then_stop, set_score(1)))
    assert len(report.attempts) == 1 and report.attempts[0].kept
    assert report.stop_reason == "stop file"


# -- Houdini and the CPU --------------------------------------------------

def test_houdini_state_from_process_list(monkeypatch):
    monkeypatch.delenv("PLEXUS_LOOP_HOUDINI", raising=False)
    assert houdini_state(lambda: ["explorer.exe", "houdinifx.exe"]) == "running"
    assert houdini_state(lambda: ["bash", "hython"]) == "running"
    assert houdini_state(lambda: ["bash", "code"]) == "absent"
    assert houdini_state(list) == "unknown"

    def broken():
        raise OSError("no ps")

    assert houdini_state(broken) == "unknown"


def test_houdini_override(monkeypatch):
    monkeypatch.setenv("PLEXUS_LOOP_HOUDINI", "running")
    assert houdini_state(lambda: ["bash"]) == "running"


@pytest.mark.parametrize("state,device", [("running", "cpu"), ("unknown", "cpu"), ("absent", "gpu")])
def test_profile_steps_aside_unless_houdini_is_clearly_absent(state, device):
    p = choose_profile(HoudiniPolicy(cpu_threads=6, cargo_jobs=3), state)
    assert p.device == device
    if device == "cpu":
        assert p.env["CUDA_VISIBLE_DEVICES"] == ""
        assert p.env["CARGO_BUILD_JOBS"] == "3"
        assert p.ollama_options == {"num_gpu": 0, "num_thread": 6}
    else:
        assert p.env == {} and p.ollama_options == {}


def test_gates_see_the_cpu_environment(repo):
    code = ("import os,sys; sys.exit(0 if os.environ.get('CUDA_VISIBLE_DEVICES') == '' "
            "and os.environ['PLEXUS_LOOP_DEVICE'] == 'cpu' else 1)")
    gate = [PY, "-c", code]
    report = run(repo, _mission(gates=[{"name": "env", "cmd": gate}]), Scripted(set_score(4)))
    assert report.attempts[0].kept


def test_gates_share_one_cargo_target_under_the_main_repo(repo):
    want = str(repo.resolve() / ".plexus_loop" / "cargo-target")
    code = ("import os,sys,pathlib; t=os.environ.get('CARGO_TARGET_DIR',''); "
            f"sys.exit(0 if pathlib.Path(t).resolve() == pathlib.Path({want!r}).resolve() else 1)")
    report = run(repo, _mission(gates=[{"name": "cargo-env", "cmd": [PY, "-c", code]}]), Scripted(set_score(4)))
    assert report.attempts[0].kept


def test_build_core_passes_with_no_crate_yet(tmp_path):
    from harness.plexus_loop import build_core

    assert build_core.main(tmp_path) == 0
    assert not (tmp_path / "plexus").exists()


def test_profile_is_rechecked_each_attempt(repo):
    profiles = iter([CPU, CPU, Profile(device="gpu", houdini="absent"), CPU])
    w = Scripted(set_score(4), set_score(3))
    m = mission_from_dict(_mission())
    report = MissionRun(m, repo, worker=w, profile_fn=lambda: next(profiles), log=lambda s: None).run()
    assert [a.device for a in report.attempts[:2]] == ["cpu", "gpu"]


def test_ollama_payload_goes_cpu_only_beside_houdini():
    w = OllamaWorker(WorkerSpec())
    body = w.payload("hi", CPU)
    assert body["model"] == "qwen3-coder:30b" and body["stream"] is False
    assert body["options"] == {"num_gpu": 0, "num_thread": 2}
    assert "options" not in w.payload("hi", Profile(device="gpu", houdini="absent"))


def test_ollama_payload_sends_num_ctx_when_set():
    w = OllamaWorker(WorkerSpec(num_ctx=40960))
    assert w.payload("hi", CPU)["options"] == {"num_gpu": 0, "num_thread": 2, "num_ctx": 40960}
    assert w.payload("hi", Profile(device="gpu", houdini="absent"))["options"] == {"num_ctx": 40960}
    m = mission_from_dict(_mission(worker={"kind": "ollama", "num_ctx": 32768}))
    assert m.worker.num_ctx == 32768


# -- diffs, prompts, metrics, mission files -------------------------------

def test_extract_diff_from_fenced_reply():
    reply = "Here you go:\n```diff\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n```\nDone."
    assert extract_diff(reply).startswith("--- a/x")
    assert extract_diff("no diff here") is None


def test_ollama_diff_is_applied(repo):
    from harness.plexus_loop import workers

    diff = ("diff --git a/plexus/score.txt b/plexus/score.txt\n--- a/plexus/score.txt\n"
            "+++ b/plexus/score.txt\n@@ -1 +1 @@\n-5\n+2\n")
    wt = repo
    res = workers.apply_diff(wt, diff)
    assert res.ok and (repo / "plexus" / "score.txt").read_text() == "2\n"


def test_prompt_names_rules_and_focus_files(repo):
    w = Scripted(set_score(4))
    run(repo, _mission(), w)
    p = w.prompts[0]
    assert "Lower the score." in p and "plexus/**" in p and "tests/acceptance/**" in p
    assert "### plexus/score.txt" in p and "### README.md" not in p


def test_pytest_failures_metric_counts_and_guards(tmp_path):
    r = tmp_path / "r"
    (r / "plexus").mkdir(parents=True)
    acc = r / "tests" / "acceptance"
    acc.mkdir(parents=True)
    (acc / "test_t.py").write_text(
        "from pathlib import Path\n"
        "def _n(): return int(Path(__file__).parents[2].joinpath('plexus/n.txt').read_text())\n"
        "def test_t1(): assert _n() >= 1\n"
        "def test_t2(): assert _n() >= 2\n"
        "def test_t3(): assert _n() >= 3\n"
    )
    (r / "plexus" / "n.txt").write_text("0")
    _git(r, "init", "-q", "-b", "master")
    _git(r, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    _git(r, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "s")
    d = _mission(metric={"kind": "pytest_failures", "target": "tests/acceptance", "min_delta": 1})

    def finish(wt):
        (wt / "plexus" / "n.txt").write_text("3")
        (wt / "plexus" / "conftest.py").write_text("")  # harmless, inside focus

    report = run(r, d, Scripted(lambda wt: (wt / "plexus" / "n.txt").write_text("2"), finish))
    assert report.baseline == 3
    assert [a.metric for a in report.attempts[:2]] == [1, 0]
    assert report.best == 0 and report.stop_reason == "every target test passes"


def test_mission_validation():
    with pytest.raises(MissionError, match="min_delta"):
        d = _mission()
        d["metric"]["min_delta"] = 0
        mission_from_dict(d)
    with pytest.raises(MissionError, match="name"):
        d = _mission()
        d["mission"]["name"] = "has space"
        mission_from_dict(d)
    m = mission_from_dict(_mission())
    assert m.is_frozen("tests/acceptance/x.py") and m.is_frozen("tests/acceptance")
    assert m.in_focus("plexus/a/b.py") and not m.in_focus("plexusx/a.py")
    assert m.branch == "plexus-loop/demo"


def test_shipped_mission_file_loads_and_refuses_without_acceptance_tests(tmp_path, capsys):
    shipped = Path(__file__).resolve().parents[2] / "harness" / "plexus_loop" / "missions" / "acceptance.toml"
    r = tmp_path / "empty"
    r.mkdir()
    _git(r, "init", "-q", "-b", "master")
    code = cli_main(["check", str(shipped), "--repo", str(r)])
    assert code == 2
    assert "not ready: missing tests/acceptance" in capsys.readouterr().out


def test_command_worker_edits_in_worktree_and_sees_prompt(repo):
    from harness.plexus_loop.workers import make_worker

    script = ("import sys,pathlib; p=pathlib.Path(sys.argv[1]).read_text(); "
              "assert 'Lower the score.' in p; pathlib.Path('plexus/score.txt').write_text('2\\n')")
    d = _mission(worker={"kind": "command", "cmd": [PY, "-c", script, "{prompt_file}"]})
    m = mission_from_dict(d)
    report = MissionRun(m, repo, worker=make_worker(m.worker), profile_fn=lambda: CPU,
                        log=lambda s: None).run()
    assert report.attempts[0].kept and report.best == 2
