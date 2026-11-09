"""Frozen, integration: the Cozy organ against a real ComfyUI, end to end, and the result composed into both projects.

Every other organ test answers with a fake engine. This one talks to the ComfyUI at PLEXUS_COMFYUI_URL (default http://127.0.0.1:8188),
started for the run as `comfy launch -- --cpu`, so it needs no GPU and leaves Houdini the card. The graph uses no model: EmptyImage into
SaveImage, a 64 by 64 red square, which runs in seconds on the CPU and still crosses every route the organ reads: /object_info,
/prompt, /history, /view and /system_stats.

It is marked integration, so CI and the harness's own score leave it out. When no ComfyUI answers it skips and says why; on each keep of
mission organ-live a skip counts as a failure, because a test that never ran has checked nothing.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path

import pytest

from tests.acceptance._support import NEURON_PARTICIPANT

pytestmark = pytest.mark.integration

URL = os.environ.get("PLEXUS_COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
ASSET_PRIM = f"/Exchange/{NEURON_PARTICIPANT}/Assets/live"
JOB_S = 180.0  # result on the CPU: about 13 s on Nov 9, most of it two fresh /object_info reads of a large install
GRAPH = {
    "1": {"class_type": "EmptyImage", "inputs": {"width": 64, "height": 64, "batch_size": 1, "color": 16711680}},
    "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0], "filename_prefix": "plexus_live"}},
}


def _answers():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(URL + "/system_stats", timeout=5) as r:
            return json.loads(r.read())
    except (OSError, ValueError):
        return None


@pytest.fixture(scope="module")
def comfyui():
    stats = _answers()
    if stats is None:
        pytest.skip(f"No ComfyUI answers at {URL}/system_stats. Start one with `comfy --workspace=<ComfyUI> launch -- --cpu`, or set PLEXUS_COMFYUI_URL.")
    return stats


def _job(cid):
    from plexus.organs.protocol import Job

    return Job(graph=json.loads(json.dumps(GRAPH)), seed=7, colorspace="srgb", correlation_id=cid)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_the_real_engine_lists_the_nodes_the_graph_needs(comfyui, tmp_path):
    from plexus.organs.cozy import CozyOrgan

    caps = CozyOrgan(URL, tmp_path / "out", deadline_s=JOB_S).capabilities()
    missing = [c for c in ("EmptyImage", "SaveImage") if c not in caps]
    assert not missing, f"capabilities() from the real engine lacks {missing}, and every ComfyUI ships both. It must read /object_info's keys."


def test_a_real_job_comes_back_as_a_file_on_disk_with_its_record(comfyui, tmp_path):
    from plexus.organs.cozy import CozyOrgan

    out = tmp_path / "out"
    organ = CozyOrgan(URL, out, deadline_s=JOB_S)
    started = time.monotonic()
    rec = organ.result(organ.submit(_job("live-file")))
    took = time.monotonic() - started
    path = Path(rec.path)
    assert path.is_file(), f"result() returned {path}, and no file is there."
    assert out.resolve() in path.resolve().parents, f"The file landed at {path}, outside output_dir {out}."
    assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", "SaveImage writes a PNG, and the file the organ fetched is not one."
    assert rec.sha256 == _sha(path), "The record's sha256 is not the hash of the bytes on disk."
    for key in ("engine", "engineJobId", "envFingerprint", "organVersion", "modelHashes"):
        assert key in rec.metadata, f"CONTRACT promises metadata['{key}'], and the real engine's record has none."
    assert rec.metadata["engineJobId"] and rec.metadata["engineJobId"] not in str(path), "The engine's job id must be in the metadata and nowhere in the path."
    assert took < JOB_S, f"A 64 by 64 job took {took:.0f} s."


def test_two_real_jobs_with_one_filename_never_share_a_file(comfyui, tmp_path):
    from plexus.organs.cozy import CozyOrgan

    organ = CozyOrgan(URL, tmp_path / "out", deadline_s=JOB_S)
    first = organ.result(organ.submit(_job("live-a")))
    first_bytes = Path(first.path).read_bytes()
    second = organ.result(organ.submit(_job("live-b")))
    assert Path(first.path) != Path(second.path), "Two jobs landed on one path."
    assert Path(first.path).read_bytes() == first_bytes, "The second job overwrote the first job's file."


def test_a_real_refusal_is_an_organ_error_with_the_engines_words(comfyui, tmp_path):
    from plexus.organs.cozy import CozyOrgan
    from plexus.organs.protocol import Job, OrganError

    organ = CozyOrgan(URL, tmp_path / "out", deadline_s=JOB_S)
    bad = {"1": {"class_type": "EmptyImage", "inputs": {"width": "wide", "height": 64, "batch_size": 1, "color": 0}},
           "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0], "filename_prefix": "plexus_live"}}}
    with pytest.raises(OrganError) as caught:
        organ.submit(Job(graph=bad, seed=7, colorspace="srgb", correlation_id="live-refused"))
    assert "width" in str(caught.value), f"ComfyUI explains which input it could not read, and the OrganError reads {str(caught.value)[:300]!r}."


def test_a_real_round_trip_composes_into_both_projects(comfyui, slice_, tmp_path):
    from plexus.organs.cozy import CozyOrgan
    from pxr import Usd

    organ = CozyOrgan(URL, tmp_path / "out", deadline_s=JOB_S)
    records, raised = [], []

    def act(ctx):
        try:
            rec = organ.result(organ.submit(_job("live-round-trip")))
            records.append(rec)
            ctx.author_asset(ASSET_PRIM, rec)
        except Exception as e:  # noqa: BLE001 - handed to the test
            raised.append(e)

    rt, _handle = slice_.start_neuron(predicate="delta(/Exchange/LookState.temperature) > 0.2", action=act)
    slice_.set_temperature(1.5)
    time.sleep(0.01)
    assert rt.wait_idle(JOB_S + 30), "The neuron's action had not finished a real job and gone idle in time."
    assert not raised, f"The action raised {type(raised[0]).__name__}: {raised[0]}"
    assert len(records) == 1, f"One write woke the neuron {len(records)} times."
    rec = records[0]
    for project in (slice_.project_a, slice_.project_b):
        stage = Usd.Stage.Open(str(project))  # kept in a local: a prim from a dropped stage is expired
        prim = stage.GetPrimAtPath(ASSET_PRIM)
        assert prim and "PlexusAssetAPI" in prim.GetAppliedSchemas(), f"{project.name} does not compose the real asset at {ASSET_PRIM}."
        assert prim.GetAttribute("plexus:sha256").Get() == rec.sha256 == _sha(rec.path), f"{project.name}'s plexus:sha256 is not the real file's hash."
        assert prim.GetAttribute("plexus:engineJobId").Get() == rec.metadata["engineJobId"]
