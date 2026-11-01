"""SessionStart hook. Prints the orientation Joe would otherwise paste: branch, frozen test count,
capsule, last harness attempts, GPU state. Output becomes session context.
"""
from __future__ import annotations

import json
import re
import sys as _s, pathlib as _p
_s.path.insert(0, str(_p.Path(__file__).resolve().parent))
from _common import PROJECT, frozen_paths, git, houdini_running

lines: list[str] = ["## Plexus session orientation (auto)"]

branch = git("branch", "--show-current") or "(detached)"
lines.append(f"- Branch: `{branch}`" + ("  ← on main: create a branch before any commit" if branch in ("main", "master") else ""))
dirty = git("status", "--short")
lines.append(f"- Working tree: {'clean' if not dirty else str(len(dirty.splitlines())) + ' changed path(s)'}")

def count(p):
    files = [p] if p.is_file() else list(p.rglob("test_*.py")) if p.is_dir() else []
    n = 0
    for f in files:
        try:
            n += len(re.findall(r"^\s*(?:async\s+)?def\s+test_\w+", f.read_text(encoding="utf-8"), re.M))
        except Exception:
            pass
    return n

acc = PROJECT / "tests" / "acceptance"
if acc.exists():
    lines.append(f"- Frozen tests: phase1={count(acc/'phase1')} phase2={count(acc/'phase2')} pending(uncounted)={count(acc/'pending')}  — frozen roots: {', '.join(frozen_paths())}")
else:
    lines.append(f"- Frozen tests: tests/acceptance not on this branch (frozen roots: {', '.join(frozen_paths())})")

cap = PROJECT / "harness" / "CAPSULE.md"
if cap.exists():
    head = [l for l in cap.read_text(encoding="utf-8").splitlines() if l.strip()][:10]
    lines.append("- Capsule (harness/CAPSULE.md):")
    lines.extend("    " + l for l in head)

state = PROJECT / ".plexus_loop"
if state.exists():
    for ledger in sorted(state.glob("*/attempts.jsonl")):
        tail = ledger.read_text(encoding="utf-8").splitlines()[-3:]
        lines.append(f"- Last attempts ({ledger.parent.name}):")
        for l in tail:
            lines.append("    " + l[:160])

h = houdini_running()
lines.append("- GPU: " + ("Houdini is OPEN → harness runs on CPU" if h else "Houdini check failed → treat as open, CPU" if h is None else "Houdini not running → GPU available to the harness"))
lines.append("- Loop: `/mission acceptance` (reads harness/plexus_loop/program.md). Decision points are listed in CLAUDE.md.")
print("\n".join(lines))
