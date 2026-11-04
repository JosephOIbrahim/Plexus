"""REVIEW.md: what a run did, written for Joe to read and decide on."""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from .fix_router import QUOTED_SAID

if TYPE_CHECKING:  # pragma: no cover
    from .loop import RunReport
    from .mission import Mission


def _when(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def write_review(path: Path, mission: Mission, r: RunReport) -> None:
    kept = [a for a in r.attempts if a.kept]
    cpu = sum(1 for a in r.attempts if a.device == "cpu")
    hours = (r.finished - r.started) / 3600
    lines = [
        f"# plexus-loop review: {mission.name}",
        "",
        mission.goal,
        "",
        f"- Status: {r.stop_reason}",
        f"- Ran {_when(r.started)} to {_when(r.finished)} ({hours:.1f} h)",
        f"- Score ({mission.metric.direction} is better): {r.baseline:g} at start, {r.best:g} now",
        f"- Attempts: {len(r.attempts)}, kept {len(kept)}, {cpu} on the CPU beside Houdini",
        f"- Branch: `{r.branch}`, from `{r.base[:10]}` to `{r.tip[:10]}`",
        "",
        "## To review",
        "",
        "Nothing has merged. Promotion is yours.",
        "",
        "```",
        f"git log --oneline {r.base[:10]}..{r.branch}",
        f"git diff {r.base[:10]}..{r.branch}",
        "```",
        "",
        "## Attempts",
        "",
        "| # | Kept | Score | Step | Houdini | Device | Why |",
        "|---|---|---|---|---|---|---|",
    ]
    for a in r.attempts:
        score = "" if a.metric is None else f"{a.metric:g}"
        fr = a.fix_route  # what the fix router made of a drop, so its picks can be labelled from this table
        # ascii(): the pick is the API's text, and this file is written outside any attempt's error handling.
        pick = ascii(fr.get("pick") or "no answer")[1:-1]
        # A pick that cleared the floor says where it went: a known fix may have matched this failure too.
        said = f" {QUOTED_SAID.get(fr.get('known_fix'), 'quoted')}" if fr.get("quoted") else ""
        routed = f" (fix router: {pick} {fr.get('confidence') or ''}{said})"
        why = (a.reason + (routed if fr else "")).replace("|", "/")
        step = (a.route or "").replace("|", "/")
        lines.append(f"| {a.n} | {'yes' if a.kept else 'no'} | {score} | {step} | {a.houdini} | {a.device} | {why} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
