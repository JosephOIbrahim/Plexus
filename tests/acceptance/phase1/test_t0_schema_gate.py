"""Spec v2.1 §3: the subprocess schema acceptance gate.

The four codeless applied-API schemas must register from plexus.schema's
plugin directory, define every attribute in the spec's tables with the right
type and allowed tokens, and round-trip each attribute through a saved layer.
It runs in a child process because USD builds its schema registry once, when
pxr first loads.
"""

from __future__ import annotations

import json
import subprocess

from tests.acceptance._support import PY, child_env

# (attribute, Sdf type name, allowed tokens or None), straight from Spec v2.1 §3.
SCHEMAS = {
    "PlexusProjectAPI": [
        ("plexus:projectId", "string", None),
        ("plexus:status", "token", ["active", "paused", "archived"]),
        ("plexus:created", "string", None),
        ("plexus:provenancePolicy", "token", ["strict", "advisory"]),
    ],
    "PlexusAssetAPI": [
        ("plexus:assetPath", "asset", None),
        ("plexus:sha256", "string", None),
        ("plexus:engine", "string", None),
        ("plexus:engineJobId", "string", None),
        ("plexus:seed", "int64", None),
        ("plexus:colorspace", "token", ["acescg", "srgb", "linear", "raw"]),
        ("plexus:modelHashes", "string[]", None),
        ("plexus:sourceLayer", "string", None),
        ("plexus:createdAt", "string", None),
        ("plexus:envFingerprint", "string", None),
        ("plexus:organVersion", "string", None),
        ("plexus:retryOf", "string", None),
        ("plexus:retryReason", "token", ["none", "quality", "transient", "operator"]),
    ],
    "PlexusNeuronAPI": [
        ("plexus:scope", "string", None),
        ("plexus:predicate", "string", None),
        ("plexus:tools", "string[]", None),
        ("plexus:budgetWakes", "int", None),
        ("plexus:budgetWindow", "double", None),
        ("plexus:budgetTokens", "int", None),
        ("plexus:state", "token", ["dormant", "awake", "muted"]),
        ("plexus:lastWake", "string", None),
    ],
    "PlexusOrganAPI": [
        ("plexus:organId", "string", None),
        ("plexus:kind", "token", ["comfyui", "houdini", "neuralPreview", "wfm"]),
        ("plexus:endpoint", "string", None),
        ("plexus:capabilities", "string[]", None),
        ("plexus:costHint", "token", ["free", "cheap", "expensive"]),
    ],
}

CHILD = r"""
import json, sys
from pxr import Usd, Sdf
spec = json.loads(sys.argv[1])
reg = Usd.SchemaRegistry()
samples = {"string": "s", "token": None, "asset": Sdf.AssetPath("a/b.exr"), "int64": 2**40,
           "string[]": ["x", "y"], "int": 7, "double": 2.5}
out = {"missing": [], "wrong": [], "roundtrip": []}
stage = Usd.Stage.CreateInMemory()
for api, attrs in spec.items():
    d = reg.FindAppliedAPIPrimDefinition(api)
    if d is None:
        out["missing"].append(api)
        continue
    prim = stage.DefinePrim("/" + api, "Scope")
    prim.AddAppliedSchema(api)
    for name, tname, tokens in attrs:
        p = d.GetAttributeDefinition(name)
        if not p:
            out["wrong"].append([api, name, "not defined"])
            continue
        if str(p.GetTypeName()) != tname:
            out["wrong"].append([api, name, "type " + str(p.GetTypeName())])
        if tokens is not None:
            got = [str(t) for t in (p.GetMetadata("allowedTokens") or [])]
            if got != tokens:
                out["wrong"].append([api, name, "tokens " + ",".join(got)])
        a = prim.GetAttribute(name)
        if not a:
            out["wrong"].append([api, name, "not on applied prim"])
            continue
        v = tokens[-1] if tokens else samples[tname]
        a.Set(v)
text = stage.GetRootLayer().ExportToString()
back = Usd.Stage.Open(Sdf.Layer.CreateAnonymous(".usda"))
back.GetRootLayer().ImportFromString(text)
for api, attrs in spec.items():
    prim = back.GetPrimAtPath("/" + api)
    if not prim:
        continue
    if api not in prim.GetAppliedSchemas():
        out["roundtrip"].append([api, "schema not applied after reload"])
    for name, tname, tokens in attrs:
        want = tokens[-1] if tokens else samples[tname]
        got = prim.GetAttribute(name).Get()
        if isinstance(want, list):
            got = list(got) if got is not None else None
        if got != want:
            out["roundtrip"].append([api, name, repr(got)])
print(json.dumps(out))
"""


def test_schemas_register_define_and_round_trip():
    from plexus.schema import plugin_dir

    d = plugin_dir()
    assert (d / "plugInfo.json").is_file(), "plugInfo.json must be committed (Spec §3)"
    assert (d / "generatedSchema.usda").is_file(), (
        "generatedSchema.usda must be committed (Spec §3)"
    )
    env = child_env()
    env["PXR_PLUGINPATH_NAME"] = str(d)
    r = subprocess.run(
        [PY, "-c", CHILD, json.dumps(SCHEMAS)],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out == {"missing": [], "wrong": [], "roundtrip": []}
