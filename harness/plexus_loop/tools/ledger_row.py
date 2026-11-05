"""One ledger row, read for an alert: outcome, timing, what flipped against the last row that ran the metric, and the failure.

    python harness/plexus_loop/tools/ledger_row.py <row> [mission]

Row N is line N of .plexus_loop/<mission>/attempts.jsonl. Checks a run owes its own step, such as which lines a reply must
hold, stay out of git in .plexus_loop/<mission>/watch/, rewritten per run. Read-only.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ERROR_LINE = re.compile(r"(?m)^.*(?:error\[E\d+\]|TypeError|AttributeError|NameError|ImportError|KeyError|SyntaxError|IndentationError).*$")


def load(repo: Path, mission: str) -> list[dict]:
    text = (repo / ".plexus_loop" / mission / "attempts.jsonl").read_text(encoding="utf-8")
    return [json.loads(x) for x in text.splitlines() if x.strip()]


def short(test_id: str) -> str:
    """The test's own name with its parameters, from pytest's id or junit's dotted one."""
    # Split before the parameters: a parameter id can hold a dot of its own (one-0.3-wakes-once).
    name, bracket, params = test_id.partition("[")
    return name.rsplit("::", 1)[-1].rsplit(".", 1)[-1] + bracket + params


def changes(rows: list[dict], n: int) -> dict[str, list[str]] | None:
    """Against the last row before row n that ran the metric. None when row n never reached the metric."""
    row = rows[n - 1]
    if row.get("metric") is None:
        return None
    now = {short(x) for x in row.get("failing") or []}
    before = next((r for r in reversed(rows[: n - 1]) if r.get("metric") is not None), None)
    was = {short(x) for x in (before or {}).get("failing") or []}
    return {"passing_now": sorted(was - now), "newly_failing": sorted(now - was), "still_failing": sorted(now & was)}


def describe(rows: list[dict], n: int) -> list[str]:
    r = rows[n - 1]
    o = r.get("ollama") or {}
    wall = "not measured" if r.get("wall_s") is None else f"{r['wall_s'] / 60:.1f} min"
    lines = [
        f"row {n} | attempt {r.get('n')} | {r.get('route')} | kept {r.get('kept')} | {r.get('reason')} | commit {r.get('commit')}",
        f"metric {r.get('metric')} | failed_gate {r.get('failed_gate')!r} | wall {wall} | device {r.get('device')}",
        f"prompt_eval_s {o.get('prompt_eval_s')} for {o.get('prompt_eval_count')} tokens | reply {o.get('eval_count')} tokens in {o.get('eval_s')} s | load {o.get('load_s')} s",
        f"gates: {[(g['name'], g['ok']) for g in r.get('gates', [])]}",
        f"changed: {r.get('changed')} | handed_on: {r.get('handed_on')} | missing: {r.get('missing')} | syntax: {r.get('syntax')}",
    ]
    flips = changes(rows, n)
    if flips is None:
        lines.append("no metric on this row, so no test changed")
    else:
        lines += [f"{k.replace('_', ' ')}: {v or 'none'}" for k, v in flips.items()]
    lines += [f"target failure: {tf[:300]}".replace("\n", " | ") for tf in (r.get("target_failures") or [])[:3]]
    seen: list[str] = []
    for m in ERROR_LINE.finditer(r.get("detail") or ""):
        line = m.group(0).strip()[:200]
        if line not in seen:
            seen.append(line)
    lines += [f"output: {x}" for x in seen[:5]]
    if r.get("fix_route"):
        lines.append(f"failure router: { {k: r['fix_route'].get(k) for k in ('pick', 'confidence', 'quoted', 'known_fix', 'note')} }")
    return lines


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    sys.stdout.reconfigure(encoding="utf-8")
    rows = load(REPO, argv[1] if len(argv) > 1 else "acceptance")
    n = int(argv[0])
    if not 1 <= n <= len(rows):
        print(f"row {n} has not landed; the ledger has {len(rows)}")
        return 1
    print("\n".join(describe(rows, n)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
