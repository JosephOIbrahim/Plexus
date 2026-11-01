"""Stop hook. Refuses to end the turn while the working tree is in a state Joe would reject.

Checks:
  1. Frozen test paths are untouched (tracked diff and untracked files).
  2. No Synapse import/dependency landed in the diff.
  3. We are not sitting on main/master with uncommitted work.

Respects stop_hook_active to avoid loops; Claude Code also caps consecutive Stop firings.
"""
from __future__ import annotations

import re

import sys as _s, pathlib as _p
_s.path.insert(0, str(_p.Path(__file__).resolve().parent))
from _common import SYNAPSE_CODE, block, frozen_paths, git, read_event

ev = read_event()
if ev.get("stop_hook_active"):
    raise SystemExit(0)

problems: list[str] = []

changed = set(filter(None, git("diff", "--name-only", "HEAD").splitlines()))
changed |= set(filter(None, git("ls-files", "--others", "--exclude-standard").splitlines()))
fz = frozen_paths()
touched = sorted(p for p in changed if any(p == f or p.startswith(f) for f in (x.rstrip("/") for x in fz)))
if touched:
    problems.append("Frozen acceptance tests were modified or added: " + ", ".join(touched) + ". Revert them (git checkout -- <path>) before stopping.")

diff = git("diff", "HEAD", "--", ".", ":(exclude)docs", ":(exclude)harness", ":(exclude).claude", ":(exclude)*.md")
added = "\n".join(l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
if added and SYNAPSE_CODE.search(added):
    problems.append("The diff adds a Synapse import or dependency. Nothing from Synapse comes into Plexus. Remove it before stopping.")

branch = git("branch", "--show-current").lower()
if branch in ("main", "master") and changed:
    problems.append(f"Uncommitted work on '{branch}'. Move it to a branch (git switch -c <branch>) before stopping.")

if problems:
    block("Cannot stop yet:\n- " + "\n- ".join(problems))

raise SystemExit(0)
