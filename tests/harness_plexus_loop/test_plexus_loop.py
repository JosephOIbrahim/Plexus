"""Tests for the plexus-loop build harness, using fake workers and a temp git repo."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from harness.plexus_loop import MissionRun, RefuseToStart, loop
from harness.plexus_loop.__main__ import main as cli_main
from harness.plexus_loop.loop import Lock
from harness.plexus_loop.metrics import MetricResult, measure, run_gate
from harness.plexus_loop.mission import Gate, HoudiniPolicy, Metric, MissionError, WorkerSpec, mission_from_dict
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


def test_a_baseline_worktree_that_cannot_be_made_is_a_refusal(repo, monkeypatch):
    def cannot_add(*args):
        raise loop.gitops.GitError("git worktree add: fatal: already exists")

    monkeypatch.setattr(loop.gitops, "add_worktree", cannot_add)
    w = Scripted()
    with pytest.raises(RefuseToStart, match="baseline worktree"):
        run(repo, _mission(), w)
    assert w.prompts == []
    assert not (repo / ".plexus_loop" / "lock").exists()


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


def test_one_lock_holds_across_the_main_checkout_and_a_linked_worktree(repo, tmp_path):
    # A linked worktree moves the same branch and loads the same model, so each side refuses while the other holds it.
    # Only the lock is shared: the ledger, REVIEW.md and the stop file stay with the checkout that owns them.
    linked = tmp_path / "linked"
    _git(repo, "worktree", "add", "-q", "--detach", str(linked))
    runs = {checkout: MissionRun(mission_from_dict(_mission()), checkout, worker=Scripted()) for checkout in (repo, linked)}
    for holder, other in ((repo, linked), (linked, repo)):
        runs[holder].lock.acquire("other")  # held by this live process
        try:
            with pytest.raises(RefuseToStart, match="holds the lock"):
                runs[other].run()
        finally:
            runs[holder].lock.release()
    main_lock, own_state = repo / ".plexus_loop" / "lock", linked / ".plexus_loop"
    seen = []

    def look(wt):
        seen.append((main_lock.is_file(), (own_state / "lock").exists()))
        set_score(4)(wt)

    run(linked, _mission(budget={"attempts": 1, "hours": 1, "max_consecutive_failures": 3}), Scripted(look))
    assert seen == [(True, False)] and not main_lock.exists()
    assert (own_state / "demo" / "attempts.jsonl").is_file() and (own_state / "demo" / "REVIEW.md").is_file()
    assert not (repo / ".plexus_loop" / "demo").exists()
    (own_state / "STOP").touch()
    with pytest.raises(RefuseToStart, match="stop file"):
        run(linked, _mission(), Scripted())
    runs[repo].preflight()  # that stop file is the linked checkout's alone


def test_a_listing_that_failed_says_nothing_about_the_lock_holder(repo, monkeypatch):
    # tasklist exits 1 with stdout empty on a filter it rejects or a WMI error, and reading that as "gone" would take a
    # live run's lock over. profile.py's check=True and the launcher's pid_alive both call it "can't tell".
    state = repo / ".plexus_loop"
    state.mkdir()
    (state / "lock").write_text(json.dumps({"pid": 4242, "mission": "other"}))
    with monkeypatch.context() as mp:  # undone here: the shared fixtures' teardown runs later and imports modules
        mp.setattr(sys, "platform", "win32")
        mp.setattr(subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1, stdout=""))
        with pytest.raises(RefuseToStart, match="holds the lock"):
            Lock(state).acquire("second")
    assert json.loads((state / "lock").read_text())["mission"] == "other"


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


def test_a_restart_works_from_the_loop_branch_whatever_head_says(repo):
    # Every run after the first is a restart, and only the mission file comes from the main tree: rows 64 to 73 ran on a
    # brief the loop branch lacked. The tip is the base and the baseline, and the ledger's row N stays line N.
    d = _mission()
    d["budget"]["attempts"] = 1
    first = run(repo, d, Scripted(set_score(4)))
    (repo / "plexus" / "score.txt").write_text("9\n")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "commit", "-qam", "head moves on")
    master = _git(repo, "rev-parse", "master").strip()
    w = Scripted(set_score(3))
    second = run(repo, d, w)
    assert second.base == first.tip and second.baseline == 4 and second.attempts[0].kept
    assert "```file:plexus/score.txt\n4\n" in w.prompts[0]
    assert _git(repo, "rev-parse", "plexus-loop/demo").strip() == second.tip and _git(repo, "rev-parse", "master").strip() == master
    rows = (repo / ".plexus_loop" / "demo" / "attempts.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(row)["n"] for row in rows] == [1, 1]


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


def test_a_worktree_that_cannot_be_made_costs_its_attempt_and_stays_out_of_the_next_prompt(repo, monkeypatch):
    # A folder held open by a left-behind process belongs to one attempt number, so the next attempt's fresh path runs.
    # git's message quotes this machine's paths: the review shows it, and the router and the next prompt never read it.
    real_add = loop.gitops.add_worktree

    def add_worktree(rp, path, sha):
        if path.name == "attempt-2":
            raise loop.gitops.GitError(f"git worktree add: fatal: '{path}' already exists")
        real_add(rp, path, sha)

    monkeypatch.setattr(loop.gitops, "add_worktree", add_worktree)
    routed = []

    def route(mi, last, attempts):
        routed.append([a.n for a in attempts])
        return loop.Route(None, "none")

    def no_gain(wt):
        (wt / "plexus" / "note.txt").write_text("no gain\n")

    w = Scripted(no_gain, set_score(4))
    m = mission_from_dict(_mission(budget={"attempts": 3, "hours": 1, "max_consecutive_failures": 5}))
    report = MissionRun(m, repo, worker=w, profile_fn=lambda: CPU, log=lambda s: None, route_fn=route).run()
    _, failed, last = report.attempts
    assert failed.reason.startswith("git: ") and "\n" not in failed.reason and failed.route_s is None
    assert len(w.prompts) == 2 and last.kept
    assert routed == [[], [1]]
    assert "Attempt 1 was dropped" in w.prompts[1] and "file:plexus/note.txt" in w.prompts[1]
    assert "already exists" not in w.prompts[1]
    assert "already exists" in (repo / ".plexus_loop" / "demo" / "REVIEW.md").read_text(encoding="utf-8")


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


def test_build_core_copies_only_what_this_build_made(tmp_path, monkeypatch):
    # Every worktree shares one cargo target, so an earlier attempt's library is always there. A failed build that copied
    # it would pass the core gate on Rust that does not compile, and the metric would score the old code. cargo keeps the
    # gate's own pipes, which is how rows 78 and 79 had E0596 in the next prompt.
    from harness.plexus_loop import build_core

    root, target = tmp_path / "wt", tmp_path / "shared"
    (root / "crates" / "plexus-core").mkdir(parents=True)
    (root / "crates" / "plexus-core" / "Cargo.toml").write_text("")
    built, name = build_core.artifact(target)
    built.parent.mkdir(parents=True)
    built.write_text("LIB")
    dest = root / "plexus" / name
    monkeypatch.setenv("CARGO_TARGET_DIR", str(target))
    codes, calls = [101, 0, 0], []

    def cargo(cmd, **kw):
        calls.append((cmd, kw))
        return SimpleNamespace(returncode=codes.pop(0))

    with monkeypatch.context() as mp:  # undone here: the shared fixtures' teardown runs later and imports modules
        mp.setattr(subprocess, "run", cargo)
        assert build_core.main(root) == 101 and not dest.exists()
        assert build_core.main(root) == 0 and dest.read_text() == "LIB"
        dest.unlink()
        built.unlink()
        assert build_core.main(root) == 2 and not dest.exists()
    (cmd, kw), *_ = calls
    assert "--release" in cmd and "python" in cmd and kw["cwd"] == root.resolve()
    assert not {"capture_output", "stdout", "stderr"} & set(kw)


def test_profile_is_rechecked_each_attempt(repo):
    profiles = iter([CPU, CPU, Profile(device="gpu", houdini="absent"), CPU])
    w = Scripted(set_score(4), set_score(3))
    m = mission_from_dict(_mission())
    report = MissionRun(m, repo, worker=w, profile_fn=lambda: next(profiles), log=lambda s: None).run()
    assert [a.device for a in report.attempts[:2]] == ["cpu", "gpu"]
    assert [p.device for p in w.profiles[:2]] == ["cpu", "gpu"]  # the row and the worker, not the row alone


def test_houdini_opening_mid_run_reaches_the_next_request_on_the_wire(repo, monkeypatch):
    # The hard rule with nothing handed in. Every other test injects a profile or reads payload() alone, so a profile
    # cached at the start, a lost [houdini] policy or a request built from another profile would leave them all green.
    monkeypatch.setenv("PLEXUS_LOOP_HOUDINI", "absent")
    # The run's load goes through this urlopen too, and test_worker_outage.py has its own test of that load.
    monkeypatch.setattr(OllamaWorker, "cannot_run", lambda self, profile: "", raising=False)
    sent = []

    def urlopen(req, timeout):
        sent.append((req.full_url, json.loads(req.data), timeout))
        monkeypatch.setenv("PLEXUS_LOOP_HOUDINI", "running")
        return io.BytesIO(json.dumps({"response": f"```file:plexus/score.txt\n{5 - len(sent)}\n```\n"}).encode())

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    d = _mission(worker={"host": "http://ollama:1/", "timeout_s": 4800, "num_ctx": 100}, houdini={"cpu_threads": 3})
    d["budget"]["attempts"] = 2
    report = MissionRun(mission_from_dict(d), repo, log=lambda s: None).run()
    assert [a.device for a in report.attempts] == ["gpu", "cpu"] and report.best == 3
    (url, first, timeout), (_, second, _) = sent
    assert url == "http://ollama:1/api/generate" and timeout == 4800 and "Lower the score." in first["prompt"]
    assert first["options"] == {"num_ctx": 100}
    assert second["options"] == {"num_gpu": 0, "num_thread": 3, "num_ctx": 100}


def test_gates_and_both_metrics_run_in_the_profile_environment_without_the_key(tmp_path, monkeypatch):
    # They run code the worker wrote, and what it prints reaches the next prompt and the API. The two device variables
    # are cleared first: inside the unit gate this process holds the CPU profile's own, and a child would inherit them.
    monkeypatch.setenv("TYPESAFE_API_KEY", "fake-key")
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.delenv("PLEXUS_LOOP_DEVICE", raising=False)
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")  # the child's plugins would add seconds to every attempt's unit gate
    ok = ("import os\nok = (os.environ.get('CUDA_VISIBLE_DEVICES') == '' and os.environ.get('PLEXUS_LOOP_DEVICE') == 'cpu'\n"
          "      and 'TYPESAFE_API_KEY' not in os.environ)\n")
    assert run_gate(Gate("g", [PY, "-c", ok + "raise SystemExit(0 if ok else 1)"]), tmp_path, CPU).passed
    assert measure(Metric(kind="command", cmd=[PY, "-c", ok + "print(1 if ok else 0)"]), tmp_path, CPU).value == 1
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "test_env.py").write_text(ok + "def test_env(): assert ok\n")
    res = measure(Metric(kind="pytest_failures", target="t"), tmp_path, CPU)
    assert (res.value, res.total) == (0.0, 1)


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
    assert "```file:plexus/score.txt" in p and "file:README.md" not in p


def test_pytest_failures_metric_counts_down_and_stops_at_zero(tmp_path):
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


def test_a_skipped_test_counts_as_not_passing(tmp_path):
    # A change must never score by skipping a test it was not allowed to skip.
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "test_s.py").write_text("import pytest\n\ndef test_skips(): pytest.skip('x')\n\ndef test_passes(): pass\n")
    res = measure(Metric(kind="pytest_failures", target="t"), tmp_path, CPU)
    assert (res.value, res.total) == (1.0, 2) and res.failing == ["t.test_s::test_skips"]


def test_a_skip_the_mission_declared_is_not_a_failure(tmp_path):
    # A case that can only run on another platform skips here for good. Counted, it is a floor no attempt
    # can clear, which is what cost mission organ-hardening a run and forced its frozen file to be split.
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "test_s.py").write_text(
        "import pytest\n\ndef test_skips_elsewhere(): pytest.skip('POSIX only')\n\ndef test_passes(): pass\n")
    res = measure(Metric(kind="pytest_failures", target="t", allowed_skips=("t.test_s::test_skips_elsewhere",)), tmp_path, CPU)
    assert (res.value, res.total, res.failing) == (0.0, 2, [])


def test_a_declared_allowance_does_not_cover_another_test_s_skip(tmp_path):
    # The allowance is per test id: one declared id must not excuse a second test's skip, nor a failure.
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "test_s.py").write_text(
        "import pytest\n\ndef test_declared(): pytest.skip('x')\n\ndef test_undeclared(): pytest.skip('y')\n\ndef test_fails(): assert False\n")
    res = measure(Metric(kind="pytest_failures", target="t",
                         allowed_skips=("t.test_s::test_declared",)), tmp_path, CPU)
    assert res.value == 2.0 and sorted(res.failing) == ["t.test_s::test_fails", "t.test_s::test_undeclared"]


def test_an_allowed_pattern_covers_a_whole_file(tmp_path):
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "test_posix.py").write_text(
        "import pytest\n\n@pytest.mark.skipif(True, reason='POSIX only')\ndef test_a(): pass\n\n"
        "@pytest.mark.skipif(True, reason='POSIX only')\ndef test_b(): pass\n")
    res = measure(Metric(kind="pytest_failures", target="t", allowed_skips=("t.test_posix::*",)), tmp_path, CPU)
    assert (res.value, res.total) == (0.0, 2)


def test_a_run_that_collects_nothing_is_an_error_never_a_score_of_zero(tmp_path):
    # A zero would read as "every target test passes" and end the run.
    (tmp_path / "t").mkdir()
    res = measure(Metric(kind="pytest_failures", target="t"), tmp_path, CPU)
    assert res.value is None and res.error == "no tests collected"


def test_a_pytest_that_writes_no_report_is_an_error_never_a_score(tmp_path):
    # A conftest that raises takes this path, and so does a native crash in code a test calls. The output is all the next
    # prompt has, and without the check a baseline ends the run on FileNotFoundError.
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "conftest.py").write_text("raise RuntimeError('BOOM-AT-CONFTEST')\n")
    (tmp_path / "t" / "test_x.py").write_text("def test_x(): pass\n")
    res = measure(Metric(kind="pytest_failures", target="t"), tmp_path, CPU)
    assert res.value is None and res.error == "pytest wrote no report" and "BOOM-AT-CONFTEST" in res.tail


def test_a_gain_that_comes_from_breaking_collection_is_dropped(tmp_path):
    # Three failures become one collection error: a lower number, from fewer tests.
    r = tmp_path / "r"
    (r / "plexus").mkdir(parents=True)
    acc = r / "tests" / "acceptance"
    acc.mkdir(parents=True)
    (acc / "test_t.py").write_text(
        "from pathlib import Path\n"
        "N = int(Path(__file__).parents[2].joinpath('plexus/n.txt').read_text())\n"
        "def test_t1(): assert N >= 1\n"
        "def test_t2(): assert N >= 2\n"
        "def test_t3(): assert N >= 3\n"
    )
    (r / "plexus" / "n.txt").write_text("0")
    _git(r, "init", "-q", "-b", "master")
    _git(r, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    _git(r, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "s")
    d = _mission(metric={"kind": "pytest_failures", "target": "tests/acceptance", "min_delta": 1})
    d["budget"]["attempts"] = 1
    report = run(r, d, Scripted(lambda wt: (wt / "plexus" / "n.txt").write_text("not a number")))
    (a,) = report.attempts
    assert not a.kept and a.metric == 1 and report.best == 3
    assert a.reason == "tests went missing (1 collected, was 3)"


def test_a_keep_raises_the_count_a_later_gain_must_hold(repo, monkeypatch):
    # A keep that turns a collection error into real tests moves the floor. A later reply that breaks collection again
    # scores lower on fewer tests, and measured against the baseline's count it would be a false keep.
    seq = [MetricResult(3.0, total=3), MetricResult(2.0, total=10), MetricResult(1.0, total=3)]
    monkeypatch.setattr(loop, "measure", lambda metric, wt, profile: seq.pop(0))
    d = _mission()
    d["budget"]["attempts"] = 2
    report = run(repo, d, Scripted(set_score(4), set_score(3)))
    first, second = report.attempts
    assert first.kept and not second.kept and report.best == 2
    assert second.reason == "tests went missing (3 collected, was 10)"
    assert _git(repo, "show", "plexus-loop/demo:plexus/score.txt").strip() == "4"


def test_a_teardown_error_in_a_passing_test_is_one_test_and_its_fix_is_kept(tmp_path):
    # The report's own tests= counts that test twice, so the attempt that clears the error read as a test gone missing,
    # at every restart too, because the next baseline measured the same tip.
    r = tmp_path / "r"
    (r / "plexus").mkdir(parents=True)
    acc = r / "tests" / "acceptance"
    acc.mkdir(parents=True)
    (acc / "test_t.py").write_text(
        "from pathlib import Path\n"
        "import pytest\n"
        "FLAG = Path(__file__).parents[2] / 'plexus' / 'stop_raises.txt'\n"
        "@pytest.fixture\n"
        "def rt():\n"
        "    yield\n"
        "    if FLAG.read_text() == '1':\n"
        "        raise RuntimeError('stop raised')\n"
        "def test_a(rt): pass\n"
        "def test_b(): pass\n"
    )
    (r / "plexus" / "stop_raises.txt").write_text("1")
    (r / ".gitignore").write_text("__pycache__/\n")
    _git(r, "init", "-q", "-b", "master")
    _git(r, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    _git(r, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "s")
    d = _mission(metric={"kind": "pytest_failures", "target": "tests/acceptance", "min_delta": 1})
    d["budget"]["attempts"] = 1
    report = run(r, d, Scripted(lambda wt: (wt / "plexus" / "stop_raises.txt").write_text("0")))
    (a,) = report.attempts
    assert a.kept and report.baseline == 1 and report.best == 0
    assert measure(Metric(kind="pytest_failures", target="tests/acceptance"), r, CPU).total == 2


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
