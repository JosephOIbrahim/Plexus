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
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import gitops
from .metrics import MetricResult, measure, run_gate
from .mission import Mission, Step
from .profile import Profile, choose_profile
from .review import write_review
from .router import Route
from .router import choose as choose_route
from .workers import Worker, make_worker

RouteFn = Callable[[Mission, MetricResult | None, list["Attempt"]], Route]


def default_route(mission: Mission, last: MetricResult | None, recent: list[Attempt]) -> Route:
    return choose_route(mission.router, mission.steps,
                        last.failing if last else [], last.tail if last else "",
                        [f"step {a.route or '?'}: {a.reason}" for a in recent if not a.kept])

STATE_DIR = ".plexus_loop"


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
        "- Reply with exactly one unified diff, paths relative to the repo root, inside a ```diff block.",
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
            "Do this step only. Later steps get their own attempts.",
        ]
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
        lines += ["", "## Latest metric output (tail)", "```", last.tail, "```"]

    used = sum(len(x) for x in lines)
    files = _context_files(mission, repo)
    if files:
        lines += ["", "## Files"]
    for rel in files:
        try:
            text = (repo / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        block = f"\n### {rel}\n```\n{text}\n```"
        if used + len(block) > budget_chars:
            lines.append(f"\n(further files left out to fit the {budget_chars}-character budget)")
            break
        lines.append(block)
        used += len(block)
    return "\n".join(lines)


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
        self.profile_fn = profile_fn or (lambda: choose_profile(mission.houdini))
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
    def _evaluate(self, wt: Path, profile: Profile) -> tuple[str | None, MetricResult | None]:
        for g in self.mission.gates:
            res = run_gate(g, wt, profile)
            if not res.passed:
                return f"gate '{g.name}' failed", None
        m = measure(self.mission.metric, wt, profile)
        if m.value is None:
            return f"metric unavailable: {m.error}", m
        return None, m

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
            why, last = self._evaluate(wt, profile)
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
            wt = wt_root / f"attempt-{n}"
            gitops.add_worktree(self.repo, wt, tip)
            try:
                route = self.route_fn(mi, last, attempts)
                a.route, a.route_note = route.label(), route.note
                if route.step is not None:
                    self.log(f"[plexus-loop] attempt {n}: step {a.route}"
                             + (f" ({route.note})" if route.note else ""))
                prompt = build_prompt(mi, wt, best, last, attempts, mi.worker.context_chars,
                                      step=route.step)
                res = self.worker.attempt(wt, prompt, profile)
                a.changed = gitops.changed_paths(wt)
                if not res.ok:
                    a.reason = f"worker: {res.note}"
                elif not a.changed:
                    a.reason = "no change"
                elif bad := [p for p in a.changed if mi.is_frozen(p)]:
                    a.reason = f"touched frozen path {bad[0]}"
                elif bad := [p for p in a.changed if not mi.in_focus(p)]:
                    a.reason = f"touched {bad[0]}, outside focus"
                else:
                    why, m = self._evaluate(wt, profile)
                    if m is not None:
                        a.metric = m.value
                    if why:
                        a.reason = why
                    elif best_total is not None and m.total is not None and m.total < best_total:
                        a.reason = f"tests went missing ({m.total} collected, was {best_total})"
                    elif not mi.metric.improves(m.value, best):
                        a.reason = f"no strict gain ({m.value:g} vs best {best:g})"
                    else:
                        msg = (f"plexus-loop({mi.name}): attempt {n}, {best:g} -> {m.value:g}\n\n"
                               f"Houdini {profile.houdini}, ran on {profile.device}.")
                        new = gitops.commit_all(wt, msg)
                        gitops.advance_branch(self.repo, mi.branch, new, tip)
                        tip, best, last = new, m.value, m
                        if m.total is not None:
                            best_total = m.total
                        a.kept, a.commit, a.reason = True, new, "strict gain"
            except gitops.GitError as e:
                a.reason = f"git: {e}"
            finally:
                gitops.remove_worktree(self.repo, wt)

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
