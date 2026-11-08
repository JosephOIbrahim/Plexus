"""Surface · What the organ contract promises and T7 and T8 leave unread: Spec v2.1 §3, §6 and §8, CONTRACT, Spec Patch 01, Blueprint §8.

T7 proves one round trip on an engine that never refuses, and T8 proves the core is blind. An organ can pass
both with profile, capabilities and stream unwritten, no seed in the graph and no deadline anywhere, and a neuron
can pass both with ctx.author_asset missing its gate, most of its attributes and its lock. This file reads what
they leave out, through CONTRACT's surface and what an engine answers, so it holds on any organ that keeps these
promises, whatever shape its code takes.

Where each thing comes from:

- Spec §3: the thirteen PlexusAssetAPI attributes and their types, the colorspace tokens, the int64 seed, and the
  PlexusOrganAPI fields behind profile().
- Spec §6: opinions land only in the neuron's own edit layer, and only a change in its scope wakes a neuron.
- Spec §8.1 and §8.2: submit does not block, the caller authors and never the organ, and a graph is checked
  against the engine's classes before it is sent.
- CONTRACT: ctx.author_asset goes through the publication gate as ctx.author does, defines its ancestors, saves as
  it lands and needs only the five metadata keys. CONTRACT also lists poll_s, deadline_s, OrganError, JobHandle,
  Progress, OrganProfile and the AssetRecord constructor, which this file calls.
- Patch 01-B: envFingerprint is the drift key, so it moves with the environment and stands still otherwise.
- Patch 01-C: the engine's job id stays inside the organ, and history is the truth.
- Patch 01-E: unknown beats invented, so no model hash without a source.
- Blueprint §8: a timeout voids a job rather than hanging it.

The engine here is a small fake of this file's own, because T7's never refuses, fails or shows a preview. T7's
graph and fake engine are imported read-only.

Every wait has a limit, because a wrong organ must fail one test and leave the run going. Each call into the organ
runs on a daemon thread under REPLY_S, each wake waits IDLE_S at most, and each child process CHILD_S. A reply that
hangs on every call would still pay those limits many times over, so all of them draw on one allowance, HANGS_S, and
past it a wait lasts AFTER_HANGS_S. That keeps the whole file on its worst wrong replies well inside the mission's
metric limit. A right reply never draws on it. A reply that has already hung that long and is also slow can fail a
later test it would pass with the full wait, so on such a reply the order of the tests can change which ones fail.

Left open on purpose: which asset wins when a second lands on one prim, and what a second job under one correlation
id gets, past the first handle keeping its own job, both the retry mission's call under Patch 01-D; the flag's words,
which only have to match ctx.author's; and how the file is named past the rules below.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import itertools
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from tests.acceptance._support import LOOK, NEURON_PARTICIPANT, PY, TEMP, child_env
from tests.acceptance.phase2.test_t7_round_trip import GRAPH, OBJECT_INFO, PNG, FakeComfy

PREDICATE = "delta(/Exchange/LookState.temperature) > 0.2"
ASSET_PRIM = f"/Exchange/{NEURON_PARTICIPANT}/Assets/plate"
WHOLE_PRIM = f"/Exchange/{NEURON_PARTICIPANT}/Assets/whole"
OUTSIDE = "/Exchange/projectA/Sneaky"
IMAGE = {"filename": "plexus_00001_.png", "subfolder": "", "type": "output"}
PREVIEW = {"filename": "ComfyUI_temp_x.png", "subfolder": "", "type": "temp"}
FIVE_KEYS = {"engine": "e", "engineJobId": "j", "envFingerprint": "f", "organVersion": "v", "modelHashes": []}
# Spec §3, PlexusAssetAPI.
SCHEMA = {
    "plexus:assetPath": "asset",
    "plexus:sha256": "string",
    "plexus:engine": "string",
    "plexus:engineJobId": "string",
    "plexus:seed": "int64",
    "plexus:colorspace": "token",
    "plexus:modelHashes": "string[]",
    "plexus:sourceLayer": "string",
    "plexus:createdAt": "string",
    "plexus:envFingerprint": "string",
    "plexus:organVersion": "string",
    "plexus:retryOf": "string",
    "plexus:retryReason": "token",
}

POLL_S = 0.01
DEADLINE_S = 2.0  # the organ's own deadline in most tests: past it a right organ raises, so a job it never sees costs this
REPLY_S = 5.0  # any one call into the organ; a right organ answers a local fake in milliseconds
REFUSED_S = 15.0  # a call that meets a closed port: one refused connection takes about 2 s on Windows
IDLE_S = 10.0  # one wake in the slice
CHILD_S = 60.0  # one child interpreter; its own waits end first
HANGS_S = 30.0  # what this whole file may spend waiting on things that never answered, before each wait shrinks
AFTER_HANGS_S = 2.0  # a wait once HANGS_S is spent; by then the reply has failed many tests, and this keeps the rest short
AFTER_REFUSED_S = 5.0  # the same for a call that meets a closed port, which needs its 2 s whatever came before
STREAM_MOST = 1000  # so a stream that never stops cannot fill the memory of the run


class Engine:
    """Answers the five routes, each from a field a test sets."""

    def __init__(self):
        self.entry = {"prompt": [0, "pid", {}, {}, ["9"]], "outputs": {"9": {"images": [dict(IMAGE)]}}, "status": {"status_str": "success", "completed": True, "messages": []}}
        self.refuse = None
        self.history_codes = []
        self.drop_history = False
        self.stats = {
            "system": {"os": "nt", "comfyui_version": "0.3.99", "python_version": "3.12.0", "pytorch_version": "2.9.0"},
            "devices": [{"name": "cuda:0 RTX", "type": "cuda", "vram_total": 24}],
        }
        self.nodes = {**OBJECT_INFO, "KSamplerAdvanced": {}, "PrimitiveInt": {}}
        self.views = []
        self.prompts = []
        self.closed = False
        engine = self

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
                if engine.refuse:
                    return self._send(400, engine.refuse)
                engine.prompts.append(body)
                return self._send(200, {"prompt_id": f"pid-{len(engine.prompts)}", "number": 0, "node_errors": {}})

            def do_GET(self):
                u = urlparse(self.path)
                if u.path == "/system_stats":
                    return self._send(200, engine.stats)
                if u.path == "/object_info":
                    return self._send(200, engine.nodes)
                if u.path.startswith("/history/"):
                    if engine.drop_history:
                        self.close_connection = True  # no reply at all, as an engine that has just died gives
                        return None
                    if engine.history_codes:
                        return self._send(engine.history_codes.pop(0), {"error": "not now"})
                    return self._send(200, {} if engine.entry is None else {u.path.rsplit("/", 1)[1]: engine.entry})
                if u.path == "/view":
                    engine.views.append(parse_qs(u.query, keep_blank_values=True))
                    return self._send(200, PNG, "image/png")
                return self._send(404, {"error": "not found"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()

    def close(self):
        if not self.closed:
            self.closed = True
            self.server.shutdown()
            self.server.server_close()


@pytest.fixture
def engine():
    e = Engine()
    yield e
    e.close()


spent_on_hangs = [0.0]


def patience(limit):
    return limit if spent_on_hangs[0] < HANGS_S else min(limit, AFTER_REFUSED_S if limit == REFUSED_S else AFTER_HANGS_S)


def within(what, call, limit=REPLY_S):
    """Runs call on a daemon thread, so an organ that never returns fails this test and leaves the run going."""
    box = {}
    limit = patience(limit)

    def run():
        try:
            box["value"] = call()
        except BaseException as e:  # noqa: BLE001 - handed back to the test's own thread below
            box["raised"] = e

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(limit)
    if thread.is_alive():
        spent_on_hangs[0] += limit
        raise AssertionError(f"{what} had not returned after {limit:g} s. Blueprint §8 says a timeout voids a job rather than hanging it.")
    if "raised" in box:
        raise box["raised"]
    return box.get("value")


def contract():
    def load():
        from plexus.organs import protocol

        return protocol

    return within("import plexus.organs.protocol", load)


class Bounded:
    """The organ under test, with every call into it on a limit."""

    def __init__(self, organ, limit):
        self.organ = organ
        self.limit = limit

    def submit(self, job):
        return within("organ.submit(job)", lambda: self.organ.submit(job), self.limit)

    def result(self, handle):
        return within("organ.result(handle)", lambda: self.organ.result(handle), self.limit)

    def collect(self, job):
        return self.result(self.submit(job))

    def stream(self, handle):
        return within("organ.stream(handle)", lambda: list(itertools.islice(self.organ.stream(handle), STREAM_MOST)), self.limit)

    def capabilities(self):
        return within("organ.capabilities()", lambda: self.organ.capabilities(), self.limit)

    def profile(self):
        return within("organ.profile()", lambda: self.organ.profile(), self.limit)


def organ_on(url, tmp_path, *, output_dir=None, poll_s=POLL_S, deadline_s=DEADLINE_S, limit=REPLY_S):
    def build():
        from plexus.organs.cozy import CozyOrgan

        return CozyOrgan(url, tmp_path / "out" if output_dir is None else output_dir, poll_s=poll_s, deadline_s=deadline_s)

    return Bounded(within("CozyOrgan(endpoint, output_dir, poll_s=, deadline_s=)", build, limit), limit)


def a_job(graph=None, seed=1234, colorspace="srgb", cid="look-1"):
    job_class = contract().Job
    return job_class(graph=copy.deepcopy(GRAPH if graph is None else graph), seed=seed, colorspace=colorspace, correlation_id=cid)


def organ_error_from(call, why):
    """The OrganError call raises. why names the clause, for the failure text."""
    organ_error = contract().OrganError
    try:
        value = call()
    except organ_error as e:
        return e
    except AssertionError as e:
        raise AssertionError(f"{e} {why}") from None
    except Exception as e:  # noqa: BLE001 - the wrong class is the finding
        raise AssertionError(f"{why} It raised {type(e).__name__}: {e}. Core knows only OrganError, so raise that.") from e
    raise AssertionError(f"{why} It returned {value!r} and raised nothing.")


def closed_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{s.getsockname()[1]}"


# ---------- __init__ and the first read ----------


def test_a_relative_output_dir_gives_an_absolute_path(engine, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rec = organ_on(engine.url, tmp_path, output_dir=Path("rel_out")).collect(a_job())
    assert rec.path.is_absolute(), (
        f"AssetRecord.path is {rec.path}, relative to the working directory, and plexus:assetPath resolves against the layer's folder, "
        "so CONTRACT's local file is lost. Store Path(output_dir).resolve() in __init__."
    )


def test_a_dead_engine_is_an_organ_error(tmp_path):
    organ_error_from(
        lambda: organ_on(closed_port(), tmp_path, limit=REFUSED_S).capabilities(),
        "capabilities() on an engine that is not running must raise OrganError, because CONTRACT gives core that error and no other. _get_json turns urllib.error.URLError and OSError into it.",
    )


# ---------- submit: the graph, the seed and what it refuses ----------


def sent_input(engine, node_id, name):
    """What the engine got for one input of one node, or None when it got no such thing."""
    return engine.prompts[0]["prompt"].get(node_id, {}).get("inputs", {}).get(name) if engine.prompts else None


def test_seed_lands_in_the_seed_input_and_nowhere_else(engine, tmp_path):
    organ_on(engine.url, tmp_path).submit(a_job(seed=98765))
    assert len(engine.prompts) == 1, f"submit() posted {len(engine.prompts)} times for one job. It posts once, with no retry and no second POST, or the engine runs a job nobody collects."
    sent = engine.prompts[0]["prompt"]
    assert set(sent) == set(GRAPH), f"Spec §8.2's link-array invariant: the node ids survive as the job gave them, {sorted(GRAPH)}, and the engine got {sorted(sent)}. Change nothing but the seed input."
    assert sent_input(engine, "3", "seed") == 98765, f"Job.seed was 98765 and the engine got seed {sent_input(engine, '3', 'seed')}. Write job.seed into each int input named in SEED_INPUTS of a copy of the graph."
    rest, want = copy.deepcopy(sent), copy.deepcopy(GRAPH)
    rest["3"]["inputs"].pop("seed")
    want["3"]["inputs"].pop("seed")
    assert rest == want, "Spec §8.2's link-array invariant: only the seed input may differ from the graph the job carried. Copy it with copy.deepcopy and change nothing else."


def test_submit_leaves_the_jobs_own_graph_alone(engine, tmp_path):
    job = a_job(seed=98765)
    organ_on(engine.url, tmp_path).submit(job)
    assert job.graph == GRAPH, "submit() wrote into the graph the caller's Job holds, and the job belongs to the caller. Write the seed into copy.deepcopy(job.graph)."


def linked_seed_graph():
    return {"12": {"class_type": "PrimitiveInt", "inputs": {"value": 5}}, "3": {"class_type": "KSampler", "inputs": {"seed": ["12", 0], "steps": 4}}}


def test_a_seed_wired_from_a_link_survives(engine, tmp_path):
    organ_on(engine.url, tmp_path).submit(a_job(linked_seed_graph()))
    assert engine.prompts, "submit() sent nothing to POST /prompt for a graph whose seed comes from a link."
    assert sent_input(engine, "3", "seed") == ["12", 0], (
        "Spec §8.2's link-array invariant: a seed input that holds the link [\"12\", 0] stays that link. Write the seed only into an input that holds an int."
    )


def test_a_seed_that_never_reached_the_engine_is_not_recorded(engine, tmp_path):
    rec = organ_on(engine.url, tmp_path).collect(a_job(linked_seed_graph()))
    assert "seed" not in rec.metadata, (
        f"The graph's seed comes from a link, so the engine never got the job's seed, and the record says seed {rec.metadata.get('seed')}. "
        "plexus:seed in Spec §3 would then record a seed that did not run. Put seed in metadata only when one was written."
    )


def test_noise_seed_is_written(engine, tmp_path):
    graph = {"3": {"class_type": "KSamplerAdvanced", "inputs": {"noise_seed": 1, "steps": 4}}}
    rec = organ_on(engine.url, tmp_path).collect(a_job(graph, seed=99))
    assert sent_input(engine, "3", "noise_seed") == 99, "CONTRACT's Job.seed has to reach an input named noise_seed too. SEED_INPUTS holds seed and noise_seed."
    assert rec.metadata.get("seed") == 99, f"The engine got seed 99 through noise_seed and the record says {rec.metadata.get('seed')}. A written seed goes in metadata."


def test_a_class_the_engine_lacks_stops_before_the_post(engine, tmp_path):
    organ = organ_on(engine.url, tmp_path)
    organ_error_from(
        lambda: organ.submit(a_job({"1": {"class_type": "NoSuchNode", "inputs": {}}})),
        "Spec §8.2 keeps validate before execute: a class the engine does not list in /object_info must raise OrganError in submit().",
    )
    assert engine.prompts == [], "submit() posted a graph with a class the engine lacks. Check every class_type against capabilities() before the POST."


def test_a_seed_past_int64_is_refused_before_the_post(engine, tmp_path):
    organ = organ_on(engine.url, tmp_path)
    organ_error_from(lambda: organ.submit(a_job(seed=2**63)), "plexus:seed is int64 in Spec §3, so a seed of 2**63 must raise OrganError in submit().")
    assert engine.prompts == [], "submit() posted a seed plexus:seed cannot hold. Check INT64_MIN to INT64_MAX before anything is sent."


def test_a_colorspace_outside_the_schema_is_refused_before_the_post(engine, tmp_path):
    organ = organ_on(engine.url, tmp_path)
    organ_error_from(lambda: organ.submit(a_job(colorspace="not-a-colorspace")), "plexus:colorspace allows acescg, srgb, linear and raw in Spec §3, so any other must raise OrganError in submit().")
    assert engine.prompts == [], "submit() posted a colorspace outside Spec §3. Check COLORSPACES before anything is sent."


def test_a_second_job_under_one_id_never_takes_the_first_handle(engine, tmp_path):
    """Patch 01-D leaves what a retry's handle is to the retry mission, so this pins only what no answer may do: a silent swap."""
    organ = organ_on(engine.url, tmp_path)
    first = organ.submit(a_job(cid="look-1"))
    organ_error = contract().OrganError
    try:
        organ.submit(a_job(cid="look-1"))
    except organ_error:
        assert len(engine.prompts) == 1, "submit() refused a correlation id it already holds after it had posted the job anyway, and nobody will collect that job. Refuse before the POST."
    rec = organ.result(first)
    assert rec.metadata.get("engineJobId") == "pid-1", (
        f"The first handle now answers with {rec.metadata.get('engineJobId')}, the second job, and no error said so. Patch 01-C makes correlation the organ's problem. "
        "Raise OrganError in submit() when self._jobs already holds job.correlation_id."
    )


def test_a_refused_graph_carries_the_engines_words(engine, tmp_path):
    engine.refuse = {"error": {"message": "bad seed type"}, "node_errors": {"3": "bad seed type"}}
    organ = organ_on(engine.url, tmp_path)
    error = organ_error_from(lambda: organ.submit(a_job()), "A 400 from POST /prompt must raise OrganError in submit().")
    assert "bad seed type" in str(error), f"The error reads {error!s}, and a real engine explains a refused graph in the reply's body. Put urllib.error.HTTPError's body text in the OrganError."


def test_submit_returns_before_the_job_is_done(engine, tmp_path):
    engine.entry = None
    organ = organ_on(engine.url, tmp_path, deadline_s=60.0)
    try:
        organ.submit(a_job())
    except AssertionError as e:
        raise AssertionError(f"{e} Spec §8.1 marks submit non-blocking, so it posts once and returns a handle while the job runs. Waiting belongs to result().") from None


# ---------- the engine's id stays inside the organ ----------


def test_the_handle_carries_no_engine_id(engine, tmp_path):
    handle = organ_on(engine.url, tmp_path).submit(a_job())
    assert handle.correlation_id == "look-1", f"CONTRACT: JobHandle.correlation_id is the job's own, and this one reads {handle.correlation_id!r}."
    held = {name: getattr(handle, name) for name in dir(handle) if not name.startswith("__")}
    leaked = {name: value for name, value in held.items() if "pid-1" in str(value)}
    assert not leaked and "pid-1" not in repr(handle), f"Patch 01-C: the handle carries nothing engine-side, and it holds the engine's job id in {sorted(leaked) or 'its repr'}. Keep that id in self._jobs."


def test_the_engine_id_leaves_only_as_metadata(engine, tmp_path):
    rec = organ_on(engine.url, tmp_path).collect(a_job())
    assert rec.metadata.get("engineJobId") == "pid-1", f"CONTRACT: metadata['engineJobId'] is the engine's job id, pid-1 here, and it reads {rec.metadata.get('engineJobId')!r}."
    assert "pid-1" not in str(rec.path), (
        f"CONTRACT: no engine job id leaves the organ except as metadata, and the file is {rec.path.name}, so the id would land on the stage in plexus:assetPath. Name the file with a uuid and the engine's filename."
    )


def test_no_error_core_sees_holds_the_engine_id(engine, tmp_path):
    organ = organ_on(engine.url, tmp_path, deadline_s=0.3, limit=REFUSED_S)
    handle = organ.submit(a_job())
    engine.history_codes = [404]
    refused = organ_error_from(lambda: organ.result(handle), "A 404 from /history must raise OrganError in result().")
    assert "pid-1" not in str(refused), f"CONTRACT: no engine job id leaves the organ except as metadata, and an error reads: {refused!s}. Name /history in the error and not the id."
    engine.close()
    dead = organ_error_from(lambda: organ.result(handle), "result() with no engine left must raise OrganError past deadline_s.")
    assert "pid-1" not in str(dead), f"CONTRACT: no engine job id leaves the organ except as metadata, and an error reads: {dead!s}. Name the correlation id in the error."


# ---------- result: polling for truth, the deadline and the file ----------


def test_result_stops_at_the_deadline(engine, tmp_path):
    engine.entry = None
    organ = organ_on(engine.url, tmp_path, deadline_s=0.2)
    handle = organ.submit(a_job())
    organ_error_from(lambda: organ.result(handle), "History never has this job, so a result() returned before /history had the job trusted something else. Blueprint §8 says a timeout voids a job rather than hanging it, so result() raises OrganError past deadline_s.")


def test_one_refused_history_read_leaves_the_job_running(engine, tmp_path):
    organ = organ_on(engine.url, tmp_path)
    handle = organ.submit(a_job())
    engine.history_codes = [503]
    assert organ.result(handle).path.is_file(), "result() returned a record whose file is not on disk after one 503 from /history."


def test_a_dead_engine_during_a_poll_waits_out_the_deadline_and_voids_the_job(engine, tmp_path):
    organ = organ_on(engine.url, tmp_path, deadline_s=0.5)
    handle = organ.submit(a_job())
    engine.drop_history = True
    start = time.monotonic()
    organ_error_from(lambda: organ.result(handle), "A history read that finds no connection means not yet, and the job is voided at deadline_s with OrganError.")
    assert time.monotonic() - start >= 0.4, "One failed read is not a timeout: result() voided the job before deadline_s. A URLError or an OSError in _history_entry returns None and the polling goes on."


def test_a_wrong_history_route_fails_at_once(engine, tmp_path):
    organ = organ_on(engine.url, tmp_path, deadline_s=60.0)
    handle = organ.submit(a_job())
    engine.history_codes = [404]
    organ_error_from(lambda: organ.result(handle), "A 4xx from /history means a wrong route, so result() raises OrganError at once and does not poll out its deadline. Only a 5xx or no connection means not yet.")


def test_an_unknown_handle_is_an_organ_error(engine, tmp_path):
    organ = organ_on(engine.url, tmp_path)
    handle_class = contract().JobHandle
    organ_error_from(lambda: organ.result(handle_class("nobody")), "result() on a correlation id the organ never saw must raise OrganError. Look it up in self._jobs with .get and raise when it is missing.")


def test_two_open_jobs_collect_out_of_order(engine, tmp_path):
    organ = organ_on(engine.url, tmp_path)
    first = organ.submit(a_job(cid="a"))
    second = organ.submit(a_job(cid="b"))
    late = organ.result(second)
    early = organ.result(first)
    got = (early.metadata.get("engineJobId"), late.metadata.get("engineJobId"))
    assert got == ("pid-1", "pid-2"), f"Patch 01-C makes correlation the organ's problem: two open jobs answered {got}. Key self._jobs by correlation id and read the job from the handle."


def test_an_error_entry_raises(engine, tmp_path):
    engine.entry["status"]["status_str"] = "error"
    organ = organ_on(engine.url, tmp_path)
    handle = organ.submit(a_job())
    organ_error_from(lambda: organ.result(handle), "A history entry whose status_str is error is a failed job, so result() raises OrganError and returns no record.")


def test_an_entry_without_images_raises(engine, tmp_path):
    engine.entry["outputs"] = {"9": {"text": ["no picture"]}}
    organ = organ_on(engine.url, tmp_path)
    handle = organ.submit(a_job())
    organ_error_from(lambda: organ.result(handle), "An entry with no image has no asset, so result() raises OrganError. Read images with output.get('images', []).")


def test_an_entry_with_only_a_preview_raises(engine, tmp_path):
    engine.entry["outputs"] = {"12": {"images": [dict(PREVIEW)]}}
    organ = organ_on(engine.url, tmp_path)
    handle = organ.submit(a_job())
    organ_error_from(lambda: organ.result(handle), "A preview's image has type temp and is not the asset, so an entry that holds only one raises OrganError. Take only images whose type is output.")


def test_the_first_output_image_is_found_past_a_node_without_images(engine, tmp_path):
    engine.entry["outputs"] = {"2": {"text": ["a caption"]}, "9": {"images": [dict(IMAGE)]}}
    rec = organ_on(engine.url, tmp_path).collect(a_job())
    assert rec.path.is_file(), "An entry whose first output holds no images must still give the saved image of a later output. Look across every output's images list."


def test_the_saved_output_wins_over_a_preview(engine, tmp_path):
    engine.entry["outputs"] = {"12": {"images": [dict(PREVIEW)]}, "9": {"images": [dict(IMAGE)]}}
    organ_on(engine.url, tmp_path).collect(a_job())
    assert [view.get("type") for view in engine.views] == [["output"]], f"The asset is the saved image of type output, and /view was asked for {engine.views}. A preview's type is temp."


def test_the_view_query_carries_subfolder_and_type(engine, tmp_path):
    engine.entry["outputs"] = {"9": {"images": [{"filename": "a.png", "subfolder": "looks", "type": "output"}]}}
    organ_on(engine.url, tmp_path).collect(a_job())
    view = engine.views[0] if engine.views else {}
    assert (view.get("filename"), view.get("subfolder"), view.get("type")) == (["a.png"], ["looks"], ["output"]), (
        f"GET /view was asked {view}. An engine finds the file by filename, subfolder and type together, so send all three through urllib.parse.urlencode."
    )


def test_the_file_on_disk_holds_the_engines_bytes(engine, tmp_path):
    rec = organ_on(engine.url, tmp_path).collect(a_job())
    assert rec.path.is_file(), f"Patch 01-C: result() returns only once the file is on disk, and {rec.path} is not there. Write the bytes GET /view answered."
    assert rec.path.read_bytes() == PNG, "CONTRACT: AssetRecord.path is the job's file, and this one does not hold the bytes GET /view answered. Write those bytes."
    assert rec.sha256 == hashlib.sha256(PNG).hexdigest(), "CONTRACT: AssetRecord.sha256 is the SHA-256 of that file. Read it back from the file with hashlib.sha256."


def test_the_file_lands_under_output_dir(engine, tmp_path):
    rec = organ_on(engine.url, tmp_path).collect(a_job())
    assert rec.path.resolve().is_relative_to((tmp_path / "out").resolve()), (
        f"CONTRACT: CozyOrgan(endpoint, output_dir) writes under output_dir, and the file is at {rec.path}. A file anywhere else is litter in the working directory. Write it under self._output_dir."
    )


def test_two_jobs_with_one_engine_filename_keep_two_files(engine, tmp_path):
    organ = organ_on(engine.url, tmp_path)
    first = organ.collect(a_job(cid="a"))
    second = organ.collect(a_job(cid="b"))
    assert first.path != second.path and first.path.is_file() and second.path.is_file(), (
        "An engine reuses a filename across jobs, and a later job must not overwrite the file an earlier record points at. Put uuid.uuid4().hex in the name."
    )


def test_model_hashes_are_empty_and_engine_is_the_organ_id(engine, tmp_path):
    organ = organ_on(engine.url, tmp_path)
    meta = organ.collect(a_job()).metadata
    assert meta.get("modelHashes") == [], f"This engine gives no model hash anywhere, so metadata['modelHashes'] reads {meta.get('modelHashes')!r} on no source. Patch 01-E: unknown beats invented. Leave it an empty list."
    organ_id = organ.profile().organ_id
    assert meta.get("engine") == organ_id, f"Spec §3 says plexus:engine holds the organ id, {organ_id!r}, and metadata['engine'] reads {meta.get('engine')!r}."
    assert meta.get("organVersion"), "Patch 01-B: metadata['organVersion'] is the organ's own version, and it is empty."


def test_the_record_holds_the_seed_the_colorspace_and_when(engine, tmp_path):
    before = datetime.now().astimezone().replace(microsecond=0)
    meta = organ_on(engine.url, tmp_path).collect(a_job(seed=77, colorspace="acescg")).metadata
    assert meta.get("seed") == 77, f"Spec §3 records the seed that ran, and metadata['seed'] reads {meta.get('seed')!r} after a job with seed 77."
    assert meta.get("colorspace") == "acescg", f"Spec §3 records the job's colorspace, and metadata['colorspace'] reads {meta.get('colorspace')!r} after a job with acescg."
    stamp = meta.get("createdAt")
    assert isinstance(stamp, str) and stamp, f"Spec §3 records plexus:createdAt as a string, and metadata['createdAt'] reads {stamp!r}. Use datetime.now(timezone.utc).isoformat(timespec='seconds')."
    try:
        when = datetime.fromisoformat(stamp).astimezone()  # naive reads as local
    except ValueError:
        raise AssertionError(f"metadata['createdAt'] reads {stamp!r}, which is not ISO-8601. Use datetime.now(timezone.utc).isoformat(timespec='seconds').") from None
    assert before <= when <= datetime.now().astimezone(), f"metadata['createdAt'] is not the time of this job: {stamp}."


# ---------- the fingerprint ----------


def test_the_fingerprint_stands_still_when_only_free_memory_moves(engine, tmp_path):
    organ = organ_on(engine.url, tmp_path)
    engine.stats["system"].update(ram_free=1000, ram_total=64, argv=["main.py"])
    engine.stats["devices"][0].update(vram_free=7, torch_vram_free=3)
    first = organ.collect(a_job(cid="a")).metadata.get("envFingerprint")
    engine.stats["system"]["ram_free"] = 2000
    engine.stats["devices"][0].update(vram_free=14, torch_vram_free=6)
    second = organ.collect(a_job(cid="b")).metadata.get("envFingerprint")
    assert first and first == second, "envFingerprint is the drift key of Patch 01-B, so free memory must not move it. Hash the engine's versions, each device's name and type and the node classes, never the whole /system_stats reply."


@pytest.mark.parametrize("move", ["os", "python_version", "pytorch_version", "device name", "device type", "a node class"])
def test_the_fingerprint_moves_with_every_field_of_the_environment(engine, tmp_path, move):
    organ = organ_on(engine.url, tmp_path)
    first = organ.collect(a_job(cid="a")).metadata.get("envFingerprint")
    if move == "a node class":
        engine.nodes["NewPackNode"] = {"input": {}, "output": []}
    elif move.startswith("device"):
        engine.stats["devices"][0][move.split()[1]] = "changed"
    else:
        engine.stats["system"][move] = "changed"
    second = organ.collect(a_job(cid="b")).metadata.get("envFingerprint")
    assert first != second, f"envFingerprint is the drift key of Patch 01-B, and a change of {move} left it as it was. Hash the engine's versions, each device's name and type and the node classes, from fresh reads of /system_stats and /object_info."


# ---------- capabilities, profile and stream ----------


def test_capabilities_name_the_engines_node_classes(engine, tmp_path):
    caps = organ_on(engine.url, tmp_path).capabilities()
    assert sorted(caps) == sorted(engine.nodes), f"CONTRACT lists capabilities() and Spec §8.1 calls it interrogation: it names each class in /object_info, and it read {caps!r}."


def test_profile_holds_the_organ_api_fields(engine, tmp_path):
    prof = organ_on(engine.url, tmp_path).profile()
    assert prof.organ_id, "Spec §3 PlexusOrganAPI: OrganProfile.organ_id is empty."
    assert prof.kind == "comfyui", f"Spec §3 PlexusOrganAPI allows comfyui for this organ's kind, and OrganProfile.kind reads {prof.kind!r}."
    assert prof.endpoint == engine.url, f"Spec §3 PlexusOrganAPI: OrganProfile.endpoint is the URL the organ was given, {engine.url}, and it reads {prof.endpoint!r}."
    assert sorted(prof.capabilities) == sorted(engine.nodes), f"Spec §3 PlexusOrganAPI: OrganProfile.capabilities is what capabilities() names, and it reads {prof.capabilities!r}."
    assert prof.cost_hint in ("free", "cheap", "expensive"), f"Spec §3 PlexusOrganAPI allows free, cheap and expensive for costHint, and OrganProfile.cost_hint reads {prof.cost_hint!r}."


def test_stream_says_queued_then_done(tmp_path):
    with FakeComfy() as comfy:
        organ = organ_on(comfy.url, tmp_path)
        progress = organ.stream(organ.submit(a_job()))
    states = [p.state for p in progress]
    assert states and states[-1] == "done" and "queued" in states and all(s == "queued" for s in states[:-1]), (
        f"CONTRACT lists stream(handle): while history lacks the job it yields queued on each poll, then done once. It yielded {states}."
    )
    assert all(p.correlation_id == "look-1" for p in progress), "Each Progress carries the job's own correlation id, and CONTRACT lets no engine id leave the organ."


def test_stream_stops_at_the_deadline(engine, tmp_path):
    engine.entry = None
    organ = organ_on(engine.url, tmp_path, deadline_s=0.2)
    handle = organ.submit(a_job())
    organ_error_from(lambda: organ.stream(handle), "Blueprint §8 says a timeout voids a job rather than hanging it, so stream() raises OrganError past deadline_s, as result() does.")


def test_stream_says_failed_on_an_error_entry(engine, tmp_path):
    engine.entry["status"]["status_str"] = "error"
    organ = organ_on(engine.url, tmp_path)
    states = [p.state for p in organ.stream(organ.submit(a_job()))]
    assert states and states[-1] == "failed", f"An entry whose status_str is error is a failed job, and stream() yielded {states}. Its last Progress says failed."


# ---------- what the files import ----------


def imports_of(module):
    """Every module a source file imports, at any scope, as the layers guard reads them. A relative import stays inside its package."""
    spec = importlib.util.find_spec(module)  # raises No module named while the package is not there yet
    assert spec and spec.origin, f"{module} is not in the repo yet."
    found = set()
    for node in ast.walk(ast.parse(Path(spec.origin).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level:
            found.update(f"plexus.{a.name}" for a in node.names) if node.module == "plexus" else found.add(node.module)
    return found


def test_the_organ_imports_the_standard_library_and_the_contract_only():
    extra = {m for m in imports_of("plexus.organs.cozy") if m.split(".")[0] not in sys.stdlib_module_names and not m.startswith("plexus.organs")}
    assert not extra, f"cozy.py imports {sorted(extra)}. The standard library and plexus.organs.protocol are all it needs: urllib for HTTP, no requests, no install, and Spec §8.1 says the caller authors, so no pxr."


def test_neuron_imports_nothing_from_organs():
    bad = {m for m in imports_of("plexus.core.neuron") if m.startswith("plexus.organs")}
    assert not bad, f"neuron.py imports {sorted(bad)}, and T8's blind core reads an AssetRecord only through record.path, record.sha256 and record.metadata, with no import, not even for a type hint."


# ---------- author_asset ----------


def on_disk(rt, prim_path):
    """The prim's attributes as the file holds them, each with its type and value, from a copy, as the disk test reads them."""
    from pxr import Sdf

    with tempfile.TemporaryDirectory() as d:
        copied = Path(d) / "copy.usda"
        shutil.copyfile(rt.edit_layer.realPath, copied)
        layer = Sdf.Layer.OpenAsAnonymous(str(copied))  # kept in a local: a spec from a dropped layer is expired
        spec = layer.GetPrimAtPath(prim_path)
        return {name: (str(spec.attributes[name].typeName), spec.attributes[name].default) for name in spec.attributes.keys()} if spec else {}


def neuron_flags(rt):
    """The non-empty plexus:flag attributes on the neuron prim, read by prefix as T5 reads them."""
    spec = rt.edit_layer.GetPrimAtPath("/Plexus/Neurons/gradeHint")
    return {name: attr.default for name, attr in spec.attributes.items() if name.startswith("plexus:flag") and attr.default} if spec else {}


def asset_record(tmp_path, sha="sha", **more):
    plate = tmp_path / "plate.png"
    plate.write_bytes(PNG)
    return contract().AssetRecord(path=plate, sha256=sha, metadata={**FIVE_KEYS, **more})


def settled(slice_, rt):
    time.sleep(0.01)
    limit = patience(IDLE_S)
    if not rt.wait_idle(limit):
        spent_on_hangs[0] += limit
        slice_.runtime = None  # stop() would wait on the stuck action too
        raise AssertionError(f"The runtime had not gone idle {limit:g} s after the write, so an action is stuck. ctx.author_asset must return: take rt._lock and let go of it, and wait on nothing else.")


def wake(slice_, act, predicate=PREDICATE):
    """Wakes one neuron on one write and waits for it. Returns the runtime, its handle and what the action raised, because an exception on the action's thread never reaches a test by itself."""
    raised = []

    def action(ctx):
        try:
            act(ctx)
        except Exception as e:  # noqa: BLE001 - handed to the test
            raised.append(e)

    rt, handle = slice_.start_neuron(predicate=predicate, action=action)
    slice_.set_temperature(1.5)
    settled(slice_, rt)
    return rt, handle, raised[0] if raised else None


def took_the_asset(raised):
    assert raised is None, f"ctx.author_asset raised {type(raised).__name__}: {raised}. CONTRACT: ctx.author_asset(prim_path, record) is a method of _Ctx and takes a record holding the five metadata keys."


def test_every_asset_attribute_lands_with_the_schemas_type_and_on_disk(slice_, tmp_path):
    rec = asset_record(tmp_path, seed=77, colorspace="srgb", createdAt="2026-11-05T12:00:00+00:00")
    saved = {}

    def act(ctx):
        ctx.author_asset(ASSET_PRIM, rec)
        saved.update(on_disk(slice_.runtime, ASSET_PRIM))  # read before the quiesce's own Save can flush a write that forgot its own

    rt, _handle, raised = wake(slice_, act)
    took_the_asset(raised)
    assert saved, "CONTRACT: an opinion is saved to disk as it lands, and ctx.author_asset returned with nothing in the file. Call layer.Save() inside with rt._lock, after the ChangeBlock."
    wrong = {name: saved.get(name, ("missing",))[0] for name, kind in SCHEMA.items() if saved.get(name, ("missing",))[0] != kind}
    assert not wrong, f"Spec §3 gives each PlexusAssetAPI attribute a type, and these read wrong or missing in the file: {wrong}. Author each through _set_attr with its Sdf.ValueTypeNames type."
    prim = rt.stage.GetPrimAtPath(ASSET_PRIM)
    assert prim and prim.IsDefined() and prim.GetParent().IsDefined(), "CONTRACT: ctx.author_asset defines, def and not over, any missing ancestor. Set each prefix's specifier to Sdf.SpecifierDef, as author does."


def test_each_asset_attribute_holds_the_records_value(slice_, tmp_path):
    rec = asset_record(tmp_path, sha="S", engine="E", engineJobId="J", envFingerprint="F", organVersion="V", modelHashes=["M"], seed=2**40, colorspace="acescg", createdAt="T")
    rt, _handle, raised = wake(slice_, lambda ctx: ctx.author_asset(ASSET_PRIM, rec))
    took_the_asset(raised)
    prim = rt.stage.GetPrimAtPath(ASSET_PRIM)
    assert prim, f"ctx.author_asset returned and no prim landed at {ASSET_PRIM}. CONTRACT: it authors the record as a PlexusAssetAPI prim in the edit layer."
    want = {"sha256": "S", "engine": "E", "engineJobId": "J", "envFingerprint": "F", "organVersion": "V", "seed": 2**40, "colorspace": "acescg", "createdAt": "T", "retryOf": "", "retryReason": "none"}
    got = {name: prim.GetAttribute(f"plexus:{name}").Get() for name in want}
    wrong = {name: got[name] for name in want if got[name] != want[name]}
    assert not wrong, f"Spec §3 says what each PlexusAssetAPI attribute holds, and these do not hold the record's value: {wrong}. plexus:retryOf is empty and plexus:retryReason is none on a first attempt."
    hashes = prim.GetAttribute("plexus:modelHashes").Get()
    assert hashes is not None and list(hashes) == ["M"], f"plexus:modelHashes holds metadata['modelHashes'] in Spec §3, ['M'] here, and it reads {hashes!r}."


def test_an_asset_outside_the_allowlist_is_dropped_and_flagged(slice_, tmp_path):
    rec = asset_record(tmp_path)
    rt, _handle, raised = wake(slice_, lambda ctx: ctx.author_asset(OUTSIDE, rec))
    took_the_asset(raised)
    assert not rt.edit_layer.GetPrimAtPath(OUTSIDE), f"CONTRACT: ctx.author_asset goes through the publication gate of Spec §7.3 as ctx.author does, and {OUTSIDE} landed. Run check_allowlist first and return without authoring."
    assert neuron_flags(rt), "CONTRACT: a write outside the allowlist puts a plexus:flag attribute on the neuron prim, and none is there. Call rt._author_on_neuron with the flag, as author does."


def test_the_deny_flag_says_what_ctx_author_says(slice_, tmp_path):
    from pxr import Sdf

    rec = asset_record(tmp_path)
    seen = {}

    def act(ctx):
        ctx.author_asset(OUTSIDE, rec)
        seen["asset"] = neuron_flags(slice_.runtime)
        ctx.author(OUTSIDE, "note", "should never land", Sdf.ValueTypeNames.String)
        seen["author"] = neuron_flags(slice_.runtime)

    _rt, _handle, raised = wake(slice_, act)
    took_the_asset(raised)
    assert seen["asset"] and seen["asset"] == seen["author"], (
        f"CONTRACT: ctx.author_asset goes through the gate the same way as ctx.author, and the two left different flags: {seen['asset']} and {seen['author']}. Open author_asset with author's whole if not check_allowlist branch."
    )


def test_a_record_with_only_the_contracts_five_keys_still_lands(slice_, tmp_path):
    rec = asset_record(tmp_path, sha="sha")
    rt, _handle, raised = wake(slice_, lambda ctx: ctx.author_asset(ASSET_PRIM, rec))
    assert raised is None, f"CONTRACT promises only five metadata keys, and ctx.author_asset raised {type(raised).__name__}: {raised}. Author plexus:seed, plexus:colorspace and plexus:createdAt only when their key is there."
    prim = rt.stage.GetPrimAtPath(ASSET_PRIM)
    assert prim and prim.GetAttribute("plexus:sha256").Get() == "sha", "A record with CONTRACT's five keys must land whole, and plexus:sha256 did not."


@pytest.mark.parametrize("broken", ["a seed past Int64", "a key CONTRACT promises left out"])
def test_a_value_that_cannot_land_leaves_nothing_in_the_file(slice_, tmp_path, broken):
    whole = asset_record(tmp_path)
    bad = asset_record(tmp_path, seed=2**63) if broken == "a seed past Int64" else asset_record(tmp_path)
    if broken != "a seed past Int64":
        bad.metadata.pop("engine")
    returned = []

    def act(ctx):
        ctx.author_asset(WHOLE_PRIM, whole)  # a reply that lands nothing must not pass here: this one has to land
        returned.append(True)
        ctx.author_asset(ASSET_PRIM, bad)

    rt, _handle, raised = wake(slice_, act)
    assert returned, f"ctx.author_asset raised {type(raised).__name__}: {raised} on a whole record. CONTRACT: ctx.author_asset(prim_path, record) takes a record holding the five metadata keys."
    assert on_disk(rt, WHOLE_PRIM), "A whole record's asset is not in the file, so nothing here can say a bad one was stopped."
    assert on_disk(rt, ASSET_PRIM) == {}, f"Half a record is in the file with {broken}, and it composes as if whole. Build every value before taking rt._lock, so one that cannot land raises with nothing authored."


def test_a_second_asset_on_one_prim_does_not_raise(slice_, tmp_path):
    """Which asset wins is the retry mission's question under Patch 01-D, so this does not pin it. An exception inside an action is only printed, so a raise half way loses the record with nothing to see."""
    first = asset_record(tmp_path, sha="one")
    second = asset_record(tmp_path, sha="two")

    def act(ctx):
        ctx.author_asset(ASSET_PRIM, first)
        ctx.author_asset(ASSET_PRIM, second)

    _rt, _handle, raised = wake(slice_, act)
    assert raised is None, f"A second ctx.author_asset on one prim raised {type(raised).__name__}: {raised}. Author every attribute through _set_attr, never a bare Sdf.AttributeSpec, because a second wake would raise."


def test_a_changed_predicate_does_not_rewake_on_its_own_asset(slice_, tmp_path):
    rec = asset_record(tmp_path)
    runs = []

    def act(ctx):
        runs.append(1)
        ctx.author_asset(ASSET_PRIM, rec)

    rt, _handle, raised = wake(slice_, act, predicate=f"changed({TEMP})")
    took_the_asset(raised)
    assert rt.edit_layer.GetPrimAtPath(ASSET_PRIM), f"The asset never landed at {ASSET_PRIM}, so nothing here can read whether it wakes its own neuron."
    time.sleep(0.5)
    settled(slice_, rt)
    assert len(runs) == 1, f"Spec §6: only a change in a neuron's scope wakes it. One write woke it {len(runs)} times, so its own asset came back as a wake. Author only in the edit layer, at the path it was given."


def in_a_child(script, *args):
    try:
        return subprocess.run([PY, "-c", script, *(str(a) for a in args)], capture_output=True, text=True, errors="replace", env=child_env(), timeout=CHILD_S)
    except subprocess.TimeoutExpired as e:
        raise AssertionError(f"A child process had not finished after {CHILD_S:g} s. Its stderr ends: {str(e.stderr)[-400:]}") from None


TWO_NEURONS = r"""
import os, sys, time
from pathlib import Path
from plexus.core.neuron import NeuronRuntime
from plexus.organs.protocol import AssetRecord
from pxr import Sdf

exchange, a_layer, look, temp, plate, idle_s = sys.argv[1:]
meta = {"engine": "e", "engineJobId": "j", "envFingerprint": "f", "organVersion": "v", "modelHashes": []}
rt = NeuronRuntime(Path(exchange), "lookNeuron")
ran = []

def action(name):
    def act(ctx):
        ctx.author_asset(f"/Exchange/lookNeuron/Assets/{name}", AssetRecord(path=Path(plate), sha256="s", metadata=meta))
        ran.append(name)
    return act

for name in ("one", "two"):
    rt.register(name, scope=look, predicate=f"changed({temp})", action=action(name), budget_wakes=10, budget_window=10.0)
rt.start()
assert rt.wait_idle(float(idle_s))
layer = Sdf.Layer.FindOrOpen(a_layer)
layer.GetAttributeAtPath(temp).default = 5.0
layer.Save()
time.sleep(0.01)
assert rt.wait_idle(float(idle_s))
print("OUT", sorted(ran), flush=True)
os._exit(0)  # daemon threads and pxr's teardown are not under test
"""


def test_two_neurons_on_one_write_both_publish(slice_, tmp_path):
    """In a child process, so a dead interpreter reads as a failed test and not as a lost report."""
    plate = tmp_path / "plate.png"
    plate.write_bytes(PNG)
    run = in_a_child(TWO_NEURONS, slice_.exchange, slice_.a_layer_path, LOOK, TEMP, plate, patience(IDLE_S))
    lock = "Two neurons woken by one write author at once: hold rt._lock around the Sdf.ChangeBlock() and layer.Save() in author_asset, as author does."
    assert run.returncode == 0, f"The child ended with exit {run.returncode}. {lock} Its stderr ends: {run.stderr[-400:]}"
    assert "OUT ['one', 'two']" in run.stdout, f"Both neurons must publish, and the child printed {run.stdout.strip()!r}. {lock} Its stderr ends: {run.stderr[-400:]}"


COLD_READ = r"""
import json, os, sys
from plexus.schema import plugin_dir
os.environ["PXR_PLUGINPATH_NAME"] = str(plugin_dir())
from pxr import Usd
stage = Usd.Stage.Open(sys.argv[1])
prim = stage.GetPrimAtPath(sys.argv[2])
ap = prim.GetAttribute("plexus:assetPath").Get()
print("OUT " + json.dumps({"schemas": list(prim.GetAppliedSchemas()), "defined": prim.IsDefined(), "path": ap.path, "resolved": ap.resolvedPath, "sha": prim.GetAttribute("plexus:sha256").Get(),
                           "fp": prim.GetAttribute("plexus:envFingerprint").Get(), "seed": prim.GetAttribute("plexus:seed").Get()}), flush=True)
os._exit(0)
"""


def test_a_second_process_reads_the_asset_from_the_file(slice_, engine, tmp_path):
    rec = organ_on(engine.url, tmp_path).collect(a_job(seed=77))
    rt, _handle, raised = wake(slice_, lambda ctx: ctx.author_asset(ASSET_PRIM, rec))
    took_the_asset(raised)
    run = in_a_child(COLD_READ, slice_.project_b, ASSET_PRIM)
    line = next((x for x in run.stdout.splitlines() if x.startswith("OUT ")), "")
    assert line, f"The stage is the record, Spec §9 T6, and a fresh process could not read the asset through project B. Its stderr ends: {run.stderr[-600:]}"
    got = json.loads(line[len("OUT ") :])
    assert got["defined"] and "PlexusAssetAPI" in got["schemas"], f"A fresh process reads no defined prim with PlexusAssetAPI at {ASSET_PRIM}: {got}. Apply it at Sdf level with spec.SetInfo('apiSchemas', Sdf.TokenListOp.Create(prependedItems=['PlexusAssetAPI']))."
    assert (got["sha"], got["fp"], got["seed"]) == (rec.sha256, rec.metadata["envFingerprint"], 77), f"A fresh process reads other values than the record's: {got}. Each attribute holds what the record holds, saved in the edit layer."
    file = Path(got["resolved"] or got["path"])
    if not file.is_absolute():
        file = Path(rt.edit_layer.realPath).parent / file
    assert file.is_file() and os.path.samefile(file, rec.path), f"plexus:assetPath does not lead a fresh process to the record's file: it reads {got['path']!r}. Author Sdf.AssetPath(str(record.path))."
