"""Ledger stats for /report: attempts, keeps, wall time by device and why attempts dropped.

    python harness/plexus_loop/tools/report_stats.py [mission]

A row that never reached the model is not an attempt, and it stays out of every mean. Rows 90 to 119 are the first case:
Ollama's server was down, and they failed in about 3 s each. Read-only.
"""

from __future__ import annotations

import json
import re
import statistics as st
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
NO_SERVER = re.compile(r"worker: ollama call failed: (URLError|RemoteDisconnected)")


def load(repo: Path, mission: str) -> list[dict]:
    text = (repo / ".plexus_loop" / mission / "attempts.jsonl").read_text(encoding="utf-8")
    return [json.loads(x) for x in text.splitlines() if x.strip()]


def no_server(r: dict) -> bool:
    """Newer rows say so themselves; rows 90 to 119 predate the field, so their reason still decides."""
    return bool(r.get("unreachable") or NO_SERVER.search(r.get("reason") or ""))


def real_attempts(rows: list[dict]) -> list[dict]:
    return [r for r in rows if not no_server(r)]


def wall_by_device(rows: list[dict]) -> dict[str, tuple[int, float, float]]:
    """Device to count, mean minutes and median minutes, over real attempts that were timed."""
    by: dict[str, list[float]] = {}
    for r in real_attempts(rows):
        if r.get("wall_s"):
            by.setdefault(r.get("device") or "?", []).append(r["wall_s"] / 60)
    return {d: (len(v), st.mean(v), st.median(v)) for d, v in by.items()}


def drop_reasons(rows: list[dict]) -> Counter:
    reasons: Counter = Counter()
    for r in rows:
        why = r.get("reason") or ""
        if no_server(r):
            key = "no server"
        elif r.get("kept"):
            key = "kept"
        elif r.get("failed_gate"):
            key = "gate " + r["failed_gate"]
        else:
            key = why.split(":")[0][:40] or "unknown"
        reasons[key] += 1
    return reasons


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    rows = load(REPO, argv[0] if argv else "acceptance")
    real = real_attempts(rows)
    kept = [(i, r.get("route"), r.get("metric"), (r.get("commit") or "")[:7]) for i, r in enumerate(rows, 1) if r.get("kept")]
    print(f"rows {len(rows)} | real attempts {len(real)} | kept {len(kept)}")
    print("kept rows:", kept)
    for device, (n, mean, median) in wall_by_device(rows).items():
        print(f"wall on {device}: n={n} mean={mean:.1f} min median={median:.1f} min")
    print("outcomes:", drop_reasons(rows).most_common())
    print("failing at the last row that ran the metric:", next((r.get("failing") for r in reversed(rows) if r.get("metric") is not None), None))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
