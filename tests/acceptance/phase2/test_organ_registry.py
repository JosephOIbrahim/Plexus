"""Registry · An organ on the stage: Spec v2.1 §3 PlexusOrganAPI, §6 and §9 T6, CONTRACT's publish_organ, Spec §10 T8.

M2 puts organs on the stage. The host hands NeuronRuntime.publish_organ(profile) an organ's profile, usually once at
startup with organ.profile(), the way it calls register(), and the runtime defines one PlexusOrganAPI prim in its own
edit layer, so a neuron reading the composed exchange, in any participant's runtime, sees the engine. This file reads
that through CONTRACT's surface and plain pxr, so it holds whatever shape the method's code takes. One test reaches past
that surface: it stands a recording lock in for rt._lock, the RLock that _Ctx.author and _Ctx.author_asset already save
under, to see the file hold the organ before the lock is let go.

Where each thing comes from:

- Spec §3: the five PlexusOrganAPI attributes, their types, and the allowed tokens of plexus:kind and plexus:costHint.
  test_t0_schema_gate.py lists them, and this file reads its list rather than keep a second one.
- Spec §6 and CONTRACT: the runtime's opinions land only in its edit layer and are saved as they land, and a missing
  ancestor is def, not over. _Ctx.author and _Ctx.author_asset save inside self._lock, and publish_organ, which may run
  while neurons do, does too.
- Spec §9 T6: the stage is the record, so a fresh process reads the organ from the file.
- Spec §10 T8 and CONTRACT: the core is blind to the engine, so neuron.py reads the profile by attribute name, imports
  nothing from plexus.organs and names no organ kind. The allowed tokens are whatever Usd.SchemaRegistry holds, which
  the unregistered-schema and widened-registry tests prove by behaviour and the guard by text.
- CONTRACT: a field of the wrong type raises TypeError, a token outside the schema or an organ id that is not a prim name
  raises ValueError, a registry without PlexusOrganAPI raises RuntimeError, any other value Sdf cannot hold raises, and
  each raises with nothing authored. A value of the right type that the schema allows lands as is: no coercion, no
  case folding, no stripping, and capabilities sorted by code point, as Python's sorted() orders them.

Every profile is built by hand through OrganProfile. No engine, fake or real, is asked anything, because publish_organ
never calls into an organ. Every refusal test first lands a good publish, so a method that authors nothing cannot pass,
and then refuses on a new organ id, so a method that authors part of a profile before it refuses cannot hide behind
opinions identical to the first publish's.

Every wait has a limit, so a wrong method fails one test and leaves the run going: each publish runs on a daemon thread
under PUBLISH_S, each settle waits IDLE_S at most, and each child process CHILD_S.

Left open on purpose: what composes when two participants publish one organ id (CONTRACT says the stronger sublayer's
opinion does, and this file publishes from one runtime only); the placement root, which this file names once, in
ORGAN_ROOT, so a flip to /Exchange/<participant>/Organs changes that one line here; whether the authoring sits in an
Sdf.ChangeBlock, which no reader of the stage or the file can tell apart; the order the five attributes are authored in,
which the file shows but every reader ignores, because USD reads an attribute by name; and the words of every message.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import tempfile
import threading
import time
import types
from enum import Enum
from pathlib import Path

import pytest

from tests.acceptance._support import NEURON_PARTICIPANT, PY, REPO, child_env
from tests.acceptance.phase1.test_t0_schema_gate import SCHEMAS

ORGAN_ROOT = "/Plexus/Organs"
ORGAN = f"{ORGAN_ROOT}/cozy"
OTHER = f"{ORGAN_ROOT}/other"
FRESH = f"{ORGAN_ROOT}/fresh"
URL = "http://127.0.0.1:8188"
PREDICATE = "delta(/Exchange/LookState.temperature) > 0.2"
NEURON_PY = REPO / "plexus" / "core" / "neuron.py"
# Spec §3, PlexusOrganAPI: each attribute and its type, read from T0's table.
FIVE = {name: type_name for name, type_name, _tokens in SCHEMAS["PlexusOrganAPI"]}
KINDS = next(tokens for name, _type_name, tokens in SCHEMAS["PlexusOrganAPI"] if name == "plexus:kind")
COSTS = next(tokens for name, _type_name, tokens in SCHEMAS["PlexusOrganAPI"] if name == "plexus:costHint")

PUBLISH_S = 10.0  # one publish_organ call; a right one returns in milliseconds
IDLE_S = 10.0  # the runtime going idle after a publish
CHILD_S = 60.0  # one child interpreter


def profile(organ_id="cozy", kind="comfyui", endpoint=URL, capabilities=None, cost_hint="free"):
    """An OrganProfile built by hand. Nothing here checks or converts a field, so a test can hand in a wrong one."""
    from plexus.organs.protocol import OrganProfile

    caps = ["Zeta", "Alpha", "Mid"] if capabilities is None else capabilities
    return OrganProfile(organ_id=organ_id, kind=kind, endpoint=endpoint, capabilities=caps, cost_hint=cost_hint)


def fresh(**fields):
    """An OrganProfile for the organ id 'fresh', which no test has published, with every field as given: capabilities=None
    stays None here, where profile() reads it as its default list."""
    from plexus.organs.protocol import OrganProfile

    given = {"organ_id": "fresh", "kind": "comfyui", "endpoint": URL, "capabilities": ["Alpha"], "cost_hint": "free", **fields}
    return OrganProfile(**given)


def a_runtime(slice_):
    """The neuron participant's runtime, not started, so nothing but publish_organ saves its edit layer."""
    from plexus.core.neuron import NeuronRuntime

    rt = NeuronRuntime(slice_.exchange, NEURON_PARTICIPANT, clock=slice_.clock)
    slice_.runtime = rt
    return rt


def publish(rt, prof):
    """rt.publish_organ(prof) on a daemon thread, so a method that never returns fails this test and leaves the run going. What it raises is raised here as it was."""
    box = {}

    def run():
        try:
            box["value"] = rt.publish_organ(prof)
        except BaseException as e:  # noqa: BLE001 - handed back to the test's own thread below
            box["raised"] = e

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(PUBLISH_S)
    if thread.is_alive():
        raise AssertionError(
            f"rt.publish_organ(profile) had not returned after {PUBLISH_S:g} s. It takes self._lock, authors, saves and lets go, "
            "and waits on nothing else: no organ call, no network, no gate."
        )
    if "raised" in box:
        raise box["raised"]
    return box.get("value")


def raised_by(call, broken):
    """The exception call raises. broken names the fault, for the failure text."""
    try:
        value = call()
    except AssertionError:
        raise
    except Exception as e:  # noqa: BLE001 - the class is judged by the caller
        return e
    raise AssertionError(f"publish_organ returned {value!r} for {broken} and raised nothing. CONTRACT: a profile that cannot land raises, with nothing authored.")


def plain(value):
    """A value read from Sdf as plain Python: an array becomes a list."""
    return value if value is None or isinstance(value, (str, bytes, int, float)) else list(value)


def in_file(rt, prim_path):
    """What the edit layer's file holds at prim_path, from a copy, because Sdf.Layer.FindOrOpen on the file hands back
    the layer in memory and would hide an unsaved write. None when the file has no prim there."""
    from pxr import Sdf

    with tempfile.TemporaryDirectory() as d:
        copied = Path(d) / "copy.usda"
        shutil.copyfile(rt.edit_layer.realPath, copied)
        layer = Sdf.Layer.OpenAsAnonymous(str(copied))  # kept in a local: a spec from a dropped layer is expired
        spec = layer.GetPrimAtPath(prim_path)
        if not spec:
            return None
        defined = {}
        for prefix in Sdf.Path(prim_path).GetPrefixes():
            held = layer.GetPrimAtPath(prefix)
            defined[str(prefix)] = bool(held) and held.specifier == Sdf.SpecifierDef
        return {
            "attrs": {name: (str(spec.attributes[name].typeName), plain(spec.attributes[name].default)) for name in spec.attributes.keys()},
            "prepended": [str(t) for t in spec.GetInfo("apiSchemas").prependedItems],
            "defined": defined,
            "type": str(spec.typeName),
        }


def landed(rt, prim_path=ORGAN):
    held = in_file(rt, prim_path)
    assert held, (
        f"publish_organ returned and the edit layer's file holds nothing at {prim_path}. CONTRACT: it defines the organ prim in the edit layer "
        "and saves it as it lands. Author into self.edit_layer, never the stage's root layer, run no publication gate, because "
        f"{ORGAN_ROOT} is the runtime's own record as register() writes /Plexus/Neurons, and call layer.Save() inside with self._lock, "
        "after the ChangeBlock."
    )
    return held


def settled(slice_, rt):
    time.sleep(0.01)
    if not rt.wait_idle(IDLE_S):
        slice_.runtime = None  # stop() would wait on the stuck runtime too
        raise AssertionError(f"The runtime had not gone idle {IDLE_S:g} s after publish_organ, so the publish left it busy. publish_organ takes self._lock, lets go of it, and wakes no neuron.")


def in_a_child(script, *args, env=None):
    try:
        return subprocess.run([PY, "-c", script, *(str(a) for a in args)], capture_output=True, text=True, errors="replace", env=env or child_env(), timeout=CHILD_S)
    except subprocess.TimeoutExpired as e:
        raise AssertionError(f"A child process had not finished after {CHILD_S:g} s. Its stderr ends: {str(e.stderr)[-400:]}") from None


def out_line(run):
    return next((x for x in run.stdout.splitlines() if x.startswith("OUT ")), "")


# ---------- what lands, and where ----------


def test_a_published_organ_is_in_the_file_with_the_schemas_types(slice_):
    from pxr import Sdf

    rt = a_runtime(slice_)
    returned = publish(rt, profile())
    held = landed(rt)
    typed = {name: type_name for name, (type_name, _value) in held["attrs"].items()}
    assert typed == FIVE, (
        f"Spec §3 gives PlexusOrganAPI exactly five attributes, {FIVE}, and the file holds {typed} at {ORGAN}. CONTRACT: publish_organ "
        "authors those five and nothing else, no plexus:sourceLayer and no flag, each through _set_attr with its Sdf.ValueTypeNames type."
    )
    assert held["prepended"] == ["PlexusOrganAPI"], (
        f"The organ prim's apiSchemas prepends {held['prepended']} in the file. Apply the schema at Sdf level with "
        "spec.SetInfo('apiSchemas', Sdf.TokenListOp.Create(prependedItems=['PlexusOrganAPI']))."
    )
    assert held["type"] == "", (
        f"The organ prim is typed {held['type']!r} in the file. CONTRACT: publish_organ authors the five attributes and the applied API "
        "schema and nothing else, so the prim stays untyped: leave spec.typeName alone."
    )
    loose = sorted(path for path, is_def in held["defined"].items() if not is_def)
    assert not loose, (
        f"CONTRACT: publish_organ defines, def and not over, every missing ancestor, and these are not def in the file: {loose}. "
        "Set each of path.GetPrefixes() to Sdf.SpecifierDef inside the ChangeBlock, as ctx.author does."
    )
    assert isinstance(returned, Sdf.Path) and returned == Sdf.Path(ORGAN), (
        f"CONTRACT: publish_organ returns the organ prim's Sdf.Path, Sdf.Path('{ORGAN}') here, and it returned {type(returned).__name__} {returned!r}. "
        "Return the path itself, never str(path): an Sdf.Path compares equal to its text, so only the type tells them apart."
    )


def test_each_organ_attribute_holds_the_profiles_value(slice_):
    rt = a_runtime(slice_)
    endpoint = "http://organ.example:9000"
    publish(rt, profile(kind="houdini", endpoint=endpoint, capabilities=["Zeta", "Alpha", "Mid", "Alpha"], cost_hint="expensive"))
    prim = rt.stage.GetPrimAtPath(ORGAN)
    assert prim, f"publish_organ returned and the composed exchange has no prim at {ORGAN}. CONTRACT: the organ prim's name is the organ id, under {ORGAN_ROOT}."
    got = {name: plain(prim.GetAttribute(name).Get()) for name in FIVE}
    want = {
        "plexus:organId": "cozy",
        "plexus:kind": "houdini",
        "plexus:endpoint": endpoint,
        "plexus:capabilities": ["Alpha", "Alpha", "Mid", "Zeta"],
        "plexus:costHint": "expensive",
    }
    wrong = {name: got[name] for name in want if got[name] != want[name]}
    assert not wrong, (
        f"Each PlexusOrganAPI attribute holds its profile field as is, and these read otherwise: {wrong}, against {want}. "
        "plexus:capabilities is sorted(profile.capabilities), a new list in ascending code-point order with every duplicate kept."
    )


class Kind(str, Enum):
    """A str subclass, as a host's own enum of organ kinds may be. isinstance(Kind.COMFYUI, str) is True, so it is a str and lands as its value."""

    COMFYUI = "comfyui"


# case: (profile fields, the attribute to read, what the file holds there). The organ prim is ORGAN_ROOT/<organ id>.
AS_IS = {
    "capabilities given as a tuple": ({"capabilities": ("Zeta", "Alpha")}, "plexus:capabilities", ["Alpha", "Zeta"]),
    "capabilities in mixed case": ({"capabilities": ["b", "a", "b", "C"]}, "plexus:capabilities", ["C", "a", "b", "b"]),
    "capabilities with spaces": ({"capabilities": [" b", "a "]}, "plexus:capabilities", [" b", "a "]),
    "no capabilities": ({"capabilities": []}, "plexus:capabilities", []),
    "an empty endpoint": ({"endpoint": ""}, "plexus:endpoint", ""),
    "an endpoint with a trailing slash": ({"endpoint": URL + "/"}, "plexus:endpoint", URL + "/"),
    "a kind in camel case": ({"kind": "neuralPreview"}, "plexus:kind", "neuralPreview"),
    "a kind given as a str enum member": ({"kind": Kind.COMFYUI}, "plexus:kind", "comfyui"),
    "an organ id with a capital and a digit": ({"organ_id": "Cozy_2"}, "plexus:organId", "Cozy_2"),
    "an organ id with a leading underscore": ({"organ_id": "_x"}, "plexus:organId", "_x"),
    "an organ id beyond ASCII": ({"organ_id": "über"}, "plexus:organId", "über"),
}


@pytest.mark.parametrize("case", sorted(AS_IS))
def test_a_value_at_the_edge_lands_as_is(slice_, case):
    from pxr import Sdf

    fields, name, want = AS_IS[case]
    rt = a_runtime(slice_)
    returned = publish(rt, profile(**fields))
    path = f"{ORGAN_ROOT}/{fields.get('organ_id', 'cozy')}"
    assert isinstance(returned, Sdf.Path) and returned == Sdf.Path(path), (
        f"For {case}, publish_organ returned {type(returned).__name__} {returned!r}, and the organ prim is Sdf.Path('{path}'). "
        "CONTRACT: the prim's name is the organ id as given, never lower-cased, sanitized or rewritten; Sdf.Path.IsValidIdentifier is the only test of it."
    )
    got = landed(rt, path)["attrs"].get(name, (None, None))[1]
    assert got == want, (
        f"For {case}, the file holds {name} {got!r}, and the profile's value lands as {want!r}. CONTRACT: a value of the right type that the schema "
        "allows lands as is. Check with isinstance, never type() is, and never coerce, case-fold, strip or dedupe; capabilities may be a list "
        "or a tuple, may be empty, and land as sorted(capabilities), Python's code-point order, where every capital comes before every lower-case letter."
    )


def test_every_participant_sees_the_organ_on_the_composed_exchange(slice_):
    from pxr import Sdf, Usd

    from plexus.core.neuron import NeuronRuntime

    rt = a_runtime(slice_)
    publish(rt, profile())
    other = NeuronRuntime(slice_.exchange, "otherNeuron")
    for who, stage in ((f"{NEURON_PARTICIPANT}, the publisher", rt.stage), ("otherNeuron, another participant", other.stage)):
        prim = stage.GetPrimAtPath(ORGAN)
        assert prim and prim.IsDefined(), (
            f"{who} reads no defined prim at {ORGAN} on the composed exchange. CONTRACT: a neuron in any participant's runtime sees the organ, "
            "so it is def, not over, in the publisher's edit layer, which exchange.usda sublayers."
        )
        loose = [str(p) for p in Sdf.Path(ORGAN).GetPrefixes() if not stage.GetPrimAtPath(p).IsDefined()]
        assert not loose, f"{who} reads these ancestors of the organ as undefined: {loose}. Set each prefix's specifier to Sdf.SpecifierDef."
        assert "PlexusOrganAPI" in prim.GetAppliedSchemas(), f"{who} reads applied schemas {list(prim.GetAppliedSchemas())} on the organ prim, without PlexusOrganAPI."
        assert prim.GetAttribute("plexus:endpoint").Get() == URL, f"{who} reads plexus:endpoint {prim.GetAttribute('plexus:endpoint').Get()!r}, and the profile said {URL}."
    project_b = Usd.Stage.Open(str(slice_.project_b))  # held in a local: a prim of a dropped stage reads as no prim
    in_b = bool(project_b.GetPrimAtPath(ORGAN))
    assert in_b == ORGAN_ROOT.startswith("/Exchange/"), (
        f"Project B composes only /Exchange from the exchange, so it should{'' if ORGAN_ROOT.startswith('/Exchange/') else ' not'} hold {ORGAN}, "
        f"and it {'does' if in_b else 'does not'}. The organ belongs under {ORGAN_ROOT} and nowhere else."
    )


COLD_READ = r"""
import json, os, sys
from pxr import Usd
stage = Usd.Stage.Open(sys.argv[1])
prim = stage.GetPrimAtPath(sys.argv[2])
if not prim:
    out = {"found": False}
else:
    caps = prim.GetAttribute("plexus:capabilities").Get()
    out = {"found": True, "defined": prim.IsDefined(), "schemas": list(prim.GetAppliedSchemas()), "kind": prim.GetAttribute("plexus:kind").Get(),
           "caps": None if caps is None else list(caps)}
print("OUT " + json.dumps(out), flush=True)
os._exit(0)
"""


def test_a_fresh_process_reads_the_organ_from_the_exchange(slice_):
    from plexus.schema import plugin_dir

    rt = a_runtime(slice_)
    publish(rt, profile())
    env = child_env()
    env["PXR_PLUGINPATH_NAME"] = str(plugin_dir())
    run = in_a_child(COLD_READ, slice_.exchange, ORGAN, env=env)
    line = out_line(run)
    assert line, f"A fresh process could not read the exchange at all. Its stderr ends: {run.stderr[-600:]}"
    got = json.loads(line[len("OUT ") :])
    want = {"found": True, "defined": True, "schemas": ["PlexusOrganAPI"], "kind": "comfyui", "caps": ["Alpha", "Mid", "Zeta"]}
    assert got == want, (
        f"The stage is the record (Spec §9 T6), and a fresh process opening exchange.usda reads {got} at {ORGAN}, against {want}. "
        "Save the edit layer inside the lock as the organ lands, define every ancestor, and sort the capabilities."
    )


def test_a_second_publish_replaces_every_value_and_leaves_other_organs(slice_):
    rt = a_runtime(slice_)
    publish(rt, profile(capabilities=["Alpha", "Beta", "Gamma"]))
    publish(rt, profile(organ_id="other", capabilities=["Keep"]))
    publish(rt, profile(kind="houdini", endpoint="http://127.0.0.1:8189", capabilities=["Beta"], cost_hint="cheap"))
    held = landed(rt)
    values = {name: value for name, (_type_name, value) in held["attrs"].items()}
    want = {
        "plexus:organId": "cozy",
        "plexus:kind": "houdini",
        "plexus:endpoint": "http://127.0.0.1:8189",
        "plexus:capabilities": ["Beta"],
        "plexus:costHint": "cheap",
    }
    assert values == want, (
        f"CONTRACT: a second publish of one organ id replaces all five values in the edit layer, and the file holds {values}, against {want}. "
        "Set each attribute's default through _set_attr, which reuses the spec, so every value, the kind included, is the new profile's, "
        "capabilities are replaced whole and never merged, and nothing beyond the five is authored."
    )
    assert held["prepended"] == ["PlexusOrganAPI"], f"After a second publish the organ prim's apiSchemas prepends {held['prepended']} in the file. SetInfo replaces the list op, so it reads ['PlexusOrganAPI']."
    applied = list(rt.stage.GetPrimAtPath(ORGAN).GetAppliedSchemas())
    assert applied.count("PlexusOrganAPI") == 1, f"After a second publish the composed organ prim reads applied schemas {applied}, and PlexusOrganAPI belongs there once."
    other = in_file(rt, OTHER)
    kept = other and other["attrs"].get("plexus:capabilities", (None, None))[1]
    assert kept == ["Keep"], (
        f"Publishing cozy again left {OTHER} holding capabilities {kept!r} in the file, and it held ['Keep']. A publish touches only its own organ prim: "
        f"it deletes or clears nothing under {ORGAN_ROOT}."
    )


# ---------- what it refuses ----------

# broken: (a call that builds the profile, the class it raises). Each builds afresh, so a generator is new for every run.
# Every profile but the two with a bad organ id is for the organ id 'fresh', which the test's first, good publish never used.
BAD = {
    "a kind outside the allowed tokens": (lambda: fresh(kind="notAnEngine"), ValueError),
    "a kind in the wrong case": (lambda: fresh(kind="ComfyUI"), ValueError),
    "a cost hint outside the allowed tokens": (lambda: fresh(cost_hint="pricey"), ValueError),
    "an organ id that is not a prim name": (lambda: fresh(organ_id="cozy-organ"), ValueError),
    "an empty organ id": (lambda: fresh(organ_id=""), ValueError),
    "an organ id given as bytes": (lambda: fresh(organ_id=b"fresh"), TypeError),
    "capabilities given as one str": (lambda: fresh(capabilities="abc"), TypeError),
    "capabilities that are not strs": (lambda: fresh(capabilities=[1, 2]), TypeError),
    "capabilities of None": (lambda: fresh(capabilities=None), TypeError),
    "capabilities given as a set": (lambda: fresh(capabilities={"Alpha"}), TypeError),
    "capabilities given as a generator": (lambda: fresh(capabilities=(c for c in ["Alpha"])), TypeError),
    "an endpoint of None": (lambda: fresh(endpoint=None), TypeError),
    "an endpoint that is an int": (lambda: fresh(endpoint=8188), TypeError),
    "a kind of None": (lambda: fresh(kind=None), TypeError),
    "a cost hint of None": (lambda: fresh(cost_hint=None), TypeError),
    "a cost hint given as bytes": (lambda: fresh(cost_hint=b"free"), TypeError),
    "a profile without cost_hint": (lambda: types.SimpleNamespace(organ_id="fresh", kind="comfyui", endpoint=URL, capabilities=["Alpha"]), AttributeError),
    "an endpoint Sdf cannot encode": (lambda: fresh(endpoint=URL + "/\ud800"), Exception),
    "a capability Sdf cannot encode": (lambda: fresh(capabilities=["Alpha", "B\ud800"]), Exception),
}
WHY = {
    ValueError: "CONTRACT: a kind or cost hint outside the allowed tokens that Usd.SchemaRegistry holds for PlexusOrganAPI, compared case and all, or an organ id that is not a valid prim name (Sdf.Path.IsValidIdentifier), raises ValueError.",
    TypeError: "CONTRACT: a field of the wrong type raises TypeError. organ_id, kind, endpoint and cost_hint are each a str, and capabilities a list or tuple of str; check with isinstance and never coerce, because Sdf lands None on a string silently and bytes on a string as text.",
    AttributeError: "publish_organ reads the five fields by attribute name, profile.cost_hint among them, with no getattr default, so a profile without one raises AttributeError.",
    Exception: "CONTRACT: any other value Sdf cannot hold raises, and the class is Sdf's. A lone surrogate is a str and passes every isinstance check, and only Sdf refuses it.",
}


@pytest.mark.parametrize("broken", sorted(BAD))
def test_a_profile_that_cannot_land_raises_with_nothing_authored(slice_, broken):
    rt = a_runtime(slice_)
    publish(rt, profile())  # a method that lands nothing must not pass here: this one has to land
    landed(rt)
    in_memory = rt.edit_layer.ExportToString()
    file = Path(rt.edit_layer.realPath)
    on_disk = file.read_bytes()
    build, want = BAD[broken]
    bad = build()
    error = raised_by(lambda: publish(rt, bad), broken)
    assert isinstance(error, want), f"publish_organ raised {type(error).__name__}: {error} for {broken}, and the class is not free. {WHY[want]}"
    assert rt.edit_layer.ExportToString() == in_memory, (
        f"publish_organ raised for {broken} after it had authored into the edit layer in memory. Every check finishes before anything is authored: "
        "read and check all five fields, the allowed tokens included, then probe them on a scratch Sdf.Layer.CreateAnonymous(), let what Sdf raises "
        "there propagate, and only then take self._lock."
    )
    assert file.read_bytes() == on_disk, f"publish_organ raised for {broken} and the edit layer's file changed. A profile that cannot land raises with nothing authored and nothing saved."
    assert in_file(rt, FRESH) is None, f"publish_organ raised for {broken} and the edit layer's file holds a prim at {FRESH}. A refused profile leaves no part of itself behind."


UNREGISTERED = r"""
import os, sys
from pathlib import Path
from pxr import Usd
Usd.SchemaRegistry()  # built before plexus is imported, so it never learns Plexus's schemas
from plexus.membrane.exchange import create_exchange
from plexus.core.neuron import NeuronRuntime
from plexus.organs.protocol import OrganProfile
rt = NeuronRuntime(create_exchange(Path(sys.argv[1])), "lookNeuron")
before = rt.edit_layer.ExportToString()
try:
    rt.publish_organ(OrganProfile("cozy", "comfyui", "http://127.0.0.1:8188", ["Alpha"], "free"))
    name, words = "nothing", ""
except Exception as e:
    name, words = type(e).__name__, str(e)
print("OUT", name, rt.edit_layer.ExportToString() == before, flush=True)
print("WORDS", " ".join(words.split())[:400], flush=True)
os._exit(0)
"""


def test_an_unregistered_schema_is_refused_with_nothing_authored(slice_, tmp_path):
    rt = a_runtime(slice_)
    publish(rt, profile())  # here, where the registry knows PlexusOrganAPI, the same profile lands
    landed(rt)
    env = child_env()
    env.pop("PXR_PLUGINPATH_NAME", None)  # so a machine-wide setting cannot register the schemas before plexus does
    cold = tmp_path / "cold" / "exchange"
    cold.mkdir(parents=True)
    run = in_a_child(UNREGISTERED, cold, env=env)
    line = out_line(run)
    assert line, f"The child never reached publish_organ. Its stderr ends: {run.stderr[-600:]}"
    words = next((x[len("WORDS ") :] for x in run.stdout.splitlines() if x.startswith("WORDS ")), "")
    _out, name, untouched = line.split()
    assert name == "RuntimeError", (
        f"With a schema registry built before plexus registered its plugin, publish_organ {'published' if name == 'nothing' else f'raised {name}: {words}'}. "
        "CONTRACT: a registry without PlexusOrganAPI raises RuntimeError. Read the allowed tokens from "
        "Usd.SchemaRegistry().FindAppliedAPIPrimDefinition('PlexusOrganAPI'), raise RuntimeError when that is None, and write no token list in neuron.py."
    )
    assert untouched == "True", "publish_organ raised RuntimeError after it had authored into the edit layer. Check the registry before anything is authored."


# ---------- under the lock ----------


class RecordingLock:
    """Stands in for rt._lock, the runtime's RLock. When its outermost holder lets go, it records what the edit layer's file
    holds at prim_path, so a test can tell whether layer.Save() ran before the lock was let go."""

    def __init__(self, rt, prim_path):
        self._inner = threading.RLock()
        self._rt, self._path = rt, prim_path
        self._depth = 0
        self.at_release = []

    def __enter__(self):
        self._inner.acquire()
        self._depth += 1
        return self

    def __exit__(self, *exc):
        self._depth -= 1
        if self._depth == 0:
            self.at_release.append(in_file(self._rt, self._path))
        self._inner.release()
        return False

    def acquire(self, *args, **kwargs):
        got = self._inner.acquire(*args, **kwargs)
        if got:
            self._depth += 1
        return got

    def release(self):
        self.__exit__(None, None, None)


def test_the_file_holds_the_organ_before_the_lock_is_let_go(slice_):
    rt = a_runtime(slice_)
    lock = RecordingLock(rt, ORGAN)
    rt._lock = lock  # the one place this file reaches past CONTRACT's surface
    publish(rt, profile())
    assert lock.at_release, (
        "publish_organ authored and saved without taking self._lock. It may run while neurons do, so, as _Ctx.author and _Ctx.author_asset do, "
        "it authors and saves inside with self._lock."
    )
    assert lock.at_release[-1] is not None, (
        f"publish_organ let go of self._lock while the edit layer's file held nothing at {ORGAN}, so the save ran outside the lock. "
        "Call layer.Save() inside with self._lock, after the ChangeBlock, as _Ctx.author_asset does."
    )


# ---------- the core stays blind ----------


def imported_by(path, package):
    """Every module a source file imports, at any scope, with a relative import resolved against its package."""
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            parts = package.split(".")
            base = ".".join(parts[: len(parts) - node.level + 1]) if node.level else ""
            module = ".".join(x for x in (base, node.module or "") if x)
            found.add(module)
            found.update(f"{module}.{a.name}" for a in node.names)
    return found


def test_neuron_names_no_organ_kind_and_imports_no_organ():
    """A guard, as T8 is: it passes before publish_organ exists and has to go on passing after."""
    kinds = re.compile(r"\b(" + "|".join(re.escape(k) for k in KINDS) + r")\b", re.IGNORECASE)
    hits = [f"neuron.py:{n}: {m.group(0)}" for n, line in enumerate(NEURON_PY.read_text(encoding="utf-8").splitlines(), 1) if (m := kinds.search(line))]
    assert not hits, (
        f"neuron.py names an organ kind of Spec §3: {hits}. The core is blind to the engine (T8), so publish_organ reads the allowed tokens "
        "from Usd.SchemaRegistry and never writes them, not even in a comment."
    )
    organs = sorted(m for m in imported_by(NEURON_PY, "plexus.core") if m == "plexus.organs" or m.startswith("plexus.organs."))
    assert not organs, f"neuron.py imports {organs}. CONTRACT: publish_organ reads profile.organ_id, .kind, .endpoint, .capabilities and .cost_hint by name and imports nothing from plexus.organs, not even for a type hint."


WIDENED = r"""
import os, sys
from pathlib import Path
from pxr import Usd
Usd.SchemaRegistry()  # built now, from the widened copy that PXR_PLUGINPATH_NAME names, before plexus registers its own plugin
from plexus.membrane.exchange import create_exchange
from plexus.core.neuron import NeuronRuntime
from plexus.organs.protocol import OrganProfile
rt = NeuronRuntime(create_exchange(Path(sys.argv[1])), "lookNeuron")
out = []
for kind, cost in ((sys.argv[2], "free"), ("comfyui", sys.argv[3])):
    try:
        rt.publish_organ(OrganProfile("cozy", kind, "http://127.0.0.1:8188", ["Alpha"], cost))
        out.append("landed")
    except Exception as e:
        out.append(type(e).__name__)
print("OUT " + " ".join(out), flush=True)
os._exit(0)
"""
NEW_KIND = "futureKind"  # a kind token and a cost token that only the widened registry allows
NEW_COST = "futureCost"


def allowed_line(tokens):
    """The allowedTokens line generatedSchema.usda writes for a token attribute."""
    return "allowedTokens = [" + ", ".join(f'"{t}"' for t in tokens) + "]"


def test_the_allowed_tokens_are_the_ones_the_registry_holds(tmp_path):
    from plexus.schema import plugin_dir

    widened = tmp_path / "schema"
    shutil.copytree(plugin_dir(), widened, ignore=shutil.ignore_patterns("*.py", "__pycache__"))
    generated = widened / "generatedSchema.usda"
    text = generated.read_text(encoding="utf-8")
    for tokens in (KINDS, COSTS):
        assert text.count(allowed_line(tokens)) == 1, f"plexus/schema/generatedSchema.usda no longer writes {allowed_line(tokens)} once, so this test cannot widen it."
    text = text.replace(allowed_line(KINDS), allowed_line([*KINDS, NEW_KIND])).replace(allowed_line(COSTS), allowed_line([*COSTS, NEW_COST]))
    generated.write_text(text, encoding="utf-8")
    env = child_env()
    env["PXR_PLUGINPATH_NAME"] = str(widened)
    cold = tmp_path / "cold" / "exchange"
    cold.mkdir(parents=True)
    run = in_a_child(WIDENED, cold, NEW_KIND, NEW_COST, env=env)
    line = out_line(run)
    assert line, f"The child never reached publish_organ. Its stderr ends: {run.stderr[-600:]}"
    assert line == "OUT landed landed", (
        f"With a registry whose PlexusOrganAPI also allows kind {NEW_KIND!r} and cost hint {NEW_COST!r}, publishing each gave {line[len('OUT ') :]}, "
        "and both land. CONTRACT: the allowed tokens are the ones Usd.SchemaRegistry holds. Read each from "
        "definition.GetAttributeDefinition(name).GetMetadata('allowedTokens'), and write neither list in neuron.py."
    )


# ---------- while neurons run ----------


def test_a_publish_while_neurons_run_lands_and_wakes_none(slice_):
    rt, handle = slice_.start_neuron(predicate=PREDICATE)
    settled(slice_, rt)
    publish(rt, profile())
    settled(slice_, rt)
    prim = rt.stage.GetPrimAtPath(ORGAN)
    assert prim and prim.IsDefined(), f"A publish after start() left no defined prim at {ORGAN} on the runtime's stage. CONTRACT: publish_organ may be called before or after start()."
    landed(rt)
    assert handle.wakes == 0, (
        f"A publish under {ORGAN_ROOT} woke the neuron scoped on /Exchange/LookState {handle.wakes} times. Spec §6: only a change in a neuron's scope wakes it, "
        f"so publish_organ authors only at its organ prim and the ancestors it lacks."
    )
