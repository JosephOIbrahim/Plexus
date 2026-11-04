"""The mission loop: attempt, check, keep only strict gains, stop on budget.

One run works one mission. Each attempt starts from the best commit so far in
a fresh git worktree, lets the worker change files, and is kept only when:

1. every changed path is inside the mission's focus,
2. no changed path is frozen,
3. every file its step lists was sent (a reply that leaves one out is never built),
4. every gate passes,
5. the metric improves by at least ``min_delta``, and
6. (for pytest_failures) no tests went missing.

A kept attempt is committed onto the harness branch. Nothing else in the repo
moves. The run writes ``REVIEW.md`` for Joe, who decides what to promote.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import warnings
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import gitops
from .metrics import GATE_HEAD_CHARS, GATE_TAIL_CHARS, MetricResult, measure, run_gate
from .mission import Mission, Step
from .profile import Profile, choose_profile, with_env
from .review import write_review
from .router import Route
from .router import choose as choose_route
from .router import failing_targets
from .workers import Worker, make_worker

RouteFn = Callable[[Mission, MetricResult | None, list["Attempt"]], Route]


def default_route(mission: Mission, last: MetricResult | None, recent: list[Attempt]) -> Route:
    return choose_route(mission.router, mission.steps,
                        last.failing if last else [], last.tail if last else "",
                        [f"step {a.route or '?'}: {a.reason}" for a in recent if not a.kept])

STATE_DIR = ".plexus_loop"
# How much of a dropped attempt's output the next prompt shows. Large enough that a clipped
# gate output (head + marker + tail) plus its "$ cmd" line is never cut again.
FEEDBACK_CHARS = GATE_HEAD_CHARS + GATE_TAIL_CHARS + 500
# At most this many syntax errors lead the feedback; one per file, each line clipped.
SYNTAX_MAX = 10
SYNTAX_LINE_CHARS = 200


def syntax_errors(root: Path, paths: list[str]) -> list[str]:
    """One line per changed .py file that Python can't compile: ``path:line: message: source``.

    A gate that parses files (the layers guard) or imports them (pytest) reports a syntax
    error deep in a traceback, often in the part of its output the next prompt leaves out.
    This puts the file, line and reason first. It only compiles; it never runs the code.
    """
    out: list[str] = []
    for rel in paths:
        if not rel.endswith(".py"):
            continue
        p = root / rel
        if not p.is_file():
            continue
        try:
            src = p.read_bytes()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # SyntaxWarning etc. are not errors
                compile(src, rel, "exec", dont_inherit=True)
        except SyntaxError as e:  # also IndentationError, TabError, bad encoding
            where = f"{rel}:{e.lineno}" if e.lineno else rel
            src_line = (e.text or "").strip()
            line = f"{where}: {e.msg}" + (f": {src_line}" if src_line else "")
            out.append(_one_line(line))
        except Exception as e:  # noqa: BLE001 - a diagnostic must never end the run
            # ValueError (null bytes), OSError (unreadable), and MemoryError or RecursionError
            # from the compiler on a degenerate file, such as a token repeated thousands of times.
            out.append(_one_line(f"{rel}: {type(e).__name__}: {e}"))
    return out


KNOWN_FIX_CHARS = 700  # one quoted brief line
# The reason _evaluate gives a failing gate. Known fixes match that gate's output too.
GATE_FAILED = re.compile(r"gate '[^']+' failed\Z")


def known_fix_quotes(mission: Mission, repo: Path, failures: list[str]) -> list[str]:
    """The written-down fix for each recognised error in ``failures``, each quoted once.

    A known fix matches with its regular expression against a target failure's text, or against
    a failing gate's output when the attempt has no target failures (``build_prompt``), and quotes
    the line of its file that contains its anchor, read from ``repo`` (the attempt's tree at tip,
    so the quote is the version the worker is given). A missing file or anchor quotes nothing.
    """
    text = "\n".join(failures)
    out: list[str] = []
    for k in mission.known_fixes:
        if not re.search(k.match, text):
            continue
        try:
            lines = (repo / k.file).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError, ValueError):
            continue
        line = next((ln for ln in lines if k.anchor in ln), None)
        if line is None:
            continue
        # Quote from the start of the sentence holding the anchor: a brief line can hold several
        # facts, and a long line must never cut the fix itself off.
        at = line.find(k.anchor)
        cut = line.rfind(". ", 0, at)
        start = cut + 2 if cut >= 0 else 0
        body = line[start:].strip()
        quote = ("…" if start else "") + body[:KNOWN_FIX_CHARS]
        if quote not in out:
            out.append(quote)
    return out


CARRY_CHARS = 40_000  # the most of a dropped attempt's files the next prompt carries
# The reason given to a reply that leaves out any of its step's files. Such a reply is dropped
# before the gates: run 12 attempts 1 and 3 sent only predicate.rs, lib.rs never declared the
# module, and every gate passed on code that was never compiled. The next prompt reads the left-out
# names back from this reason (left_out_of); the router hands the whole reason to Jev as a recent drop.
LEFT_OUT = "reply left out step files"


def left_out(step: Step | None, sent: list[str]) -> list[str]:
    """The step's files the reply did not send, in the step's order."""
    return [f for f in (step.files if step else []) if f not in sent]


def left_out_of(reason: str) -> list[str]:
    """The file names a LEFT_OUT reason lists, or [] for any other reason."""
    head, sep, names = reason.partition(": ")
    return [x for x in names.split(", ") if x] if sep and head == LEFT_OUT else []


def carry_files(root: Path, changed: list[str], mission: Mission, step: Step | None) -> dict[str, str]:
    """The text of the files a dropped attempt wrote, for the next prompt to hand back.

    Only files in focus and not frozen, readable as UTF-8, the step's own files first, up to
    CARRY_CHARS in all. A file that would pass the limit is left out whole, never cut.
    """
    own = [f for f in (step.files if step else []) if f in changed]
    order = own + sorted(f for f in changed if f not in own)
    out: dict[str, str] = {}
    used = 0
    for rel in order:
        if not mission.in_focus(rel) or mission.is_frozen(rel):
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeError, ValueError):
            continue
        if used + len(text) > CARRY_CHARS:
            continue
        out[rel] = text
        used += len(text)
    return out


def merge_carried(prev: dict[str, str], new: dict[str, str], step: Step | None) -> dict[str, str]:
    """What the next prompt hands back after a left-out drop: the reply's own files over the set
    the last prompt carried, the step's files first, within CARRY_CHARS.

    After a left-out drop the worker edits its last draft rather than resending the step (run 18
    attempts 1 and 2 each sent one file and saw only that file handed back), so the last full
    attempt's versions of the other files stay in view instead of vanishing one reply at a time.
    """
    merged = {**prev, **new}
    own = [f for f in (step.files if step else []) if f in merged]
    order = own + sorted(f for f in merged if f not in own)
    out: dict[str, str] = {}
    used = 0
    # The reply's own files are admitted first, so near the limit a stale carried file gives way
    # to what was just sent, never the other way round; the result is shown in step order.
    for rel in [f for f in order if f in new] + [f for f in order if f not in new]:
        text = merged[rel]
        if used + len(text) > CARRY_CHARS:
            continue
        out[rel] = text
        used += len(text)
    return {rel: out[rel] for rel in order if rel in out}


TARGET_FAILURES_MAX = 3  # at most this many target tests lead the feedback


def target_failures(m: MetricResult, step: Step) -> list[str]:
    """The step's own target tests that failed, each as "junit id\\nits failure message".

    The general output the next prompt shows is the end of the whole test run, which with many
    tests failing is some later step's test. This puts the step's own tests first.
    """
    out = []
    for tid in failing_targets(step, m.failing)[:TARGET_FAILURES_MAX]:
        out.append(f"{tid}\n{m.messages.get(tid, '(no message in the report)')}".rstrip())
    return out


def missing_files(root: Path, files: list[str]) -> list[str]:
    """The step's files that are not in the worktree, in the step's order.

    A file a kept commit already holds counts as present: every attempt starts from that
    commit. This only looks for files; it never reads them.
    """
    out: list[str] = []
    for rel in files:
        try:
            present = (root / rel).is_file()
        except (OSError, ValueError):
            present = False
        if not present:
            out.append(rel)
    return out


def _one_line(text: str) -> str:
    """Clip to SYNTAX_LINE_CHARS and keep it on one line, so a bullet can never start a fence."""
    return text.replace("\r", " ").replace("\n", " ")[:SYNTAX_LINE_CHARS]


class RefuseToStart(RuntimeError):
    """The run can't begin, and the message says why."""


@dataclass
class Attempt:
    n: int
    started: float
    houdini: str
    device: str
    kept: bool = False
    reason: str = ""
    metric: float | None = None
    changed: list[str] = field(default_factory=list)
    commit: str = ""
    route: str = ""  # e.g. "S2 via jev 0.81", empty when the mission has no steps
    route_note: str = ""
    reply_file: str = ""  # the raw model reply, under .plexus_loop/<mission>/replies/
    detail: str = ""  # output of the failing gate or metric, shown to the next attempt
    syntax: list[str] = field(default_factory=list)  # changed .py files that don't compile, one line each
    # The dropped attempt's own step's target tests that failed, each "junit id\nits failure",
    # from the metric's junit report. The next prompt leads with them.
    target_failures: list[str] = field(default_factory=list)
    # Files the next prompt hands back in full after this drop: what it sent when it passed every
    # gate, or, after a left-out drop, what it sent laid over the last full attempt's files.
    handed_on: list[str] = field(default_factory=list)
    # Ledger diagnostic: the step's files absent from the worktree after the attempt, whatever the reply
    # sent. A file at tip the reply did not send is not here (that is a LEFT_OUT drop). The next prompt
    # does not use it; it lists what is absent from its own fresh worktree, which also lacks what was sent.
    missing: list[str] = field(default_factory=list)
    # Where the time went, in seconds of real (monotonic) time, to a tenth. None means not
    # measured: that step never ran, or the row predates timing. Never read a missing value as 0.
    # wall_s minus the parts is the harness's own work: worktree setup and teardown, building
    # the prompt (git ls-files and reading the context files), saving the reply, the changed-
    # and ignored-file scans, the syntax check, and on a keep the commit and branch advance.
    wall_s: float | None = None  # the whole attempt, worktree in to worktree out
    route_s: float | None = None  # choosing the step (one Jev call when the router is jev)
    worker_s: float | None = None  # the worker: the model call plus writing its files
    gates: list[dict] = field(default_factory=list)  # [{"name", "seconds", "ok"}], in run order
    metric_s: float | None = None  # the metric run; only when every gate passed
    # The gate that stopped the attempt, by name, or "". `reason` keeps its wording, because
    # the router and the next prompt read it; this is the structured copy.
    failed_gate: str = ""
    # Every failing test's junit id from the metric run (the whole list, not just the step's
    # targets), or [] when the metric did not run.
    failing: list[str] = field(default_factory=list)
    # The model server's own timing for the worker call (workers.ollama_stats), or {}.
    ollama: dict = field(default_factory=dict)


@dataclass
class RunReport:
    mission: str
    branch: str
    base: str
    tip: str
    baseline: float
    best: float
    attempts: list[Attempt]
    stop_reason: str
    started: float
    finished: float


def _pid_alive(pid: int) -> bool | None:
    if pid <= 0:
        return False
    if sys.platform.startswith("win"):
        try:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                                 capture_output=True, text=True, errors="replace", timeout=15,
                                 check=False).stdout or ""
        except Exception:  # noqa: BLE001 - can't tell
            return None
        return f'"{pid}"' in out
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


class Lock:
    """One mission at a time across the whole repo."""

    def __init__(self, state: Path):
        self.path = state / "lock"

    def acquire(self, mission: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                held = json.loads(self.path.read_text(encoding="utf-8"))
                pid = int(held.get("pid", 0))
            except (ValueError, OSError):
                held, pid = {}, 0
            alive = _pid_alive(pid)
            if alive is not False:
                raise RefuseToStart(
                    f"another run holds the lock ({held.get('mission', '?')}, pid {pid}). "
                    f"If that run is gone, delete {self.path}."
                )
            self.path.unlink()
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "mission": mission, "started": time.time()}, f)

    def release(self) -> None:
        self.path.unlink(missing_ok=True)


def build_prompt(mission: Mission, repo: Path, best: float, last: MetricResult | None,
                 recent: list[Attempt], budget_chars: int, step: Step | None = None,
                 carried: tuple[int, dict[str, str]] | None = None) -> str:
    """The worker's prompt. ``carried`` is (attempt number, {path: text}) of the files the next
    prompt hands back after a drop: what a gate-passing attempt sent, or what a left-out reply sent
    laid over the last full attempt's files; it is shown only when that attempt is the last one."""
    lines = [
        f"# Mission: {mission.name}",
        "",
        mission.goal,
        "",
        "## Rules",
        f"- Change only paths matching: {', '.join(mission.focus)}",
        f"- Never change: {', '.join(mission.frozen) or '(none)'}",
        "- For each NEW file, or a file you rewrite completely, reply with its whole content in a fenced block "
        "whose info string is file:<path>, e.g. ```file:plexus/core/axon.py.",
        "- For edits to existing files, reply with one unified diff (paths relative to the repo root, "
        "a/ and b/ prefixes) inside a ```diff block.",
        "- Make the smallest change that moves the number. Don't skip, delete or weaken tests.",
    ]
    # Ollama reuses the cached prefix of the previous prompt, so everything that is the same on
    # every attempt of a run (this header, then the context files) comes first, and everything
    # that changes per attempt (the step, the last drop, handed-on files, the score, the metric
    # tail) follows the files. Run 12 attempt 1 spent 709 of its 1473 model seconds reading a
    # 24,464-token prompt, most of it the same brief and tests every time.
    head, lines = lines, []
    if step is not None:
        lines += [
            "",
            f"## This attempt: step {step.id}",
            f"Aim at: {', '.join(step.targets)}",
            "",
            step.text,
            "",
        ]
    # Measured in this attempt's fresh worktree at the branch tip, for the step it is on: a
    # dropped attempt's files are gone, so whatever it sent must be sent again.
    absent = missing_files(repo, step.files) if step is not None else []
    if step is not None:
        if step.files:
            lines += [f"Files this step writes: {', '.join(step.files)}. "
                      "Send each new or rewritten file as a whole-file block; every .rs file always is one. "
                      "Your reply must include every one of these files, including any you leave as it is; "
                      "a reply that leaves one out is dropped before anything is built."]
            if absent:
                lines.append(f"Not in the repo yet, so your reply must include each in full: {', '.join(absent)}.")
            lines.append("")
        lines.append("Do this step only. Later steps get their own attempts.")
    dropped = recent[-1] if recent and not recent[-1].kept else None
    if dropped is not None and (dropped.detail or dropped.syntax or absent or dropped.target_failures
                                or left_out_of(dropped.reason)):
        lines += [
            "",
            "## Why the last attempt was dropped",
            f"Attempt {dropped.n}" + (f" (step {dropped.route})" if dropped.route else "")
            + f" was dropped: {dropped.reason}.",
        ]
        if dropped.target_failures:
            block = "\n\n".join(dropped.target_failures)
            tfence = "`" * max(3, _longest_backtick_run(block) + 1)
            lines += ["Its step's own target tests failed like this. Start here; tests for later steps "
                      "are expected to fail until those steps land:", tfence, block, tfence]
            quotes = known_fix_quotes(mission, repo, dropped.target_failures)
            if quotes:
                lines.append("This is a known error. The worker brief already gives its fix; apply it to the "
                             "line the failure points at:")
                lines += [f"> {q}" for q in quotes]
        if absent:
            # A left-out drop never had every file, so "its files are gone" would misdescribe it.
            lead = "Every" if left_out_of(dropped.reason) else "Its files are gone: every"
            lines += [f"{lead} attempt starts from the last kept commit. Step {step.id} "
                      "needs these files, and none of them is in the repo. Send each one in full as a "
                      "whole-file block:"]
            lines += [f"- {p}" for p in absent]
        if dropped.syntax:
            shown = dropped.syntax[:SYNTAX_MAX]
            lines += ["Python could not compile these files. Fix them first; every .py file must compile:"]
            lines += [f"- {s}" for s in shown]
            if len(dropped.syntax) > len(shown):
                lines.append(f"- (and {len(dropped.syntax) - len(shown)} more)")
        if dropped.detail:
            detail = dropped.detail[-FEEDBACK_CHARS:]
            fence = "`" * max(3, _longest_backtick_run(detail) + 1)
            lines += ["This is what it printed:", fence, detail.rstrip("\n"), fence]
            if dropped.target_failures:
                lines.append("That is the end of the whole run, for context. Fix the target-test failures above first.")
            else:
                lines.append("Fix the cause first. It is usually one rule or one error near the top of that output.")
                # A failing gate (a build, a guard) has no target tests to match, so its known
                # fixes match the gate output the worker was just shown.
                quotes = known_fix_quotes(mission, repo, [detail]) if GATE_FAILED.match(dropped.reason) else []
                if quotes:
                    lines.append("It is a known error. The worker brief already gives its fix; apply it to the "
                                 "line the output points at:")
                    lines += [f"> {q}" for q in quotes]
        elif dropped.syntax:
            lines.append("Fix those files first.")
    if dropped is not None and left_out_of(dropped.reason):
        # A left-out drop ran nothing, so it has no failure of its own; the one the worker is
        # still meant to fix belongs to its last full attempt, which this section keeps in view.
        prior = None
        for x in reversed(recent[:-1]):
            if x.kept:
                break  # a keep draws the line: nothing dropped before it is still the thing to fix
            if step is not None and x.route.split()[:1] != [step.id]:
                continue  # another step's failure is not this step's
            if x.target_failures or x.detail:
                prior = x
                break
        if prior is not None:
            lines += ["", f"## Your last full attempt ({prior.n}) was dropped: {prior.reason}"]
            if prior.target_failures:
                block = "\n\n".join(prior.target_failures)
                tfence = "`" * max(3, _longest_backtick_run(block) + 1)
                lines += ["Its step's own target tests failed like this. This is still the thing to fix:",
                          tfence, block, tfence]
                quotes = known_fix_quotes(mission, repo, prior.target_failures)
                if quotes:
                    lines.append("This is a known error. The worker brief already gives its fix; apply it to the "
                                 "line the failure points at:")
                    lines += [f"> {q}" for q in quotes]
            elif prior.detail:
                detail = prior.detail[-FEEDBACK_CHARS:]
                fence = "`" * max(3, _longest_backtick_run(detail) + 1)
                lines += ["This is what it printed:", fence, detail.rstrip("\n"), fence]
                quotes = known_fix_quotes(mission, repo, [detail]) if GATE_FAILED.match(prior.reason) else []
                if quotes:
                    lines.append("It is a known error. The worker brief already gives its fix; apply it to the "
                                 "line the output points at:")
                    lines += [f"> {q}" for q in quotes]
    handed: dict[str, str] = {}
    if dropped is not None and carried and carried[0] == dropped.n and carried[1]:
        handed = carried[1]
        left = left_out_of(dropped.reason)
        if left:
            sent = [f for f in handed if f in dropped.changed]
            older = [f for f in handed if f not in dropped.changed]
            why = (f"Attempt {dropped.n} sent only {', '.join(sent) or 'no step file'} and left out "
                   f"{', '.join(left)}, so nothing it sent was built or tested."
                   + (f" The other files below ({', '.join(older)}) are your last full attempt's versions."
                      if older else ""))
        else:
            why = f"Attempt {dropped.n} passed every gate."
        lines += [
            "",
            "## Your last attempt's files",
            f"{why} Its versions of these files are below. The repo no "
            "longer has them: every attempt starts from the last kept commit, so each is gone or back to "
            "its last kept version. Resend every one of them in full, as whole-file blocks, "
            + ((f"together with every file still missing: {', '.join(still)}." if (still := [f for f in left if f not in handed])
                else "with the fix.") if left
               else "with the fix, plus any other file the step needs."),
        ]
        for rel, text in handed.items():
            fence = "`" * max(3, _longest_backtick_run(text) + 1)
            tail = "" if text.endswith("\n") else "\n"
            lines.append(f"\n{fence}file:{rel}\n{text}{tail}{fence}")
    lines += [
        "",
        "## Where it stands",
        (f"Current {mission.metric.direction}-is-better score: {best:g}. "
         f"A change is kept only if it improves this by at least {mission.metric.min_delta:g}."),
    ]
    if recent:
        lines += ["", "## Recent attempts that were not kept"]
        lines += [f"- attempt {a.n}: {a.reason}" for a in recent[-3:] if not a.kept]
    if last and last.tail:
        mfence = "`" * max(3, _longest_backtick_run(last.tail) + 1)
        lines += ["", "## Latest metric output (tail)", mfence, last.tail, mfence]

    reply = ["", "## Your reply",
             "New or fully rewritten files: one ```file:<path> block each, holding the whole file. "
             "Edits to existing files: one ```diff block with a/ and b/ prefixes. Nothing else inside either."]
    used = sum(len(x) for x in head + lines + reply)
    # A handed-on file is shown once, in the attempt's version below, never again at its tip version.
    files = [f for f in _context_files(mission, repo) if f not in handed]
    file_blocks: list[str] = ["", "## Files"] if files else []
    for rel in files:
        try:
            text = (repo / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        fence = "`" * max(3, _longest_backtick_run(text) + 1)
        tail = "" if text.endswith("\n") else "\n"
        block = f"\n{fence}file:{rel}\n{text}{tail}{fence}"
        if used + len(block) > budget_chars:
            file_blocks.append(f"\n(further files left out to fit the {budget_chars}-character budget)")
            break
        file_blocks.append(block)
        used += len(block)
    return "\n".join(head + file_blocks + lines + reply)


def _secs(t0: float) -> float:
    """Seconds since a time.monotonic() reading, to a tenth."""
    return round(time.monotonic() - t0, 1)


def _longest_backtick_run(text: str) -> int:
    best = run = 0
    for ch in text:
        run = run + 1 if ch == "`" else 0
        best = max(best, run)
    return best


def _context_files(mission: Mission, repo: Path) -> list[str]:
    # -z: without it git C-quotes a non-ASCII path ("plexus/\303\201vila.py"), which then fails
    # in_focus on its leading quote and silently leaves the prompt.
    tracked = [p for p in gitops.git(repo, "ls-files", "-z").split("\0") if p]
    ctx = [p for p in mission.context if (repo / p).is_file()]
    focus = [p for p in tracked if mission.in_focus(p) and not mission.is_frozen(p) and p not in ctx]
    return ctx + sorted(focus)


class MissionRun:
    def __init__(self, mission: Mission, repo: Path, worker: Worker | None = None,
                 profile_fn: Callable[[], Profile] | None = None,
                 clock: Callable[[], float] = time.time, log: Callable[[str], None] = print,
                 route_fn: RouteFn | None = None):
        self.mission = mission
        self.route_fn = route_fn or default_route
        self.repo = gitops.repo_root(repo)
        self.state = self.repo / STATE_DIR
        self.mdir = self.state / mission.name
        self.worker = worker or make_worker(mission.worker)
        base_profile = profile_fn or (lambda: choose_profile(mission.houdini))
        # One cargo target directory for every gate in every worktree, resolved against the
        # main repo, so Rust builds and `cargo test` stay warm from attempt to attempt.
        cargo_target = str(self.state / "cargo-target")
        self.profile_fn = lambda: with_env(base_profile(), CARGO_TARGET_DIR=cargo_target)
        self.clock = clock
        self.log = log
        self.lock = Lock(self.state)

    # -- checks before anything runs -------------------------------------
    def preflight(self) -> None:
        missing = [p for p in self.mission.requires if not (self.repo / p).exists()]
        if missing:
            raise RefuseToStart(
                f"mission '{self.mission.name}' needs {', '.join(missing)}, which isn't in the repo yet. "
                "Nothing was run."
            )
        if (self.state / "STOP").exists():
            raise RefuseToStart(f"a stop file is present at {self.state / 'STOP'}. Delete it to run.")
        if not self.mission.gates:
            raise RefuseToStart("the mission names no gates, so nothing would guard a kept change")

    # -- one evaluation in a worktree -------------------------------------
    def _evaluate(self, wt: Path, profile: Profile,
                  timing: Attempt | None = None) -> tuple[str | None, MetricResult | None, str]:
        """Run the gates, then the metric. Returns (why it failed or None, metric, output to show).

        With ``timing``, each gate's seconds and result, and the metric's seconds, go on it.
        """
        for g in self.mission.gates:
            t0 = time.monotonic()
            res = run_gate(g, wt, profile)
            if timing is not None:
                timing.gates.append({"name": g.name, "seconds": _secs(t0), "ok": res.passed})
            if not res.passed:
                if timing is not None:
                    timing.failed_gate = g.name
                return f"gate '{g.name}' failed", None, f"$ {' '.join(g.cmd)}\n{res.tail}"
        t0 = time.monotonic()
        m = measure(self.mission.metric, wt, profile)
        if timing is not None:
            timing.metric_s = _secs(t0)
        if m.value is None:
            return f"metric unavailable: {m.error}", m, m.tail
        return None, m, m.tail

    def _save_reply(self, run_started: float, n: int, reply: str) -> str:
        """Keep the worker's raw reply, so a dropped attempt can be read afterwards."""
        d = self.mdir / "replies"
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{time.strftime('%Y%m%d-%H%M%S', time.localtime(run_started))}-attempt-{n}.md"
        f.write_text(reply, encoding="utf-8", errors="replace")
        return str(f.relative_to(self.repo)).replace("\\", "/")

    def run(self) -> RunReport:
        self.preflight()
        self.lock.acquire(self.mission.name)
        try:
            return self._run()
        finally:
            self.lock.release()

    def _run(self) -> RunReport:
        mi = self.mission
        started = self.clock()
        base = tip = gitops.ensure_branch(self.repo, mi.branch)
        self.mdir.mkdir(parents=True, exist_ok=True)
        attempts_log = self.mdir / "attempts.jsonl"
        wt_root = self.state / "worktrees"

        # Baseline on the branch tip: the gates must already pass, and the
        # metric must be readable, or no attempt could ever be judged.
        profile = self.profile_fn()
        wt = wt_root / "baseline"
        gitops.add_worktree(self.repo, wt, tip)
        try:
            why, last, _ = self._evaluate(wt, profile)
        finally:
            gitops.remove_worktree(self.repo, wt)
        if why:
            raise RefuseToStart(f"before any change, {why}. Fix that first; nothing was attempted.")
        assert last is not None and last.value is not None
        baseline = best = last.value
        best_total = last.total
        self.log(f"[plexus-loop] {mi.name}: baseline {baseline:g} on {tip[:10]} ({profile.device})")

        attempts: list[Attempt] = []
        carried: tuple[int, dict[str, str]] | None = None  # files of the last gate-passing or left-out drop
        consecutive = 0
        stop = "finished"
        n = 0
        while True:
            if (self.state / "STOP").exists():
                stop = "stop file"
                break
            if n >= mi.budget.attempts:
                stop = f"attempt budget ({mi.budget.attempts}) used"
                break
            if (self.clock() - started) >= mi.budget.hours * 3600:
                stop = f"hour budget ({mi.budget.hours:g}h) used"
                break
            if consecutive >= mi.budget.max_consecutive_failures:
                stop = f"{consecutive} attempts in a row were not kept"
                break
            if mi.metric.kind == "pytest_failures" and best <= 0:
                stop = "every target test passes"
                break

            n += 1
            profile = self.profile_fn()
            a = Attempt(n=n, started=self.clock(), houdini=profile.houdini, device=profile.device)
            t_attempt = time.monotonic()
            wt = wt_root / f"attempt-{n}"
            gitops.add_worktree(self.repo, wt, tip)
            try:
                t0 = time.monotonic()
                route = self.route_fn(mi, last, attempts)
                a.route_s = _secs(t0)
                a.route, a.route_note = route.label(), route.note
                if route.step is not None:
                    self.log(f"[plexus-loop] attempt {n}: step {a.route}"
                             + (f" ({route.note})" if route.note else ""))
                prompt = build_prompt(mi, wt, best, last, attempts, mi.worker.context_chars,
                                      step=route.step, carried=carried)
                t0 = time.monotonic()
                try:
                    res = self.worker.attempt(wt, prompt, profile)
                finally:
                    a.worker_s = _secs(t0)
                a.ollama = dict(getattr(res, "stats", None) or {})
                if getattr(res, "reply", ""):
                    a.reply_file = self._save_reply(started, n, res.reply)
                a.changed = sorted(set(gitops.changed_paths(wt)) | set(getattr(res, "wrote", []) or []))
                ignored = gitops.ignored_paths(wt)
                if not res.ok:
                    a.reason = f"worker: {res.note}"
                elif ignored:
                    a.reason = f"wrote {ignored[0]}, which git ignores, so it would not be committed"
                elif not a.changed:
                    a.reason = "no change"
                elif bad := [p for p in a.changed if mi.is_frozen(p)]:
                    a.reason = f"touched frozen path {bad[0]}"
                elif bad := [p for p in a.changed if not mi.in_focus(p)]:
                    a.reason = f"touched {bad[0]}, outside focus"
                elif left := left_out(route.step, a.changed):
                    # Never built or tested, so it cannot pass vacuously; its files go to the
                    # next prompt with the names of the ones it left out.
                    a.reason = f"{LEFT_OUT}: {', '.join(left)}"
                    # compile() is not a build: a .py that cannot compile is named now rather
                    # than handed back verbatim and caught by a gate one attempt later.
                    a.syntax = syntax_errors(wt, a.changed)
                    # The reply's files over whatever the last prompt carried, so a one-file
                    # reply does not shrink the next prompt to that one file.
                    prev = carried[1] if carried and carried[0] == n - 1 else {}
                    carried = (n, merge_carried(prev, carry_files(wt, a.changed, mi, route.step), route.step))
                    a.handed_on = list(carried[1])
                else:
                    why, m, detail = self._evaluate(wt, profile, timing=a)
                    if m is not None:
                        a.metric = m.value
                        a.failing = list(m.failing)
                    if why:
                        a.reason, a.detail = why, detail
                    elif best_total is not None and m.total is not None and m.total < best_total:
                        a.reason = f"tests went missing ({m.total} collected, was {best_total})"
                        a.detail = detail
                    elif not mi.metric.improves(m.value, best):
                        a.reason = f"no strict gain ({m.value:g} vs best {best:g})"
                        a.detail = detail
                    else:
                        msg = (f"plexus-loop({mi.name}): attempt {n}, {best:g} -> {m.value:g}\n\n"
                               f"Houdini {profile.houdini}, ran on {profile.device}.")
                        new = gitops.commit_all(wt, msg)
                        gitops.advance_branch(self.repo, mi.branch, new, tip)
                        tip, best, last = new, m.value, m
                        if m.total is not None:
                            best_total = m.total
                        a.kept, a.commit, a.reason = True, new, "strict gain"
                    if not a.kept:
                        a.syntax = syntax_errors(wt, a.changed)
                        if m is not None and route.step is not None:
                            a.target_failures = target_failures(m, route.step)
                        if len(a.gates) == len(mi.gates) and all(g["ok"] for g in a.gates):
                            # It passed every gate: hand its files to the next attempt, which
                            # starts from tip without them.
                            carried = (n, carry_files(wt, a.changed, mi, route.step))
                            a.handed_on = list(carried[1])
                if not a.kept and route.step is not None:
                    a.missing = missing_files(wt, route.step.files)
            except gitops.GitError as e:
                a.reason = f"git: {e}"
            except (OSError, UnicodeError) as e:
                # A worker or filesystem error costs this attempt, never the run.
                a.reason = f"attempt error: {type(e).__name__}: {e}"
            finally:
                try:
                    gitops.remove_worktree(self.repo, wt)
                finally:
                    a.wall_s = _secs(t_attempt)

            consecutive = 0 if a.kept else consecutive + 1
            attempts.append(a)
            with attempts_log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(a)) + "\n")
            self.log(f"[plexus-loop] attempt {n}: {'KEPT' if a.kept else 'dropped'} ({a.reason})")
            report = RunReport(mi.name, mi.branch, base, tip, baseline, best, attempts,
                               "running", started, self.clock())
            write_review(self.mdir / "REVIEW.md", mi, report)

        report = RunReport(mi.name, mi.branch, base, tip, baseline, best, attempts, stop,
                           started, self.clock())
        write_review(self.mdir / "REVIEW.md", mi, report)
        self.log(f"[plexus-loop] stopped: {stop}. Review at {self.mdir / 'REVIEW.md'}")
        return report
