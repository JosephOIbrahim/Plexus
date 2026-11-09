"""Frozen: a reply that parses as JSON but holds the wrong shape, a reply that breaks HTTP itself, or a graph JSON cannot write, ends in an OrganError.

test_organ_malformed.py made thirteen replies end in OrganError. Its reviewer found eight more that still escaped cozy.py at 0428f77 as
AttributeError, TypeError, KeyError, ValueError or one of http.client's own errors: an entry, a status, an output or an image that is a list or
null where the organ reads an object; an image without a filename; /object_info or /system_stats without the shape or the field the organ reads;
a reply whose status line is not HTTP or whose body stops short of its Content-Length (http.client.HTTPException is not an OSError); a graph
holding a value json cannot write; and a prompt_id that is not a str. The caller catches one type, so each of these is an OrganError.

The fake engine and helpers are test_organ_malformed.py's, imported read-only. A reply that breaks HTTP comes from a bare socket server here,
because http.server will not send one. Everything runs offline, as T7 does.
"""
from __future__ import annotations

import copy
import json
import socket
import threading
from urllib.parse import urlparse

import pytest

from tests.acceptance.phase2.test_organ_malformed import ENTRY, LIMIT_S, STATS, Engine, job, organ, organ_error, raised
from tests.acceptance.phase2.test_t7_round_trip import GRAPH, OBJECT_INFO, PNG

PID = "ENGINE-PID-7f3a"  # the prompt_id the fake engine hands out


@pytest.fixture
def engine():
    e = Engine()
    yield e
    e.close()


def with_entry(engine, entry):
    """The fake engine's /history now holds `entry` for the job."""
    engine.replies["/history"] = (200, json.dumps({PID: entry}).encode(), "application/json")


def call(o, name):
    """The organ call that reads the reply: capabilities(), submit(), or submit() then stream() or result()."""
    if name == "capabilities":
        return o.capabilities
    if name == "submit":
        return lambda: o.submit(job())
    h = o.submit(job())
    return (lambda: list(o.stream(h))) if name == "stream" else (lambda: o.result(h))


# 1. A history entry, or its status, that is not an object.

@pytest.mark.parametrize("via", ["stream", "result"])
@pytest.mark.parametrize("entry", [[0, "pid", {}], "success"], ids=["a list", "a string"])
def test_a_history_entry_that_is_not_an_object_raises_organ_error(engine, tmp_path, entry, via):
    o = organ(engine, tmp_path, deadline_s=1.0)
    f = call(o, via)
    with_entry(engine, entry)
    organ_error(raised(f, via), via, f"The engine's /history entry for the job is {entry!r}, not an object")


@pytest.mark.parametrize("via", ["stream", "result"])
# A null status is not here: ComfyUI's PromptQueue.task_done takes an optional status and writes null when it has none
# (execution.py, task_done), so null means no status, and the job is done (Joe, Nov 9).
@pytest.mark.parametrize("status", [["success"], "success"], ids=["a list", "a string"])
def test_a_history_status_that_is_not_an_object_raises_organ_error(engine, tmp_path, status, via):
    o = organ(engine, tmp_path, deadline_s=1.0)
    f = call(o, via)
    with_entry(engine, {**ENTRY, "status": status})
    organ_error(raised(f, via), via, f"The engine's /history entry holds the status {status!r}, not an object")


# 2. Outputs the organ cannot read: a node's outputs, its images, or one image that is not the shape the organ reads.

@pytest.mark.parametrize("outputs", [
    {"9": [{"filename": "plexus_00001_.png", "type": "output"}]},
    {"9": None},
    {"9": "plexus_00001_.png"},
    {"9": {"images": {"0": {"filename": "plexus_00001_.png", "type": "output"}}}},
    {"9": {"images": None}},
    {"9": {"images": 1}},
    {"9": {"images": "plexus_00001_.png"}},
    {"9": {"images": ["plexus_00001_.png"]}},
    {"9": {"images": [None]}},
    {"9": {"images": [["plexus_00001_.png", "output"]]}},
], ids=["node outputs a list", "node outputs null", "node outputs a string", "images an object", "images null", "images a number",
        "images a string", "an image a string", "an image null", "an image a list"])
def test_outputs_that_are_not_objects_holding_a_list_of_image_objects_raise_organ_error(engine, tmp_path, outputs):
    o = organ(engine, tmp_path)
    f = call(o, "result")
    with_entry(engine, {**ENTRY, "outputs": outputs})
    organ_error(raised(f, "result"), "result", f"The engine's history entry holds the outputs {outputs!r}")


# 3. An output image without a filename the organ can write.

@pytest.mark.parametrize("filename", ["missing", None, 7, ["plexus_00001_.png"]], ids=["missing", "null", "a number", "a list"])
def test_an_output_image_without_a_string_filename_raises_organ_error(engine, tmp_path, filename):
    image = {"subfolder": "", "type": "output"}
    if filename != "missing":
        image["filename"] = filename
    o = organ(engine, tmp_path)
    f = call(o, "result")
    with_entry(engine, {**ENTRY, "outputs": {"9": {"images": [image]}}})
    organ_error(raised(f, "result"), "result", f"The engine's output image is {image!r}, with no filename that is a str")


# 4. /object_info that is not an object, read by capabilities() and by the fingerprint in result().

@pytest.mark.parametrize("via", ["capabilities", "result"])
@pytest.mark.parametrize("info", [sorted(OBJECT_INFO), None], ids=["a list", "null"])
def test_an_object_info_reply_that_is_not_an_object_raises_organ_error(engine, tmp_path, info, via):
    o = organ(engine, tmp_path)
    f = call(o, via)
    engine.replies["/object_info"] = (200, json.dumps(info).encode(), "application/json")
    organ_error(raised(f, via), via, f"The engine answered /object_info with {json.dumps(info)[:60]}, not an object of node classes")


# 5. /system_stats without a field the fingerprint reads.

def _stats(change):
    s = copy.deepcopy(STATS)
    change(s)
    return s


@pytest.mark.parametrize("stats", [
    _stats(lambda s: s.pop("system")),
    _stats(lambda s: s["system"].pop("comfyui_version")),
    _stats(lambda s: s.pop("devices")),
    _stats(lambda s: s["devices"][0].pop("name")),
    _stats(lambda s: s.update(devices=None)),
    _stats(lambda s: s.update(devices=["cuda:0 RTX"])),
    _stats(lambda s: s.update(system=["nt", "0.3.99"])),
    [STATS],
], ids=["no system", "no comfyui_version", "no devices", "a device without a name", "devices null", "a device a string", "system a list",
        "the reply a list"])
def test_a_system_stats_reply_without_a_field_the_fingerprint_reads_raises_organ_error(engine, tmp_path, stats):
    o = organ(engine, tmp_path)
    f = call(o, "result")
    engine.replies["/system_stats"] = (200, json.dumps(stats).encode(), "application/json")
    organ_error(raised(f, "result"), "result", f"The engine answered /system_stats, which the fingerprint reads, with {json.dumps(stats)[:80]}")


# 6. A reply that breaks HTTP itself. http.client raises BadStatusLine or IncompleteRead, which are not OSError, so no except OSError catches them.

def _http(code, body, ctype="application/json"):
    head = f"HTTP/1.1 {code} X\r\nContent-Type: {ctype}\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n"
    return head.encode() + body


BAD_STATUS = b"HTTP/1.1 two-hundred OK\r\nContent-Length: 2\r\n\r\n{}"  # a status line http.client cannot read
TRUNCATED = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 4096\r\nConnection: close\r\n\r\n{\"prompt"  # then the close
REFUSED_TRUNCATED = b"HTTP/1.1 400 Bad Request\r\nContent-Type: text/plain\r\nContent-Length: 4096\r\nConnection: close\r\n\r\nENGINE-SAYS"


class RawEngine:
    """A bare socket server. Each route answers with the exact bytes in `replies`; None under /history answers this job's entry."""

    def __init__(self):
        self.posts = []
        self.replies = {
            "/system_stats": _http(200, json.dumps(STATS).encode()),
            "/object_info": _http(200, json.dumps({**OBJECT_INFO, "SaveImage": {}}).encode()),
            "/prompt": _http(200, json.dumps({"prompt_id": PID, "number": 0, "node_errors": {}}).encode()),
            "/history": None,
            "/view": _http(200, PNG, "image/png"),
        }
        self.sock = socket.create_server(("127.0.0.1", 0))
        self.sock.settimeout(0.05)
        self.url = f"http://127.0.0.1:{self.sock.getsockname()[1]}"
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while not self.stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except OSError:
                continue
            with conn:
                try:
                    self._answer(conn)
                except OSError:
                    pass

    def _answer(self, conn):
        conn.settimeout(LIMIT_S)
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(65536)
            if not chunk:
                return
            data += chunk
        head, body = data.split(b"\r\n\r\n", 1)
        lines = head.decode("latin-1").split("\r\n")
        length = next((int(v) for k, _, v in (h.partition(":") for h in lines[1:]) if k.strip().lower() == "content-length"), 0)
        while len(body) < length:  # read the whole request, so the close below is a clean one and not a reset
            chunk = conn.recv(65536)
            if not chunk:
                break
            body += chunk
        method, target = lines[0].split(" ")[:2]
        path = urlparse(target).path
        if method == "POST":
            self.posts.append(path)
            route = "/prompt"
        elif path.startswith("/history/"):
            route = "/history"
        else:
            route = path
        reply = self.replies.get(route, _http(404, b"{}"))
        if reply is None:
            reply = _http(200, json.dumps({path.rsplit("/", 1)[1]: ENTRY}).encode())
        conn.sendall(reply)
        conn.shutdown(socket.SHUT_WR)

    def close(self):
        self.stop.set()
        self.thread.join(LIMIT_S)
        self.sock.close()


@pytest.fixture
def raw():
    e = RawEngine()
    yield e
    e.close()


@pytest.mark.parametrize("fault", [BAD_STATUS, TRUNCATED], ids=["a bad status line", "a body short of its Content-Length"])
@pytest.mark.parametrize("route,via", [("/object_info", "capabilities"), ("/prompt", "submit"), ("/history", "result"), ("/view", "result"),
                                       ("/system_stats", "result")], ids=["object_info", "prompt", "history", "view", "system_stats"])
def test_a_reply_that_breaks_http_raises_organ_error(raw, tmp_path, route, via, fault):
    o = organ(raw, tmp_path, deadline_s=1.0)
    f = call(o, via)
    raw.replies[route] = fault
    organ_error(raised(f, via), via, f"The engine answered {route} with {fault[:40]!r}..., which http.client cannot read: it raises "
                "http.client.HTTPException, which is not an OSError, so catch it beside OSError")


def test_a_refusal_whose_body_stops_short_raises_organ_error(raw, tmp_path):
    o = organ(raw, tmp_path)
    raw.replies["/prompt"] = REFUSED_TRUNCATED
    organ_error(raised(lambda: o.submit(job()), "submit"), "submit", "The engine refused the graph with a 400 whose body stops short of its "
                "Content-Length, so reading the refusal's words raises http.client.IncompleteRead")


# 7. A graph holding a value json cannot write.

def _cycle():
    inputs = {"text": "warm dusk"}
    inputs["clip"] = inputs
    return inputs


@pytest.mark.parametrize("value", [object, set, _cycle], ids=["an object", "a set", "a cycle"])
def test_a_graph_json_cannot_write_raises_organ_error_before_anything_is_sent(engine, tmp_path, value):
    graph = copy.deepcopy(GRAPH)
    if value is _cycle:
        graph["6"]["inputs"] = _cycle()
    else:
        graph["6"]["inputs"]["text"] = value()
    o = organ(engine, tmp_path)
    organ_error(raised(lambda: o.submit(job(graph=graph)), "submit"), "submit", "Node 6 of the graph holds a value json.dumps cannot write")
    assert engine.posts == [], "A graph the organ cannot write must be refused before anything reaches the engine, and it was posted."


# 8. A prompt_id that is not a str.

@pytest.mark.parametrize("pid", [["ENGINE", "PID"], ["ENGINE-PID"], {"id": "ENGINE-PID"}], ids=["a list", "a one-item list", "an object"])
def test_a_prompt_id_that_is_not_a_string_raises_organ_error(engine, tmp_path, pid):
    engine.replies["/prompt"] = (200, json.dumps({"prompt_id": pid, "number": 0, "node_errors": {}}).encode(), "application/json")
    o = organ(engine, tmp_path, deadline_s=1.0)
    organ_error(raised(lambda: o.result(o.submit(job())), "submit then result"), "submit then result",
                f"The engine's /prompt reply holds the prompt_id {pid!r}, not a str, and the organ builds the /history URL and reads the "
                "history reply by it. Refuse it in submit, where the reply is read")
