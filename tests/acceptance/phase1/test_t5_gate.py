"""T5 · Gate (Spec v2.1 §9, §7.3).

An action targeting a path outside the neuron's allowlist is dropped and
flagged on the neuron prim, and nothing lands in the membrane.
"""

from __future__ import annotations

from tests.acceptance._support import TEMP, settle

OUTSIDE = "/Exchange/projectA/Sneaky"


def test_write_outside_allowlist_is_dropped_and_flagged(slice_):
    from pxr import Sdf, Usd

    def rogue(ctx):
        ctx.author(OUTSIDE, "note", "should never land", Sdf.ValueTypeNames.String)

    rt, h = slice_.start_neuron(predicate=f"changed({TEMP})", action=rogue)
    settle(rt)
    slice_.set_temperature(1.5)
    settle(rt)
    assert h.wakes == 1

    xstage = Usd.Stage.Open(str(slice_.exchange))
    for layer in xstage.GetLayerStack(includeSessionLayers=False):
        assert layer.GetPrimAtPath(OUTSIDE) is None, f"{layer.identifier} received the write"
    assert not Usd.Stage.Open(str(slice_.project_b)).GetPrimAtPath(OUTSIDE)

    prim = rt.stage.GetPrimAtPath(h.prim_path)
    flags = [a for a in prim.GetAttributes() if a.GetName().startswith("plexus:flag")]
    assert flags and any(a.Get() not in (None, "", False) for a in flags), "denial must be flagged"


def test_write_inside_allowlist_lands(slice_):
    from pxr import Usd

    rt, _h = slice_.start_neuron(predicate=f"changed({TEMP})")
    settle(rt)
    slice_.set_temperature(1.5)
    settle(rt)
    assert Usd.Stage.Open(str(slice_.project_b)).GetPrimAtPath("/Exchange/lookNeuron/Hints")
