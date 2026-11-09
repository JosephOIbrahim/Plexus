"""Frozen: whatever an engine sends back, the organ answers with an OrganError, never a plain Python error, and never a hang past its deadline.

The organ contract says an organ's failures are OrganError. A real engine can reply with a body that is not JSON, a reply missing the field the
organ reads, or a call that never returns, and the caller must be able to catch one exception type for all of them. The adversary on O1's keep,
4ce9db9, found each case below escaping as KeyError, TypeError or JSONDecodeError, or a hung call running 60 s past a 0.3 s deadline.

A fake engine answers on a local port, so this runs offline, as T7 does.
"""
from __future__ import annotations

import copy
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import pytest

from tests.acceptance.phase2.test_t7_round_trip import GRAPH, OBJECT_INFO, PNG

LIMIT_S = 10.0  # every call here must come back, raised or not, within this
ENTRY = {"prompt": [0, "pid", {}, {}, ["9"]], "outputs": {"9": {"images": [{"filename": "plexus_00001_.png", "subfolder": "", "type": "output"}]}},
         "status": {"status_str": "success", "completed": True, "messages": []}}
STATS = {"system": {"os": "nt", "comfyui_version": "0.3.99", "python_version": "3.12.0", "pytorch_version": "2.9.0"},
         "devices": [{"name": "cuda:0 RTX", "type": "cuda"}]}


class Engine:
    """Answers each route from `replies`: (status, body bytes, content type), or ("hang", seconds) for a call that never answers in time."""

    def __init__(self):
        self.posts = []
        self.replies = {
            "/system_stats": (200, json.dumps(STATS).encode(), "application/json"),
            "/object_info": (200, json.dumps({**OBJECT_INFO, "SaveImage": {}}).encode(), "application/json"),
            "/prompt": (200, json.dumps({"prompt_id": "ENGINE-PID-7f3a", "number": 0, "node_errors": {}}).encode(), "application/json"),
            "/history": (200, None, "application/json"),  # None: this job's entry under its id
            "/view": (200, PNG, "image/png"),
        }
        engine = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _answer(self, route, pid=None):
                reply = engine.replies[route]
                if reply[0] == "hang":
                    time.sleep(reply[1])
                    self.close_connection = True
                    return
                code, body, ctype = reply
                if body is None:
                    body = json.dumps({pid: ENTRY}).encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                engine.posts.append(self.path)
                self._answer("/prompt")

            def do_GET(self):
                path = urlparse(self.path).path
                if path.startswith("/history/"):
                    return self._answer("/history", path.rsplit("/", 1)[1])
                for route in ("/system_stats", "/object_info", "/view"):
                    if path == route or path.startswith(route + "/"):
                        return self._answer(route)
                self.send_response(404)
                self.end_headers()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def engine():
    e = Engine()
    yield e
    e.close()


def organ(engine, tmp_path, deadline_s=5.0):
    from plexus.organs.cozy import CozyOrgan

    return CozyOrgan(engine.url, tmp_path / "out", poll_s=0.05, deadline_s=deadline_s)


def job(**change):
    from plexus.organs.protocol import Job

    return Job(**{"graph": copy.deepcopy(GRAPH), "seed": 7, "colorspace": "srgb", "correlation_id": f"cid-{uuid.uuid4().hex}", **change})


def raised(call, what):
    """What call raised, from a daemon thread, so a call that never returns fails this test instead of the run."""
    box = {}

    def run():
        try:
            box["value"] = call()
        except BaseException as e:  # noqa: BLE001 - handed back below
            box["raised"] = e

    t = threading.Thread(target=run, daemon=True)
    started = time.monotonic()
    t.start()
    t.join(LIMIT_S)
    assert not t.is_alive(), f"{what} had not returned after {LIMIT_S:g} s. Blueprint §8: a timeout voids a job rather than hanging it."
    box["took"] = time.monotonic() - started
    return box


def organ_error(box, what, why):
    from plexus.organs.protocol import OrganError

    assert "raised" in box, f"{what} returned {box.get('value')!r}. {why}, so it must raise OrganError."
    e = box["raised"]
    assert isinstance(e, OrganError), (
        f"{what} raised {type(e).__name__}: {e}. {why}. The organ contract says an organ's failures are OrganError, so the caller can catch one type: "
        "turn this into raise OrganError(...) from the error."
    )
    return e


def test_a_prompt_reply_that_is_not_json_raises_organ_error(engine, tmp_path):
    engine.replies["/prompt"] = (200, b"<html>proxy page</html>", "text/html")
    o = organ(engine, tmp_path)
    organ_error(raised(lambda: o.submit(job()), "submit"), "submit", "The engine answered /prompt with a body that is not JSON")


def test_a_prompt_reply_without_a_prompt_id_raises_organ_error(engine, tmp_path):
    engine.replies["/prompt"] = (200, json.dumps({"number": 0, "node_errors": {}}).encode(), "application/json")
    o = organ(engine, tmp_path)
    organ_error(raised(lambda: o.submit(job()), "submit"), "submit", "The engine's /prompt reply holds no prompt_id")


def test_a_node_without_inputs_raises_organ_error_before_anything_is_sent(engine, tmp_path):
    graph = copy.deepcopy(GRAPH)
    del graph["5"]["inputs"]
    o = organ(engine, tmp_path)
    organ_error(raised(lambda: o.submit(job(graph=graph)), "submit"), "submit", "Node 5 of the graph has no inputs")
    assert engine.posts == [], "A graph the organ cannot read must be refused before anything reaches the engine, and it was posted."


@pytest.mark.parametrize("seed", ["7", 7.5, True], ids=["a string", "a float", "a bool"])
def test_a_seed_that_is_not_an_integer_raises_organ_error_before_anything_is_sent(engine, tmp_path, seed):
    o = organ(engine, tmp_path)
    organ_error(raised(lambda: o.submit(job(seed=seed)), "submit"), "submit", f"The job's seed is {seed!r}, not an int, and plexus:seed is an Int64")
    assert engine.posts == [], "A seed that cannot land must be refused before anything reaches the engine, and the graph was posted."


def test_a_history_entry_without_outputs_raises_organ_error(engine, tmp_path):
    entry = {k: v for k, v in ENTRY.items() if k != "outputs"}
    engine.replies["/history"] = (200, None, "application/json")
    o = organ(engine, tmp_path)
    h = o.submit(job())
    engine.replies["/history"] = (200, json.dumps({"ENGINE-PID-7f3a": entry}).encode(), "application/json")
    organ_error(raised(lambda: o.result(h), "result"), "result", "The engine's history entry for the job has no outputs")


def test_a_history_reply_that_is_not_json_raises_organ_error_by_the_deadline(engine, tmp_path):
    o = organ(engine, tmp_path, deadline_s=1.0)
    h = o.submit(job())
    engine.replies["/history"] = (200, b"not json", "text/plain")
    organ_error(raised(lambda: o.result(h), "result"), "result", "Every /history reply is a body that is not JSON")


def test_a_system_stats_reply_that_is_not_json_raises_organ_error(engine, tmp_path):
    engine.replies["/system_stats"] = (200, b"<html>login</html>", "text/html")
    o = organ(engine, tmp_path)
    h = o.submit(job())
    organ_error(raised(lambda: o.result(h), "result"), "result", "The engine answered /system_stats, which the fingerprint reads, with a body that is not JSON")


def test_an_object_info_reply_that_is_not_json_raises_organ_error(engine, tmp_path):
    engine.replies["/object_info"] = (200, b"<html>login</html>", "text/html")
    o = organ(engine, tmp_path)
    organ_error(raised(o.capabilities, "capabilities()"), "capabilities()", "The engine answered /object_info with a body that is not JSON")


@pytest.mark.parametrize("code", [400, 500], ids=["a 4xx", "a 5xx"])
def test_a_refusal_keeps_the_engines_words_even_when_they_are_not_json(engine, tmp_path, code):
    words = f"ENGINE-SAYS-{code}: the graph names a model this server does not have"
    engine.replies["/prompt"] = (code, words.encode(), "text/plain")
    o = organ(engine, tmp_path)
    e = organ_error(raised(lambda: o.submit(job()), "submit"), "submit", f"The engine refused the graph with {code}")
    assert words in str(e), (
        f"The engine explained its {code} in the reply's body, and the OrganError reads {str(e)!r}. Put the body's text in the error, "
        "decoded as UTF-8 with errors='replace', whether or not it is JSON."
    )


def test_a_hung_history_call_cannot_overrun_the_deadline(engine, tmp_path):
    o = organ(engine, tmp_path, deadline_s=1.0)
    h = o.submit(job())
    engine.replies["/history"] = ("hang", 30.0)
    box = raised(lambda: o.result(h), "result")
    organ_error(box, "result", "The engine never answered /history")
    assert box["took"] < 6.0, (
        f"result took {box['took']:.1f} s against a deadline of 1 s, because one /history call waited its whole socket timeout. "
        "Give each call a timeout of no more than the time left before the deadline, and at least a small floor."
    )
