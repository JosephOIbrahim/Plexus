"""Mission files: what one harness run works on, and what it may touch.

A mission is a TOML file. It names the goal, the paths the worker may change
(focus), the paths it must never change (frozen), the gate commands that must
pass, the number that counts as better, the worker, and the budgets.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib as _toml
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as _toml  # type: ignore[no-redef]


class MissionError(ValueError):
    """The mission file is missing a field or has a bad value."""


@dataclass(frozen=True)
class Gate:
    name: str
    cmd: list[str]
    timeout_s: int = 1800


@dataclass(frozen=True)
class Metric:
    kind: str  # "pytest_failures" or "command"
    direction: str = "lower"  # "lower" or "higher"
    min_delta: float = 1.0
    target: str = ""  # pytest path for pytest_failures
    cmd: list[str] = field(default_factory=list)  # for kind="command"
    timeout_s: int = 1800

    def improves(self, new: float, best: float) -> bool:
        """True only for a strict gain of at least min_delta."""
        if self.direction == "lower":
            return new <= best - self.min_delta
        return new >= best + self.min_delta


@dataclass(frozen=True)
class WorkerSpec:
    kind: str = "ollama"  # "ollama" or "command"
    model: str = "qwen3-coder:30b"
    host: str = "http://127.0.0.1:11434"
    cmd: list[str] = field(default_factory=list)
    timeout_s: int = 1800
    context_chars: int = 60_000
    num_ctx: int = 0  # Ollama context window in tokens; 0 leaves the server default (which can truncate)


@dataclass(frozen=True)
class Budget:
    attempts: int = 40
    hours: float = 6.0
    max_consecutive_failures: int = 8


@dataclass(frozen=True)
class HoudiniPolicy:
    cpu_threads: int = 8
    cargo_jobs: int = 4


@dataclass(frozen=True)
class Step:
    """One plan step: what a single attempt should do, and the tests it aims at."""

    id: str
    targets: list[str]  # pytest ids or prefixes, e.g. "tests/acceptance/phase1/test_t0_schema_gate.py"
    text: str
    # Repo-relative files the step writes: every reply to the step must send each of them, or
    # it is dropped before the gates with the names. The prompt lists them, and a dropped
    # attempt after which any is absent from the worktree has that named in the next prompt.
    files: list[str] = field(default_factory=list)
    # Ids of earlier steps this one builds on. The router offers a step only once every step
    # it names has no failing target left, so a dependency is a rule in code, never a guess.
    after: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class KnownFix:
    """A recognised failure and where its fix is written down.

    When a dropped attempt's own target test fails with text matching ``match`` (a regular
    expression), or it has no target failures and its failing gate's output matches, the next
    prompt quotes the line of ``file`` that contains ``anchor`` under the failure or the output.
    """

    match: str
    file: str
    anchor: str


@dataclass(frozen=True)
class RouterSpec:
    """How the next attempt's step is picked (see router.py)."""

    kind: str = "none"  # "none", "first" or "jev"
    model: str = "jev-latest"
    host: str = "https://api.typesafe.ai"
    api_key_env: str = "TYPESAFE_API_KEY"
    min_confidence: float = 0.3
    timeout_s: int = 60


@dataclass(frozen=True)
class FixRouterSpec:
    """How a failure no known fix matches is matched to a line of the brief (see fix_router.py)."""

    kind: str = "none"  # "none" or "jev"
    model: str = "jev-latest"
    host: str = "https://api.typesafe.ai"
    api_key_env: str = "TYPESAFE_API_KEY"
    timeout_s: int = 60  # a deadline on the whole call, not only on each socket operation
    # The floor judged on 39 replayed failures: at 0.7, on run 19's brief, 32 quoted and 30 of them right.
    min_confidence: float = 0.7
    brief: str = ""  # repo-relative; required for kind "jev"


@dataclass(frozen=True)
class Mission:
    name: str
    goal: str
    focus: list[str]
    frozen: list[str]
    gates: list[Gate]
    metric: Metric
    worker: WorkerSpec = field(default_factory=WorkerSpec)
    budget: Budget = field(default_factory=Budget)
    houdini: HoudiniPolicy = field(default_factory=HoudiniPolicy)
    requires: list[str] = field(default_factory=list)
    context: list[str] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    router: RouterSpec = field(default_factory=RouterSpec)
    known_fixes: list[KnownFix] = field(default_factory=list)
    fix_router: FixRouterSpec = field(default_factory=FixRouterSpec)

    @property
    def branch(self) -> str:
        return f"plexus-loop/{self.name}"

    def is_frozen(self, rel_path: str) -> bool:
        return _matches(rel_path, self.frozen)

    def in_focus(self, rel_path: str) -> bool:
        return _matches(rel_path, self.focus)


def _norm(path: str) -> str:
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def _matches(rel_path: str, patterns: list[str]) -> bool:
    p = _norm(rel_path)
    for pat in patterns:
        pat = _norm(pat)
        if fnmatch.fnmatchcase(p, pat):
            return True
        base = pat[:-3] if pat.endswith("/**") else pat.rstrip("/")
        if p == base or p.startswith(base + "/"):
            return True
    return False


def _req(d: dict[str, Any], key: str, where: str) -> Any:
    if key not in d:
        raise MissionError(f"{where}: missing '{key}'")
    return d[key]


def _not_a_repo_file(path: str) -> bool:
    return (not path or path.startswith("/") or path.endswith("/") or ":" in path
            or any(part in ("", ".", "..") for part in path.split("/")))


def _fix_router(fr: Any, focus: list[str], frozen: list[str], context: list[str],
                known_fix_files: list[str]) -> FixRouterSpec:
    """The [fix_router] section. Checks only the file itself: a mission loads before any repo is at hand."""
    if not isinstance(fr, dict):
        raise MissionError("[fix_router] must be a table")
    if any(isinstance(fr.get(k), bool) for k in ("timeout_s", "min_confidence")):
        raise MissionError("[fix_router] timeout_s and min_confidence must be numbers")
    try:
        spec = FixRouterSpec(
            kind=str(fr.get("kind", "none")),
            model=str(fr.get("model", "jev-latest")),
            host=str(fr.get("host", "https://api.typesafe.ai")),
            api_key_env=str(fr.get("api_key_env", "TYPESAFE_API_KEY")),
            timeout_s=int(fr.get("timeout_s", 60)),
            min_confidence=float(fr.get("min_confidence", 0.7)),
            brief=_norm(str(fr.get("brief", ""))),
        )
    except (TypeError, ValueError, OverflowError) as e:
        raise MissionError(f"[fix_router] timeout_s and min_confidence must be numbers: {e}") from e
    if spec.kind not in ("none", "jev"):
        raise MissionError("[fix_router] kind must be 'none' or 'jev'")
    if not 0 <= spec.min_confidence <= 1:  # also refuses nan
        raise MissionError("[fix_router] min_confidence must be between 0 and 1")
    if spec.timeout_s <= 0:
        raise MissionError("[fix_router] timeout_s must be above zero")
    if spec.brief and _not_a_repo_file(spec.brief):
        raise MissionError(f"[fix_router] brief {spec.brief!r} must be a repo-relative file path")
    if spec.kind == "jev":
        if not spec.brief:
            raise MissionError("[fix_router] kind 'jev' needs brief, the file its lines come from")
        if not (spec.model and spec.host and spec.api_key_env):
            raise MissionError("[fix_router] model, host and api_key_env must not be empty")
        # A quote must be a line the prompt carries, and the copy the router reads in the attempt's
        # worktree must be the copy the next prompt shows: no attempt that reaches the router may
        # have changed it. The same holds for the files known fixes quote, so that the loop and the
        # next prompt cannot disagree on whether a known fix matched.
        if spec.brief not in [_norm(c) for c in context]:
            raise MissionError(f"[fix_router] brief {spec.brief} must be in [mission] context, so the prompt carries it")
        for f in (spec.brief, *known_fix_files):
            if _matches(f, focus) and not _matches(f, frozen):
                raise MissionError(f"[fix_router] {f} must not be a file the worker may change")
    return spec


def load_mission(path: str | Path) -> Mission:
    raw = _toml.loads(Path(path).read_text(encoding="utf-8"))
    return mission_from_dict(raw)


def mission_from_dict(raw: dict[str, Any]) -> Mission:
    m = _req(raw, "mission", "file")
    name = str(_req(m, "name", "[mission]"))
    if not name or any(c in name for c in " /\\:"):
        raise MissionError("[mission] name must be a short slug with no spaces or slashes")

    met = _req(raw, "metric", "file")
    metric = Metric(
        kind=str(_req(met, "kind", "[metric]")),
        direction=str(met.get("direction", "lower")),
        min_delta=float(met.get("min_delta", 1.0)),
        target=str(met.get("target", "")),
        cmd=[str(x) for x in met.get("cmd", [])],
        timeout_s=int(met.get("timeout_s", 1800)),
    )
    if metric.kind not in ("pytest_failures", "command"):
        raise MissionError("[metric] kind must be 'pytest_failures' or 'command'")
    if metric.direction not in ("lower", "higher"):
        raise MissionError("[metric] direction must be 'lower' or 'higher'")
    if metric.min_delta <= 0:
        raise MissionError("[metric] min_delta must be above zero, so only strict gains count")
    if metric.kind == "pytest_failures" and not metric.target:
        raise MissionError("[metric] pytest_failures needs a target path")
    if metric.kind == "command" and not metric.cmd:
        raise MissionError("[metric] command needs cmd")

    gates = [
        Gate(name=str(_req(g, "name", "[[gates]]")), cmd=[str(x) for x in _req(g, "cmd", "[[gates]]")],
             timeout_s=int(g.get("timeout_s", 1800)))
        for g in raw.get("gates", [])
    ]

    w = raw.get("worker", {})
    worker = WorkerSpec(
        kind=str(w.get("kind", "ollama")),
        model=str(w.get("model", "qwen3-coder:30b")),
        host=str(w.get("host", "http://127.0.0.1:11434")),
        cmd=[str(x) for x in w.get("cmd", [])],
        timeout_s=int(w.get("timeout_s", 1800)),
        context_chars=int(w.get("context_chars", 60_000)),
        num_ctx=int(w.get("num_ctx", 0)),
    )
    if worker.kind not in ("ollama", "command"):
        raise MissionError("[worker] kind must be 'ollama' or 'command'")
    if worker.kind == "command" and not worker.cmd:
        raise MissionError("[worker] command needs cmd")

    b = raw.get("budget", {})
    budget = Budget(
        attempts=int(b.get("attempts", 40)),
        hours=float(b.get("hours", 6.0)),
        max_consecutive_failures=int(b.get("max_consecutive_failures", 8)),
    )
    h = raw.get("houdini", {})
    houdini = HoudiniPolicy(cpu_threads=int(h.get("cpu_threads", 8)), cargo_jobs=int(h.get("cargo_jobs", 4)))

    steps = []
    for s in raw.get("steps", []):
        sid = str(_req(s, "id", "[[steps]]"))
        # One token: the router attributes drops by parsing "step <id> via ...: reason".
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", sid):
            raise MissionError(f"[[steps]] {sid!r}: a step id is one token of letters, digits, '_', '.' or '-'")
        targets = [str(x) for x in _req(s, "targets", f"[[steps]] {sid}")]
        if not targets:
            raise MissionError(f"[[steps]] {sid}: targets must name at least one test")
        raw_files = s.get("files", [])
        if not isinstance(raw_files, list):
            raise MissionError(f"[[steps]] {sid}: files must be a list of paths")
        files = [_norm(str(x)) for x in raw_files]
        if any(_not_a_repo_file(f) for f in files):
            raise MissionError(f"[[steps]] {sid}: files must be repo-relative file paths")
        if len(set(files)) != len(files):
            raise MissionError(f"[[steps]] {sid}: files must not repeat")
        raw_after = s.get("after", [])
        if not isinstance(raw_after, list) or not all(isinstance(x, str) for x in raw_after):
            raise MissionError(f"[[steps]] {sid}: after must be a list of step ids")
        earlier = {p.id: p for p in steps}
        if bad := [x for x in raw_after if x not in earlier]:
            raise MissionError(f"[[steps]] {sid}: after names {bad[0]!r}, which is not an earlier step")
        if len(set(raw_after)) != len(raw_after):
            raise MissionError(f"[[steps]] {sid}: after must not repeat")
        # Close `after` over what each named step itself builds on, so readiness holds through the
        # whole chain: a step whose groundwork two levels down fails again is not ready either.
        # Earlier steps are already closed, and only earlier ids are allowed, so this cannot loop.
        closed: list[str] = []
        for x in raw_after:
            for y in [x, *earlier[x].after]:
                if y not in closed:
                    closed.append(y)
        steps.append(Step(id=sid, targets=targets, text=str(_req(s, "text", f"[[steps]] {sid}")),
                          files=files, after=closed))
    if len({s.id for s in steps}) != len(steps):
        raise MissionError("[[steps]] ids must be unique")

    rt = raw.get("router", {})
    router = RouterSpec(
        kind=str(rt.get("kind", "first" if steps else "none")),
        model=str(rt.get("model", "jev-latest")),
        host=str(rt.get("host", "https://api.typesafe.ai")),
        api_key_env=str(rt.get("api_key_env", "TYPESAFE_API_KEY")),
        min_confidence=float(rt.get("min_confidence", 0.3)),
        timeout_s=int(rt.get("timeout_s", 60)),
    )
    if router.kind not in ("none", "first", "jev"):
        raise MissionError("[router] kind must be 'none', 'first' or 'jev'")
    if router.kind != "none" and not steps:
        raise MissionError("[router] needs [[steps]] to route between")

    focus = [str(x) for x in _req(m, "focus", "[mission]")]
    if not focus:
        raise MissionError("[mission] focus must name at least one path")
    known_fixes = []
    raw_fixes = raw.get("known_fixes", [])
    if not isinstance(raw_fixes, list) or not all(isinstance(k, dict) for k in raw_fixes):
        raise MissionError("[[known_fixes]] must be a list of tables")
    for k in raw_fixes:
        match = str(_req(k, "match", "[[known_fixes]]"))
        anchor = str(_req(k, "anchor", "[[known_fixes]]"))
        file = _norm(str(_req(k, "file", "[[known_fixes]]")))
        try:
            re.compile(match)
        except re.error as e:
            raise MissionError(f"[[known_fixes]] match {match!r} is not a valid regular expression: {e}") from e
        if not match or not anchor:
            raise MissionError("[[known_fixes]] match and anchor must not be empty")
        if file.startswith("/") or ":" in file or ".." in file.split("/"):
            raise MissionError(f"[[known_fixes]] file {file!r} must be a repo-relative path")
        known_fixes.append(KnownFix(match=match, file=file, anchor=anchor))

    frozen = [str(x) for x in m.get("frozen", [])]
    for s in steps:
        for f in s.files:
            if not _matches(f, focus) or _matches(f, frozen):
                raise MissionError(f"[[steps]] {s.id}: {f} is outside focus or frozen, so the worker could never write it")
    context = [str(x) for x in m.get("context", [])]
    return Mission(
        name=name,
        goal=str(_req(m, "goal", "[mission]")),
        focus=focus,
        frozen=frozen,
        gates=gates,
        metric=metric,
        worker=worker,
        budget=budget,
        houdini=houdini,
        requires=[str(x) for x in m.get("requires", [])],
        context=context,
        steps=steps,
        router=router,
        known_fixes=known_fixes,
        fix_router=_fix_router(raw.get("fix_router", {}), focus, frozen, context, [k.file for k in known_fixes]),
    )
