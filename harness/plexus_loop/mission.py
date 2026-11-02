"""Mission files: what one harness run works on, and what it may touch.

A mission is a TOML file. It names the goal, the paths the worker may change
(focus), the paths it must never change (frozen), the gate commands that must
pass, the number that counts as better, the worker, and the budgets.
"""

from __future__ import annotations

import fnmatch
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
        targets = [str(x) for x in _req(s, "targets", f"[[steps]] {sid}")]
        if not targets:
            raise MissionError(f"[[steps]] {sid}: targets must name at least one test")
        steps.append(Step(id=sid, targets=targets, text=str(_req(s, "text", f"[[steps]] {sid}"))))
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
    return Mission(
        name=name,
        goal=str(_req(m, "goal", "[mission]")),
        focus=focus,
        frozen=[str(x) for x in m.get("frozen", [])],
        gates=gates,
        metric=metric,
        worker=worker,
        budget=budget,
        houdini=houdini,
        requires=[str(x) for x in m.get("requires", [])],
        context=[str(x) for x in m.get("context", [])],
        steps=steps,
        router=router,
    )
