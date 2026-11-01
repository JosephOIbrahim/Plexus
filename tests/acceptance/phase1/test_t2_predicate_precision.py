"""T2 · Predicate precision (Spec v2.1 §9, §4).

delta(/Exchange/LookState.temperature) > 0.2: a 0.3 change wakes the neuron
exactly once, a 0.1 change wakes it zero times, and two 0.15 changes wake it
once, because the delta cache updates only on wake.
"""

from __future__ import annotations

import pytest

from tests.acceptance._support import TEMP, settle

PRED = f"delta({TEMP}) > 0.2"


@pytest.mark.parametrize(
    "steps,wakes",
    [([0.3], 1), ([0.1], 0), ([0.15, 0.15], 1)],
    ids=["one-0.3-wakes-once", "one-0.1-never-wakes", "two-0.15-wake-once"],
)
def test_delta_threshold_and_cache(slice_, steps, wakes):
    rt, h = slice_.start_neuron(predicate=PRED)
    settle(rt)
    assert h.wakes == 0, "registering must not wake the neuron"
    value = 1.0
    for step in steps:
        value = round(value + step, 6)
        slice_.set_temperature(value)
        settle(rt)
    assert h.wakes == wakes
    assert h.state == "dormant"


def test_bad_predicates_fail_at_registration(slice_):
    from plexus.core.predicate import PredicateError

    with pytest.raises(PredicateError):
        slice_.start_neuron(predicate=f"delta({TEMP}) > 0.2 OR exists({TEMP})", name="orNeuron")
    with pytest.raises(PredicateError):
        slice_.start_neuron(predicate="changed(/Exchange/Elsewhere.x)", name="outOfScope")
