"""Failure routing: ask Jev which line of the brief fixes what a dropped attempt printed.

A ``[[known_fixes]]`` regular expression quotes its brief line when it recognises a failure. It only
knows the failures already seen, and it can fire on a symptom and name the wrong cause, so the loop
asks here on every dropped attempt the gates or the metric ran on that printed something, whether or
not a known fix matches. ``route_failure`` offers Jev every prose line of the brief as one Choice, plus
"none", and the next prompt quotes the pick only when its confidence clears the mission's floor: on
its own when no known fix matched, under the known fixes as a second candidate when it is another
line, and not at all when a known fix already quotes that line (``loop.fix_lines`` decides).

The route only shapes the prompt. Whether an attempt is kept is still decided by the gates and the
metric, so a wrong quote can cost an attempt each time its failure comes back, and can never make a
keep. Every failure here means "no quote": this code never raises into the run.

What leaves the machine, on every call: the failure output, the step's id and text, and the brief's
prose lines, sent to the mission's ``host``. The request shape is the one replayed and judged on 39
real failures, on jev-1.14.0 and on run 19's brief (the floor belongs to this shape: list items and
prose lines whole, target failures whole, this wording), so change it only with a new replay.
"""

from __future__ import annotations

import math
import os
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .mission import FixRouterSpec, Step
from .router import STEP_TEXT_FOR_ROUTER, Post, _http_post, unavailable_note

FAILURE_CHARS = 4500  # the failure output one request carries
# The API takes 1 to 255 options in one Choice, so the lines stop one short of that to leave room
# for "none". Run 19's brief offers 101 lines at about 10.5k input tokens, against the API's limit
# of 32k per question: a brief that outgrew that gets a 400, which here only means no quote.
MAX_OPTIONS = 255
PROSE_MIN_CHARS = 40  # a shorter line outside a list is a label, not a rule
NOTE_CHARS = 300
NONE = "none"
NONE_TEXT = "None of these lines addresses this failure."
# What became of a pick that cleared the floor, by its row's "known_fix", for the log and REVIEW.md.
QUOTED_SAID = {"": "quoted", "other": "quoted under a known fix", "same": "same line as its known fix"}
FIX_LINE_INSTRUCTIONS = (
    "`failure_output` is what a coding model's failed attempt printed. Find the first error it shows in the "
    "attempt's own code, not in a test for later work. The options are lines of the brief the model works from. "
    "Which line states the fix for that error: it names that error, or the call or rule that causes it? A line "
    "merely about the same file or topic does not count. If no line does, choose none."
)


@dataclass(frozen=True)
class FixRoute:
    """What the router made of one failure. The ledger keeps all of it, quoted or not, so a later
    run can label the picks that fell below the floor."""

    pick: str = ""  # the option Jev chose ("b71", "l050", "none"), or "" when it never answered
    confidence: float | None = None
    line: str = ""  # the chosen line, whole; "" for "none", an unknown pick or no answer
    quoted: bool = False  # it cleared the floor, so the next prompt shows `line`, routed or as a known fix's own quote
    note: str = ""  # why it is not quoted
    model: str = ""  # the model that answered, as the response names it: the floor belongs to one model


def option_text(line: str) -> str:
    """A raw line of the brief as ``brief_lines`` offers it: a list item without its marker, any other
    line stripped. A known fix's line goes through this too, so the two compare as whole lines."""
    s = line.strip()
    return s[2:].strip() if line.startswith("- ") else s


def brief_lines(text: str) -> dict[str, str]:
    """Every prose line of the brief outside fenced code, whole, by option id: list items in order as
    b00, b01..., then the other prose lines as l<line number>. A repeated line keeps its first place,
    and past the API's limit the prose goes first."""
    fence = None
    items: list[str] = []
    prose: list[tuple[int, str]] = []
    for no, ln in enumerate(text.splitlines(), 1):
        f = re.match(r"^ {0,3}(`{3,})(.*)$", ln)
        if fence is None:
            if f:
                fence = len(f.group(1))
                continue
        else:
            if f and len(f.group(1)) >= fence and not f.group(2).strip():
                fence = None
            continue
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if ln.startswith("- "):
            if text_of_item := option_text(ln):
                items.append(text_of_item)
        elif len(s) > PROSE_MIN_CHARS:
            prose.append((no, s))
    items = list(dict.fromkeys(items))
    lines = {f"b{i:02d}": t for i, t in enumerate(items)}
    seen = set(items)
    for no, t in prose:
        if t not in seen:
            seen.add(t)
            lines[f"l{no:03d}"] = t
    return dict(list(lines.items())[:MAX_OPTIONS - 1])


def failure_output(target_failures: list[str], detail: str) -> str:
    """The target failures whole, then as much of the end of the detail as FAILURE_CHARS leaves.
    A plain tail would cut the target failures' own message off a long detail."""
    tf = "\n\n".join(target_failures)
    if not tf:
        return detail[-FAILURE_CHARS:]
    room = FAILURE_CHARS - len(tf) - 2
    return tf[:FAILURE_CHARS] if room <= 0 else tf + "\n\n" + detail[-room:]


def fix_line_request(spec: FixRouterSpec, step: Step | None, failure_text: str, lines: dict[str, str]) -> dict:
    """The System One request body for one failure."""
    return {
        "model": spec.model,
        "state": {
            "step_id": step.id if step else "",
            "step_text": step.text[:STEP_TEXT_FOR_ROUTER] if step else "",
            "failure_output": failure_text,
        },
        "questions": {
            "fix_line": {
                "type": "choice",
                "instructions": FIX_LINE_INSTRUCTIONS,
                "criteria": {**lines, NONE: NONE_TEXT},
            }
        },
    }


def _within(seconds: float, call: Callable[[], dict]) -> dict:
    """What ``call`` returns, or TimeoutError once ``seconds`` have passed.

    urllib's timeout is per socket operation and per address: four unreachable addresses cost it
    four times over, a server sending a byte at a time never trips it, and the stop file waits for
    all of that. The call runs on a daemon thread, so an abandoned one dies with the process.
    """
    box: dict = {}

    def run() -> None:
        try:
            box["out"] = call()
        except Exception as e:  # noqa: BLE001 - raised again below, on the caller's thread
            box["err"] = e

    t = threading.Thread(target=run, daemon=True, name="fix-router-call")
    t.start()
    t.join(seconds)
    if t.is_alive():
        raise TimeoutError(f"no answer within {seconds:g} s")
    if "err" in box:
        raise box["err"]
    return box["out"]


def route_failure(spec: FixRouterSpec, repo: Path, failure_text: str, step: Step | None,
                  post: Post | None = None, api_key: str | None = None) -> FixRoute:
    """Which brief line fixes this failure, if Jev is sure enough. Never raises.

    The brief is read from ``repo``, the attempt's worktree, because that is the copy the next prompt
    carries (mission.py refuses a brief the worker may change, so an attempt that reaches here left
    it as it was at tip).
    """
    if spec.kind != "jev":
        return FixRoute(note="the fix router is off")
    if not failure_text.strip():
        return FixRoute(note="no failure text to route")
    try:
        lines = brief_lines((repo / spec.brief).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as e:
        return FixRoute(note=f"brief {spec.brief} cannot be read: {type(e).__name__}")
    if not lines:
        return FixRoute(note=f"brief {spec.brief} has no lines to offer")
    key = (api_key if api_key is not None else os.environ.get(spec.api_key_env, "")).strip()
    if not key:
        return FixRoute(note=f"{spec.api_key_env} is not set")
    if any(c.isspace() for c in key):
        return FixRoute(note=f"{spec.api_key_env} has whitespace inside it, so it was not sent")
    send = post or _http_post
    try:
        out = _within(spec.timeout_s, lambda: send(
            spec.host.rstrip("/") + "/v1/systemone",
            fix_line_request(spec, step, failure_text, lines),
            {"Authorization": "Bearer " + key},
            spec.timeout_s,
        ))
        ans = out["answers"]["fix_line"]
        pick, raw = str(ans["choice"])[:NOTE_CHARS], ans["confidence"]
        if isinstance(raw, bool) or not isinstance(raw, int | float):  # float() would take "0.99" and True
            raise ValueError(f"confidence {raw!r} is not a number")
        conf, model = float(raw), str(out.get("model", ""))[:NOTE_CHARS]
    except Exception as e:  # noqa: BLE001 - network, auth, timeout, bad JSON, schema: all mean "no quote"
        return FixRoute(note=unavailable_note(e, key)[:NOTE_CHARS])
    if not (math.isfinite(conf) and 0 <= conf <= 1):
        return FixRoute(pick=pick, note=f"jev gave confidence {conf}", model=model)
    if pick == NONE:
        return FixRoute(pick=pick, confidence=conf, note=f"jev chose none at {conf:.2f}", model=model)
    if pick not in lines:
        return FixRoute(pick=pick, confidence=conf, note=f"jev picked unknown line {pick!r}"[:NOTE_CHARS], model=model)
    if conf < spec.min_confidence:
        return FixRoute(pick=pick, confidence=conf, line=lines[pick], model=model,
                        note=f"jev picked {pick} at {conf:.2f}, below {spec.min_confidence:g}")
    return FixRoute(pick=pick, confidence=conf, line=lines[pick], quoted=True, model=model)
