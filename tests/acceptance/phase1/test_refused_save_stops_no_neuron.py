"""Stall · A refused Save stops no neuron. Spec v2.1 §5, one dispatcher, and §6, visible,
never silent; CONTRACT, saved as it lands; frozen test_mute_isolation.py; the review of Nov 5.

CONTRACT saves every opinion as it lands, so a wake now saves, and §5 gives a runtime one
dispatcher, so what a refused Save does to that thread it does to every neuron.
test_mute_isolation.py holds the first half: a refused Save costs no neuron its wake. The
review of Nov 5 found the second half, the report. A print on the dispatcher waits for ever on
a pipe nobody reads and raises on a closed stderr, and healing the file ends neither.

So the runtime runs in a child, and the point is what that process's stderr does. On Windows
an unread pipe holds 4096 bytes and a write that does not fit waits whole. One refused Save's
traceback runs past 1000 bytes, so eight neurons or four wakes are past it, and twelve writes
to eight neurons are 96 wakes. A thread already blocked printing stands for rarer lines,
shorter lines and whatever else fills the pipe.

The record is read in either of two places, and nothing else is pinned about it. §6 puts what
must stay visible in a flagged opinion, so a new non-empty plexus:flag attribute counts,
anywhere on the stage. A process says things on stderr, so text on a stderr someone reads
counts too. Words, line counts, threads and helpers are free. A mute on a refused file flags
the mute anyway, so there the refusal needs a flag of its own, as a dropped write has in
test_truth_on_disk.py, or text.

A read-only file is how a refused Save looks on Windows. POSIX renames over it, so there the
child also turns off the layer's permission to save. USD retries a refused rename for about
344 ms a Save, and three of its settings, in the child alone, cut that to about 2 ms and keep
its banner off stderr. The refusal and its error stay the same.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import time

from tests.acceptance._support import LOOK, NEURON_PARTICIPANT, PY, TEMP, child_env

PREDICATE = f"changed({TEMP}) AND delta({TEMP}) > 0.2"
NEURONS = 8
WRITES = 12
TO_THE_BRINK = 3  # a budget of one: wake, trip, trip, so the next write is the third trip
REFUSED = 3
HARD_S = 180.0  # the child ends itself when wakes stop, and this is for a child too stuck to
QUICK_REFUSAL = {
    "PXR_WINDOWS_FILE_ATOMIC_RENAME_RETRIES": "1",
    "PXR_WINDOWS_FILE_ATOMIC_RENAME_RETRY_WAIT_MS": "0",
    "TF_ENV_SETTING_ALERTS_ENABLED": "0",
}

CHILD = r"""
import json, os, stat, sys, threading, time, traceback
from pathlib import Path

STALL_S = 20.0  # no wake and no idle for this long is a stall; a right tree settles in under a second
REPORT_S = 5.0  # how long a report from another thread gets to show


def main(exchange, a_layer, participant, scope, target, predicate, muting, free, healthy, refused, how):
    from pxr import Sdf
    from plexus.core.neuron import NeuronRuntime

    rt = NeuronRuntime(Path(exchange), participant, global_wakes_per_min=10**6)

    def neuron(name, wakes):
        return rt.register(name, scope=scope, predicate=predicate, action=lambda ctx: None, budget_wakes=wakes, budget_window=3600.0)

    muters = [neuron(f"muting{i}", 1) for i in range(muting)]
    others = [neuron(f"free{i}", 10**6) for i in range(free)]  # last, so what the muters' turn does to the dispatcher reaches them
    everyone = muters + others
    rt.start()
    layer = Sdf.Layer.FindOrOpen(a_layer)  # the runtime only hears writers in its own process
    attr = layer.GetAttributeAtPath(target)

    def settled():
        time.sleep(0.01)
        count = lambda: sum(h.wakes for h in everyone)
        seen, end = count(), time.monotonic() + STALL_S
        while time.monotonic() < end:
            if rt.wait_idle(0.1):
                return True
            if count() != seen:
                seen, end = count(), time.monotonic() + STALL_S
        return False

    def write(times):
        # One at a time, each after the last has settled: a writer in this process must not overlap a wake's Saves.
        for i in range(times):
            attr.default = attr.default + 0.5
            if not settled():
                return i
        return times

    def flags():
        return {str(x.GetPath()): str(x.Get()) for p in rt.stage.Traverse() for x in p.GetAttributes()
                if x.GetName().startswith("plexus:flag") and x.Get() not in (None, "", False)}

    if not settled() or write(healthy) != healthy:
        return {"before_refusal": [h.wakes for h in everyone]}
    before, mark = flags(), os.fstat(2).st_size if how == "file" else 0
    if how == "full":  # a thread blocked printing: the pipe stays full and every later writer waits behind it
        threading.Thread(target=lambda: os.write(2, b"x" * 2**20), daemon=True).start()
        time.sleep(0.2)
    elif how == "closed":
        sys.stderr.close()
    elif how == "none":
        sys.stderr = None
    path = rt.edit_layer.realPath
    os.chmod(path, stat.S_IREAD)
    if os.name != "nt":
        rt.edit_layer.SetPermissionToSave(False)
    landed = write(refused)
    out = {"landed": landed, "states": [h.state for h in muters], "wakes": [h.wakes for h in others], "writable": bool(os.stat(path).st_mode & stat.S_IWUSR)}
    if how == "file" and landed == refused:
        new = lambda: {k: v for k, v in flags().items() if before.get(k) != v}
        end = time.monotonic() + REPORT_S
        while time.monotonic() < end and not new() and os.fstat(2).st_size == mark:
            time.sleep(0.02)
        out.update(flags=new(), stderr=[mark, os.fstat(2).st_size])
        if others:  # the file heals, and the next wake's Save has to land
            os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
            if os.name != "nt":
                rt.edit_layer.SetPermissionToSave(True)
            out["healed"] = write(1)
            on_disk = Sdf.Layer.OpenAsAnonymous(path)  # kept in a local: a spec from a dropped layer is expired
            spec = on_disk.GetAttributeAtPath(f"{others[0].prim_path}.plexus:lastWake")
            out["stamp"] = spec.default if spec else None
    return out


try:
    report = main(*json.loads(sys.argv[1]))
except BaseException:
    report = {"crash": traceback.format_exc()[-1200:]}
print("\nOUT " + json.dumps(report), flush=True)
time.sleep(300)  # the parent kills this process with anything it started
"""


def kill_tree(proc):
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=60, check=False)
    proc.kill()
    proc.wait(timeout=60)


def run_child(slice_, tmp_path, *, muting=0, free=1, healthy=0, refused=REFUSED, how="unread"):
    """One scene in a child. stderr is a pipe this process never reads, or a file when the scene reads it after."""
    args = [str(slice_.exchange), str(slice_.a_layer_path), NEURON_PARTICIPANT, LOOK, TEMP, PREDICATE, muting, free, healthy, refused, how]
    out = tmp_path / f"child_{muting}_{free}_{how}.out"
    err = tmp_path / f"child_{muting}_{free}_{how}.err"
    with out.open("wb") as sink, err.open("wb") as said:
        proc = subprocess.Popen([PY, "-c", CHILD, json.dumps(args)], stdin=subprocess.DEVNULL, stdout=sink,
                                stderr=said if how == "file" else subprocess.PIPE, env={**child_env(), **QUICK_REFUSAL})
    line = None
    try:
        end = time.monotonic() + HARD_S
        while line is None and proc.poll() is None and time.monotonic() < end:
            time.sleep(0.05)
            line = next((x for x in out.read_text(errors="replace").splitlines(keepends=True) if x.startswith("OUT ") and x.endswith("\n")), None)
        code = proc.poll()
    finally:
        kill_tree(proc)
        if proc.stderr is not None:
            proc.stderr.close()
        for f in slice_.exchange.parent.glob("*.usda"):
            os.chmod(f, stat.S_IREAD | stat.S_IWRITE)  # a kill leaves it refused, and pytest removes this folder later
    assert line, f"the child reported nothing in {HARD_S:g} s, exit {code}: it died, or it is stuck where its own clock cannot see"
    got = json.loads(line[len("OUT ") :])
    assert "crash" not in got, f"the child failed before it could judge this: {got['crash']}"
    assert "before_refusal" not in got, f"the neurons did not settle on a good file, wakes {got['before_refusal']}"
    assert not got["writable"], "the runtime made a read-only file writable: lifting a refusal is the operator's call, and the file must stay as it was"
    got["said"] = err.read_bytes()[slice(*got["stderr"])].strip() if "stderr" in got else b""
    return got


def test_refused_saves_with_stderr_unread_stop_no_neuron(slice_, tmp_path):
    got = run_child(slice_, tmp_path, free=NEURONS, refused=WRITES)
    assert got["landed"] == WRITES and min(got["wakes"]) >= WRITES, (
        f"With the file refusing Saves and stderr a pipe nobody reads, {got['landed']} of {WRITES} writes settled and the slowest of "
        f"{NEURONS} neurons woke {min(got['wakes'])} times. A refused Save costs no wake, and no report of one may wait on stderr: on the dispatcher it stops every neuron once the pipe fills."
    )


def test_a_refused_mute_with_stderr_unread_stops_no_neighbour(slice_, tmp_path):
    got = run_child(slice_, tmp_path, muting=NEURONS, healthy=TO_THE_BRINK)
    want = TO_THE_BRINK + REFUSED
    assert got["landed"] == REFUSED and got["wakes"][0] >= want, (
        f"{NEURONS} neurons tripped into a mute on a refused file with stderr a pipe nobody reads, {got['landed']} of {REFUSED} writes settled, and their "
        f"neighbour woke {got['wakes'][0]} of {want} times. The mute's own report of a refused Save may not wait on stderr either."
    )
    assert got["states"] == ["muted"] * NEURONS, f"the third trip must still mute: {got['states']}"


def test_a_full_stderr_stops_no_neuron(slice_, tmp_path):
    got = run_child(slice_, tmp_path, muting=1, healthy=TO_THE_BRINK, how="full")
    want = TO_THE_BRINK + REFUSED
    assert got["landed"] == REFUSED and got["wakes"][0] >= want, (
        f"With another thread already blocked printing and the file refusing Saves, {got['landed']} of {REFUSED} writes settled and the free neuron woke "
        f"{got['wakes'][0]} of {want} times. A report that can wait on stderr stops the dispatcher there at its first byte, however short and however rare."
    )


def test_a_closed_stderr_stops_no_neuron(slice_, tmp_path):
    want = TO_THE_BRINK + REFUSED
    for how, plain in (("closed", "closed"), ("none", "None")):
        got = run_child(slice_, tmp_path, muting=1, healthy=TO_THE_BRINK, how=how)
        assert got["landed"] == REFUSED and got["wakes"][0] >= want, (
            f"With sys.stderr {plain} and the file refusing Saves, {got['landed']} of {REFUSED} writes settled and the free neuron woke {got['wakes'][0]} of "
            f"{want} times. A refused Save costs no wake, and a report that raises out of its guard takes the dispatcher down."
        )


def test_a_refused_save_is_not_silent(slice_, tmp_path):
    wake = run_child(slice_, tmp_path, refused=1, how="file")
    assert wake["landed"] == 1, "a wake on a refused file never settled, with stderr a file that takes every byte"
    assert wake["flags"] or wake["said"], (
        "A neuron woke on a refused file and nothing records the refusal: no new plexus:flag on the stage and nothing on stderr. A refused Save must be visible, never silent."
    )
    assert wake["healed"] == 1 and wake["stamp"], (
        "The file healed and a wake settled, and plexus:lastWake is still not in the file. A refused Save costs that Save, not the ones after it."
    )

    mute = run_child(slice_, tmp_path, muting=1, free=0, healthy=TO_THE_BRINK, refused=1, how="file")
    assert mute["landed"] == 1 and mute["states"] == ["muted"], f"the third trip on a refused file must settle and mute: {mute['landed']}, {mute['states']}"
    assert len(mute["flags"]) >= 2 or mute["said"], (
        f"A mute on a refused file flagged only the mute, {sorted(mute['flags'])}, and stderr holds nothing. The refused Save needs a record of its own."
    )
