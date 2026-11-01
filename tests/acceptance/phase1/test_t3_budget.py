"""T3 · Budget (Spec v2.1 §9, §6).

With budgetWakes=1 and budgetWindow=10, a second qualifying change at t+2s
produces no wake and no mute. The third and fourth qualifying changes are the
second and third consecutive trips, which mute the neuron with a visible flag.
"""

from __future__ import annotations

from tests.acceptance._support import TEMP, settle


def test_budget_trips_then_mutes_visibly(slice_):
    from pxr import Sdf

    pred = f"changed({TEMP}) AND delta({TEMP}) > 0.2"
    rt, h = slice_.start_neuron(predicate=pred, budget_wakes=1, budget_window=10.0)
    settle(rt)

    slice_.set_temperature(1.3)  # t+0: wakes
    settle(rt)
    assert h.wakes == 1

    slice_.clock.advance(2.0)  # t+2: first trip
    slice_.set_temperature(1.6)
    settle(rt)
    assert h.wakes == 1
    assert h.state != "muted"

    for v in (1.9, 2.2):  # t+4, t+6: second and third trips
        slice_.clock.advance(2.0)
        slice_.set_temperature(v)
        settle(rt)
    assert h.wakes == 1
    assert h.state == "muted"

    prim = rt.stage.GetPrimAtPath(h.prim_path)
    assert prim, "the neuron prim must exist on the runtime stage"
    assert prim.GetAttribute("plexus:state").Get() == "muted", "mute must be a visible opinion"
    flags = [a for a in prim.GetAttributes() if a.GetName().startswith("plexus:flag")]
    assert flags and any(a.Get() not in (None, "", False) for a in flags), "mute must be flagged"
    spec = rt.edit_layer.GetPropertyAtPath(h.prim_path.AppendProperty("plexus:state"))
    assert spec is not None and spec.default == "muted", "the mute lands in the neuron's own layer"
    assert isinstance(h.prim_path, Sdf.Path)
