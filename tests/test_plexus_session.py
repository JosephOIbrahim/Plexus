"""The live session's neuron sends a job to ComfyUI through the Cozy organ and lands the result as an asset project B composes.

The engine here is T7's FakeComfy, imported read-only, so this runs offline. tests/acceptance/live/test_organ_live.py runs the same
organ against a real ComfyUI.
"""

from __future__ import annotations

import hashlib
import json
import socket
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "examples"))

import plexus_session as ps  # noqa: E402
from tests.acceptance.phase2.test_t7_round_trip import GRAPH, FakeComfy  # noqa: E402


@pytest.fixture
def fake():
    with FakeComfy(history_delay_reads=1) as f:
        yield f


@pytest.fixture
def closed_url():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return f"http://127.0.0.1:{port}"


def session(tmp_path, **kw):
    return ps.Session(ps.new_session_folder(tmp_path / "sessions"), **kw)


def test_the_swatch_runs_from_cool_blue_to_warm_orange():
    assert ps.swatch_color(0.0) == (40 << 16) | (110 << 8) | 255
    assert ps.swatch_color(3.0) == ps.swatch_color(9.0) == (255 << 16) | (140 << 8) | 30
    assert ps.swatch_color(-1.0) == ps.swatch_color(0.0)
    reds = [ps.swatch_color(v) >> 16 for v in (0.5, 1.0, 1.5, 2.0, 2.5)]
    assert reds == sorted(reds) and len(set(reds)) == len(reds), "Warmer must read redder at every step"
    g = ps.swatch_graph(1.5)
    assert {n["class_type"] for n in g.values()} == {"EmptyImage", "SaveImage"}, "The swatch needs no model"
    assert g["2"]["inputs"]["images"] == ["1", 0]


def test_a_wake_sends_one_job_and_project_b_composes_the_asset(tmp_path, fake):
    s = session(tmp_path, organ_url=fake.url, graph=GRAPH)
    try:
        line = s.set_temperature(1.5)
        assert "woke" in line and "landed" in line, line
        assert len(fake.prompts) == 1, f"one wake sent {len(fake.prompts)} jobs"
        rec = s.last_record
        assert rec is not None and Path(rec.path).is_file()
        assert (s.root / "assets").resolve() in Path(rec.path).resolve().parents, "The organ's files belong to the session folder"
        prim = s.project_b.GetPrimAtPath(ps.ASSET)
        assert prim and "PlexusAssetAPI" in prim.GetAppliedSchemas(), "Project B does not compose the asset"
        assert prim.GetAttribute("plexus:sha256").Get() == hashlib.sha256(Path(rec.path).read_bytes()).hexdigest()
        assert prim.GetAttribute("plexus:sourceLayer").Get() == s.runtime.edit_layer.identifier
        text = "\n".join(s.status(fake.url))
        assert "Organ     cozy" in text and f"Project B asset {ps.ASSET}" in text and "landed" in text, text
    finally:
        s.close()


def test_the_seed_the_neuron_sends_reaches_the_graph(tmp_path, fake):
    s = session(tmp_path, organ_url=fake.url, graph=GRAPH)
    try:
        s.set_temperature(1.5)
        sent = fake.prompts[0]["prompt"] if "prompt" in fake.prompts[0] else fake.prompts[0]
        seeds = [n["inputs"]["seed"] for n in sent.values() if "seed" in n.get("inputs", {})]
        assert seeds == [1], f"The first wake's seed is 1, and the graph carried {seeds}"
    finally:
        s.close()


def test_a_comfyui_that_is_not_there_lands_as_a_line_on_the_stage(tmp_path, closed_url):
    s = session(tmp_path, organ_url=closed_url)
    try:
        line = s.set_temperature(1.5)
        assert "woke" in line and "failed" in line, line
        assert s.runtime.wait_idle(5.0), "A failed job must still let the runtime go idle"
        render = s._read(ps.HINTS + ".render")
        assert render and render.startswith("failed:"), f"Project B reads render = {render!r}"
        assert not s.project_b.GetPrimAtPath(ps.ASSET), "No asset may land from a failed job"
        assert s._read(ps.HINTS + ".grade_hint") == "warmer", "The hint lands before the job, whatever the job does"
    finally:
        s.close()


def test_no_organ_keeps_the_hint_alone(tmp_path):
    s = session(tmp_path)
    try:
        line = s.set_temperature(1.5)
        assert "woke" in line and "ComfyUI" not in line, line
        assert s._read(ps.HINTS + ".render") is None
        assert "off (--no-organ)" in "\n".join(s.status("http://127.0.0.1:1"))
    finally:
        s.close()


def test_a_ui_format_workflow_is_refused_with_how_to_export_one(tmp_path):
    ui = tmp_path / "ui.json"
    ui.write_text(json.dumps({"nodes": [{"id": 1, "type": "KSampler"}], "links": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="Save \\(API\\)"):
        ps.load_workflow(ui)
    api = tmp_path / "api.json"
    api.write_text(json.dumps(GRAPH), encoding="utf-8")
    assert ps.load_workflow(api) == GRAPH


def test_the_script_drives_a_wake_end_to_end(tmp_path, fake, capsys):
    wf = tmp_path / "wf.json"
    wf.write_text(json.dumps(GRAPH), encoding="utf-8")
    code = ps.main(["--url", fake.url, "--script", "temp 1.5; status; quit", "--sessions-root", str(tmp_path / "s"), "--workflow", str(wf)])
    out = capsys.readouterr().out
    assert code == 0
    assert "landed" in out and f"Project B asset {ps.ASSET}" in out, out
