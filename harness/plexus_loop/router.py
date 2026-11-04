"""Step routing: pick the one plan step the next attempt works on.

A mission can list ``[[steps]]``, each naming the tests it is aimed at. Before
each attempt the harness narrows the steps in code to those whose targets
still fail, then picks one:

- A step is *ready* when its targets still fail and every step it names in
  ``after`` has no failing target left. Dependencies are known rules, so they
  live in code: no router ever offers a step whose groundwork is missing.
- ``kind = "first"`` takes the earliest ready step.
- ``kind = "jev"`` asks TypeSafe's Jev model to choose among the ready steps,
  from the latest test output, each step's own failing targets and the reasons
  its recent attempts were dropped. That is the part ordinary code can't read:
  which of several independent next steps the next attempt is most likely to
  move. With one ready step there is nothing to choose and Jev is not called.
  Any failure, or a pick below ``min_confidence``, falls back to the earliest
  ready step.

The route only shapes the prompt. Whether an attempt is kept is still decided
by the gates and the metric, never by the router.
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from .mission import RouterSpec, Step

TAIL_FOR_ROUTER = 3000
STEP_TEXT_FOR_ROUTER = 600

Post = Callable[[str, dict, dict, int], dict]


@dataclass(frozen=True)
class Route:
    step: Step | None
    how: str  # "none", "first", "jev", "fallback"
    confidence: float | None = None
    note: str = ""

    def label(self) -> str:
        if self.step is None:
            return ""
        conf = "" if self.confidence is None else f" {self.confidence:.2f}"
        return f"{self.step.id} via {self.how}{conf}"


def _norm(test_id: str) -> str:
    """Make 'a/b/test_x.py::test_y' and junit 'a.b.test_x.test_y' comparable."""
    s = test_id.replace("\\", "/")
    head, sep, tail = s.partition("::")
    if head.endswith(".py"):
        head = head[:-3]
    head = head.replace("/", ".")
    return head + ("." + tail.replace("::", ".") if sep else "")


def failing_targets(step: Step, failing: list[str]) -> list[str]:
    """The ids in ``failing`` that one of the step's targets names, in ``failing``'s order, once each."""
    norms = [_norm(t) for t in step.targets]
    out = []
    for f in failing:
        if f in out:  # junit repeats an id when a test fails and its teardown errors too
            continue
        nf = _norm(f)
        if any(nf == nt or nf.startswith(nt + ".") or nf.startswith(nt + "[") for nt in norms):
            out.append(f)
    return out


def targets_failing(step: Step, failing: list[str]) -> bool:
    return bool(failing_targets(step, failing))


def eligible(steps: list[Step], failing: list[str]) -> list[Step]:
    return [s for s in steps if targets_failing(s, failing)]


def ready(steps: list[Step], failing: list[str]) -> list[Step]:
    """Eligible steps whose every ``after`` step has no failing target left."""
    by_id = {s.id: s for s in steps}
    return [s for s in eligible(steps, failing)
            if all(not targets_failing(by_id[p], failing) for p in s.after if p in by_id)]


def _attempts_on(step_id: str, recent: list[str]) -> list[str]:
    """The reasons of ``recent`` drops routed to this step ("step S3 via first: ...")."""
    out = []
    for r in recent:
        head, sep, reason = r.partition(": ")
        if sep and head.split()[1:2] == [step_id]:
            out.append(reason)
    return out


MAX_REPLY_BYTES = 1 << 20  # far above any real answer; a longer reply fails to parse, which means no answer


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """A redirect is a failed call: urllib would follow it and send the Authorization header wherever it points."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirects)


def _http_post(url: str, body: dict, headers: dict, timeout: int) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={**headers, "Content-Type": "application/json"})
    with _OPENER.open(req, timeout=timeout) as resp:
        return json.loads(resp.read(MAX_REPLY_BYTES).decode("utf-8"))


def unavailable_note(e: Exception, key: str) -> str:
    """A failed Jev call as a note, which reaches the ledger and the log. http.client's ValueError for a bad
    header value repeats the whole header, in a bytes repr a plain replace of the key can miss, so a message
    that names the header is left out."""
    text = str(e)
    note = f"jev unavailable: {type(e).__name__}" + ("" if "Bearer" in text else f": {text}")
    return note.replace(key, "<key>")


READY_INSTRUCTIONS = (
    "A coding model gets exactly one attempt to make more of `failing_tests` pass. "
    "Every option is a plan step that is ready: the steps it builds on already pass, "
    "so any of them can be worked on now. Which one should that attempt work on? "
    "Choose the step whose next attempt is most likely to make at least one of its "
    "own failing tests pass. Read `latest_test_output_tail` and each option's "
    "`its_failing_tests` and `its_recent_drops`: favour a step whose failures point "
    "at one specific piece it owns and that the output shows how to fix. A step "
    "whose recent attempts were all dropped for the same reason is less likely to "
    "pass next time than a ready step that has not been tried yet."
)
# For a mission whose steps name no `after`: nothing says the options are ready, so the
# question keeps the earliest-first rule the router used before prerequisites existed.
ORDERED_INSTRUCTIONS = (
    "A coding model gets exactly one attempt to make more of `failing_tests` pass. "
    "Which plan step should that attempt work on? Choose the earliest step whose code "
    "`latest_test_output_tail` shows is missing or broken. Choose a later step only "
    "when the output shows the earlier steps' code already works. If "
    "`recent_dropped_attempts` show the same step failing for the same reason, the "
    "step itself may still be right: keep it unless the output points elsewhere."
)


def jev_request(spec: RouterSpec, steps: list[Step], failing: list[str], tail: str,
                recent: list[str], graph: bool = True) -> dict:
    """The System One request body for one routing decision.

    ``graph`` says whether the mission's steps name prerequisites, so that every option really
    is ready; without them the question keeps the earliest-first wording.
    """
    return {
        "model": spec.model,
        "state": {
            "failing_tests": failing,
            "latest_test_output_tail": tail[-TAIL_FOR_ROUTER:],
            "recent_dropped_attempts": recent[-3:],
        },
        "questions": {
            "next_step": {
                "type": "choice",
                "instructions": READY_INSTRUCTIONS if graph else ORDERED_INSTRUCTIONS,
                "criteria": {
                    s.id: {
                        "what_it_builds": s.text[:STEP_TEXT_FOR_ROUTER],
                        "aimed_at": list(s.targets),
                        "its_failing_tests": failing_targets(s, failing),
                        "its_recent_drops": _attempts_on(s.id, recent)[-3:],
                    }
                    for s in steps
                },
            }
        },
    }


def choose(spec: RouterSpec, steps: list[Step], failing: list[str], tail: str = "",
           recent: list[str] | None = None, post: Post | None = None,
           api_key: str | None = None) -> Route:
    if spec.kind == "none" or not steps:
        return Route(None, "none")
    elig = eligible(steps, failing)
    if not elig:
        return Route(None, "none", note="no step targets a failing test")
    rdy = ready(steps, failing)
    if not rdy:
        # Unreachable for a mission that loads: `after` names only earlier steps, so the earliest
        # failing step's prerequisites all pass and it is always ready. Kept for Step lists built
        # by hand (tests, tools), where `after` may point forward.
        return Route(elig[0], "first", note="no failing step has its prerequisites passing")
    if spec.kind == "first" or len(rdy) == 1:
        return Route(rdy[0], "first")

    key = (api_key if api_key is not None else os.environ.get(spec.api_key_env, "")).strip()
    if not key:
        return Route(rdy[0], "fallback", note=f"{spec.api_key_env} is not set")
    try:
        out = (post or _http_post)(
            spec.host.rstrip("/") + "/v1/systemone",
            jev_request(spec, rdy, failing, tail, recent or [], graph=any(s.after for s in steps)),
            {"Authorization": "Bearer " + key},
            spec.timeout_s,
        )
        ans = out["answers"]["next_step"]
        pick, conf = str(ans["choice"]), float(ans["confidence"])
    except Exception as e:  # noqa: BLE001 - network, auth, schema: all mean "route in code"
        return Route(rdy[0], "fallback", note=unavailable_note(e, key))
    by_id = {s.id: s for s in rdy}
    if pick not in by_id:
        return Route(rdy[0], "fallback", note=f"jev picked unknown step {pick!r}")
    if conf < spec.min_confidence:
        return Route(rdy[0], "fallback", conf, note=f"jev picked {pick} at {conf:.2f}, below "
                                                    f"{spec.min_confidence:g}")
    return Route(by_id[pick], "jev", conf)
