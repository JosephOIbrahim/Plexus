"""T1 · Propagation (Spec v2.1 §9).

An opinion authored in A's exchange sublayer is visible in B's composed value
in under 250 ms, p95 over 50 trials: author, notice, B recompose read.
"""

from __future__ import annotations

import threading
import time

from tests.acceptance._support import TEMP, p95

TRIALS = 50
BUDGET_S = 0.250


def test_a_to_b_visibility_p95_under_250ms(slice_):
    from plexus.core.axon import PlexusAxon
    from pxr import Sdf, Usd

    stage_b = Usd.Stage.Open(str(slice_.project_b))
    attr = stage_b.GetAttributeAtPath(Sdf.Path(TEMP))
    assert attr and attr.Get() == 1.0, "B must see A's opinion through the composed exchange"

    seen = threading.Event()
    want = {"v": None}

    def on_event(event):
        if want["v"] is not None and stage_b.GetAttributeAtPath(Sdf.Path(TEMP)).Get() == want["v"]:
            seen.set()

    axon = PlexusAxon(stage_b)
    axon.subscribe(on_event)
    axon.start()
    try:
        samples = []
        for i in range(TRIALS):
            value = 2.0 + i * 0.5
            seen.clear()
            want["v"] = value
            t0 = time.perf_counter()
            slice_.set_temperature(value)
            assert seen.wait(2.0), f"trial {i}: B never saw {value}"
            samples.append(time.perf_counter() - t0)
    finally:
        axon.cool()
    assert p95(samples) < BUDGET_S, f"p95 {p95(samples) * 1000:.1f} ms"
