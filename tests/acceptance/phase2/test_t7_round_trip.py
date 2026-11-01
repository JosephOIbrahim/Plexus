"""Spec v2.1 §10 T7, as extended by Spec Patch 01: the round trip through the Cozy organ.

A fake ComfyUI HTTP server stands in for the engine, so this runs offline. It
answers /prompt, /history/<id>, /view, /object_info and /system_stats like the
real one, and it keeps /history empty for the first few reads so an organ that
trusts anything but history (Patch 01-C, "poll for truth") fails here.
"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from tests.acceptance._support import NEURON_PARTICIPANT

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x8e\xd0"
    b"\x9b\x00\x00\x00\x00IEND\xaeB`\x82"
)

# A plain text-to-image API graph. Every ["node_id", output_index] pair is a link.
GRAPH = {
    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "base.safetensors"}},
    "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": 64, "height": 64, "batch_size": 1},
    },
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "warm dusk", "clip": ["4", 1]}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["4", 1]}},
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 1234,
            "steps": 4,
            "cfg": 5.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
            "model": ["4", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0],
        },
    },
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
    "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "plexus", "images": ["8", 0]}},
}


def _req(kind, *extra):
    return [kind, *extra] if extra else [kind]


OBJECT_INFO = {
    "CheckpointLoaderSimple": {
        "input": {"required": {"ckpt_name": [["base.safetensors"]]}},
        "output": ["MODEL", "CLIP", "VAE"],
    },
    "EmptyLatentImage": {
        "input": {
            "required": {"width": _req("INT"), "height": _req("INT"), "batch_size": _req("INT")}
        },
        "output": ["LATENT"],
    },
    "CLIPTextEncode": {
        "input": {"required": {"text": _req("STRING"), "clip": _req("CLIP")}},
        "output": ["CONDITIONING"],
    },
    "KSampler": {
        "input": {
            "required": {
                "model": _req("MODEL"),
                "seed": _req("INT"),
                "steps": _req("INT"),
                "cfg": _req("FLOAT"),
                "sampler_name": [["euler"]],
                "scheduler": [["normal"]],
                "positive": _req("CONDITIONING"),
                "negative": _req("CONDITIONING"),
                "latent_image": _req("LATENT"),
                "denoise": _req("FLOAT"),
            }
        },
        "output": ["LATENT"],
    },
    "VAEDecode": {
        "input": {"required": {"samples": _req("LATENT"), "vae": _req("VAE")}},
        "output": ["IMAGE"],
    },
    "SaveImage": {
        "input": {"required": {"images": _req("IMAGE"), "filename_prefix": _req("STRING")}},
        "output": [],
    },
}


def links(graph: dict) -> str:
    """Every link in a graph, as one canonical byte string."""
    out = {}
    for nid, node in graph.items():
        for name, v in node.get("inputs", {}).items():
            if (
                isinstance(v, list)
                and len(v) == 2
                and isinstance(v[0], str)
                and isinstance(v[1], int)
            ):
                out[f"{nid}.{name}"] = v
    return json.dumps(out, sort_keys=True, separators=(",", ":"))


class FakeComfy:
    def __init__(self, *, history_delay_reads: int = 3, version: str = "0.3.99"):
        self.prompts: list[dict] = []
        self.history_reads = 0
        self.history_delay_reads = history_delay_reads
        self.history_ready_at: float | None = None
        self.version = version
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body, ctype="application/json"):
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                if urlparse(self.path).path != "/prompt":
                    return self._send(404, {"error": "not found"})
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.prompts.append(body)
                return self._send(
                    200, {"prompt_id": f"pid-{len(fake.prompts)}", "number": 0, "node_errors": {}}
                )

            def do_GET(self):
                u = urlparse(self.path)
                if u.path == "/system_stats":
                    return self._send(
                        200,
                        {
                            "system": {
                                "os": "posix",
                                "comfyui_version": fake.version,
                                "python_version": "3.12.0",
                                "pytorch_version": "2.9.0",
                            },
                            "devices": [{"name": "cpu", "type": "cpu", "vram_total": 0}],
                        },
                    )
                if u.path == "/object_info":
                    return self._send(200, OBJECT_INFO)
                if u.path.startswith("/history/"):
                    pid = u.path.rsplit("/", 1)[1]
                    fake.history_reads += 1
                    if fake.history_reads <= fake.history_delay_reads:
                        return self._send(200, {})
                    if fake.history_ready_at is None:
                        fake.history_ready_at = time.monotonic()
                    return self._send(
                        200,
                        {
                            pid: {
                                "prompt": [0, pid, fake.prompts[-1]["prompt"], {}, ["9"]],
                                "outputs": {
                                    "9": {
                                        "images": [
                                            {
                                                "filename": "plexus_00001_.png",
                                                "subfolder": "",
                                                "type": "output",
                                            }
                                        ]
                                    }
                                },
                                "status": {
                                    "status_str": "success",
                                    "completed": True,
                                    "messages": [],
                                },
                            }
                        },
                    )
                if u.path == "/view":
                    q = parse_qs(u.query)
                    if q.get("filename") == ["plexus_00001_.png"]:
                        return self._send(200, PNG, "image/png")
                return self._send(404, {"error": "not found"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *a):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def comfy():
    with FakeComfy() as f:
        yield f


def _job(seed=1234, cid="look-1"):
    from plexus.organs.protocol import Job

    return Job(graph=copy.deepcopy(GRAPH), seed=seed, colorspace="srgb", correlation_id=cid)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.mark.parametrize("seed", [1234, 98765], ids=["no-intended-change", "seed-mutated"])
def test_link_arrays_survive_the_organ_byte_for_byte(comfy, tmp_path, seed):
    from plexus.organs.cozy import CozyOrgan

    organ = CozyOrgan(comfy.url, tmp_path / "out")
    organ.result(organ.submit(_job(seed=seed)))
    assert len(comfy.prompts) == 1
    sent = comfy.prompts[0]["prompt"]
    assert links(sent) == links(GRAPH)
    assert {k: v["class_type"] for k, v in sent.items()} == {
        k: v["class_type"] for k, v in GRAPH.items()
    }


def test_result_waits_for_history_and_a_real_file(comfy, tmp_path):
    from plexus.organs.cozy import CozyOrgan

    organ = CozyOrgan(comfy.url, tmp_path / "out")
    handle = organ.submit(_job())
    assert handle.correlation_id == "look-1"
    rec = organ.result(handle)
    assert comfy.history_ready_at is not None, "result() returned before /history had the job"
    assert comfy.history_reads > comfy.history_delay_reads
    assert rec.path.is_file()
    assert rec.sha256 == _sha(rec.path)
    for key in ("engine", "engineJobId", "envFingerprint", "organVersion", "modelHashes"):
        assert key in rec.metadata, key
    assert rec.metadata["envFingerprint"], "envFingerprint must be non-empty (Patch 01)"


def test_env_fingerprint_tracks_the_engine_environment(tmp_path):
    from plexus.organs.cozy import CozyOrgan

    prints = []
    for i, version in enumerate(("0.3.99", "0.4.0")):
        with FakeComfy(history_delay_reads=0, version=version) as f:
            organ = CozyOrgan(f.url, tmp_path / f"out{i}")
            prints.append(organ.result(organ.submit(_job())).metadata["envFingerprint"])
    assert prints[0] != prints[1], (
        "envFingerprint is the drift key; it must change with the engine"
    )


def test_neuron_round_trip_composes_into_both_projects(slice_, comfy, tmp_path):
    from plexus.organs.cozy import CozyOrgan
    from pxr import Usd

    organ = CozyOrgan(comfy.url, tmp_path / "out")
    asset_prim = f"/Exchange/{NEURON_PARTICIPANT}/Assets/plate"
    records = []

    def act(ctx):
        rec = organ.result(organ.submit(_job()))
        records.append(rec)
        ctx.author_asset(asset_prim, rec)

    rt, _handle = slice_.start_neuron(
        predicate="delta(/Exchange/LookState.temperature) > 0.2", action=act
    )
    slice_.set_temperature(1.5)
    time.sleep(0.01)
    assert rt.wait_idle(30.0)
    assert len(records) == 1
    rec = records[0]

    for project in (slice_.project_a, slice_.project_b):
        stage = Usd.Stage.Open(str(project))
        prim = stage.GetPrimAtPath(asset_prim)
        assert prim and "PlexusAssetAPI" in prim.GetAppliedSchemas(), project.name
        ap = prim.GetAttribute("plexus:assetPath").Get()
        on_disk = Path(ap.resolvedPath or ap.path)
        if not on_disk.is_absolute():
            on_disk = Path(rt.edit_layer.realPath).parent / on_disk
        assert prim.GetAttribute("plexus:sha256").Get() == _sha(on_disk) == rec.sha256
        fp = prim.GetAttribute("plexus:envFingerprint").Get()
        assert fp and fp == rec.metadata["envFingerprint"]
        assert prim.GetAttribute("plexus:sourceLayer").Get() == rt.edit_layer.identifier
