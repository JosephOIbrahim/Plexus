"""T4 · Provenance (Spec v2.1 §9).

The grade_hint opinion's prim carries plexus:sourceLayer naming the neuron's
edit layer, and B's property stack shows the opinion came from that layer.
"""

from __future__ import annotations

from tests.acceptance._support import HINT_PRIM, TEMP, settle


def test_grade_hint_is_attributed_to_the_neuron_layer(slice_):
    from pxr import Sdf, Usd

    rt, h = slice_.start_neuron(predicate=f"changed({TEMP}) AND delta({TEMP}) > 0.2")
    settle(rt)
    slice_.set_temperature(1.5)
    settle(rt)
    assert h.wakes == 1

    stage_b = Usd.Stage.Open(str(slice_.project_b))
    prim = stage_b.GetPrimAtPath(HINT_PRIM)
    assert prim, "grade_hint must compose into project B"
    assert prim.GetAttribute("grade_hint").Get() == "warmer"
    src = prim.GetAttribute("plexus:sourceLayer").Get()
    assert src == rt.edit_layer.identifier

    stack = prim.GetAttribute("grade_hint").GetPropertyStack(Usd.TimeCode.Default())
    layers = {s.layer.identifier for s in stack}
    assert layers == {rt.edit_layer.identifier}, f"opinion came from {layers}"
    assert stage_b.GetRootLayer().GetPrimAtPath(HINT_PRIM) is None, "B itself authored nothing"
    assert isinstance(prim.GetPath(), Sdf.Path)
