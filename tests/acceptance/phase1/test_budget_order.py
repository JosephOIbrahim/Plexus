"""Budget order (Spec v2.1 §6, the wake path's strict order).

The predicate runs before the budget gate. A change the predicate rejects is not
a wake, so it spends nothing: not the neuron's budget, not the global one. T3
cannot see this, because every change it sends qualifies.
"""

from __future__ import annotations

from tests.acceptance._support import LOOK, NEURON_PARTICIPANT, TEMP, settle

PRED = f"changed({TEMP}) AND delta({TEMP}) > 0.2"
REJECTED = (1.05, 1.1, 1.15, 1.2)  # each within 0.2 of the 1.0 the fixture sets, so none matches


def test_a_rejected_change_spends_no_neuron_budget(slice_):
    rt, h = slice_.start_neuron(predicate=PRED, budget_wakes=1, budget_window=10.0)
    settle(rt)

    for v in REJECTED:
        slice_.clock.advance(1.0)
        slice_.set_temperature(v)
        settle(rt)
    assert h.wakes == 0
    assert h.state != "muted", "changes the predicate rejected must not mute the neuron"

    slice_.clock.advance(1.0)  # still inside the 10 s window
    slice_.set_temperature(1.5)
    settle(rt)
    assert h.wakes == 1, "the first change that matches must find the budget untouched"
    assert h.state != "muted"


def test_a_rejected_change_spends_no_global_budget(slice_):
    from plexus.core.neuron import NeuronRuntime

    rt = NeuronRuntime(slice_.exchange, NEURON_PARTICIPANT, clock=slice_.clock, global_wakes_per_min=3)
    h = rt.register("gradeHint", scope=LOOK, predicate=PRED, action=lambda ctx: None,
                    budget_wakes=100, budget_window=10.0)
    rt.start()
    slice_.runtime = rt
    settle(rt)

    for v in REJECTED:
        slice_.clock.advance(1.0)
        slice_.set_temperature(v)
        settle(rt)
    assert h.wakes == 0

    slice_.clock.advance(1.0)  # still inside the global minute
    slice_.set_temperature(1.5)
    settle(rt)
    assert h.wakes == 1, "changes the predicate rejected must not use up the global budget"
