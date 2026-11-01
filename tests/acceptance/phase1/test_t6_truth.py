"""T6 · Truth (Spec v2.1 §9).

Kill both processes mid-session. Reopening the stages reproduces all composed
state: the stage is the record, with no hidden runtime truth.
"""

from __future__ import annotations

import inspect
import json
import subprocess
import time
from pathlib import Path

from tests.acceptance._support import PY, child_env


def dump(stage, roots):
    """Every authored attribute under roots, as reprs. Runs here and in the child."""
    from pxr import Usd

    out = {}
    for root in roots:
        prim = stage.GetPrimAtPath(root)
        if not prim:
            continue
        for p in Usd.PrimRange(prim):
            for a in p.GetAuthoredAttributes():
                v = a.Get()
                out[str(a.GetPath())] = repr(
                    list(v) if hasattr(v, "__len__") and not isinstance(v, str) else v
                )
    return out


DUMP = inspect.getsource(dump)

WRITER = r"""
import sys, time
from pxr import Sdf
layer = Sdf.Layer.FindOrOpen(sys.argv[1])
for i, v in enumerate([1.5, 2.0, 2.6]):
    prim = layer.GetPrimAtPath("/Exchange/LookState") or Sdf.CreatePrimInLayer(layer, "/Exchange/LookState")
    prim.specifier = Sdf.SpecifierDef
    attr = prim.attributes["temperature"] if "temperature" in prim.attributes else Sdf.AttributeSpec(prim, "temperature", Sdf.ValueTypeNames.Double)
    attr.default = v
    layer.Save()
    time.sleep(0.3)
print("WROTE", flush=True)
time.sleep(600)
"""

RUNTIME = (
    r"""
import json, sys, time
from pathlib import Path
from pxr import Sdf, Usd
from plexus.core.neuron import NeuronRuntime
"""
    + DUMP
    + r"""
exchange, project_b = Path(sys.argv[1]), Path(sys.argv[2])
rt = NeuronRuntime(exchange, "lookNeuron")
def act(ctx):
    ctx.author("/Exchange/lookNeuron/Hints", "grade_hint", "warmer", Sdf.ValueTypeNames.String)
h = rt.register("gradeHint", scope="/Exchange/LookState",
                predicate="changed(/Exchange/LookState.temperature) AND delta(/Exchange/LookState.temperature) > 0.2",
                action=act, budget_wakes=10, budget_window=10.0)
rt.start()
print("STARTED", flush=True)
sys.stdin.readline()
assert rt.wait_idle(10)
for layer in rt.stage.GetLayerStack(includeSessionLayers=False):
    layer.Reload()
assert rt.wait_idle(10)
b = Usd.Stage.Open(str(project_b))
print("STATE " + json.dumps({"wakes": h.wakes,
      "exchange": dump(rt.stage, ["/Exchange", "/Plexus"]),
      "b": dump(b, ["/Exchange", "/Project"])}), flush=True)
time.sleep(600)
"""
)


def _read_until(proc, prefix, timeout=30.0):
    end = time.time() + timeout
    while time.time() < end:
        line = proc.stdout.readline()
        if not line:
            break
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    raise AssertionError(
        f"child never printed {prefix!r}: {proc.stderr.read()[-2000:] if proc.poll() is not None else ''}"
    )


def test_kill_both_processes_and_reopen(slice_, tmp_path: Path):
    from pxr import Usd

    env = child_env()
    rt_proc = subprocess.Popen(
        [PY, "-c", RUNTIME, str(slice_.exchange), str(slice_.project_b)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    writer = None
    try:
        _read_until(rt_proc, "STARTED")
        time.sleep(0.5)
        writer = subprocess.Popen(
            [PY, "-c", WRITER, str(slice_.a_layer_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        _read_until(writer, "WROTE")
        time.sleep(0.5)
        rt_proc.stdin.write("go\n")
        rt_proc.stdin.flush()
        before = json.loads(_read_until(rt_proc, "STATE "))
    finally:
        for p in (writer, rt_proc):
            if p is not None:
                p.kill()  # no clean shutdown: SIGKILL on POSIX, TerminateProcess on Windows
                p.wait(timeout=10)

    assert before["wakes"] >= 1, "the session must have done something worth recovering"
    assert before["b"], "B must have composed state to recover"

    xstage = Usd.Stage.Open(str(slice_.exchange))
    bstage = Usd.Stage.Open(str(slice_.project_b))
    for layer in list(xstage.GetLayerStack(False)) + list(bstage.GetLayerStack(False)):
        layer.Reload()
    after_x = dump(xstage, ["/Exchange", "/Plexus"])
    after_b = dump(bstage, ["/Exchange", "/Project"])
    assert after_x == before["exchange"]
    assert after_b == before["b"]
    assert any(k.endswith(".grade_hint") for k in after_b), "the neuron's opinion survived"
