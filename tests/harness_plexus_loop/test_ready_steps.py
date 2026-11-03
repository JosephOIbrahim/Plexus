"""A step is offered only when the steps it builds on pass; Jev chooses among the ready ones.

Runs 9 and 10 sent three attempts to S8 (Jev at 0.32 to 0.38) while S3 to S7, which S8
needs, did not exist yet, and none could gain. The dependency is a known rule, so it lives
in code (`after` in the mission file); Jev only chooses where code cannot: between steps
that are all ready, from the test output and each step's own recent drops.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from harness.plexus_loop.mission import MissionError, RouterSpec, Step, load_mission, mission_from_dict
from harness.plexus_loop.router import ORDERED_INSTRUCTIONS, READY_INSTRUCTIONS, choose, jev_request, ready

PY = sys.executable
P1 = "tests.acceptance.phase1."
STEPS = [
    Step("S3", ["tests/acceptance/phase1/test_t2_predicate_precision.py::test_bad"], "Rust predicate."),
    Step("S4", ["tests/acceptance/phase1/test_t5_gate.py::test_inside"], "Runtime.", after=["S3"]),
    Step("S6", ["tests/acceptance/phase1/test_t5_gate.py::test_outside"], "Publication gate.", after=["S4"]),
    Step("S7", ["tests/acceptance/phase1/test_t3_budget.py"], "Rust budget.", after=["S4"]),
    Step("S8", ["tests/acceptance/phase1/test_t6_truth.py"], "Truth.", after=["S6", "S7"]),
]
ALL = [P1 + "test_t2_predicate_precision::test_bad", P1 + "test_t5_gate::test_inside",
       P1 + "test_t5_gate::test_outside", P1 + "test_t3_budget::test_trips", P1 + "test_t6_truth::test_kill"]
AFTER_S4 = ALL[2:]  # S3 and S4 pass; S6, S7 and S8 still fail
JEV = RouterSpec(kind="jev", min_confidence=0.5)


def fake_jev(choice, confidence=0.9, seen=None):
    def post(url, body, headers, timeout):
        if seen is not None:
            seen.append(body)
        return {"answers": {"next_step": {"type": "choice", "choice": choice, "confidence": confidence,
                                          "probabilities": {}}}}
    return post


def test_a_step_whose_groundwork_fails_is_never_offered():
    assert [s.id for s in ready(STEPS, ALL)] == ["S3"]
    assert [s.id for s in ready(STEPS, AFTER_S4)] == ["S6", "S7"]
    assert [s.id for s in ready(STEPS, [ALL[-1]])] == ["S8"]


def test_with_one_ready_step_jev_is_not_called_even_when_later_steps_fail():
    # choose() turns any exception from the call into a fallback, so record calls instead of
    # raising: a raise here would only show up as how == "fallback".
    calls = []
    r = choose(JEV, STEPS, ALL, post=lambda *a: calls.append(a) or {}, api_key="k")
    assert calls == [] and r.step.id == "S3" and r.how == "first"


def test_jev_chooses_only_among_ready_steps():
    seen = []
    r = choose(JEV, STEPS, AFTER_S4, tail="AssertionError: budget", post=fake_jev("S7", 0.8, seen), api_key="k")
    assert r.step.id == "S7" and r.how == "jev"
    assert set(seen[0]["questions"]["next_step"]["criteria"]) == {"S6", "S7"}


@pytest.mark.parametrize("post,why", [(fake_jev("S7", 0.4), "below 0.5"), (fake_jev("S8"), "unknown step")])
def test_a_weak_or_unready_pick_falls_back_to_the_earliest_ready_step(post, why):
    r = choose(JEV, STEPS, AFTER_S4, post=post, api_key="k")
    assert r.step.id == "S6" and r.how == "fallback" and why in r.note


def test_first_router_takes_the_earliest_ready_step():
    assert choose(RouterSpec(kind="first"), STEPS, AFTER_S4).step.id == "S6"


def test_each_option_carries_its_own_failing_tests_and_recent_drops():
    recent = ["step S6 via jev 0.70: gate 'core' failed", "step S7 via jev 0.80: no strict gain (5 vs best 5)",
              "step S6 via fallback 0.40: gate 'core' failed", "step ?: worker: ollama call failed"]
    q = jev_request(JEV, ready(STEPS, AFTER_S4), AFTER_S4, "tail", recent)["questions"]["next_step"]
    assert q["criteria"]["S6"]["its_failing_tests"] == [P1 + "test_t5_gate::test_outside"]
    assert q["criteria"]["S6"]["its_recent_drops"] == ["gate 'core' failed", "gate 'core' failed"]
    assert q["criteria"]["S7"]["its_recent_drops"] == ["no strict gain (5 vs best 5)"]
    assert q["criteria"]["S7"]["aimed_at"] == ["tests/acceptance/phase1/test_t3_budget.py"]
    assert q["instructions"] == READY_INSTRUCTIONS


def _raw(steps):
    return {"mission": {"name": "demo", "goal": "g", "focus": ["plexus/**"], "frozen": ["tests/acceptance/**"]},
            "metric": {"kind": "command", "cmd": [PY, "-c", "print(1)"]},
            "gates": [{"name": "ok", "cmd": [PY, "-c", "pass"]}], "steps": steps}


def test_after_parses_and_names_only_earlier_steps():
    m = mission_from_dict(_raw([{"id": "A", "targets": ["t.py"], "text": "a"},
                                {"id": "B", "targets": ["u.py"], "text": "b", "after": ["A"]}]))
    assert [s.after for s in m.steps] == [[], ["A"]]
    for bad, why in [([{"id": "A", "targets": ["t.py"], "text": "a", "after": ["B"]},
                       {"id": "B", "targets": ["u.py"], "text": "b"}], "not an earlier step"),
                     ([{"id": "A", "targets": ["t.py"], "text": "a", "after": ["A"]}], "not an earlier step"),
                     ([{"id": "A", "targets": ["t.py"], "text": "a"},
                       {"id": "B", "targets": ["u.py"], "text": "b", "after": ["A", "A"]}], "must not repeat"),
                     ([{"id": "A", "targets": ["t.py"], "text": "a", "after": "S1"}], "list of step ids")]:
        with pytest.raises(MissionError, match=why):
            mission_from_dict(_raw(bad))


def test_readiness_holds_through_the_whole_chain():
    # Reviewer, 3eb25d5: readiness was checked one level deep. After S5 is kept, an attempt that
    # breaks S3 again leaves S4 passing, so S6 and S7 looked ready next to S3. `after` is now
    # closed at load, so a step two levels above a failing step is not ready either.
    m = mission_from_dict(_raw([
        {"id": "S3", "targets": ["tests/acceptance/phase1/test_t2_predicate_precision.py::test_bad"], "text": "a"},
        {"id": "S4", "targets": ["tests/acceptance/phase1/test_t5_gate.py::test_inside"], "text": "b", "after": ["S3"]},
        {"id": "S6", "targets": ["tests/acceptance/phase1/test_t5_gate.py::test_outside"], "text": "c", "after": ["S4"]},
    ]))
    assert [s.after for s in m.steps] == [[], ["S3"], ["S4", "S3"]]
    s3_broken_again = [ALL[0], ALL[2]]  # S3 fails again, S4 still passes, S6 still fails
    assert [s.id for s in ready(m.steps, s3_broken_again)] == ["S3"]


def test_a_mission_without_after_keeps_the_earliest_first_question():
    # With no prerequisites named, nothing makes the options ready, so the question must not
    # say they are (reviewer, 3eb25d5, finding 5).
    flat = [Step(s.id, s.targets, s.text) for s in STEPS]
    seen = []
    choose(JEV, flat, AFTER_S4, post=fake_jev("S6", 0.9, seen), api_key="k")
    # Compared whole: "ready" alone also sits in the earliest-first question ("already works").
    assert seen[0]["questions"]["next_step"]["instructions"] == ORDERED_INSTRUCTIONS
    seen.clear()
    choose(JEV, STEPS, AFTER_S4, post=fake_jev("S6", 0.9, seen), api_key="k")
    assert seen[0]["questions"]["next_step"]["instructions"] == READY_INSTRUCTIONS


def test_a_reason_holding_its_own_colons_is_attributed_whole():
    recent = ["step S6 via jev 0.70: worker: ollama call failed: TimeoutError: timed out"]
    q = jev_request(JEV, ready(STEPS, AFTER_S4), AFTER_S4, "tail", recent)["questions"]["next_step"]
    assert q["criteria"]["S6"]["its_recent_drops"] == ["worker: ollama call failed: TimeoutError: timed out"]
    assert q["criteria"]["S7"]["its_recent_drops"] == []


def test_a_drop_belongs_to_the_whole_step_id_only():
    # "step S60 via ..." is S60's line: a prefix match would also hand it to S6.
    steps = [Step("S6", STEPS[2].targets, "Publication gate."), Step("S60", STEPS[3].targets, "Rust budget.")]
    recent = ["step S60 via first: gate 'core' failed", "step S6 via first: no strict gain (5 vs best 5)"]
    crit = jev_request(JEV, steps, AFTER_S4, "tail", recent)["questions"]["next_step"]["criteria"]
    assert crit["S6"]["its_recent_drops"] == ["no strict gain (5 vs best 5)"]
    assert crit["S60"]["its_recent_drops"] == ["gate 'core' failed"]


@pytest.mark.parametrize("bad, why", [
    ({"id": "S 1", "targets": ["t.py"], "text": "a"}, "one token"),
    ({"id": "S1: x", "targets": ["t.py"], "text": "a"}, "one token"),
    ({"id": "S1", "targets": ["t.py"], "text": "a", "after": [1]}, "list of step ids"),
])
def test_step_ids_are_one_token_and_after_holds_ids(bad, why):
    with pytest.raises(MissionError, match=why):
        mission_from_dict(_raw([bad]))


def test_the_real_mission_offers_only_s3_while_s3_fails():
    # Run 12 attempt 1's real failing list: nine tests, S3's target among them. Under the old
    # router S8 was eligible here; now only S3 is ready, so Jev is not even asked.
    repo = Path(__file__).resolve().parents[2]
    m = load_mission(repo / "harness" / "plexus_loop" / "missions" / "acceptance.toml")
    failing = [P1 + "test_t2_predicate_precision::test_delta_threshold_and_cache[one-0.3-wakes-once]",
               P1 + "test_t2_predicate_precision::test_delta_threshold_and_cache[one-0.1-never-wakes]",
               P1 + "test_t2_predicate_precision::test_delta_threshold_and_cache[two-0.15-wake-once]",
               P1 + "test_t2_predicate_precision::test_bad_predicates_fail_at_registration",
               P1 + "test_t3_budget::test_budget_trips_then_mutes_visibly",
               P1 + "test_t4_provenance::test_grade_hint_is_attributed_to_the_neuron_layer",
               P1 + "test_t5_gate::test_write_outside_allowlist_is_dropped_and_flagged",
               P1 + "test_t5_gate::test_write_inside_allowlist_lands",
               P1 + "test_t6_truth::test_kill_both_processes_and_reopen"]
    assert m.router.kind == "jev" and [s.id for s in ready(m.steps, failing)] == ["S3"]
    # once S3 and S4 pass, only S5 is ready: S6 and S7 need its wake counting (T5-outside and
    # T3 assert h.wakes == 1). Once S5 passes too, S6 and S7 are ready together and S8 waits.
    after_s4 = [f for f in failing if "test_bad_predicates" not in f and "inside_allowlist" not in f]
    assert [s.id for s in ready(m.steps, after_s4)] == ["S5"]
    after_s5 = [f for f in after_s4 if "delta_threshold" not in f and "test_t4_provenance" not in f]
    assert [s.id for s in ready(m.steps, after_s5)] == ["S6", "S7"]
