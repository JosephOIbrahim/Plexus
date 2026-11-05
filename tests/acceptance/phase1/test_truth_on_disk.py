"""Disk · Truth on disk (Spec v2.1 §6 step 7 and States, §9 T6; CONTRACT: saved as it lands).

The stage is the record, so what a neuron did has to be in its layer's file. T3
reads the layer in memory, and T6's dumps agree when neither side wrote anything,
so every read here comes from a copy of the file: Sdf.Layer.FindOrOpen on the file
itself hands back the layer in memory, which would hide an unsaved write. Actions
that author nothing keep ctx.author's Save from flushing a write that forgot its own.

Only test_flag_names_are_the_stage_words pins flag names. Everything else reads
the plexus:flag prefix, so that one function can be left out and the rest hold.
"""

from __future__ import annotations

import inspect
import json
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from tests.acceptance._support import LOOK, NEURON_PARTICIPANT, PY, TEMP, child_env, settle

PREDICATE = f"changed({TEMP}) AND delta({TEMP}) > 0.2"
OUTSIDE = "/Exchange/projectA/Sneaky"
RELEASE = "Restart the neuron runtime to unmute it."
IDLE_S = 30.0  # only a box that stalls ever waits this long, and a stall is not what these tests judge


def on_disk(rt, h):
    """The neuron prim's attribute values as the file holds them. Runs here and in the child."""
    import shutil
    import tempfile

    from pxr import Sdf

    with tempfile.TemporaryDirectory() as d:
        copy = Path(d) / "copy.usda"
        shutil.copyfile(rt.edit_layer.realPath, copy)
        layer = Sdf.Layer.OpenAsAnonymous(str(copy))  # kept in a local: a spec from a dropped layer is expired
        spec = layer.GetPrimAtPath(str(h.prim_path))
        return {name: spec.attributes[name].default for name in spec.attributes.keys()} if spec else {}


def flags(attrs):
    """The non-empty plexus:flag… attributes, judged as T3 and T5 judge them."""
    return {k: v for k, v in attrs.items() if k.startswith("plexus:flag") and v not in (None, "", False)}


def start_budgeted(slice_, action):
    return slice_.start_neuron(predicate=PREDICATE, budget_wakes=1, budget_window=10.0, action=action)


def held_action():
    """An action that holds its wake open until the test lets go, so the order is forced with events."""
    entered, release = threading.Event(), threading.Event()

    def action(ctx):
        entered.set()
        release.wait(60)

    return entered, release, action


def trip_to_mute(slice_, rt):
    for v in (1.6, 1.9, 2.2):
        slice_.clock.advance(2.0)
        slice_.set_temperature(v)
        settle(rt, IDLE_S)


def run_to_mute(slice_, rt):
    """T3's sequence: one wake, then three trips."""
    settle(rt, IDLE_S)
    slice_.set_temperature(1.3)
    settle(rt, IDLE_S)
    trip_to_mute(slice_, rt)


def denied_then_muted(slice_):
    """The flags in the file after registering, after a dropped write and after a mute, on one neuron."""
    from pxr import Sdf

    def rogue(ctx):
        ctx.author(OUTSIDE, "note", "should never land", Sdf.ValueTypeNames.String)

    rt, h = start_budgeted(slice_, rogue)
    settle(rt, IDLE_S)
    registered = flags(on_disk(rt, h))
    slice_.set_temperature(1.3)
    settle(rt, IDLE_S)
    denied = flags(on_disk(rt, h))
    trip_to_mute(slice_, rt)
    return registered, denied, flags(on_disk(rt, h))


def test_registration_is_on_disk(slice_):
    rt, h = start_budgeted(slice_, lambda ctx: None)
    settle(rt, IDLE_S)

    attrs = on_disk(rt, h)
    held = {name: attrs.get(f"plexus:{name}") for name in ("scope", "predicate", "budgetWakes", "budgetWindow", "budgetTokens")}
    assert held == {"scope": LOOK, "predicate": PREDICATE, "budgetWakes": 1, "budgetWindow": 10.0, "budgetTokens": 0}, held
    prim = rt.stage.GetPrimAtPath(h.prim_path)
    assert prim.IsDefined() and prim.GetParent().IsDefined(), "the neuron prim and its ancestors must be def, not over"
    assert "PlexusNeuronAPI" in prim.GetAppliedSchemas(), prim.GetAppliedSchemas()


def test_quiesce_is_on_disk(slice_):
    rt, h = slice_.start_neuron(predicate=PREDICATE, action=lambda ctx: None)
    settle(rt, IDLE_S)
    time.sleep(1.01 - time.time() % 1)  # so a stamp from registration sits in an earlier second than any wake's
    before = datetime.now().astimezone().replace(microsecond=0)
    slice_.set_temperature(1.5)
    settle(rt, IDLE_S)

    attrs = on_disk(rt, h)
    assert attrs.get("plexus:state") == "dormant", "quiesce must leave state = dormant in the file"
    stamp = attrs.get("plexus:lastWake")
    assert stamp, "quiesce must leave plexus:lastWake in the file"
    when = datetime.fromisoformat(stamp).astimezone()  # raises on anything else, such as str(clock()); naive reads as local
    assert before <= when <= datetime.now().astimezone(), f"lastWake is not the wall-clock time of this wake: {stamp}"


def test_the_file_says_awake_while_the_action_runs(slice_):
    entered, release, action = held_action()
    rt, h = slice_.start_neuron(predicate=PREDICATE, action=action)
    settle(rt, IDLE_S)
    slice_.set_temperature(1.5)
    try:
        assert entered.wait(IDLE_S), "the wake never reached its action"
        state = on_disk(rt, h).get("plexus:state")  # nothing has called wait_idle since the write, so no Save hangs on that
    finally:
        release.set()
    assert state == "awake", f"a neuron running its action must read awake in the file: {state!r}"


def test_mute_is_on_disk(slice_):
    rt, h = start_budgeted(slice_, lambda ctx: None)
    run_to_mute(slice_, rt)

    attrs = on_disk(rt, h)
    assert attrs.get("plexus:state") == "muted", "the mute must be in the file"
    assert flags(attrs), "the mute's flag must be in the file"


def test_dropped_write_and_mute_keep_separate_flags(slice_):
    registered, denied, muted = denied_then_muted(slice_)
    record = {k: v for k, v in denied.items() if registered.get(k) != v}
    assert record, "a dropped write must put a record of its own in the file"
    assert record.items() <= muted.items(), "the mute must leave the dropped write's flag as it was"
    assert len(muted) > len(denied), "the mute must add a flag of its own"


def test_mute_outlives_the_running_action(slice_):
    entered, release, action = held_action()
    rt, h = start_budgeted(slice_, action)
    settle(rt, IDLE_S)
    slice_.set_temperature(1.3)
    try:
        assert entered.wait(IDLE_S), "the first wake never reached its action"
        # The action holds the wake open while trips arrive. The clock stands still, so every write
        # trips. Three trips mute, and the extra writes cover a pair that merged. The wait between
        # writes keeps one from landing on top of the mute's own.
        v = 1.3
        for _ in range(6):
            v += 0.3
            slice_.set_temperature(v)
            end = time.monotonic() + 0.3
            while h.state != "muted" and time.monotonic() < end:
                time.sleep(0.002)
            if h.state == "muted":
                break
        assert h.state == "muted", f"trips during a wake must count, and these left the neuron {h.state!r}, so no mute landed"
    finally:
        release.set()
    settle(rt, IDLE_S)

    file_says = on_disk(rt, h).get("plexus:state")
    stage_says = rt.stage.GetPrimAtPath(h.prim_path).GetAttribute("plexus:state").Get()
    assert (file_says, stage_says) == ("muted", "muted"), f"the action's quiesce must not write over a mute: file {file_says!r}, stage {stage_says!r}"


def test_flag_names_are_the_stage_words(slice_):
    _, denied, muted = denied_then_muted(slice_)
    assert "plexus:flag:publicationGate" in denied and "plexus:flag:budgetGate" not in denied, sorted(denied)
    assert "plexus:flag:publicationGate" in muted and "plexus:flag:budgetGate" in muted, sorted(muted)


RESTART = (
    r"""
import json, os, sys, time
from pathlib import Path
from pxr import Sdf
from plexus.core.neuron import NeuronRuntime
"""
    + inspect.getsource(on_disk)
    + r"""
exchange, a_layer, participant, name, scope, target, predicate = sys.argv[1:]
ran = []
rt = NeuronRuntime(Path(exchange), participant)
h = rt.register(name, scope=scope, predicate=predicate, action=lambda ctx: ran.append(1), budget_wakes=1, budget_window=10.0)
rt.start()
assert rt.wait_idle(30)
# Read before any wake: the wake's own quiesce would hide a mute that stayed.
state = [on_disk(rt, h).get("plexus:state"), rt.stage.GetPrimAtPath(h.prim_path).GetAttribute("plexus:state").Get()]
layer = Sdf.Layer.FindOrOpen(a_layer)  # the runtime only hears writers in its own process
layer.GetAttributeAtPath(target).default = 5.0
layer.Save()
time.sleep(0.01)
assert rt.wait_idle(30)
print("OUT " + json.dumps({"state": state, "ran": len(ran)}), flush=True)
os._exit(0)  # daemon threads and pxr's teardown are not under test
"""
)


def test_restart_really_unmutes(slice_):
    rt, h = start_budgeted(slice_, lambda ctx: None)
    run_to_mute(slice_, rt)
    # Read before the restart: an old flag may stay on the prim as history or go, and that is not pinned.
    held = flags(on_disk(rt, h))
    assert any(RELEASE in str(v) for v in held.values()), f"no flag in the file says {RELEASE!r}"
    file = Path(rt.edit_layer.realPath)
    as_killed = file.read_bytes()
    rt.stop()
    slice_.runtime = None
    file.write_bytes(as_killed)  # a kill runs no stop(), so only registering again may release the mute

    # A fresh process, because that is what the sentence tells an operator to do. It starts from the file alone.
    run = subprocess.run(
        [PY, "-c", RESTART, str(slice_.exchange), str(slice_.a_layer_path), NEURON_PARTICIPANT, h.name, LOOK, TEMP, PREDICATE],
        capture_output=True,
        text=True,
        errors="replace",
        env=child_env(),
        timeout=120,
    )
    line = next((x for x in run.stdout.splitlines() if x.startswith("OUT ")), "")
    assert line, f"the restart failed: {run.stderr[-2000:]}"
    after = json.loads(line[len("OUT ") :])
    assert after["state"] == ["dormant", "dormant"], f"registering again must release the mute, in the file and on the stage: {after['state']}"
    assert after["ran"] == 1, "a qualifying change must wake the restarted neuron and run its action"
