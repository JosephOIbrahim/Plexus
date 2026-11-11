"""Lifecycle state · An organ's engine state on its prim: CONTRACT's publish_organ_state, Spec §6 and §9 T6, Blueprint 5.2 rules 6 and 7.

M3 puts an engine's lifecycle on the stage. The host measures its engine (CozyLifecycle does that, in test_organ_lifecycle.py) and hands
each measurement to NeuronRuntime.publish_organ_state(organ_id, state), which authors one token attribute, plexus:lifecycle, on the
organ prim /Plexus/Organs/<organId> that publish_organ defined, in the runtime's own edit layer, and saves it as it lands. A neuron in
this process scoped on the organ prim wakes on it. This file reads that through CONTRACT's surface and plain pxr only.

What this file pins:

- CONTRACT sentence 1: one token attribute, plexus:lifecycle, holding the state, saved as it lands; the prim's Sdf.Path is returned;
  the four states are "stopped", "starting", "ready" and "unavailable"; a neuron in this process scoped on the organ wakes on it.
- CONTRACT sentence 2: it writes only for an organ whose prim this runtime's own edit layer holds with PlexusOrganAPI; it authors
  nothing else on the prim; a later publish_organ of that organ leaves plexus:lifecycle as it is.
- CONTRACT sentence 3: a non-str organ id or state raises TypeError; a state outside the four, an organ id that is not a prim name,
  or an organ this runtime's edit layer has not published raises ValueError; each raises with nothing authored.
- Sentence 2's "imports nothing from plexus.organs and names no engine" is read by test_organ_registry.py's guard, already frozen.

Every case builds its own exchange in tmp_path and publishes the organ 'cozy' (ASCII, because a predicate cannot scope a non-ASCII
id) before it writes a state, so a method that authors nothing cannot pass, and every refusal case ends with a good call that has
to land. Every call to publish_organ_state runs on a daemon thread under PUBLISH_S, and every settle waits IDLE_S at most, so a
wrong method fails one test and leaves the run going. The file is read through a copy, because Sdf.Layer.FindOrOpen on the file
hands back the layer in memory and would hide an unsaved write.

Left open on purpose: whether the authoring sits in an Sdf.ChangeBlock; the order of the checks when a call is wrong in two ways;
the words of every message; cross-process wakes, which wait for T1b; and what a second runtime of the same participant does.
"""

from __future__ import annotations

import shutil
import tempfile
import threading
import time
from pathlib import Path

import pytest

ORGAN_ROOT = "/Plexus/Organs"
ORGAN = f"{ORGAN_ROOT}/cozy"
OTHER = f"{ORGAN_ROOT}/other"
ATTR = "plexus:lifecycle"
LIFECYCLE = f"{ORGAN}.{ATTR}"
READY = f'changed({LIFECYCLE}) AND attr({LIFECYCLE}) == "ready"'
STATES = ("stopped", "starting", "ready", "unavailable")

PUBLISH_S = 10.0  # one publish_organ_state call; a right one returns in milliseconds
IDLE_S = 10.0  # a runtime going idle after a write

SENTENCE_1 = (
    "CONTRACT, publish_organ_state(organ_id: str, state: str) -> Sdf.Path: it authors one token attribute, plexus:lifecycle, holding "
    "state, on /Plexus/Organs/<organId> in the edit layer and saves it as it lands, so a neuron in this process scoped on the organ wakes "
    "on it; state is one of 'stopped', 'starting', 'ready' or 'unavailable'."
)
SENTENCE_2 = (
    "CONTRACT: it writes only for an organ whose prim this runtime's own edit layer holds with PlexusOrganAPI, so publish_organ comes "
    "first; it authors nothing else (no API schema, none of the five PlexusOrganAPI attributes, no plexus:sourceLayer), a later "
    "publish_organ of that organ leaves plexus:lifecycle as it is, and it imports nothing from plexus.organs, names no engine and returns "
    "the prim's Sdf.Path."
)
SENTENCE_3 = (
    "CONTRACT: a non-str organ id or state raises TypeError; a state outside those four, an organ id that is not a valid prim name, or "
    "an organ this runtime's edit layer has not published raises ValueError; each raises with nothing authored."
)


def profile(organ_id="cozy", endpoint="http://127.0.0.1:1"):
    from plexus.organs.protocol import OrganProfile

    return OrganProfile(organ_id, "comfyui", endpoint, ["A"], "free")


@pytest.fixture
def runtimes():
    """Every NeuronRuntime a test builds, stopped at teardown."""
    made = []
    yield made
    for rt in made:
        try:
            rt.stop()
        except Exception:  # noqa: BLE001 - teardown must reach every runtime
            pass


def a_runtime(runtimes, exchange, participant="host"):
    from plexus.core.neuron import NeuronRuntime

    rt = NeuronRuntime(exchange, participant)
    runtimes.append(rt)
    return rt


def an_exchange(tmp_path, name="x"):
    from plexus.membrane.exchange import create_exchange

    return create_exchange(tmp_path / name / "shared" / "exchange")


def published(runtimes, tmp_path, *organ_ids):
    """A runtime 'host' on a fresh exchange that has published each organ id, 'cozy' when none is given."""
    rt = a_runtime(runtimes, an_exchange(tmp_path))
    for organ_id in organ_ids or ("cozy",):
        rt.publish_organ(profile(organ_id))
    return rt


def call_state(rt, organ_id, state):
    """rt.publish_organ_state(organ_id, state) on a daemon thread under PUBLISH_S. Returns {'value': ...} or {'raised': ...}."""
    if not hasattr(rt, "publish_organ_state"):
        raise AssertionError(f"NeuronRuntime has no method publish_organ_state. {SENTENCE_1} Add it to NeuronRuntime right after publish_organ.")
    box = {}

    def run():
        try:
            box["value"] = rt.publish_organ_state(organ_id, state)
        except BaseException as e:  # noqa: BLE001 - handed back to the test's own thread
            box["raised"] = e

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(PUBLISH_S)
    if thread.is_alive():
        raise AssertionError(
            f"rt.publish_organ_state({organ_id!r}, {state!r}) had not returned after {PUBLISH_S:g} s. It checks its arguments, takes "
            "self._lock, authors one attribute, saves and lets go, and waits on nothing else: no engine, no network, no gate."
        )
    return box


def set_state(rt, organ_id, state):
    """A call that has to land: what it returns, or an AssertionError naming what it raised."""
    box = call_state(rt, organ_id, state)
    if "raised" in box:
        e = box["raised"]
        raise AssertionError(
            f"rt.publish_organ_state({organ_id!r}, {state!r}) raised {type(e).__name__}: {e}, for an organ this runtime published and a "
            f"state of the four. {SENTENCE_1}"
        )
    return box.get("value")


def plain(value):
    return value if value is None or isinstance(value, (str, bytes, int, float)) else list(value)


def in_file(rt, prim_path=ORGAN):
    """What the edit layer's file holds at prim_path, from a copy. None when the file has no prim there."""
    from pxr import Sdf

    with tempfile.TemporaryDirectory() as d:
        copied = Path(d) / "copy.usda"
        shutil.copyfile(rt.edit_layer.realPath, copied)
        layer = Sdf.Layer.OpenAsAnonymous(str(copied))  # kept in a local: a spec from a dropped layer is expired
        spec = layer.GetPrimAtPath(prim_path)
        if not spec:
            return None
        return {
            "attrs": {name: (str(spec.attributes[name].typeName), plain(spec.attributes[name].default)) for name in spec.attributes.keys()},
            "prepended": [str(t) for t in spec.GetInfo("apiSchemas").prependedItems],
            "type": str(spec.typeName),
        }


def file_bytes(rt):
    file = Path(rt.edit_layer.realPath)
    return file.read_bytes() if file.exists() else None


def settled(*rts):
    time.sleep(0.15)
    for rt in rts:
        assert rt.wait_idle(IDLE_S), f"A runtime had not gone idle {IDLE_S:g} s after publish_organ_state. It takes self._lock, lets go of it, and runs no action itself."


def until(read, limit=IDLE_S, every=0.25):
    end = time.monotonic() + limit
    while True:
        value = read()
        if value or time.monotonic() > end:
            return value
        time.sleep(every)


# ---------- what lands, and where ----------


def test_a_state_lands_as_one_token_beside_the_profile(runtimes, tmp_path):
    from pxr import Sdf

    rt = published(runtimes, tmp_path)
    before = in_file(rt)
    assert before and len(before["attrs"]) == 5, f"publish_organ did not leave the five PlexusOrganAPI attributes at {ORGAN} in the file: {before}. That is M2's surface, which this file stands on."
    returned = set_state(rt, "cozy", "starting")
    held = in_file(rt)
    assert held is not None, f"{SENTENCE_1} The edit layer's file holds nothing at {ORGAN} after the call."
    extra = {name: v for name, v in held["attrs"].items() if name not in before["attrs"]}
    assert extra == {ATTR: ("token", "starting")}, (
        f"After publish_organ_state('cozy', 'starting') the file holds these attributes beyond the profile's five at {ORGAN}: {extra}, and it "
        f"holds exactly one, {ATTR} of type token with the value 'starting'. {SENTENCE_1} Author it with _set_attr(spec, '{ATTR}', state, "
        "Sdf.ValueTypeNames.Token) on the organ prim's spec in self.edit_layer, and call layer.Save() inside with self._lock."
    )
    kept = {name: v for name, v in held["attrs"].items() if name in before["attrs"]}
    assert kept == before["attrs"], f"publish_organ_state changed the profile's attributes: {kept}, against {before['attrs']}. {SENTENCE_2}"
    assert held["prepended"] == ["PlexusOrganAPI"] and held["type"] == "", (
        f"After publish_organ_state the organ prim's apiSchemas prepends {held['prepended']} and its type is {held['type']!r}, and they were "
        f"['PlexusOrganAPI'] and ''. {SENTENCE_2}"
    )
    assert isinstance(returned, Sdf.Path) and returned == Sdf.Path(ORGAN), (
        f"publish_organ_state returned {type(returned).__name__} {returned!r}, and it returns the organ prim's Sdf.Path, Sdf.Path('{ORGAN}'). "
        "Return the path itself, never str(path)."
    )
    on_stage = rt.stage.GetAttributeAtPath(LIFECYCLE)
    assert on_stage and on_stage.Get() == "starting", f"The runtime's own composed stage reads {LIFECYCLE} as {on_stage.Get() if on_stage else None!r}, and the call wrote 'starting'. {SENTENCE_1}"
    import plexus.core.neuron as neuron

    text = Path(neuron.__file__).read_text(encoding="utf-8")
    named = [w for w in ("plexus.organs", "comfy") if w in text.lower()]
    assert not named, (
        f"plexus/core/neuron.py holds {named}, in an import, an __import__ or importlib call, or a name. {SENTENCE_2} Take organ_id and "
        "state as plain strings; the lifecycle in plexus.organs calls the runtime, never the other way."
    )


def test_a_second_state_and_a_republish_each_leave_the_other_alone(runtimes, tmp_path):
    rt = published(runtimes, tmp_path)
    before = in_file(rt)
    set_state(rt, "cozy", "starting")
    set_state(rt, "cozy", "ready")
    held = in_file(rt)
    others = {name: v for name, v in held["attrs"].items() if name != ATTR}
    assert others == before["attrs"] and held["attrs"].get(ATTR) == ("token", "ready"), (
        f"After 'starting' then 'ready' the file holds {held['attrs']} at {ORGAN}. A second state replaces only {ATTR}, now ('token', 'ready'), "
        f"and the profile's five stay {before['attrs']}. {SENTENCE_2}"
    )
    rt.publish_organ(profile(endpoint="http://127.0.0.1:2"))
    again = in_file(rt)
    assert again["attrs"].get(ATTR) == ("token", "ready"), (
        f"A later publish_organ of 'cozy' left {ATTR} at {again['attrs'].get(ATTR)!r} in the file, and it stays ('token', 'ready'). "
        f"{SENTENCE_2} publish_organ_state never touches the five, and publish_organ never touches {ATTR}."
    )
    assert again["attrs"].get("plexus:endpoint", (None, None))[1] == "http://127.0.0.1:2", f"The republish's endpoint did not land: {again['attrs']}."


@pytest.mark.parametrize("state", STATES)
def test_each_of_the_four_states_lands(runtimes, tmp_path, state):
    rt = published(runtimes, tmp_path)
    set_state(rt, "cozy", state)
    held = in_file(rt)
    assert held["attrs"].get(ATTR) == ("token", state), f"publish_organ_state('cozy', {state!r}) left {held['attrs'].get(ATTR)!r} in the file. {SENTENCE_1}"


# ---------- what it refuses ----------

# case: (organ_id, state, the class it raises). Every organ id but 'other' is published first; 'other' never is.
BAD = {
    "a state outside the four": ("cozy", "running", ValueError),
    "a state given as an int": ("cozy", 1, TypeError),
    "an organ id of None": (None, "ready", TypeError),
    "an organ id that is not a prim name": ("1bad", "ready", ValueError),
    "a state in the wrong case": ("cozy", "Ready", ValueError),
    "the word failed, which is not a state": ("cozy", "failed", ValueError),
    "an organ this runtime never published": ("other", "ready", ValueError),
}


@pytest.mark.parametrize("case", sorted(BAD))
def test_a_call_that_cannot_land_raises_with_nothing_authored(runtimes, tmp_path, case):
    from pxr import Sdf

    organ_id, state, want = BAD[case]
    rt = published(runtimes, tmp_path)
    in_memory = rt.edit_layer.ExportToString()
    on_disk = file_bytes(rt)
    box = call_state(rt, organ_id, state)
    assert "raised" in box, f"publish_organ_state({organ_id!r}, {state!r}), {case}, returned {box.get('value')!r} and raised nothing. {SENTENCE_3}"
    error = box["raised"]
    assert type(error) is want, f"publish_organ_state({organ_id!r}, {state!r}), {case}, raised {type(error).__name__}: {error}, and it raises {want.__name__}. {SENTENCE_3}"
    assert rt.edit_layer.ExportToString() == in_memory and file_bytes(rt) == on_disk, (
        f"publish_organ_state raised for {case} after it had authored or saved. {SENTENCE_3} Check both types, the four states, "
        "Sdf.Path.IsValidIdentifier(organ_id) and, under self._lock, that self.edit_layer.GetPrimAtPath(path) prepends PlexusOrganAPI, "
        "all before anything is authored; never create the prim."
    )
    assert in_file(rt, OTHER) is None, f"publish_organ_state raised for {case} and the file holds a prim at {OTHER}. {SENTENCE_3}"
    returned = set_state(rt, "cozy", "ready")  # a method that refuses everything must not pass here
    assert returned == Sdf.Path(ORGAN) and in_file(rt)["attrs"].get(ATTR) == ("token", "ready"), (
        f"After the refusal, publish_organ_state('cozy', 'ready') in the same runtime left {in_file(rt)['attrs'].get(ATTR)!r} in the file and "
        f"returned {returned!r}. {SENTENCE_1}"
    )


def test_only_the_runtime_that_published_the_organ_writes_its_state(runtimes, tmp_path):
    """Blueprint 5.2 rule 6: a participant authors only what it owns. Another participant sees the organ, and cannot write its state."""
    exchange = an_exchange(tmp_path)
    a = a_runtime(runtimes, exchange, "host")
    a.publish_organ(profile())
    b = a_runtime(runtimes, exchange, "other")
    assert b.stage.GetPrimAtPath(ORGAN), f"Runtime 'other' reads no prim at {ORGAN} although 'host' published it. That is M2's surface, which this test stands on."
    b_memory, b_disk = b.edit_layer.ExportToString(), file_bytes(b)
    box = call_state(b, "cozy", "ready")
    assert "raised" in box and type(box["raised"]) is ValueError, (
        f"Runtime 'other', which never published 'cozy', called publish_organ_state('cozy', 'ready') and "
        f"{'raised ' + type(box['raised']).__name__ + ': ' + str(box['raised']) if 'raised' in box else 'it returned ' + repr(box.get('value'))}. "
        f"{SENTENCE_2} {SENTENCE_3} Read the prim from self.edit_layer, never from the composed stage, which holds every participant's organs."
    )
    assert b.edit_layer.ExportToString() == b_memory and file_bytes(b) == b_disk, f"The refused call changed runtime 'other''s edit layer. {SENTENCE_3}"
    set_state(a, "cozy", "ready")
    read = until(lambda: (b.stage.GetAttributeAtPath(LIFECYCLE) and b.stage.GetAttributeAtPath(LIFECYCLE).Get()) == "ready", IDLE_S)
    assert read, f"'host' wrote 'ready', and runtime 'other' in the same process does not read it on its composed stage within {IDLE_S:g} s. {SENTENCE_1}"


# ---------- who wakes ----------


def test_a_ready_wakes_each_ready_neuron_in_this_process_once(runtimes, tmp_path):
    """Every participant registers and both organs are published before either runtime starts, so no first write lands in the window
    (a first write by another participant under /Plexus can mark watched attributes changed; that hazard is M4's, DESIGN D5)."""
    exchange = an_exchange(tmp_path)
    host = a_runtime(runtimes, exchange, "host")
    host.publish_organ(profile())
    host.publish_organ(profile("other", "http://127.0.0.1:2"))
    second = a_runtime(runtimes, exchange, "second")
    seen_host, seen_second, seen_other = [], [], []
    h1 = host.register("watch", scope=ORGAN, predicate=READY, budget_wakes=10, budget_window=10.0,
                       action=lambda ctx: seen_host.append(host.stage.GetAttributeAtPath(LIFECYCLE).Get()))
    h2 = second.register("watch2", scope=ORGAN, predicate=READY, budget_wakes=10, budget_window=10.0,
                         action=lambda ctx: seen_second.append(second.stage.GetAttributeAtPath(LIFECYCLE).Get()))
    ho = host.register("elsewhere", scope=OTHER, predicate=f"changed({OTHER}.{ATTR})", budget_wakes=10, budget_window=10.0,
                       action=lambda ctx: seen_other.append(1))
    host.start()
    second.start()
    settled(host, second)
    set_state(host, "cozy", "starting")
    settled(host, second)
    assert (h1.wakes, h2.wakes, ho.wakes) == (0, 0, 0), (
        f"'starting' woke the ready-neurons {h1.wakes} and {h2.wakes} times and the neuron on {OTHER} {ho.wakes} times, and it wakes none: "
        f"their predicate asks for 'ready'. {SENTENCE_1} Author only {ATTR} on {ORGAN}."
    )
    set_state(host, "cozy", "ready")
    settled(host, second)
    assert (h1.wakes, h2.wakes) == (1, 1) and seen_host == ["ready"] and seen_second == ["ready"], (
        f"'ready' woke the writer's neuron {h1.wakes} times reading {seen_host} and the other runtime's {h2.wakes} times reading {seen_second}, "
        f"and it wakes each once, reading 'ready'. {SENTENCE_1} Author into self.edit_layer inside with self._lock and save, as publish_organ does."
    )
    set_state(host, "cozy", "ready")
    settled(host, second)
    assert (h1.wakes, h2.wakes, ho.wakes) == (1, 1, 0), (
        f"Writing 'ready' again left the ready-neurons at {h1.wakes} and {h2.wakes} wakes and the neuron on {OTHER} at {ho.wakes}, and they stay "
        "at 1, 1 and 0: the same value is no change, and no other organ's attribute moves. Author only the one attribute, on the named organ."
    )
    assert not host.stage.GetAttributeAtPath(f"{OTHER}.{ATTR}"), f"{OTHER} holds a {ATTR} although nobody wrote one for it. Author only on the organ named."
