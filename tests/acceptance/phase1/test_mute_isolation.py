"""A mute that cannot be saved (Spec v2.1 §6, the per-neuron wake path; a mute is "visible, never silent").

No other frozen test holds two neurons or a Save that fails. One neuron's refused
write stays that neuron's problem, and its mute still shows on the stage. A read-only
file is how a refused Save looks on Windows, the primary target; on POSIX the rename
succeeds, so these pass there without proving anything.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from tests.acceptance._support import LOOK, NEURON_PARTICIPANT, TEMP, settle

PRED = f"changed({TEMP}) AND delta({TEMP}) > 0.2"


def test_a_mute_that_cannot_be_saved_leaves_later_neurons_running(slice_):
    from plexus.core.neuron import NeuronRuntime

    rt = NeuronRuntime(slice_.exchange, NEURON_PARTICIPANT, clock=slice_.clock)
    a = rt.register("a", scope=LOOK, predicate=PRED, action=lambda ctx: None, budget_wakes=1, budget_window=10.0)
    b = rt.register("b", scope=LOOK, predicate=PRED, action=lambda ctx: None, budget_wakes=100, budget_window=10.0)
    rt.start()
    slice_.runtime = rt
    settle(rt)

    for v in (1.5, 2.0, 2.5):  # a: wake, trip, trip. b: three wakes.
        slice_.clock.advance(1.0)
        slice_.set_temperature(v)
        settle(rt)
    assert (a.wakes, b.wakes) == (1, 3)

    path = Path(rt.edit_layer.realPath)
    os.chmod(path, stat.S_IREAD)
    try:
        slice_.clock.advance(1.0)
        slice_.set_temperature(3.0)  # a's third trip, and its Save raises
        settle(rt)
        assert a.state == "muted"
        assert b.wakes == 4, "one neuron's failed mute write must not cost the next neuron its wake"
    finally:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)


def test_a_mute_that_cannot_be_saved_is_still_flagged_on_the_stage(slice_):
    rt, h = slice_.start_neuron(predicate=PRED, budget_wakes=1, budget_window=10.0)
    settle(rt)

    for v in (1.5, 2.0, 2.5):  # wake, trip, trip
        slice_.clock.advance(1.0)
        slice_.set_temperature(v)
        settle(rt)

    path = Path(rt.edit_layer.realPath)
    os.chmod(path, stat.S_IREAD)
    try:
        slice_.clock.advance(1.0)
        slice_.set_temperature(3.0)  # the third trip, and its Save raises
        settle(rt)
        prim = rt.stage.GetPrimAtPath(h.prim_path)
        assert h.state == "muted"
        assert prim.GetAttribute("plexus:state").Get() == "muted", "the mute must show on the stage"
        flags = [a for a in prim.GetAttributes() if a.GetName().startswith("plexus:flag")]
        assert flags and any(a.Get() not in (None, "", False) for a in flags), "the mute must be flagged even unsaved"
    finally:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
