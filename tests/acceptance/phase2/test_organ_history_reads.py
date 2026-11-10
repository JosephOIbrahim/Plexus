"""Frozen: a null history status reads as done (Joe, Nov 9), and a /history reply that breaks HTTP is an OrganError at once, as R2's step said.

Mission organ-registry's R2 keep, 8654893, passed test_organ_reply_shapes.py with two of R2's changes not made, because no case there could see
them. A null status got past _history_entry and then raised AttributeError from result() and stream(), which still read
entry.get('status', {}).get('status_str'). ComfyUI's PromptQueue.task_done takes an optional status and writes null when it has none
(execution.py, task_done), so null means no status, and the job is done. And http.client.HTTPException joined _history_entry's not-yet branch,
so a /history reply that breaks HTTP, or a history URL http.client will not send, was read again and again until the job's deadline and then
reported as a timeout: 600 s in the session, an hour by default. test_organ_reply_shapes.py gives the organ a one-second deadline, so there an
OrganError at once and one at the deadline look the same. The fake engines and helpers are test_organ_malformed.py's and
test_organ_reply_shapes.py's, imported read-only. Everything runs offline, as T7 does.
"""
from __future__ import annotations

import json

import pytest

from tests.acceptance.phase2.test_organ_malformed import ENTRY, Engine, job, organ, organ_error, raised
from tests.acceptance.phase2.test_organ_reply_shapes import BAD_STATUS, PID, TRUNCATED, RawEngine, call

DEADLINE_S = 6.0  # long enough to tell an OrganError at once from one at the deadline
POLL_S = 0.5  # so an organ that reads /history again until the deadline opens about a dozen sockets, not a hundred


def waiting_organ(engine, tmp_path):
    """The organ with DEADLINE_S and POLL_S."""
    from plexus.organs.cozy import CozyOrgan

    return CozyOrgan(engine.url, tmp_path / "out", poll_s=POLL_S, deadline_s=DEADLINE_S)


@pytest.fixture
def engine():
    e = Engine()
    yield e
    e.close()


@pytest.fixture
def raw():
    e = RawEngine()
    yield e
    e.close()


# 1. A null status is no status, and the job is done.

def null_status(engine):
    """The fake engine's /history now holds the job's entry with "status": null."""
    engine.replies["/history"] = (200, json.dumps({PID: {**ENTRY, "status": None}}).encode(), "application/json")


def test_result_returns_the_record_when_the_history_status_is_null(engine, tmp_path):
    o = organ(engine, tmp_path)
    h = o.submit(job())
    null_status(engine)
    box = raised(lambda: o.result(h), "result")
    assert "raised" not in box, (
        f"result() raised {type(box['raised']).__name__}: {box['raised']} on a finished job whose history status is null. Null is ComfyUI's "
        "own 'no status', so the job is done: read the status as (entry.get('status') or {}).get('status_str'), never with .get on None."
    )
    rec = box["value"]
    assert rec is not None and rec.path.is_file(), "result() must return the job's AssetRecord, its file on disk, when the history status is null."


def test_stream_ends_done_when_the_history_status_is_null(engine, tmp_path):
    o = organ(engine, tmp_path)
    h = o.submit(job())
    null_status(engine)
    box = raised(lambda: [p.state for p in o.stream(h)], "stream")
    assert "raised" not in box, (
        f"stream() raised {type(box['raised']).__name__}: {box['raised']} on a finished job whose history status is null. Null is ComfyUI's "
        "own 'no status': read the status as (entry.get('status') or {}).get('status_str'), and end the stream with 'done'."
    )
    assert box["value"] and box["value"][-1] == "done", f"stream() must end with 'done' when the history status is null; it gave {box['value']!r}."


# 2. A /history reply that breaks HTTP is the engine's answer, not a wait.

@pytest.mark.parametrize("fault", [BAD_STATUS, TRUNCATED], ids=["a bad status line", "a body short of its Content-Length"])
@pytest.mark.parametrize("via", ["stream", "result"])
def test_a_history_reply_that_breaks_http_raises_organ_error_at_once(raw, tmp_path, via, fault):
    o = waiting_organ(raw, tmp_path)
    f = call(o, via)
    raw.replies["/history"] = fault
    box = raised(f, via)
    organ_error(box, via, f"The engine answered /history with {fault[:40]!r}..., which http.client cannot read")
    assert box["took"] < DEADLINE_S / 2, (
        f"{via}() raised OrganError after {box['took']:.1f} s of its {DEADLINE_S:g} s deadline, so it read /history again until the deadline. "
        "A reply that breaks HTTP is the engine's answer, not a wait: in _history_entry the branch except (urllib.error.URLError, OSError) as e: "
        "holds no http.client.HTTPException, and the branch after it, except http.client.HTTPException as e:, raises OrganError at once."
    )


# 3. A history URL http.client will not send: a prompt_id holding a space makes http.client raise InvalidURL, an HTTPException, not an OSError.

@pytest.mark.parametrize("via", ["stream", "result"])
def test_a_history_url_http_will_not_send_raises_organ_error_at_once(engine, tmp_path, via):
    engine.replies["/prompt"] = (200, json.dumps({"prompt_id": "ENGINE PID 7f3a", "number": 0, "node_errors": {}}).encode(), "application/json")
    o = waiting_organ(engine, tmp_path)
    f = call(o, via)
    box = raised(f, via)
    organ_error(box, via, "The engine's /prompt reply holds the prompt_id 'ENGINE PID 7f3a', and http.client will not send a URL holding a space")
    assert box["took"] < DEADLINE_S / 2, (
        f"{via}() raised OrganError after {box['took']:.1f} s of its {DEADLINE_S:g} s deadline, so it read /history again until the deadline. "
        "http.client raises InvalidURL for this history URL every time, so it is no wait: in _history_entry the branch "
        "except (urllib.error.URLError, OSError) as e: holds no http.client.HTTPException, and the branch after it, "
        "except http.client.HTTPException as e:, raises OrganError at once."
    )
