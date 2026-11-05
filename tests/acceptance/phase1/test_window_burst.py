"""Window · Burst (Spec v2.1 §5, debounce window; §6, budget trips and un-mute).

The dispatcher drains with a debounce window, and events within the window
coalesce into one StageEvent with a merged path set. A window that closes early is
more than a slow axon: every extra event can be another wake charged to the budget,
three trips mute the neuron, and un-mute is operator-only (§6), so one burst can
silence it.

test_burst_with_the_budget_spent_does_not_mute runs at the runtime's own default
window and reads what the operator would see, a mute. A window opened by its first
event cannot split writes spanning S into more than 1 + S // W events, and load only
lengthens it, so the count of events cannot fail a real drain. A fixed tick or a
throttle can split them further, so its verdict here rests on phase and load, and
nothing is promised about it. The writes skip Save, so the span does not rest on the
disk. The one way a real drain can fail is a box too busy to fit any burst inside
the span limit, and it says so at the end instead of passing on nothing.

test_writes_inside_one_window_coalesce sets the window wider than all its writes and
spaces them GAP apart, so a window that closes on a quiet gap or a clamp under GAP,
or ignores debounce_s, hands back one event per write. A drain that keeps only part
of what it held, or groups by path, shows the same way. A quiet gap wider than GAP
merges them as a real window does, and is not told apart here.
"""

from __future__ import annotations

import time

from tests.acceptance._support import LOOK, TEMP, settle

WINDOW = 2.0
GAP = 0.55  # four writes this far apart sit inside WINDOW, and a quiet gap or a clamp under this splits all four
CHILD = LOOK + "/Child"

BURST_WRITES = 3  # each one a trip once the budget is spent, and three in a row mute
BURST_GAP_S = 0.04  # inside the window, and past a 10 ms quiet gap even when that wait comes back late
BURST_SPAN_LIMIT_S = 0.095  # three events need two whole windows between the first write and the last: 100 ms
BURST_ROUNDS = 3
BURST_TIME_LIMIT_S = 5.0  # a box too busy for one burst inside the limit in this long has shown nothing, and that is a fail


def nap_until(moment: float) -> None:
    """Short naps, not one long sleep: on a loaded box a 40 ms sleep comes back near 48 ms, which would stretch a burst."""
    while (left := moment - time.perf_counter()) > 0:
        time.sleep(min(left, 0.002))


def test_burst_with_the_budget_spent_does_not_mute(slice_):
    """Writes spaced inside the window are one change, or two across a window edge, and never three trips (§5, §6)."""
    value = 2.0
    counted = attempt = 0
    spans = []
    give_up = time.monotonic() + BURST_TIME_LIMIT_S
    while counted < BURST_ROUNDS and time.monotonic() < give_up:
        attempt += 1
        rt, h = slice_.start_neuron(
            predicate=f"changed({TEMP})",
            budget_wakes=1,
            budget_window=10.0,
            action=lambda ctx: None,
            name=f"burst{attempt}",
        )
        settle(rt)
        value += 0.5
        slice_.set_temperature(value)  # the one wake; the clock stands still, so every event after it trips
        settle(rt)  # no window left open by the wake's own writes, so the burst's first write opens the first window

        temperature = slice_.a_layer().GetAttributeAtPath(TEMP)
        start = time.perf_counter()
        for i in range(BURST_WRITES):
            nap_until(start + i * BURST_GAP_S)
            value += 0.5
            temperature.default = value
        span = time.perf_counter() - start
        spans.append(span)
        settle(rt)

        assert h.wakes == 1, f"a budget of one wake per 10 s woke {h.wakes} times"
        if span < BURST_SPAN_LIMIT_S:  # past it, three events are honest and a mute proves nothing
            assert h.state != "muted", f"{BURST_WRITES} writes over {span * 1000:.0f} ms counted as {BURST_WRITES} trips"
            counted += 1
        rt.stop()
        slice_.runtime = None
    assert counted, f"none of {attempt} bursts spanned under {BURST_SPAN_LIMIT_S * 1000:.0f} ms, the shortest {min(spans) * 1000:.0f} ms"


def test_writes_inside_one_window_coalesce(slice_):
    from plexus.core.axon import PlexusAxon
    from pxr import Sdf, Usd

    layer = slice_.a_layer()
    look = layer.GetPrimAtPath(LOOK)
    attrs = [layer.GetAttributeAtPath(TEMP)] + [Sdf.AttributeSpec(look, n, Sdf.ValueTypeNames.Double) for n in ("second", "third", "fourth")]
    want = {a.path for a in attrs}
    stage = Usd.Stage.Open(str(slice_.exchange))
    events = []
    axon = PlexusAxon(stage, debounce_s=WINDOW)
    axon.subscribe(events.append)

    def held():
        return set().union(*(e.paths for e in events))

    axon.start()
    try:
        start = time.monotonic()
        for i, attr in enumerate(attrs):
            time.sleep(GAP if i else 0)
            attr.default = 7.0  # no Save, so the verdict does not rest on the disk
            if i == 1:
                Sdf.CreatePrimInLayer(layer, CHILD)  # a resync, the other half of a merged event
        span = time.monotonic() - start
        deadline = time.monotonic() + WINDOW + 10.0
        while not want <= held() and time.monotonic() < deadline:  # a window still open has not spoken yet
            time.sleep(0.01)
    finally:
        axon.cool()

    assert want <= held(), f"lost inside the window: {sorted(map(str, want - held()))}"
    assert any(Sdf.Path(CHILD).HasPrefix(r) for e in events for r in e.resynced), "the resync inside the window was lost"
    # One split is forgiven. Past that, a window lasts at least WINDOW, so only a writer stalled for
    # span seconds can honestly need 1 + span / WINDOW events. No load can push a real window over this.
    allowed = max(2, 1 + int(span / WINDOW))
    assert len(events) <= allowed, f"{len(attrs)} writes in {span:.2f} s made {len(events)} events, window {WINDOW} s"
