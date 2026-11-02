"""The mission loop: attempt, check, keep only strict gains, stop on budget.

One run works one mission. Each attempt starts from the best commit so far in
a fresh git worktree, lets the worker change files, and is kept only when:

1. every changed path is inside the mission's focus,
2. no changed path is frozen,
3. every gate passes,
4. the metric improves by at least ``min_delta``, and
5. (for pytest_failures) no tests went missing.

A kept attempt is committed onto the harness branch. Nothing else in the repo
moves. The run writes ``REVIEW.md`` for Joe, who decides what to promote.
"""

from __future__ import annotations

import json
import os
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
    # Ledger diagnostic: the step's files the dropped reply left out. The next prompt does not
    # use it; it lists what is absent from its own fresh worktree, which also lacks what was sent.
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
                                 capture_output=True, text=True, timeout=15, check=False).stdout
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
                 recent: list[Attempt], budget_chars: int, step: Step | None = None) -> str:
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
                      "Send each new or rewritten file as a whole-file block; every .rs file always is one."]
            if absent:
                lines.append(f"Not in the repo yet, so your reply must include each in full: {', '.join(absent)}.")
            lines.append("")
        lines.append("Do this step only. Later steps get their own attempts.")
    dropped = recent[-1] if recent and not recent[-1].kept else None
    if dropped is not None and (dropped.detail or dropped.syntax or absent or dropped.target_failures):
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
        if absent:
            lines += [f"Its files are gone: every attempt starts from the last kept commit. Step {step.id} "
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
            lines.append("Fix the cause first. It is usually one rule or one error near the top of that output.")
        elif dropped.syntax:
            lines.append("Fix those files first.")
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

    used = sum(len(x) for x in lines)
    files = _context_files(mission, repo)
    if files:
        lines += ["", "## Files"]
    for rel in files:
        try:
            text = (repo / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        fence = "`" * max(3, _longest_backtick_run(text) + 1)
        tail = "" if text.endswith("\n") else "\n"
        block = f"\n{fence}file:{rel}\n{text}{tail}{fence}"
        if used + len(block) > budget_chars:
            lines.append(f"\n(further files left out to fit the {budget_chars}-character budget)")
            break
        lines.append(block)
        used += len(block)
    lines += ["", "## Your reply",
              "New or fully rewritten files: one ```file:<path> block each, holding the whole file. "
              "Edits to existing files: one ```diff block with a/ and b/ prefixes. Nothing else inside either."]
    return "\n".join(lines)


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
    tracked = gitops.git(repo, "ls-files").splitlines()
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
                                      step=route.step)
                t0 = time.monotonic()
                try:
                    res = self.worker.attempt(wt, prompt, profile)
                finally:
                    a.worker_s = _secs(t0)
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
                else:
                    why, m, detail = self._evaluate(wt, profile, timing=a)
                    if m is not None:
                        a.metric = m.value
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
