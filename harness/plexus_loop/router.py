"""Step routing: pick the one plan step the next attempt works on.

A mission can list ``[[steps]]``, each naming the tests it is aimed at. Before
each attempt the harness narrows the steps in code to those whose targets
still fail, then picks one:

- ``kind = "first"`` takes the earliest eligible step. That is a known rule,
  so it lives in code.
- ``kind = "jev"`` asks TypeSafe's Jev model to choose among the eligible
  steps from the latest test output and the reasons recent attempts were
  dropped. That is the part ordinary code can't read: whether an error in a
  later test actually points back at an earlier step's code. Any failure, or
  a pick below ``min_confidence``, falls back to the earliest eligible step.

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


def _http_post(url: str, body: dict, headers: dict, timeout: int) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={**headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def jev_request(spec: RouterSpec, steps: list[Step], failing: list[str], tail: str,
                recent: list[str]) -> dict:
    """The System One request body for one routing decision."""
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
                "instructions": (
                    "A coding model gets exactly one attempt to make more of `failing_tests` pass. "
                    "Which plan step should that attempt work on? Choose the earliest step whose code "
                    "`latest_test_output_tail` shows is missing or broken. Choose a later step only "
                    "when the output shows the earlier steps' code already works. If "
                    "`recent_dropped_attempts` show the same step failing for the same reason, the "
                    "step itself may still be right: keep it unless the output points elsewhere."
                ),
                "criteria": {
                    s.id: f"{s.text[:STEP_TEXT_FOR_ROUTER]} (aimed at: {', '.join(s.targets)})"
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
    if spec.kind == "first" or len(elig) == 1:
        return Route(elig[0], "first")

    key = api_key if api_key is not None else os.environ.get(spec.api_key_env, "")
    if not key:
        return Route(elig[0], "fallback", note=f"{spec.api_key_env} is not set")
    try:
        out = (post or _http_post)(
            spec.host.rstrip("/") + "/v1/systemone",
            jev_request(spec, elig, failing, tail, recent or []),
            {"Authorization": "Bearer " + key},
            spec.timeout_s,
        )
        ans = out["answers"]["next_step"]
        pick, conf = str(ans["choice"]), float(ans["confidence"])
    except Exception as e:  # noqa: BLE001 - network, auth, schema: all mean "route in code"
        return Route(elig[0], "fallback", note=f"jev unavailable: {type(e).__name__}: {e}")
    by_id = {s.id: s for s in elig}
    if pick not in by_id:
        return Route(elig[0], "fallback", note=f"jev picked unknown step {pick!r}")
    if conf < spec.min_confidence:
        return Route(elig[0], "fallback", conf, note=f"jev picked {pick} at {conf:.2f}, below "
                                                     f"{spec.min_confidence:g}")
    return Route(by_id[pick], "jev", conf)
