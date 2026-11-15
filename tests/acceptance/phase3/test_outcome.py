"""M2b · The Outcome envelope (Blueprint v5.4 §4).

Every Plexus call returns one envelope: a status that is "ok", "unavailable" or "blocked", a
payload, and a reason that is required whenever the status is not "ok". It is defined once in
Rust, in plexus-core, and Python sees it as plexus._core.Outcome. These cases read the Python
surface CONTRACT.md pins. Each imports Outcome itself, so a missing class fails each case alone.
"""

from __future__ import annotations

import pytest


def test_ok_carries_its_payload_and_no_reason():
    from plexus._core import Outcome

    payload = {"stage": "/Exchange", "revision": 3}
    o = Outcome("ok", payload)
    assert o.status == "ok"
    assert o.ok is True
    assert o.payload is payload, "the payload is the object given, not a copy"
    assert o.reason_code is None
    assert o.reason is None
    assert o.missing == ()

    bare = Outcome("ok")
    assert bare.ok is True
    assert bare.payload is None, "an ok outcome may carry no payload"
    assert Outcome("ok", payload=0).payload == 0


def test_unavailable_carries_a_reason_and_what_is_missing():
    from plexus._core import Outcome

    o = Outcome("unavailable", reason_code="non_finite", reason="temperature is NaN",
                missing=["temperature", "exposure"])
    assert o.status == "unavailable"
    assert o.ok is False
    assert o.payload is None
    assert o.reason_code == "non_finite"
    assert o.reason == "temperature is NaN"
    assert o.missing == ("temperature", "exposure"), "missing keeps the names in the order given"
    assert type(o.missing) is tuple

    plain = Outcome("unavailable", reason_code="model_not_indexed", reason="no index holds this model")
    assert plain.missing == ()


def test_blocked_carries_a_reason():
    from plexus._core import Outcome

    o = Outcome("blocked", reason_code="gate_denied", reason="the publication gate refused the write")
    assert o.status == "blocked"
    assert o.ok is False
    assert o.payload is None
    assert o.reason_code == "gate_denied"
    assert o.reason == "the publication gate refused the write"
    assert o.missing == ()


@pytest.mark.parametrize("status", ["unavailable", "blocked"])
@pytest.mark.parametrize("given", [
    {},
    {"reason_code": "gate_denied"},
    {"reason": "the publication gate refused the write"},
], ids=["nothing", "code-only", "sentence-only"])
def test_a_status_that_is_not_ok_needs_a_reason(status, given):
    from plexus._core import Outcome

    with pytest.raises(ValueError):
        Outcome(status, **given)


def test_missing_alone_is_no_reason():
    from plexus._core import Outcome

    with pytest.raises(ValueError):
        Outcome("unavailable", missing=["temperature"])


@pytest.mark.parametrize("given", [
    {"reason_code": "gate_denied", "reason": ""},
    {"reason_code": "gate_denied", "reason": "   \t"},
    {"reason_code": "", "reason": "the publication gate refused the write"},
], ids=["empty-sentence", "blank-sentence", "empty-code"])
def test_a_blank_reason_is_no_reason(given):
    from plexus._core import Outcome

    with pytest.raises(ValueError):
        Outcome("blocked", **given)


@pytest.mark.parametrize("given", [
    {"reason_code": "gate_denied", "reason": "a sentence"},
    {"reason_code": "gate_denied"},
    {"reason": "a sentence"},
    {"missing": ["temperature"]},
], ids=["code-and-sentence", "code", "sentence", "missing"])
def test_ok_carries_no_reason(given):
    from plexus._core import Outcome

    with pytest.raises(ValueError):
        Outcome("ok", 1, **given)


@pytest.mark.parametrize("status", ["unavailable", "blocked"])
def test_only_ok_carries_a_payload(status):
    from plexus._core import Outcome

    with pytest.raises(ValueError):
        Outcome(status, {"partial": True}, reason_code="limit_reached", reason="the window is full")
    with pytest.raises(ValueError):
        Outcome(status, 0, reason_code="limit_reached", reason="the window is full")


def test_only_unavailable_names_what_is_missing():
    from plexus._core import Outcome

    with pytest.raises(ValueError):
        Outcome("blocked", reason_code="gate_denied", reason="a sentence", missing=["temperature"])


@pytest.mark.parametrize("code", ["non_finite", "unsupported_type", "limit2", "x"])
def test_a_snake_case_reason_code_is_accepted(code):
    from plexus._core import Outcome

    assert Outcome("blocked", reason_code=code, reason="a sentence").reason_code == code


@pytest.mark.parametrize("code", ["NonFinite", "Non_finite", "non-finite", "non finite", "2fast", "_hidden",
                                  "café_closed", "non_finite "])
def test_a_reason_code_that_is_not_snake_case_is_refused(code):
    from plexus._core import Outcome

    with pytest.raises(ValueError):
        Outcome("unavailable", reason_code=code, reason="a sentence")


_REASON = {"reason_code": "gate_denied", "reason": "a sentence"}


@pytest.mark.parametrize("status, given", [
    ("OK", {}), ("Ok", {}), (" ok", {}), ("ok ", {}),
    ("Blocked", _REASON), ("UNAVAILABLE", _REASON), (" blocked", _REASON),
    ("failed", _REASON), ("unknown", _REASON), ("", {}),
], ids=["OK", "Ok", "space-ok", "ok-space", "Blocked", "UNAVAILABLE", "space-blocked", "failed", "unknown", "empty"])
def test_status_is_one_of_three_lowercase_words(status, given):
    """Each spelling comes with the arguments its nearest real status would accept, so only the spelling can refuse it."""
    from plexus._core import Outcome

    with pytest.raises(ValueError):
        Outcome(status, **given)


@pytest.mark.parametrize("args, kwargs", [
    ((1,), {}),
    ((None,), {}),
    (("blocked",), {"reason_code": 5, "reason": "a sentence"}),
    (("blocked",), {"reason_code": "gate_denied", "reason": b"a sentence"}),
    (("unavailable",), {"reason_code": "non_finite", "reason": "a sentence", "missing": "temperature"}),
    (("unavailable",), {"reason_code": "non_finite", "reason": "a sentence", "missing": ["temperature", 3]}),
], ids=["status-int", "status-none", "code-int", "sentence-bytes", "missing-bare-str", "missing-int-item"])
def test_an_argument_of_the_wrong_type_raises_type_error(args, kwargs):
    from plexus._core import Outcome

    with pytest.raises(TypeError):
        Outcome(*args, **kwargs)


def test_the_envelope_is_frozen():
    from plexus._core import Outcome

    for o in (Outcome("ok", [1, 2]),
              Outcome("unavailable", reason_code="non_finite", reason="temperature is NaN", missing=["temperature"])):
        for name, value in (("status", "blocked"), ("payload", 3), ("reason_code", "x"), ("reason", "y"),
                            ("missing", ()), ("ok", True), ("note", "z")):
            with pytest.raises(AttributeError):
                setattr(o, name, value)
    o = Outcome("blocked", reason_code="gate_denied", reason="a sentence")
    assert (o.status, o.reason_code, o.reason, o.ok) == ("blocked", "gate_denied", "a sentence", False)


def test_the_envelope_is_plexus_cores_own_and_says_what_it_holds():
    from plexus._core import Outcome

    assert Outcome.__module__ == "plexus._core"
    assert not issubclass(Outcome, BaseException), "an Outcome is returned, never raised"
    blocked = repr(Outcome("blocked", reason_code="gate_denied", reason="a sentence"))
    assert "blocked" in blocked and "gate_denied" in blocked, blocked
    unavailable = repr(Outcome("unavailable", reason_code="non_finite", reason="a sentence", missing=["temperature"]))
    assert "unavailable" in unavailable and "non_finite" in unavailable, unavailable
    ok = repr(Outcome("ok", 41))
    assert "ok" in ok and "41" in ok, ok
