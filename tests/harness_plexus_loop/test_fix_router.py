"""A dropped attempt's failure gets the brief line Jev chooses, when Jev is sure enough, whether or not a known fix matches.

Regular expressions only know the failures already seen, and one can fire on a symptom and name the wrong
cause. Replayed from stored picks on run 19's brief and known fixes, the 58 full attempts in the ledger make
one call for each of the 56 with failure output, 35 of them on a known fix. At a floor of 0.7, 30 of those 35
pick the line the known fix already quotes, so nothing is added, and rows 38, 67, 68 and 69 gain a line, all
labelled right, with no wrong line. The quote only shapes the next prompt: the gates and the metric still
decide what is kept.
No outside network: Jev is faked, as in test_router.py, and the real POST talks to a server on loopback.
"""

from __future__ import annotations

import http.server
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from harness.plexus_loop import MissionRun, fix_router, loop
from harness.plexus_loop.__main__ import main as cli_main
from harness.plexus_loop.fix_router import (
    FAILURE_CHARS,
    MAX_OPTIONS,
    NOTE_CHARS,
    FixRoute,
    brief_lines,
    failure_output,
    fix_line_request,
    route_failure,
)
from harness.plexus_loop.loop import (
    FEEDBACK_CHARS,
    KNOWN_FIX_CHARS,
    LEFT_OUT,
    ROUTED_LINE_CHARS,
    Attempt,
    build_prompt,
    drop_known_fixes,
    fix_lines,
)
from harness.plexus_loop.metrics import MetricResult
from harness.plexus_loop.mission import FixRouterSpec, MissionError, RouterSpec, Step, load_mission, mission_from_dict
from harness.plexus_loop.profile import Profile, with_env
from harness.plexus_loop.router import MAX_REPLY_BYTES, Route, choose
from harness.plexus_loop.workers import WorkerResult

PY = sys.executable
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
REPO = Path(__file__).resolve().parents[2]
BRIEF = "docs/brief.md"
PROSE = "A prose rule outside any list, long enough to count."
CHANGED = "`changed` is a list of `str`, never a `Path`: write `str(p)` for each one."
FINDOR = "`FindOrOpen` returns `None` for a missing file, so write `FindOrOpen(p) or CreateNew(p)`."
BRIEF_TEXT = (f"# Brief\n\n{PROSE}\nShort label.\n\n## Facts\n\n- {CHANGED}\n- {FINDOR}\n\n"
              "```python\n- `Fenced.Item` is code, so it is never offered.\n```\n")
OPTIONS = {"b00": CHANGED, "b01": FINDOR, "l003": PROSE}
SPEC = FixRouterSpec(kind="jev", brief=BRIEF)
STEP = Step("S1", ["tests/acceptance/phase1/test_t1.py"], "Do the step.")
TEST_ID = "tests.acceptance.phase1.test_t1::t"
TYPE_ERROR = "[failure] TypeError: 'Path' object is not an instance of 'str' while processing 'changed'"
NULL_LAYER = "[failure] Cannot create prim in null or expired layer"
ROUTE_LEAD = "may fix this"  # the routed line's wording, which never says "known error"
QUOTED = {"pick": "b00", "confidence": 0.9, "line": CHANGED, "quoted": True, "note": "", "seconds": 0.2}


def fake_jev(choice, confidence=0.9, seen=None):
    def post(url, body, headers, timeout):
        if seen is not None:
            seen.append((url, body, headers, timeout))
        return {"answers": {"fix_line": {"type": "choice", "choice": choice,
                                         "confidence": confidence, "probabilities": {}}}}
    return post


def raising(error):
    def post(url, body, headers, timeout):
        raise error
    return post


def _tree(tmp_path: Path, text: str = BRIEF_TEXT) -> Path:
    """All route_failure needs of a repo: the brief."""
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / BRIEF).write_text(text, encoding="utf-8")
    return tmp_path


# -- the brief's lines ------------------------------------------------------------------

def test_brief_lines_offers_list_items_then_prose_and_never_fenced_code():
    text = "\n".join([
        "# A heading is long enough to count as prose, and is never offered",
        PROSE,
        "Short label.",
        "- first item",
        "```python",
        "- a fenced item is code",
        "A fenced prose line, long enough to count if it were not code.",
        "```",
        "",
        "- second item",
        "````",
        "```",
        "- still fenced: a shorter fence does not close a longer one",
        "```",
        "````",
        "  - an indented item is prose, and this one is long enough to count",
        "- ",
    ])
    assert list(brief_lines(text).items()) == [
        ("b00", "first item"), ("b01", "second item"), ("l002", PROSE),
        ("l016", "- an indented item is prose, and this one is long enough to count"),
    ]


def test_brief_lines_keeps_a_repeated_line_once_at_its_first_place():
    twice = "A prose line long enough to count as an option, surely."
    both = "A list item that is also written out as a prose line."
    text = "\n".join(["- one", "- two", "- one", twice, twice, f"- {both}", both])
    assert list(brief_lines(text).items()) == [("b00", "one"), ("b01", "two"), ("b02", both), ("l004", twice)]


def test_brief_lines_stop_within_the_apis_limit_and_prose_gives_way_first():
    lines = brief_lines(PROSE + "\n" + "\n".join(f"- item {i}" for i in range(300)))
    assert MAX_OPTIONS == 255 and len(lines) == 254
    assert list(lines)[:2] == ["b00", "b01"] and list(lines)[-1] == "b253" and PROSE not in lines.values()
    criteria = fix_line_request(SPEC, None, "x", lines)["questions"]["fix_line"]["criteria"]
    assert len(criteria) == MAX_OPTIONS and list(criteria)[-1] == "none"


def test_failure_output_keeps_the_target_failures_whole_and_fills_up_with_the_end_of_the_detail():
    # The tail alone cut the "[failure] ..." line off all 19 replayed failures that had target failures.
    tf = ["t::a\n[failure] " + "m" * 1500, "t::b\n[failure] the message"]
    detail = "start" + "x" * 9000 + "end"
    out = failure_output(tf, detail)
    assert out.startswith("t::a") and "the message" in out and out.endswith("end") and len(out) == FAILURE_CHARS
    assert "start" not in out
    assert failure_output([], detail) == detail[-FAILURE_CHARS:]
    huge = ["t\n" + "y" * 9000]
    assert failure_output(huge, detail) == huge[0][:FAILURE_CHARS]


# -- one call ---------------------------------------------------------------------------

def test_the_request_is_one_choice_over_the_lines_and_none(tmp_path):
    seen = []
    route_failure(SPEC, _tree(tmp_path), "the failure", STEP, post=fake_jev("b00", 0.9, seen), api_key="k")
    ((url, body, headers, timeout),) = seen
    assert url == "https://api.typesafe.ai/v1/systemone" and timeout == 60
    assert headers == {"Authorization": "Bearer k"}
    assert body["model"] == "jev-latest"
    assert body["state"] == {"step_id": "S1", "step_text": "Do the step.", "failure_output": "the failure"}
    q = body["questions"]["fix_line"]
    assert q["type"] == "choice" and {k: v for k, v in q["criteria"].items() if k != "none"} == OPTIONS
    assert list(q["criteria"])[-1] == "none"


def test_the_request_clips_the_step_and_works_without_one():
    state = fix_line_request(SPEC, Step("S1", ["t"], "s" * 900), "x", OPTIONS)["state"]
    assert len(state["step_text"]) == 600
    assert fix_line_request(SPEC, None, "x", OPTIONS)["state"] == {"step_id": "", "step_text": "", "failure_output": "x"}


def test_every_field_the_question_names_is_in_the_request():
    # Backticks in the question mark field names, as in test_router.py.
    body = fix_line_request(SPEC, STEP, "x", OPTIONS)
    named = set(re.findall(r"`(\w+)`", body["questions"]["fix_line"]["instructions"]))
    assert named and named <= set(body["state"])


def test_a_sure_pick_is_quoted_whole(tmp_path):
    long = "An earlier fact. " * 90 + "The fix is at the end of the line."
    tree = _tree(tmp_path, f"- {long}\n")
    fr = route_failure(SPEC, tree, "the failure", STEP, post=fake_jev("b00", 0.82), api_key="k")
    assert fr == FixRoute(pick="b00", confidence=0.82, line=long, quoted=True)
    assert len(fr.line) > KNOWN_FIX_CHARS


def test_the_floor_is_inclusive_and_a_pick_below_it_is_kept_for_labelling_but_not_quoted(tmp_path):
    tree = _tree(tmp_path)
    assert route_failure(SPEC, tree, "f", STEP, post=fake_jev("l003", 0.7), api_key="k").quoted
    fr = route_failure(SPEC, tree, "f", STEP, post=fake_jev("b00", 0.69), api_key="k")
    assert not fr.quoted and (fr.pick, fr.confidence, fr.line) == ("b00", 0.69, CHANGED)
    assert "below 0.7" in fr.note


def test_none_and_an_unknown_pick_are_not_quoted_and_hold_no_line(tmp_path):
    tree = _tree(tmp_path)
    fr = route_failure(SPEC, tree, "f", STEP, post=fake_jev("none", 0.95), api_key="k")
    assert not fr.quoted and (fr.pick, fr.confidence, fr.line) == ("none", 0.95, "") and "chose none" in fr.note
    fr = route_failure(SPEC, tree, "f", STEP, post=fake_jev("b99", 0.95), api_key="k")
    assert not fr.quoted and (fr.pick, fr.line) == ("b99", "") and "unknown line" in fr.note


@pytest.mark.parametrize("post, why", [
    (raising(OSError("down")), "jev unavailable: OSError: down"),
    (raising(TimeoutError("timed out")), "jev unavailable: TimeoutError"),
    (raising(json.JSONDecodeError("bad", "x", 0)), "jev unavailable: JSONDecodeError"),
    (lambda *a: {"answers": {}}, "jev unavailable: KeyError"),
    (lambda *a: ["not", "a", "dict"], "jev unavailable: TypeError"),
    (lambda *a: {"answers": {"fix_line": {"choice": "b00"}}}, "jev unavailable: KeyError"),
    (lambda *a: {"answers": {"fix_line": {"choice": "b00", "confidence": "high"}}}, "jev unavailable: ValueError"),
    (fake_jev("b00", "0.99"), "jev unavailable: ValueError"),  # float() would take these two
    (fake_jev("b00", True), "jev unavailable: ValueError"),
    (fake_jev("b00", float("nan")), "confidence nan"),
    (fake_jev("b00", 1.5), "confidence 1.5"),
])
def test_a_failed_call_or_a_bad_answer_quotes_nothing_and_never_raises(tmp_path, post, why):
    fr = route_failure(SPEC, _tree(tmp_path), "the failure", STEP, post=post, api_key="k")
    assert not fr.quoted and fr.line == "" and fr.confidence is None and why in fr.note


def test_the_model_that_answered_is_kept_with_the_answer(tmp_path):
    # The floor belongs to one model, and the request may name only "jev-latest".
    def answer(confidence):
        return lambda *a: {"model": "jev-1.14.0", "answers": {"fix_line": {"choice": "b00", "confidence": confidence}}}
    tree = _tree(tmp_path)
    assert route_failure(SPEC, tree, "f", STEP, post=answer(0.9), api_key="k").model == "jev-1.14.0"
    assert route_failure(SPEC, tree, "f", STEP, post=answer(0.5), api_key="k").model == "jev-1.14.0"
    assert route_failure(SPEC, tree, "f", STEP, post=fake_jev("b00", 0.9), api_key="k").model == ""


def test_a_runaway_pick_or_error_is_clipped_before_it_reaches_the_row(tmp_path):
    tree = _tree(tmp_path)
    fr = route_failure(SPEC, tree, "f", STEP, post=fake_jev("x" * 5000, 0.9), api_key="k")
    assert not fr.quoted and len(fr.pick) == NOTE_CHARS and len(fr.note) == NOTE_CHARS
    fr = route_failure(SPEC, tree, "f", STEP, post=raising(OSError("x" * 5000)), api_key="k")
    assert not fr.quoted and len(fr.note) == NOTE_CHARS


def test_the_whole_call_has_a_deadline(tmp_path):
    # urllib's timeout is per socket operation and per address, so it does not bound the call.
    release = threading.Event()

    def stuck(url, body, headers, timeout):
        release.wait(30)
        return {}
    t0 = time.monotonic()
    fr = route_failure(FixRouterSpec(kind="jev", brief=BRIEF, timeout_s=0.2), _tree(tmp_path), "f", STEP, post=stuck, api_key="k")
    release.set()
    assert time.monotonic() - t0 < 5 and not fr.quoted and "TimeoutError: no answer within 0.2 s" in fr.note


class _Api(http.server.BaseHTTPRequestHandler):
    """The API on loopback: each test sets what it answers, and it records every request."""

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.server.seen.append((self.command, self.path, self.headers.get("Authorization")))
        status, headers, body = self.server.reply
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:  # the client stopped reading, which is what the size test wants
            pass

    do_GET = do_POST

    def log_message(self, *a):
        pass


@pytest.fixture
def api():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Api)
    srv.seen, srv.reply = [], (200, {}, b"{}")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _spec_for(api):
    return FixRouterSpec(kind="jev", brief=BRIEF, host=f"http://127.0.0.1:{api.server_port}", timeout_s=20)


ANSWER = json.dumps({"model": "m", "answers": {"fix_line": {"choice": "b00", "confidence": 0.9}}}).encode()


def test_the_real_post_sends_the_key_once_and_reads_the_answer(api, tmp_path):
    api.reply = (200, {}, ANSWER)
    fr = route_failure(_spec_for(api), _tree(tmp_path), "f", STEP, api_key="fake-key")
    assert fr.quoted and fr.model == "m" and api.seen == [("POST", "/v1/systemone", "Bearer fake-key")]


def test_a_redirect_is_a_failed_call_and_the_key_goes_nowhere_else(api, tmp_path):
    api.reply = (302, {"Location": f"http://127.0.0.1:{api.server_port}/elsewhere"}, b"")
    fr = route_failure(_spec_for(api), _tree(tmp_path), "f", STEP, api_key="fake-key")
    assert not fr.quoted and "jev unavailable: HTTPError" in fr.note
    assert [path for _, path, _ in api.seen] == ["/v1/systemone"]


def test_a_runaway_reply_is_not_read_whole(api, tmp_path):
    api.reply = (200, {}, b" " * MAX_REPLY_BYTES + ANSWER)  # valid JSON, if it were read to the end
    fr = route_failure(_spec_for(api), _tree(tmp_path), "f", STEP, api_key="fake-key")
    assert not fr.quoted and "jev unavailable: JSONDecodeError" in fr.note


JEV_STEPS = RouterSpec(kind="jev")
TWO_STEPS = [Step("S1", ["t/test_a.py"], "a"), Step("S2", ["t/test_b.py"], "b")]
TWO_FAILING = ["t.test_a::x", "t.test_b::y"]


@pytest.mark.parametrize("key", ["sk-secret-value\n", "sk-secret\\value", "sk-secret'val\"ue", "sk-secrét-value"])
def test_no_note_from_either_router_carries_the_key(tmp_path, key):
    # The note reaches the ledger and the log, and http.client's ValueError for a bad header value
    # repeats the whole header, in a bytes repr a plain replace of the key can miss.
    def bad_header(url, body, headers, timeout):
        raise ValueError(f"Invalid header value {headers['Authorization'].encode()!r}")
    fr = route_failure(SPEC, _tree(tmp_path), "the failure", STEP, post=bad_header, api_key=key)
    assert not fr.quoted and fr.note == "jev unavailable: ValueError"
    route = choose(JEV_STEPS, TWO_STEPS, TWO_FAILING, post=bad_header, api_key=key)
    assert route.how == "fallback" and route.note == "jev unavailable: ValueError"


def test_a_key_named_by_an_error_is_taken_out_of_the_note(tmp_path):
    post = raising(OSError("refused sk-secret-value"))
    fr = route_failure(SPEC, _tree(tmp_path), "the failure", STEP, post=post, api_key="sk-secret-value")
    assert fr.note == "jev unavailable: OSError: refused <key>"
    route = choose(JEV_STEPS, TWO_STEPS, TWO_FAILING, post=post, api_key="sk-secret-value")
    assert route.note == "jev unavailable: OSError: refused <key>"


@pytest.mark.parametrize("key", ["sk-one\ntwo", "sk-one two", "sk-one\ttwo", "sk-one\r\ntwo\r\n"])
def test_a_key_with_whitespace_inside_it_is_not_sent(tmp_path, key):
    seen = []
    fr = route_failure(SPEC, _tree(tmp_path), "f", STEP, post=fake_jev("b00", 0.9, seen), api_key=key)
    assert seen == [] and not fr.quoted and "TYPESAFE_API_KEY has whitespace inside it" in fr.note and "sk-one" not in fr.note


def test_either_router_strips_the_key_before_sending_it(tmp_path):
    # A stray newline used to fail every call all night: http.client refuses that header.
    seen = []
    route_failure(SPEC, _tree(tmp_path), "f", STEP, post=fake_jev("b00", 0.9, seen), api_key="  sk-one\r\n")
    choose(JEV_STEPS, TWO_STEPS, TWO_FAILING, post=fake_jev("S1", 0.9, seen), api_key="  sk-one\r\n")
    assert [s[2] for s in seen] == [{"Authorization": "Bearer sk-one"}] * 2


def test_gates_never_get_the_key(monkeypatch):
    # Gates run code the worker wrote, and whatever it prints now goes to the API as failure output.
    monkeypatch.setenv("TYPESAFE_API_KEY", "fake-key")
    monkeypatch.setenv("SOME_OTHER_VAR", "kept")
    env = with_env(Profile(device="cpu", houdini="running"), TYPESAFE_API_KEY="fake-key", ADDED="yes").environ()
    assert "TYPESAFE_API_KEY" not in env and env["SOME_OTHER_VAR"] == "kept" and env["ADDED"] == "yes"


@pytest.mark.parametrize("key", ["", "   "])
def test_no_key_makes_no_call(tmp_path, key):
    seen = []
    fr = route_failure(SPEC, _tree(tmp_path), "f", STEP, post=fake_jev("b00", 0.9, seen), api_key=key)
    assert seen == [] and not fr.quoted and "TYPESAFE_API_KEY is not set" in fr.note


def test_the_key_comes_from_the_specs_env_var(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setenv("TYPESAFE_API_KEY", "from-env")
    route_failure(SPEC, _tree(tmp_path), "f", STEP, post=fake_jev("b00", 0.9, seen))
    assert seen[0][2] == {"Authorization": "Bearer from-env"}
    monkeypatch.delenv("TYPESAFE_API_KEY")
    fr = route_failure(SPEC, _tree(tmp_path), "f", STEP, post=fake_jev("b00", 0.9, seen))
    assert len(seen) == 1 and "is not set" in fr.note


def test_a_brief_that_cannot_be_read_or_offers_nothing_makes_no_call(tmp_path):
    seen = []
    post = fake_jev("b00", 0.9, seen)
    assert "cannot be read" in route_failure(SPEC, tmp_path, "f", STEP, post=post, api_key="k").note  # missing
    (tmp_path / "docs").mkdir()
    (tmp_path / BRIEF).mkdir()
    assert "cannot be read" in route_failure(SPEC, tmp_path, "f", STEP, post=post, api_key="k").note  # a directory
    (tmp_path / BRIEF).rmdir()
    (tmp_path / BRIEF).write_bytes(b"- \xff\xfe not UTF-8\n")
    assert "cannot be read" in route_failure(SPEC, tmp_path, "f", STEP, post=post, api_key="k").note
    (tmp_path / BRIEF).write_text("# Only a heading\n", encoding="utf-8")
    assert "no lines" in route_failure(SPEC, tmp_path, "f", STEP, post=post, api_key="k").note
    assert seen == []


@pytest.mark.parametrize("text", ["", "  \n "])
def test_empty_failure_text_makes_no_call(tmp_path, text):
    seen = []
    fr = route_failure(SPEC, _tree(tmp_path), text, STEP, post=fake_jev("b00", 0.9, seen), api_key="k")
    assert seen == [] and not fr.quoted and "no failure text" in fr.note


def test_kind_none_makes_no_call(tmp_path):
    seen = []
    off = FixRouterSpec(brief=BRIEF)  # a readable brief, so only the kind stops the call
    fr = route_failure(off, _tree(tmp_path), "f", STEP, post=fake_jev("b00", 0.9, seen), api_key="k")
    assert seen == [] and not fr.quoted and "off" in fr.note


# -- the mission section ----------------------------------------------------------------

def _raw(fix_router=None, files=None, attempts=2):
    step = {"id": "S1", "targets": STEP.targets, "text": STEP.text}
    if files:
        step["files"] = files
    gate = ("import pathlib, sys; p = pathlib.Path('plexus/gate.txt'); "
            "print(p.read_text() if p.exists() else 'ok'); sys.exit(1 if p.exists() else 0)")
    d = {
        "mission": {"name": "demo", "goal": "g", "requires": ["tests/acceptance"], "focus": ["plexus/**"],
                    "frozen": ["tests/acceptance/**"], "context": [BRIEF]},
        "metric": {"kind": "command", "cmd": [PY, "-c", "print(open('plexus/score.txt').read().strip())"]},
        "gates": [{"name": "build", "cmd": [PY, "-c", gate]}],
        "steps": [step],
        "router": {"kind": "first"},
        "known_fixes": [{"match": "null or expired layer", "file": BRIEF, "anchor": "returns `None` for a missing file"}],
        "budget": {"attempts": attempts, "hours": 1, "max_consecutive_failures": 9},
    }
    if fix_router is not None:
        d["fix_router"] = fix_router
    return d


def _mission(**kw):
    return mission_from_dict(_raw({"kind": "jev", "brief": BRIEF}, **kw))


def test_the_section_parses_and_defaults_to_off():
    plain = mission_from_dict(_raw())
    assert plain.fix_router == FixRouterSpec() and plain.fix_router.kind == "none"
    assert FixRouterSpec().min_confidence == 0.7
    assert mission_from_dict(_raw({"kind": "none"})).fix_router.kind == "none"
    m = mission_from_dict(_raw({"kind": "jev", "brief": BRIEF, "model": "jev-x", "host": "http://h", "api_key_env": "K",
                                "timeout_s": 5, "min_confidence": 0.8}))
    assert m.fix_router == FixRouterSpec("jev", "jev-x", "http://h", "K", 5, 0.8, BRIEF)
    assert mission_from_dict(_raw({"kind": "jev", "brief": "./docs\\brief.md"})).fix_router.brief == BRIEF


@pytest.mark.parametrize("section, why", [
    ("jev", "must be a table"),
    ({"kind": "llm"}, "kind must be"),
    ({"kind": "jev"}, "needs brief"),
    ({"kind": "jev", "brief": "/abs/brief.md"}, "repo-relative"),
    ({"kind": "jev", "brief": "../brief.md"}, "repo-relative"),
    ({"kind": "jev", "brief": "C:/brief.md"}, "repo-relative"),
    ({"kind": "jev", "brief": "docs/"}, "repo-relative"),
    ({"kind": "none", "brief": "../brief.md"}, "repo-relative"),
    ({"kind": "jev", "brief": "docs/other.md"}, "must be in \\[mission\\] context"),
    ({"kind": "jev", "brief": BRIEF, "min_confidence": 1.5}, "between 0 and 1"),
    ({"kind": "jev", "brief": BRIEF, "min_confidence": -0.1}, "between 0 and 1"),
    ({"kind": "jev", "brief": BRIEF, "min_confidence": float("nan")}, "between 0 and 1"),
    ({"kind": "jev", "brief": BRIEF, "min_confidence": "high"}, "must be numbers"),
    ({"kind": "jev", "brief": BRIEF, "min_confidence": True}, "must be numbers"),
    ({"kind": "jev", "brief": BRIEF, "timeout_s": 0}, "above zero"),
    ({"kind": "jev", "brief": BRIEF, "timeout_s": "soon"}, "must be numbers"),
    ({"kind": "jev", "brief": BRIEF, "timeout_s": float("inf")}, "must be numbers"),
    ({"kind": "jev", "brief": BRIEF, "model": ""}, "must not be empty"),
    ({"kind": "jev", "brief": BRIEF, "host": ""}, "must not be empty"),
    ({"kind": "jev", "brief": BRIEF, "api_key_env": ""}, "must not be empty"),
])
def test_bad_values_are_refused(section, why):
    with pytest.raises(MissionError, match=why):
        mission_from_dict(_raw(section))


def test_a_brief_the_worker_may_change_is_refused():
    # The router reads the attempt's worktree and the next prompt reads a fresh one at tip, so the
    # two copies are the same only if no attempt that reaches the router can have changed it.
    d = _raw({"kind": "jev", "brief": "plexus/brief.md"})
    d["mission"]["context"] = ["plexus/brief.md"]
    with pytest.raises(MissionError, match="may change"):
        mission_from_dict(d)
    d["mission"]["frozen"] = ["plexus/brief.md"]  # a touched frozen path drops the attempt first
    assert mission_from_dict(d).fix_router.brief == "plexus/brief.md"


def test_a_known_fix_file_the_worker_may_change_is_refused_when_the_router_is_on():
    # The loop asks "did a known fix match?" of the attempt's tree and the next prompt of a fresh one
    # at tip, so an attempt that changed that file could get a call and a known-fix quote, or neither.
    d = _raw({"kind": "jev", "brief": BRIEF})
    d["known_fixes"][0]["file"] = "plexus/notes.md"
    with pytest.raises(MissionError, match="may change"):
        mission_from_dict(d)
    d["fix_router"] = {"kind": "none"}
    assert mission_from_dict(d).known_fixes[0].file == "plexus/notes.md"


@pytest.mark.parametrize("value, says", [("fake-key-value", "TYPESAFE_API_KEY is set"),
                                         ("  ", "TYPESAFE_API_KEY is NOT set")])
def test_check_says_whether_the_router_can_run_and_never_shows_the_key(tmp_path, monkeypatch, capsys, value, says):
    monkeypatch.setenv("TYPESAFE_API_KEY", value)
    monkeypatch.setattr("harness.plexus_loop.__main__.load_mission", lambda p: _mission())
    assert cli_main(["check", "any.toml", "--repo", str(_repo(tmp_path))]) == 0
    out = capsys.readouterr().out
    assert "fix router: jev (jev-latest), floor 0.7" in out and says in out and "fake-key-value" not in out


def test_check_says_nothing_of_the_router_without_the_section(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("harness.plexus_loop.__main__.load_mission", lambda p: mission_from_dict(_raw()))
    assert cli_main(["check", "any.toml", "--repo", str(_repo(tmp_path))]) == 0
    assert "fix router" not in capsys.readouterr().out


# -- whole runs -------------------------------------------------------------------------

def _repo(tmp_path: Path, brief: str = BRIEF_TEXT) -> Path:
    r = tmp_path / "repo"
    (r / "docs").mkdir(parents=True)
    (r / "plexus").mkdir()
    (r / "tests" / "acceptance").mkdir(parents=True)
    (r / "tests" / "acceptance" / "f.txt").write_text("x")
    (r / "plexus" / "score.txt").write_text("5\n")
    (r / "plexus" / "b.py").write_text("B = 0\n")
    (r / ".gitignore").write_text("*.tmp\n")
    (r / BRIEF).write_text(brief, encoding="utf-8")
    for args in (["init", "-q", "-b", "master"], ["add", "-A"], ["commit", "-q", "-m", "s"]):
        subprocess.run([*GIT, *args], cwd=r, check=True, capture_output=True)
    return r


class Steps:
    def __init__(self, *steps):
        self.steps, self.prompts = list(steps), []

    def attempt(self, wt, prompt, profile):
        self.prompts.append(prompt)
        return self.steps.pop(0)(wt)


def _write(files: dict[str, str]):
    def step(wt):
        for rel, text in files.items():
            (wt / rel).write_text(text)
        return WorkerResult(True, "ok", wrote=list(files))
    return step


def _run(m, r, worker, log=lambda s: None):
    return MissionRun(m, r, worker=worker, log=log, route_fn=lambda mi, last, att: Route(mi.steps[0], "first"),
                      profile_fn=lambda: Profile(device="cpu", houdini="running")).run()


def _ask_jev(monkeypatch, post):
    """The real route_failure on the loop's path, with Jev faked, as test_router.py fakes choose_route."""
    real = fix_router.route_failure
    monkeypatch.setattr(loop, "route_failure",
                        lambda spec, repo, text, step: real(spec, repo, text, step, post=post, api_key="k"))


def _metrics(monkeypatch, *results):
    """The baseline's result, then one per attempt that reaches the metric."""
    seq = list(results)
    monkeypatch.setattr(loop, "measure", lambda metric, wt, profile: seq.pop(0))


def _failing(value, message=None, tail="the end of the run"):
    return MetricResult(value, total=1, tail=tail, failing=[TEST_ID], messages={TEST_ID: message} if message else {})


def _ledger(r):
    return [json.loads(x) for x in (r / ".plexus_loop" / "demo" / "attempts.jsonl").read_text(encoding="utf-8").splitlines()]


def test_a_no_gain_drop_with_no_known_fix_asks_once_and_the_next_prompt_quotes_the_line(tmp_path, monkeypatch):
    seen = []
    _ask_jev(monkeypatch, fake_jev("b00", 0.82, seen))
    _metrics(monkeypatch, _failing(5.0), _failing(5.0, TYPE_ERROR), _failing(4.0, "[failure] the next one"))
    r = _repo(tmp_path)
    # An uncommitted edit in the main checkout: the attempt's own worktree is the copy that counts.
    (r / BRIEF).write_text("- a line only the main checkout has\n", encoding="utf-8")
    w = Steps(_write({"plexus/a.py": "A = 1\n"}), _write({"plexus/a.py": "A = 2\n"}))
    a, b = _run(_mission(), r, w).attempts
    assert a.reason == "no strict gain (5 vs best 5)" and b.kept
    # One call, for the drop; the keep makes none.
    ((_, body, _, _),) = seen
    assert body["state"]["step_id"] == "S1" and TYPE_ERROR in body["state"]["failure_output"]
    assert body["state"]["failure_output"].endswith("the end of the run")
    assert {k: v for k, v in body["questions"]["fix_line"]["criteria"].items() if k != "none"} == OPTIONS
    # The next prompt quotes it under the target failure, as a guess, never as a known error.
    fb = w.prompts[1].split("## Why the last attempt was dropped", 1)[1]
    assert fb.index("TypeError") < fb.index(ROUTE_LEAD) < fb.index(f"> {CHANGED}") < fb.index("the end of the run")
    assert "the line the failure points at if it fits, and ignore it if it does not:" in fb
    assert fb.count(f"> {CHANGED}") == 1 and "known error" not in w.prompts[1]
    # The ledger row holds the answer and its seconds; the keep's row holds nothing.
    row, kept = _ledger(r)
    seconds = row["fix_route"].pop("seconds")
    assert isinstance(seconds, float) and seconds >= 0
    assert row["fix_route"] == {"pick": "b00", "confidence": 0.82, "line": CHANGED, "quoted": True, "note": "",
                                "model": "", "shown_before": False, "known_fix": ""}
    assert kept["fix_route"] == {}
    # REVIEW.md shows the pick, so its picks can be labelled without reading the ledger.
    review = (r / ".plexus_loop" / "demo" / "REVIEW.md").read_text(encoding="utf-8")
    assert "no strict gain (5 vs best 5) (fix router: b00 0.82 quoted) |" in review


# A second candidate goes to the worker's own code, not to the line the failure points at: 19 of the 33 recorded
# target failures end at a frozen test, and a right line about the code does not fit that test's line.
SECOND_LEAD = ("The worker brief also has a line that may fix this; apply it to your own code "
               "if it fits, and ignore it if it does not:")
SHOWN_SECOND_LEAD = ("The worker brief also has a line that may fix this, but attempt {n} was already shown it and "
                     "still failed, so it did not clear the failure. Apply it to your own code "
                     "only if it clearly fits, and otherwise look for the cause elsewhere:")
# Past both clips, with its anchor in a later sentence: the known fix's quote starts there and stops at
# KNOWN_FIX_CHARS, and the routed line starts at the top and stops at ROUTED_LINE_CHARS.
LONG = ("An earlier fact. " * 30 + "`FindOrOpen` returns `None` for a missing file, " + "so keep reading it. " * 60).strip()
# Past both clips, with its anchor in the first sentence: the two quotes share a start, and only a whole-line compare sees that.
LONG_FIRST = ("`FindOrOpen` returns `None` for a missing file, " + "so keep reading it. " * 70).strip()


def _two_drops():
    """The metric's results for two attempts dropped on the known error, and the worker that wrote them."""
    results = [_failing(5.0), _failing(5.0, NULL_LAYER), _failing(5.0, NULL_LAYER)]
    return results, Steps(_write({"plexus/a.py": "A = 1\n"}), _write({"plexus/a.py": "A = 2\n"}))


def _with_second_fix(**kw):
    """The demo mission with one more known fix, whose line is the one the first known fix does not quote."""
    raw = _raw({"kind": "jev", "brief": BRIEF}, **kw)
    raw["known_fixes"].append({"match": "is not an instance of 'str'", "file": BRIEF, "anchor": "`changed` is a list of `str`"})
    return mission_from_dict(raw)


def test_a_known_fix_still_asks_and_a_different_line_goes_under_it_as_a_second_candidate(tmp_path, monkeypatch):
    seen, logs = [], []
    _ask_jev(monkeypatch, fake_jev("b00", 0.99, seen))
    results, w = _two_drops()
    _metrics(monkeypatch, *results)
    r = _repo(tmp_path)
    a, _ = _run(_mission(), r, w, log=logs.append).attempts
    assert len(seen) == 2 and NULL_LAYER in seen[0][1]["state"]["failure_output"]
    assert a.fix_route["quoted"] and a.fix_route["known_fix"] == "other" and not a.fix_route["shown_before"]
    fb = w.prompts[1].split("## Why the last attempt was dropped", 1)[1]
    assert (fb.index("[failure] Cannot create prim") < fb.index("This is a known error") < fb.index(f"> - {FINDOR}\n")
            < fb.index(SECOND_LEAD) < fb.index(f"> {CHANGED}\n") < fb.index("the end of the run"))
    assert fb.count(ROUTE_LEAD) == 1 and fb.count(f"> {CHANGED}") == 1
    assert any("attempt 1: fix router: b00 0.99, quoted under a known fix" in s for s in logs)
    review = (r / ".plexus_loop" / "demo" / "REVIEW.md").read_text(encoding="utf-8")
    assert "no strict gain (5 vs best 5) (fix router: b00 0.99 quoted under a known fix) |" in review


def test_a_known_fix_and_the_same_routed_line_show_it_once(tmp_path, monkeypatch):
    seen, logs = [], []
    _ask_jev(monkeypatch, fake_jev("b01", 0.99, seen))
    _metrics(monkeypatch, _failing(5.0), *[_failing(5.0, NULL_LAYER)] * 3)
    w = Steps(*[_write({"plexus/a.py": f"A = {i}\n"}) for i in range(3)])
    r = _repo(tmp_path)
    a, b, _ = _run(_mission(attempts=3), r, w, log=logs.append).attempts
    assert len(seen) == 3 and a.fix_route["quoted"] and a.fix_route["line"] == FINDOR and a.fix_route["known_fix"] == "same"
    # Shown before or not, the known fix's lines stay as they were and nothing goes under them.
    assert not a.fix_route["shown_before"] and b.fix_route["shown_before"]
    for prompt in w.prompts[1:]:
        fb = prompt.split("## Why the last attempt was dropped", 1)[1]
        assert fb.count(f"> - {FINDOR}\n") == 1 and f"> {FINDOR}" not in fb
        assert ROUTE_LEAD not in fb and "already shown" not in fb
    assert any("attempt 1: fix router: b01 0.99, same line as its known fix" in s for s in logs)
    review = (r / ".plexus_loop" / "demo" / "REVIEW.md").read_text(encoding="utf-8")
    assert "no strict gain (5 vs best 5) (fix router: b01 0.99 same line as its known fix) |" in review


@pytest.mark.parametrize("line, brief, pick", [
    (LONG, f"- {LONG}\n", "b00"),
    (LONG_FIRST, f"- {LONG_FIRST}\n", "b00"),
    (LONG_FIRST, f"{LONG_FIRST}\n", "l001"),
], ids=["list item, anchor in a later sentence", "list item, anchor in the first sentence", "prose, anchor in the first sentence"])
def test_a_known_fix_and_the_same_routed_line_show_it_once_when_the_line_is_long_enough_to_clip(tmp_path, monkeypatch, line, brief, pick):
    assert len(line) > ROUTED_LINE_CHARS > KNOWN_FIX_CHARS
    seen = []
    _ask_jev(monkeypatch, fake_jev(pick, 0.9, seen))
    results, w = _two_drops()
    _metrics(monkeypatch, *results)
    a, b = _run(_mission(), _repo(tmp_path, brief), w).attempts
    assert len(seen) == 2 and a.fix_route["quoted"] and a.fix_route["line"] == line and a.fix_route["known_fix"] == "same"
    fb = w.prompts[1].split("## Why the last attempt was dropped", 1)[1]
    assert fb.count("is a known error") == 1 and ROUTE_LEAD not in fb
    assert sum(ln.startswith("> ") for ln in fb.splitlines()) == 1
    assert f"> {line[:ROUTED_LINE_CHARS]}" not in fb
    # And the second attempt's own prompt quoted it, clipped, as that known fix: it counts as shown.
    assert not a.fix_route["shown_before"] and b.fix_route["shown_before"]


def test_two_known_fixes_match_and_the_pick_is_the_second_ones_line_so_it_shows_once(tmp_path, monkeypatch):
    # Rows 46 to 48, 52, 54 and 56 matched two or three known fixes. A pick of a later one's line must not print twice.
    _ask_jev(monkeypatch, fake_jev("b00", 0.9))
    both = f"{NULL_LAYER}\n{TYPE_ERROR}"
    _metrics(monkeypatch, _failing(5.0), _failing(5.0, both), _failing(5.0, both))
    w = Steps(_write({"plexus/a.py": "A = 1\n"}), _write({"plexus/a.py": "A = 2\n"}))
    a, _ = _run(_with_second_fix(), _repo(tmp_path), w).attempts
    assert a.fix_route["known_fix"] == "same"
    fb = w.prompts[1].split("## Why the last attempt was dropped", 1)[1]
    assert fb.count(f"> - {CHANGED}\n") == 1 and fb.count(f"> - {FINDOR}\n") == 1
    assert f"> {CHANGED}\n" not in fb and ROUTE_LEAD not in fb


@pytest.mark.parametrize("post, says", [
    (fake_jev("none", 0.95), "jev chose none"),
    (fake_jev("b00", 0.69), "below 0.7"),
    (fake_jev("b99", 0.95), "unknown line"),
    (raising(OSError("down")), "jev unavailable: OSError"),
    (raising(TimeoutError("timed out")), "jev unavailable: TimeoutError"),
], ids=["abstains", "below the floor", "an unknown line", "fails", "times out"])
def test_under_a_known_fix_no_usable_answer_leaves_the_prompt_as_it_was_byte_for_byte(tmp_path, monkeypatch, post, says):
    calls = []

    def counted(*args):
        calls.append(args)
        return post(*args)
    _ask_jev(monkeypatch, counted)
    results, w = _two_drops()
    _metrics(monkeypatch, *results)
    a, _ = _run(_mission(), _repo(tmp_path / "on"), w).attempts
    assert len(calls) == 2 and says in a.fix_route["note"] and not a.fix_route["quoted"] and a.fix_route["known_fix"]
    results, without = _two_drops()
    _metrics(monkeypatch, *results)
    _run(mission_from_dict(_raw()), _repo(tmp_path / "off"), without)
    assert w.prompts[1] == without.prompts[1] and "This is a known error" in w.prompts[1] and ROUTE_LEAD not in w.prompts[1]


def test_both_quotes_and_the_compare_are_read_from_the_attempts_worktree(tmp_path, monkeypatch):
    # The next prompt reads a fresh worktree at tip, never the main checkout (the Nov 3 mistake). Read from
    # here, this anchor would be gone: the row would say no known fix matched and the line was never shown,
    # while the prompts quote the known fix.
    seen = []
    _ask_jev(monkeypatch, fake_jev("b01", 0.99, seen))
    results, w = _two_drops()
    _metrics(monkeypatch, *results)
    r = _repo(tmp_path)
    (r / BRIEF).write_text("- a line only the main checkout has\n", encoding="utf-8")
    a, b = _run(_mission(), r, w).attempts
    assert len(seen) == 2 and a.fix_route["known_fix"] == b.fix_route["known_fix"] == "same"
    assert [a.fix_route["shown_before"], b.fix_route["shown_before"]] == [False, True]
    assert "This is a known error" in w.prompts[1] and ROUTE_LEAD not in w.prompts[1]


@pytest.mark.parametrize("line", [FINDOR, LONG], ids=["whole", "clipped, from a later sentence"])
def test_a_line_shown_as_a_known_fix_quote_counts_as_shown_when_no_known_fix_matches_the_next_failure(tmp_path, monkeypatch, line):
    # The known fix quoted it on attempt 2's prompt, attempt 2 failed another way, and Jev now picks that line.
    brief = BRIEF_TEXT if line == FINDOR else f"- {CHANGED}\n- {line}\n"
    _ask_jev(monkeypatch, fake_jev("b01", 0.9))
    _metrics(monkeypatch, _failing(5.0), _failing(5.0, NULL_LAYER), _failing(5.0, TYPE_ERROR), _failing(5.0, TYPE_ERROR))
    w = Steps(*[_write({"plexus/a.py": f"A = {i}\n"}) for i in range(3)])
    first, second, _ = _run(_mission(attempts=3), _repo(tmp_path, brief), w).attempts
    assert not first.fix_route["shown_before"] and second.fix_route["shown_before"] and second.fix_route["known_fix"] == ""
    fb = w.prompts[2].split("## Why the last attempt was dropped", 1)[1]
    assert "The worker brief has a line that may fix this, but attempt 2 was already shown it and still failed" in fb
    assert "the line the failure points at only if it clearly fits" in fb and "is a known error" not in fb
    assert fb.count(f"> {line[:ROUTED_LINE_CHARS]}") == 1


def test_a_line_shown_as_one_known_fix_counts_as_shown_under_another(tmp_path, monkeypatch):
    # Attempt 2's prompt quotes the first known fix, its failure matches the second, and Jev picks the first's line.
    _ask_jev(monkeypatch, fake_jev("b01", 0.9))
    _metrics(monkeypatch, _failing(5.0), _failing(5.0, NULL_LAYER), _failing(5.0, TYPE_ERROR), _failing(5.0, TYPE_ERROR))
    w = Steps(*[_write({"plexus/a.py": f"A = {i}\n"}) for i in range(3)])
    _, second, _ = _run(_with_second_fix(attempts=3), _repo(tmp_path), w).attempts
    assert second.fix_route["shown_before"] and second.fix_route["known_fix"] == "other"
    fb = w.prompts[2].split("## Why the last attempt was dropped", 1)[1]
    assert (fb.index("This is a known error") < fb.index(f"> - {CHANGED}\n") < fb.index(SHOWN_SECOND_LEAD.format(n=2))
            < fb.index(f"> {FINDOR}\n"))
    assert fb.count(ROUTE_LEAD) == 1


def test_a_second_candidate_that_did_not_clear_the_failure_is_said_to_have_been_shown(tmp_path, monkeypatch):
    _ask_jev(monkeypatch, fake_jev("b00", 0.9))
    _metrics(monkeypatch, _failing(5.0), *[_failing(5.0, NULL_LAYER)] * 3)
    w = Steps(*[_write({"plexus/a.py": f"A = {i}\n"}) for i in range(3)])
    atts = _run(_mission(attempts=3), _repo(tmp_path), w).attempts
    assert [a.fix_route["shown_before"] for a in atts] == [False, True, True]
    assert SECOND_LEAD in w.prompts[1] and "already shown" not in w.prompts[1]
    fb = w.prompts[2].split("## Why the last attempt was dropped", 1)[1]
    assert (fb.index("This is a known error") < fb.index(f"> - {FINDOR}\n") < fb.index(SHOWN_SECOND_LEAD.format(n=2))
            < fb.index(f"> {CHANGED}\n"))


def test_a_line_the_prompt_did_not_quote_is_not_said_to_have_been_shown_because_a_known_fix_was(tmp_path, monkeypatch):
    # Attempt 2's prompt quotes the known fix and nothing else, because Jev fell below the floor, and Jev now picks another line.
    answers = [("b00", 0.5), ("b00", 0.9)]

    def post(url, body, headers, timeout):
        choice, confidence = answers.pop(0)
        return {"answers": {"fix_line": {"choice": choice, "confidence": confidence}}}
    _ask_jev(monkeypatch, post)
    results, w = _two_drops()
    _metrics(monkeypatch, *results)
    a, b = _run(_mission(), _repo(tmp_path), w).attempts
    assert not a.fix_route["quoted"] and b.fix_route["quoted"] and b.fix_route["known_fix"] == "other"
    assert f"> - {FINDOR}\n" in w.prompts[1] and not b.fix_route["shown_before"]


def test_a_known_fix_whose_file_is_gone_counts_for_nothing_and_stops_nothing(tmp_path, monkeypatch):
    raw = _raw({"kind": "jev", "brief": BRIEF})
    raw["known_fixes"].insert(0, {"match": "null or expired layer", "file": "docs/gone.md", "anchor": "not there"})
    raw["known_fixes"][1]["anchor"] = "an anchor no line holds"
    _ask_jev(monkeypatch, fake_jev("b00", 0.9))
    results, w = _two_drops()
    _metrics(monkeypatch, *results)
    a, b = _run(mission_from_dict(raw), _repo(tmp_path), w).attempts
    assert a.fix_route["known_fix"] == "" and a.reason == "no strict gain (5 vs best 5)" and b.fix_route["shown_before"]
    assert "is a known error" not in w.prompts[1] and ROUTE_LEAD in w.prompts[1]


def test_a_line_the_attempt_was_already_shown_is_quoted_again_with_that_said(tmp_path, monkeypatch):
    # The floor does not catch a wrong pick that repeats: replayed, wrong picks scored as high as right ones.
    seen = []
    _ask_jev(monkeypatch, fake_jev("b00", 0.9, seen))
    _metrics(monkeypatch, _failing(5.0), *[_failing(5.0, TYPE_ERROR)] * 3)
    r = _repo(tmp_path)
    w = Steps(*[_write({"plexus/a.py": f"A = {i}\n"}) for i in range(3)])
    atts = _run(_mission(attempts=3), r, w).attempts
    assert len(seen) == 3 and [a.fix_route["shown_before"] for a in atts] == [False, True, True]
    assert [row["fix_route"]["shown_before"] for row in _ledger(r)] == [False, True, True]
    first = w.prompts[1].split("## Why the last attempt was dropped", 1)[1]
    assert "already shown" not in first and first.count(f"> {CHANGED}") == 1
    again = w.prompts[2].split("## Why the last attempt was dropped", 1)[1]
    assert "attempt 2 was already shown it and still failed, so it did not clear the failure" in again
    assert "the line the failure points at only if it clearly fits" in again
    assert again.index("already shown") < again.index(f"> {CHANGED}") and again.count(f"> {CHANGED}") == 1
    assert "known error" not in w.prompts[2]


def test_a_different_line_or_one_below_the_floor_is_not_said_to_have_been_shown(tmp_path, monkeypatch):
    answers = [("b00", 0.9), ("b01", 0.9), ("b01", 0.5), ("b01", 0.9)]

    def post(url, body, headers, timeout):
        choice, confidence = answers.pop(0)
        return {"answers": {"fix_line": {"choice": choice, "confidence": confidence}}}
    _ask_jev(monkeypatch, post)
    _metrics(monkeypatch, _failing(5.0), *[_failing(5.0, TYPE_ERROR)] * 4)
    w = Steps(*[_write({"plexus/a.py": f"A = {i}\n"}) for i in range(4)])
    atts = _run(_mission(attempts=4), _repo(tmp_path), w).attempts
    # The last one: its own prompt carried no quote, because the attempt before it fell below the floor.
    assert [a.fix_route["shown_before"] for a in atts] == [False, False, False, False]


def test_a_routed_line_past_the_known_fix_clip_counts_as_shown(tmp_path, monkeypatch):
    line = "An earlier fact. " * 50 + "The fix is at the end of the line."
    assert KNOWN_FIX_CHARS < len(line) < ROUTED_LINE_CHARS
    _ask_jev(monkeypatch, fake_jev("b00", 0.9))
    _metrics(monkeypatch, _failing(5.0), _failing(5.0, TYPE_ERROR), _failing(5.0, TYPE_ERROR))
    w = Steps(_write({"plexus/a.py": "A = 1\n"}), _write({"plexus/a.py": "A = 2\n"}))
    a, b = _run(_mission(), _repo(tmp_path, f"- {line}\n"), w).attempts
    assert [a.fix_route["shown_before"], b.fix_route["shown_before"]] == [False, True]


def test_a_longer_line_quoted_does_not_count_for_the_line_it_starts_with(tmp_path, monkeypatch):
    short = "A rule that is the start of a longer one, long enough."
    long = short + " And more that the longer one goes on to say."
    answers = [("b01", 0.9), ("b00", 0.9)]

    def post(url, body, headers, timeout):
        choice, confidence = answers.pop(0)
        return {"answers": {"fix_line": {"choice": choice, "confidence": confidence}}}
    _ask_jev(monkeypatch, post)
    _metrics(monkeypatch, _failing(5.0), _failing(5.0, TYPE_ERROR), _failing(5.0, TYPE_ERROR))
    w = Steps(_write({"plexus/a.py": "A = 1\n"}), _write({"plexus/a.py": "A = 2\n"}))
    _, b = _run(_mission(), _repo(tmp_path, f"- {short}\n- {long}\n"), w).attempts
    assert b.fix_route["line"] == short and not b.fix_route["shown_before"]


def test_a_note_the_console_cannot_encode_leaves_the_drop_reason_alone(tmp_path, monkeypatch):
    # A redirected stdout here is cp1252. A raise from the log would reach the attempt's error
    # handling, which replaces the reason on the row and in the next prompt.
    said = []

    def cp1252(s):
        said.append(s)
        s.encode("cp1252")
    _ask_jev(monkeypatch, fake_jev("→b00", 0.9))
    _metrics(monkeypatch, _failing(5.0), _failing(5.0, TYPE_ERROR))
    (a,) = _run(_mission(attempts=1), _repo(tmp_path), Steps(_write({"plexus/a.py": "A = 1\n"})), log=cp1252).attempts
    assert a.reason == "no strict gain (5 vs best 5)" and a.fix_route["pick"] == "→b00"
    assert any("fix router: jev picked unknown line" in s and "\\u2192b00" in s for s in said)


def test_a_pick_no_file_can_hold_cannot_stop_the_run(tmp_path, monkeypatch):
    # JSON can carry a lone surrogate, which UTF-8 refuses, and REVIEW.md is written outside any
    # attempt's error handling: a raise there would end the run, not the attempt.
    _ask_jev(monkeypatch, fake_jev("\ud800\nb|00", 0.9))
    _metrics(monkeypatch, _failing(5.0), _failing(5.0, TYPE_ERROR), _failing(5.0, TYPE_ERROR))
    r = _repo(tmp_path)
    w = Steps(_write({"plexus/a.py": "A = 1\n"}), _write({"plexus/a.py": "A = 2\n"}))
    assert len(_run(_mission(), r, w).attempts) == 2 and len(_ledger(r)) == 2
    assert "(fix router: \\ud800\\nb/00 0.9)" in (r / ".plexus_loop" / "demo" / "REVIEW.md").read_text(encoding="utf-8")


def test_a_failing_gate_asks_whether_or_not_a_known_fix_matches_and_a_keep_never_asks(tmp_path, monkeypatch):
    seen, picks = [], ["b01", "b00"]

    def post(url, body, headers, timeout):
        seen.append(body)
        return {"answers": {"fix_line": {"choice": picks.pop(0), "confidence": 0.9}}}
    _ask_jev(monkeypatch, post)
    w = Steps(_write({"plexus/gate.txt": "error: null or expired layer"}),
              _write({"plexus/gate.txt": "error[E0999]: a new one"}),
              _write({"plexus/score.txt": "4\n"}))
    known, new, kept = _run(_mission(attempts=3), _repo(tmp_path), w).attempts
    assert known.reason == new.reason == "gate 'build' failed" and kept.kept and kept.fix_route == {}
    assert len(seen) == 2 and "null or expired layer" in seen[0]["state"]["failure_output"]
    assert "E0999" in seen[1]["state"]["failure_output"]
    # The known fix quotes the line Jev chose, so it shows once. The new failure has no known fix: today's wording stands.
    assert known.fix_route["known_fix"] == "same" and new.fix_route["known_fix"] == ""
    assert "It is a known error" in w.prompts[1] and ROUTE_LEAD not in w.prompts[1]
    fb = w.prompts[2].split("## Why the last attempt was dropped", 1)[1]
    assert fb.index("E0999") < fb.index("Fix the cause first") < fb.index(ROUTE_LEAD) < fb.index(f"> {CHANGED}")
    assert "the line the output points at if it fits" in fb and "known error" not in w.prompts[2]


def test_a_failing_gates_known_fix_takes_a_different_line_under_it(tmp_path, monkeypatch):
    _ask_jev(monkeypatch, fake_jev("b00", 0.9))
    w = Steps(_write({"plexus/gate.txt": "error: null or expired layer"}), _write({"plexus/gate.txt": "x"}))
    _run(_mission(), _repo(tmp_path), w)
    fb = w.prompts[1].split("## Why the last attempt was dropped", 1)[1]
    assert (fb.index("It is a known error") < fb.index("the line the output points at:\n> - `FindOrOpen`")
            < fb.index(SECOND_LEAD) < fb.index(f"> {CHANGED}\n"))


def test_a_keep_never_asks_even_with_a_known_error_in_its_targets(tmp_path, monkeypatch):
    seen = []
    _ask_jev(monkeypatch, fake_jev("b00", 0.9, seen))
    _metrics(monkeypatch, _failing(5.0), _failing(5.0, NULL_LAYER), _failing(4.0, NULL_LAYER))
    w = Steps(_write({"plexus/a.py": "A = 1\n"}), _write({"plexus/a.py": "A = 2\n"}))
    dropped, kept = _run(_mission(), _repo(tmp_path), w).attempts
    assert kept.kept and kept.fix_route == {} and dropped.fix_route["pick"] == "b00" and len(seen) == 1


def test_a_drop_that_ran_nothing_makes_no_call_even_right_after_a_known_fix_asked(tmp_path, monkeypatch):
    asks = []

    def ask(*args):
        asks.append(args)
        return FixRoute(note="faked")
    monkeypatch.setattr(loop, "route_failure", ask)
    _metrics(monkeypatch, _failing(5.0), _failing(5.0, NULL_LAYER))
    w = Steps(_write({"plexus/a.py": "A = 1\n"}),
              lambda wt: WorkerResult(False, "model returned nothing usable"),
              lambda wt: WorkerResult(True, "ok"),
              _write({"tests/acceptance/x.txt": "x"}),
              _write({"docs/other.md": "x"}),
              _write({"plexus/x.tmp": "x"}))
    full, *rest = _run(_mission(attempts=6), _repo(tmp_path), w).attempts
    assert full.fix_route["known_fix"] and len(asks) == 1 and all(a.fix_route == {} for a in rest)
    assert [a.reason.split(":")[0].split(" ")[0] for a in rest] == ["worker", "no", "touched", "touched", "wrote"]


def test_a_drop_that_ran_nothing_makes_no_call(tmp_path, monkeypatch):
    asks = []
    monkeypatch.setattr(loop, "route_failure", lambda *a, **kw: asks.append(a))
    w = Steps(lambda wt: WorkerResult(False, "model returned nothing usable"),
              lambda wt: WorkerResult(True, "ok"),
              _write({"tests/acceptance/x.txt": "x"}),
              _write({"docs/other.md": "x"}),
              _write({"plexus/x.tmp": "x"}))
    atts = _run(_mission(attempts=5), _repo(tmp_path), w).attempts
    assert [a.reason.split(":")[0].split(" ")[0] for a in atts] == ["worker", "no", "touched", "touched", "wrote"]
    assert asks == [] and all(a.fix_route == {} for a in atts)


FILES = ["plexus/a.py", "plexus/b.py"]
BOTH = {"plexus/a.py": "A = 1\n", "plexus/b.py": "B = 2\n"}
ONLY_A = {"plexus/a.py": "A = 2\n"}


def test_a_left_out_drop_makes_no_call_and_still_shows_the_last_full_attempts_line(tmp_path, monkeypatch):
    seen = []
    _ask_jev(monkeypatch, fake_jev("b00", 0.9, seen))
    _metrics(monkeypatch, _failing(5.0), _failing(5.0, TYPE_ERROR))
    w = Steps(_write(BOTH), _write(ONLY_A), _write(ONLY_A))
    full, lo1, lo2 = _run(_mission(files=FILES, attempts=3), _repo(tmp_path), w).attempts
    assert full.fix_route["quoted"] and len(seen) == 1
    assert lo1.reason == lo2.reason == f"{LEFT_OUT}: plexus/b.py" and lo1.fix_route == lo2.fix_route == {}
    section = w.prompts[2].split("## Your last full attempt (1) was dropped", 1)[1].split("## Your last attempt's files", 1)[0]
    assert section.index("TypeError") < section.index(ROUTE_LEAD) < section.index(f"> {CHANGED}")
    assert "the line the failure points at" in section


def test_a_left_out_drop_makes_no_call_and_still_shows_both_lines_of_the_last_full_attempt(tmp_path, monkeypatch):
    seen = []
    _ask_jev(monkeypatch, fake_jev("b00", 0.9, seen))
    _metrics(monkeypatch, _failing(5.0), _failing(5.0, NULL_LAYER))
    w = Steps(_write(BOTH), _write(ONLY_A), _write(ONLY_A))
    full, lo1, lo2 = _run(_mission(files=FILES, attempts=3), _repo(tmp_path), w).attempts
    assert full.fix_route["known_fix"] == "other" and len(seen) == 1 and lo1.fix_route == lo2.fix_route == {}
    section = w.prompts[2].split("## Your last full attempt (1) was dropped", 1)[1].split("## Your last attempt's files", 1)[0]
    assert (section.index("This is a known error") < section.index(f"> - {FINDOR}\n") < section.index(SECOND_LEAD)
            < section.index(f"> {CHANGED}\n"))


def test_a_left_out_drop_shows_the_line_for_a_last_full_attempt_with_only_a_metric_tail(tmp_path, monkeypatch):
    seen = []
    _ask_jev(monkeypatch, fake_jev("b01", 0.9, seen))
    w = Steps(_write(BOTH), _write(ONLY_A), _write(ONLY_A))
    full, _, _ = _run(_mission(files=FILES, attempts=3), _repo(tmp_path), w).attempts
    assert full.target_failures == [] and full.detail and len(seen) == 1  # the command metric has no test ids
    section = w.prompts[2].split("## Your last full attempt (1) was dropped", 1)[1].split("## Your last attempt's files", 1)[0]
    assert section.index("This is what it printed:") < section.index(ROUTE_LEAD) < section.index(f"> {FINDOR}")
    assert "the line the output points at" in section


def test_a_line_quoted_in_the_last_full_attempts_section_counts_as_shown(tmp_path, monkeypatch):
    _ask_jev(monkeypatch, fake_jev("b00", 0.9))
    _metrics(monkeypatch, _failing(5.0), _failing(5.0, TYPE_ERROR), _failing(5.0, TYPE_ERROR))
    w = Steps(_write(BOTH), _write(ONLY_A), _write({"plexus/a.py": "A = 3\n", "plexus/b.py": "B = 3\n"}))
    full, _, again = _run(_mission(files=FILES, attempts=3), _repo(tmp_path), w).attempts
    assert not full.fix_route["shown_before"] and again.fix_route["shown_before"]


def test_a_left_out_drop_on_another_step_does_not_bring_back_the_other_steps_router_line(tmp_path):
    m, r = _mission(), _repo(tmp_path)
    full = _drop(detail="the end of the run", target_failures=[f"{TEST_ID}\n{TYPE_ERROR}"], fix_route=QUOTED)
    left = _drop(n=2, reason=f"{LEFT_OUT}: plexus/b.py", changed=["plexus/a.py"])
    left.route = "S2 via first"
    p = build_prompt(m, r, 5, None, [full, left], 100000, step=Step("S2", ["t/test_two.py"], "Do step two."))
    assert "## Your last full attempt" not in p and f"> {CHANGED}" not in p


def test_a_drop_asks_when_it_ran_and_printed_something_whatever_its_reason(tmp_path, monkeypatch):
    # No target failures on any of these: a tail is all they have. The last one printed nothing.
    seen = []
    _ask_jev(monkeypatch, fake_jev("b00", 0.9, seen))
    _metrics(monkeypatch,
             MetricResult(5.0, total=5, tail="base"),
             MetricResult(5.0, total=5, tail="a null or expired layer in a later step's test"),
             MetricResult(5.0, total=3, tail="ERROR collecting test_t1.py"),
             MetricResult(None, tail="boom", error="no tests collected"),
             MetricResult(5.0, total=5, tail=""))
    w = Steps(*[_write({"plexus/a.py": f"A = {i}\n"}) for i in range(4)])
    tail, missing, unavailable, silent = _run(_mission(attempts=4), _repo(tmp_path), w).attempts
    assert missing.reason.startswith("tests went missing") and unavailable.reason.startswith("metric unavailable")
    assert len(seen) == 3 and silent.fix_route == {}
    # A tail is only ever matched by a known fix for a failing gate, so the regex in the first tail
    # quotes nothing in the prompt, and the row says no known fix matched.
    assert tail.fix_route["quoted"] and tail.fix_route["known_fix"] == "" and "known error" not in w.prompts[1]
    for p in w.prompts[1:]:
        fb = p.split("## Why the last attempt was dropped", 1)[1]
        assert fb.index("Fix the cause first") < fb.index(ROUTE_LEAD) < fb.index(f"> {CHANGED}")


def test_a_failed_call_costs_the_quote_and_nothing_else(tmp_path, monkeypatch):
    logs: list[str] = []
    _ask_jev(monkeypatch, raising(OSError("down")))
    w = Steps(_write({"plexus/a.py": "A = 1\n"}), _write({"plexus/score.txt": "4\n"}))
    a, b = _run(_mission(), _repo(tmp_path), w, log=logs.append).attempts
    assert not a.fix_route["quoted"] and "jev unavailable: OSError: down" in a.fix_route["note"]
    assert isinstance(a.fix_route["seconds"], float) and b.kept
    assert ROUTE_LEAD not in w.prompts[1]
    assert any("attempt 1: fix router: jev unavailable" in s for s in logs)


# -- a mission without the section ------------------------------------------------------

def test_a_mission_without_the_section_makes_no_call_logs_nothing_and_its_rows_hold_nothing(tmp_path, monkeypatch):
    calls, logs = [], []
    monkeypatch.setenv("TYPESAFE_API_KEY", "k")
    monkeypatch.setattr(fix_router, "_http_post", lambda *a: calls.append(a))
    monkeypatch.setattr(loop, "route_failure", lambda *a, **kw: calls.append(a))
    r = _repo(tmp_path)
    w = Steps(_write({"plexus/gate.txt": "error[E0999]: a new one"}), _write({"plexus/a.py": "A = 1\n"}))
    atts = _run(mission_from_dict(_raw()), r, w, log=logs.append).attempts
    assert [a.reason for a in atts] == ["gate 'build' failed", "no strict gain (5 vs best 5)"]
    assert calls == [] and all(a.fix_route == {} for a in atts)
    assert [row["fix_route"] for row in _ledger(r)] == [{}, {}]
    assert not any("fix router" in s for s in logs) and ROUTE_LEAD not in w.prompts[1]
    assert "fix router" not in (r / ".plexus_loop" / "demo" / "REVIEW.md").read_text(encoding="utf-8")


def test_new_rows_default_to_no_route():
    assert Attempt(n=1, started=0.0, houdini="off", device="gpu").fix_route == {}


# These three are what build_prompt printed before the fix router existed, generated at 370c95c. Word a
# change to the prompt here on purpose: "nothing changes without the section" is what they pin.
_HEAD = [
    "# Mission: demo",
    "",
    "g",
    "",
    "## Rules",
    "- Change only paths matching: nothing/**",
    "- Never change: harness/**",
    "- For each NEW file, or a file you rewrite completely, reply with its whole content in a fenced block whose info string is file:<path>, e.g. ```file:plexus/core/axon.py.",
    "- For edits to existing files, reply with one unified diff (paths relative to the repo root, a/ and b/ prefixes) inside a ```diff block.",
    "- Make the smallest change that moves the number. Don't skip, delete or weaken tests.",
    "",
    "## This attempt: step S1",
    "Aim at: t/test_t1.py",
    "",
    "Do the step.",
    "",
    "Do this step only. Later steps get their own attempts.",
    "",
    "## Why the last attempt was dropped",
]
_REPLY = [
    "",
    "## Your reply",
    "New or fully rewritten files: one ```file:<path> block each, holding the whole file. Edits to existing files: one ```diff block with a/ and b/ prefixes. Nothing else inside either.",
]
BEFORE_LEFT_OUT = "\n".join([
    *_HEAD,
    "Attempt 2 (step S1 via first) was dropped: reply left out step files: nothing/b.py.",
    "",
    "## Your last full attempt (1) was dropped: no strict gain (5 vs best 5)",
    "Its step's own target tests failed like this. This is still the thing to fix:",
    "```",
    "tests.acceptance.phase1.test_t1::t",
    "[failure] Cannot create prim in null or expired layer",
    "```",
    "This is a known error. The worker brief already gives its fix; apply it to the line the failure points at:",
    "> - `FindOrOpen` returns `None` for a missing file, so write `FindOrOpen(p) or CreateNew(p)`.",
    "",
    "## Your last attempt's files",
    "Attempt 2 sent only nothing/a.py and left out nothing/b.py, so nothing it sent was built or tested. Its versions of these files are below. The repo no longer has them: every attempt starts from the last kept commit, so each is gone or back to its last kept version. Resend every one of them in full, as whole-file blocks, together with every file still missing: nothing/b.py.",
    "",
    "```file:nothing/a.py",
    "A = 1",
    "```",
    "",
    "## Where it stands",
    "Current lower-is-better score: 5. A change is kept only if it improves this by at least 1.",
    "",
    "## Recent attempts that were not kept",
    "- attempt 1: no strict gain (5 vs best 5)",
    "- attempt 2: reply left out step files: nothing/b.py",
    *_REPLY,
])
BEFORE_GATE = "\n".join([
    *_HEAD,
    "Attempt 1 (step S1 via first) was dropped: gate 'build' failed.",
    "This is what it printed:",
    "```",
    "$ build",
    "error: null or expired layer",
    "```",
    "Fix the cause first. It is usually one rule or one error near the top of that output.",
    "It is a known error. The worker brief already gives its fix; apply it to the line the output points at:",
    "> - `FindOrOpen` returns `None` for a missing file, so write `FindOrOpen(p) or CreateNew(p)`.",
    "",
    "## Where it stands",
    "Current lower-is-better score: 5. A change is kept only if it improves this by at least 1.",
    "",
    "## Recent attempts that were not kept",
    "- attempt 1: gate 'build' failed",
    "",
    "## Latest metric output (tail)",
    "```",
    "the tail",
    "```",
    *_REPLY,
])
BEFORE_TAIL = "\n".join([
    *_HEAD,
    "Attempt 1 (step S1 via first) was dropped: no strict gain (5 vs best 5).",
    "This is what it printed:",
    "```",
    "the end of the run",
    "```",
    "Fix the cause first. It is usually one rule or one error near the top of that output.",
    "",
    "## Where it stands",
    "Current lower-is-better score: 5. A change is kept only if it improves this by at least 1.",
    "",
    "## Recent attempts that were not kept",
    "- attempt 1: no strict gain (5 vs best 5)",
    *_REPLY,
])


def _drop(**kw):
    kw.setdefault("reason", "no strict gain (5 vs best 5)")
    return Attempt(n=kw.pop("n", 1), started=0.0, houdini="off", device="cpu", route="S1 via first", **kw)


def _before_mission():
    return mission_from_dict({
        "mission": {"name": "demo", "goal": "g", "focus": ["nothing/**"], "frozen": ["harness/**"], "context": []},
        "metric": {"kind": "command", "cmd": ["x"]},
        "gates": [{"name": "build", "cmd": ["x"]}],
        "steps": [{"id": "S1", "targets": ["t/test_t1.py"], "text": "Do the step."}],
        "router": {"kind": "first"},
        "known_fixes": [{"match": "null or expired layer", "file": BRIEF, "anchor": "returns `None` for a missing file"}],
    })


def test_a_mission_without_the_section_gets_the_prompt_it_got_before_byte_for_byte(tmp_path):
    m, r = _before_mission(), _repo(tmp_path)
    assert build_prompt(m, r, 5, None,
                        [_drop(detail="the end of the run", target_failures=[f"{TEST_ID}\n{NULL_LAYER}"]),
                         _drop(n=2, reason=f"{LEFT_OUT}: nothing/b.py", changed=["nothing/a.py"])],
                        100000, step=m.steps[0], carried=(2, {"nothing/a.py": "A = 1\n"})) == BEFORE_LEFT_OUT
    assert build_prompt(m, r, 5, MetricResult(5.0, tail="the tail"),
                        [_drop(reason="gate 'build' failed", detail="$ build\nerror: null or expired layer")],
                        100000, step=m.steps[0]) == BEFORE_GATE
    assert build_prompt(m, r, 5, None, [_drop(detail="the end of the run")], 100000, step=m.steps[0]) == BEFORE_TAIL


# -- the prompt -------------------------------------------------------------------------

def test_a_quoted_route_adds_exactly_its_two_lines_and_building_the_prompt_never_calls_jev(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(fix_router, "_http_post", lambda *a: calls.append(a))
    monkeypatch.setattr(loop, "route_failure", lambda *a, **kw: calls.append(a))
    m, r = _mission(), _repo(tmp_path)
    plain = build_prompt(m, r, 5, None, [_drop(detail="the end of the run")], 100000, step=m.steps[0])
    quoted = build_prompt(m, r, 5, None, [_drop(detail="the end of the run", fix_route=QUOTED)], 100000, step=m.steps[0])
    added = ("The worker brief has a line that may fix this; apply it to the line the output points at if it fits, "
             f"and ignore it if it does not:\n> {CHANGED}\n")
    assert added in quoted and quoted.replace(added, "") == plain
    assert calls == []


@pytest.mark.parametrize("route", [
    {},
    {"pick": "b00", "confidence": 0.5, "line": CHANGED, "quoted": False, "note": "jev picked b00 at 0.50, below 0.7", "seconds": 0.2},
    {"pick": "none", "confidence": 0.9, "line": "", "quoted": False, "note": "jev chose none at 0.90", "seconds": 0.2},
    {"pick": "", "confidence": None, "line": "", "quoted": False, "note": "jev unavailable: OSError: down", "seconds": 0.2},
])
def test_a_route_that_is_not_quoted_changes_nothing_in_the_prompt(tmp_path, route):
    m, r = _mission(), _repo(tmp_path)
    plain = build_prompt(m, r, 5, None, [_drop(detail="the end of the run")], 100000, step=m.steps[0])
    assert build_prompt(m, r, 5, None, [_drop(detail="the end of the run", fix_route=route)], 100000, step=m.steps[0]) == plain


def test_a_stored_route_goes_under_a_known_fix_and_adds_exactly_its_two_lines(tmp_path):
    m, r = _mission(), _repo(tmp_path)
    failure = {"detail": "the end of the run", "target_failures": [f"{TEST_ID}\n{NULL_LAYER}"]}
    plain = build_prompt(m, r, 5, None, [_drop(**failure)], 100000, step=m.steps[0])
    p = build_prompt(m, r, 5, None, [_drop(**failure, fix_route=QUOTED)], 100000, step=m.steps[0])
    added = f"{SECOND_LEAD}\n> {CHANGED}\n"
    assert p.index(f"> - {FINDOR}\n") < p.index(added) and p.replace(added, "") == plain


def test_the_compare_is_on_whole_lines_of_the_brief_not_on_their_quotes(tmp_path):
    # The known fix below points at the first line holding its anchor. The same line shows once; another line is
    # added, even when its text is a sentence of the known fix's line or the known fix's line is a sentence of it.
    tail = "`FindOrOpen` returns `None` for a missing file."
    prose = f"A prose rule long enough to be offered. {tail}"
    indented = f"- A rule in an indented item, long enough to be offered. {tail}"
    m = _mission()

    def quotes(brief, routed):
        a = _drop(detail="x", target_failures=[f"{TEST_ID}\n{NULL_LAYER}"], fix_route={**QUOTED, "line": routed})
        return [ln for ln in fix_lines(m, _tree(tmp_path, brief), a) if ln.startswith("> ")]
    # The same line: a prose line, an indented item brief_lines offers with its marker, and a list item.
    for brief, routed in ((f"{prose}\n", prose), (f"  {indented}\n", indented), (f"- {prose}\n", prose)):
        assert list(brief_lines(brief).values()) == [routed]
        assert len(quotes(brief, routed)) == 1
    # Another line: the routed line is the known fix's anchored sentence, or holds the known fix's whole line.
    assert quotes(f"- {prose}\n- {tail}\n", tail) == [f"> …{tail}", f"> {tail}"]
    assert quotes(f"- {tail}\n- {prose}\n", prose) == [f"> - {tail}", f"> {prose}"]
    # Another line, though the two agree on all that either quote shows.
    one, two = f"{LONG_FIRST} The end of one.", f"{LONG_FIRST} The end of two."
    assert quotes(f"- {one}\n- {two}\n", two) == [f"> - {one}"[:KNOWN_FIX_CHARS + 2], f"> {two[:ROUTED_LINE_CHARS]}"]


def test_a_routed_line_is_shown_whole_where_a_known_fix_would_clip(tmp_path):
    m, r = _mission(), _repo(tmp_path)
    long = "An earlier fact. " * 50 + "The fix is at the end of the line."
    assert KNOWN_FIX_CHARS < len(long) < ROUTED_LINE_CHARS
    a = _drop(detail="x", fix_route={**QUOTED, "line": long})
    assert fix_lines(m, r, a)[-1] == f"> {long}"
    runaway = _drop(detail="x", fix_route={**QUOTED, "line": "y" * (ROUTED_LINE_CHARS + 500)})
    assert fix_lines(m, r, runaway)[-1] == "> " + "y" * ROUTED_LINE_CHARS


def test_one_rule_says_whether_a_known_fix_matched(tmp_path):
    m, r = _mission(), _repo(tmp_path)
    quote = f"- {FINDOR}"
    # A target failure is read when there is one, and then nothing else is.
    assert drop_known_fixes(m, r, _drop(target_failures=[f"{TEST_ID}\n{NULL_LAYER}"])) == [quote]
    assert drop_known_fixes(m, r, _drop(target_failures=["t::x\n[failure] other"], detail=NULL_LAYER,
                                        reason="gate 'build' failed")) == []
    # A failing gate's output is read as far as the prompt shows it.
    assert drop_known_fixes(m, r, _drop(reason="gate 'build' failed", detail=NULL_LAYER)) == [quote]
    assert drop_known_fixes(m, r, _drop(reason="gate 'build' failed", detail=NULL_LAYER + "x" * FEEDBACK_CHARS)) == []
    # Any other drop's output is the end of the metric run, which is about later steps' tests.
    for reason in ("no strict gain (5 vs best 5)", "metric unavailable: boom", "tests went missing (3 collected, was 5)"):
        assert drop_known_fixes(m, r, _drop(reason=reason, detail=NULL_LAYER)) == []
    assert drop_known_fixes(m, r, _drop(reason="gate 'build' failed")) == []


def test_two_known_fixes_with_one_quote_print_it_once(tmp_path):
    raw = _raw({"kind": "jev", "brief": BRIEF})
    raw["known_fixes"].append(dict(raw["known_fixes"][0]))
    out = fix_lines(mission_from_dict(raw), _tree(tmp_path), _drop(detail="x", target_failures=[f"{TEST_ID}\n{NULL_LAYER}"]))
    assert [ln for ln in out if ln.startswith("> ")] == [f"> - {FINDOR}"]


def test_known_fixes_print_in_mission_order(tmp_path):
    raw = _raw({"kind": "jev", "brief": BRIEF})
    raw["known_fixes"].insert(0, {"match": "is not an instance of 'str'", "file": BRIEF, "anchor": "`changed` is a list of `str`"})
    a = _drop(detail="x", target_failures=[f"{TEST_ID}\n{NULL_LAYER}\n{TYPE_ERROR}"])
    out = fix_lines(mission_from_dict(raw), _tree(tmp_path), a)
    assert [ln for ln in out if ln.startswith("> ")] == [f"> - {CHANGED}", f"> - {FINDOR}"]


# -- the real mission -------------------------------------------------------------------

# These read the mission file and brief the run itself reads, inside a gate the run needs: a test that pins
# their content makes the off switch, a new floor or an edit to the brief refuse the next run's baseline.
# So they ask only what must hold for any content. mission_from_dict refuses the rest when the file loads.

def _acceptance():
    return load_mission(REPO / "harness" / "plexus_loop" / "missions" / "acceptance.toml")


def test_the_acceptance_section_loads_with_legal_values():
    fr = _acceptance().fix_router
    assert fr.kind in ("none", "jev") and 0 <= fr.min_confidence <= 1 and fr.timeout_s > 0


def test_the_acceptance_brief_offers_only_whole_lines_of_itself():
    m = _acceptance()
    if m.fix_router.kind == "none":
        pytest.skip("the fix router is off in the mission file")
    text = (REPO / m.fix_router.brief).read_text(encoding="utf-8")
    lines = brief_lines(text)
    assert 0 < len(lines) < MAX_OPTIONS and len(set(lines.values())) == len(lines)
    raw = text.splitlines()
    assert all(any(t in ln for ln in raw) for t in lines.values())
