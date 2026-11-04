"""Tests for step routing (harness/plexus_loop/router.py). No network: Jev is faked."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from harness.plexus_loop import MissionRun, loop
from harness.plexus_loop.loop import Attempt, build_prompt
from harness.plexus_loop.metrics import MetricResult
from harness.plexus_loop.mission import MissionError, RouterSpec, Step, mission_from_dict
from harness.plexus_loop.router import Route, choose, eligible, jev_request
from harness.plexus_loop.profile import Profile
from harness.plexus_loop.workers import WorkerResult

PY = sys.executable
T0 = "tests/acceptance/phase1/test_t0_schema_gate.py"
T2 = "tests/acceptance/phase1/test_t2_predicate_precision.py::test_delta_threshold_and_cache"
STEPS = [
    Step("S1", [T0], "Write the schema plugin."),
    Step("S2", ["tests/acceptance/phase1/test_t1_propagation.py"], "Build the exchange and axon."),
    Step("S5", [T2], "Add delta with a wake-only cache."),
]
FAILING_ALL = [
    "tests.acceptance.phase1.test_t0_schema_gate::test_schemas_register_define_and_round_trip",
    "tests.acceptance.phase1.test_t1_propagation::test_a_to_b_visibility_p95_under_250ms",
    "tests.acceptance.phase1.test_t2_predicate_precision::test_delta_threshold_and_cache[one-0.3-wakes-once]",
]
JEV = RouterSpec(kind="jev")


def fake_jev(choice, confidence=0.9, seen=None):
    def post(url, body, headers, timeout):
        if seen is not None:
            seen.append((url, body, headers))
        return {"answers": {"next_step": {"type": "choice", "choice": choice,
                                          "confidence": confidence, "probabilities": {}}}}
    return post


def test_eligible_matches_junit_ids_files_and_parametrized_prefixes():
    assert [s.id for s in eligible(STEPS, FAILING_ALL)] == ["S1", "S2", "S5"]
    assert [s.id for s in eligible(STEPS, FAILING_ALL[1:])] == ["S2", "S5"]
    assert eligible(STEPS, []) == []
    # a prefix must end at a name boundary: test_t1 does not match test_t10
    one = [Step("X", ["a/test_m.py::test_t1"], "x")]
    assert eligible(one, ["a.test_m::test_t10"]) == []
    assert eligible(one, ["a.test_m::test_t1[p]"]) != []


def test_first_router_takes_the_earliest_failing_step():
    r = choose(RouterSpec(kind="first"), STEPS, FAILING_ALL[1:])
    assert r.step.id == "S2" and r.how == "first" and r.label() == "S2 via first"


def test_none_router_and_no_eligible_step_route_nothing():
    assert choose(RouterSpec(kind="none"), STEPS, FAILING_ALL).step is None
    r = choose(JEV, STEPS, [], post=fake_jev("S1"), api_key="k")
    assert r.step is None and "no step" in r.note


def test_jev_pick_is_used_and_sees_only_eligible_steps():
    seen = []
    r = choose(JEV, STEPS, FAILING_ALL[1:], tail="ImportError: plexus.core.axon", recent=["x"],
               post=fake_jev("S5", 0.8, seen), api_key="k")
    assert r.step.id == "S5" and r.how == "jev" and r.label() == "S5 via jev 0.80"
    url, body, headers = seen[0]
    assert url == "https://api.typesafe.ai/v1/systemone"
    assert headers["Authorization"] == "Bearer k"
    assert set(body["questions"]["next_step"]["criteria"]) == {"S2", "S5"}
    assert body["state"]["latest_test_output_tail"].endswith("plexus.core.axon")


def test_single_eligible_step_skips_the_network():
    def boom(*a):
        raise AssertionError("should not call Jev with one candidate")
    r = choose(JEV, STEPS, FAILING_ALL[2:], post=boom, api_key="k")
    assert r.step.id == "S5" and r.how == "first"


@pytest.mark.parametrize("post,key,why", [
    (fake_jev("S5", 0.1), "k", "below"),
    (fake_jev("S9"), "k", "unknown step"),
    (lambda *a: (_ for _ in ()).throw(OSError("down")), "k", "jev unavailable"),
    (fake_jev("S5"), "", "is not set"),
])
def test_jev_falls_back_to_the_earliest_step(post, key, why):
    r = choose(JEV, STEPS, FAILING_ALL, post=post, api_key=key)
    assert r.step.id == "S1" and r.how == "fallback" and why in r.note


def test_jev_request_is_a_single_choice_question():
    body = jev_request(JEV, STEPS, FAILING_ALL, "t" * 10_000, ["a", "b", "c", "d"])
    assert body["model"] == "jev-latest"
    assert len(body["state"]["latest_test_output_tail"]) == 3000
    assert body["state"]["recent_dropped_attempts"] == ["b", "c", "d"]
    q = body["questions"]["next_step"]
    assert q["type"] == "choice" and q["criteria"]["S1"]["aimed_at"] == [T0]


def test_every_field_the_question_names_is_in_the_request():
    # Backticks in the question mark field names: a field renamed on one side only would have
    # Jev read for something the request no longer carries.
    for graph in (True, False):
        body = jev_request(JEV, STEPS, FAILING_ALL, "tail", [], graph=graph)
        q = body["questions"]["next_step"]
        fields = set(body["state"]) | {k for option in q["criteria"].values() for k in option}
        named = set(re.findall(r"`(\w+)`", q["instructions"]))
        assert named and named <= fields, named - fields


def test_the_loops_own_drop_lines_reach_their_option(monkeypatch):
    # The other jev tests type their drop lines by hand. default_route writes the real ones from
    # Route.label(), and choose() hands them to jev_request: a change to either side alone would
    # leave every option's its_recent_drops empty.
    seen, real = [], loop.choose_route
    monkeypatch.setattr(loop, "choose_route",
                        lambda *a, **kw: real(*a, **kw, post=fake_jev("S5", 0.9, seen), api_key="k"))
    m = mission_from_dict(_mission(steps=[{"id": s.id, "targets": s.targets, "text": s.text} for s in STEPS],
                                   router={"kind": "jev"}))
    drop = Attempt(n=1, started=0.0, houdini="off", device="cpu", reason="gate 'core' failed",
                   route=Route(m.steps[1], "jev", 0.7).label())
    assert loop.default_route(m, MetricResult(3.0, failing=FAILING_ALL[1:]), [drop]).step.id == "S5"
    crit = seen[0][1]["questions"]["next_step"]["criteria"]
    assert crit["S2"]["its_recent_drops"] == ["gate 'core' failed"] and crit["S5"]["its_recent_drops"] == []


def _mission(**over):
    d = {
        "mission": {"name": "demo", "goal": "Lower the score.", "focus": ["plexus/**"],
                    "frozen": ["tests/acceptance/**"]},
        "metric": {"kind": "command", "cmd": [PY, "-c", "print(1)"]},
        "gates": [{"name": "ok", "cmd": [PY, "-c", "pass"]}],
    }
    d.update(over)
    return d


def test_mission_parses_steps_and_router():
    m = mission_from_dict(_mission(steps=[{"id": "S1", "targets": [T0], "text": "do it"}],
                                   router={"kind": "jev", "min_confidence": 0.5}))
    assert m.steps == [Step("S1", [T0], "do it")]
    assert m.router.kind == "jev" and m.router.min_confidence == 0.5
    assert mission_from_dict(_mission()).router.kind == "none"
    assert mission_from_dict(_mission(steps=[{"id": "S1", "targets": [T0], "text": "x"}])).router.kind == "first"


def test_mission_rejects_bad_router_and_steps():
    with pytest.raises(MissionError, match="needs"):
        mission_from_dict(_mission(router={"kind": "jev"}))
    with pytest.raises(MissionError, match="kind"):
        mission_from_dict(_mission(steps=[{"id": "S1", "targets": [T0], "text": "x"}],
                                   router={"kind": "llm"}))
    with pytest.raises(MissionError, match="unique"):
        mission_from_dict(_mission(steps=[{"id": "S1", "targets": [T0], "text": "x"},
                                          {"id": "S1", "targets": [T0], "text": "y"}]))
    with pytest.raises(MissionError, match="targets"):
        mission_from_dict(_mission(steps=[{"id": "S1", "targets": [], "text": "x"}]))


def test_prompt_puts_the_step_near_the_top(tmp_path):
    m = mission_from_dict(_mission())
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    p = build_prompt(m, tmp_path, 3, None, [], 10_000, step=STEPS[1])
    assert "## This attempt: step S2" in p and "Build the exchange and axon." in p
    assert p.index("## This attempt") < p.index("## Where it stands")
    assert "## This attempt" not in build_prompt(m, tmp_path, 3, None, [], 10_000)


def test_run_records_the_route_and_hands_the_step_to_the_worker(tmp_path):
    r = tmp_path / "repo"
    (r / "plexus").mkdir(parents=True)
    acc = r / "tests" / "acceptance"
    acc.mkdir(parents=True)
    (acc / "test_t.py").write_text(
        "from pathlib import Path\n"
        "def _n(): return int(Path(__file__).parents[2].joinpath('plexus/n.txt').read_text())\n"
        "def test_a(): assert _n() >= 1\n"
        "def test_b(): assert _n() >= 2\n"
    )
    (r / "plexus" / "n.txt").write_text("0")
    for args in (["init", "-q", "-b", "master"], ["add", "-A"],
                 ["-c", "commit.gpgsign=false", "commit", "-q", "-m", "s"]):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=r,
                       check=True, capture_output=True)
    d = _mission(
        metric={"kind": "pytest_failures", "target": "tests/acceptance", "min_delta": 1},
        steps=[{"id": "A", "targets": ["tests/acceptance/test_t.py::test_a"], "text": "make a pass"},
               {"id": "B", "targets": ["tests/acceptance/test_t.py::test_b"], "text": "make b pass"}],
        router={"kind": "first"},
        budget={"attempts": 2, "hours": 1, "max_consecutive_failures": 3},
    )
    prompts = []

    class W:
        def attempt(self, wt: Path, prompt: str, profile: Profile) -> WorkerResult:
            prompts.append(prompt)
            (wt / "plexus" / "n.txt").write_text(str(len(prompts)))
            return WorkerResult(True, "ok")

    report = MissionRun(mission_from_dict(d), r, worker=W(), log=lambda s: None,
                        profile_fn=lambda: Profile(device="cpu", houdini="running")).run()
    assert [a.route for a in report.attempts] == ["A via first", "B via first"]
    assert "step A" in prompts[0] and "step B" in prompts[1]
    assert report.best == 0
    review = (r / ".plexus_loop" / "demo" / "REVIEW.md").read_text(encoding="utf-8")
    assert "| Step |" in review and "A via first" in review
