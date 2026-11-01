"""PreToolUse hook for Bash. Deterministic gates on shell commands.

Blocks:
  1. Any push to main/master, any force push, any commit/merge/rebase while on main/master,
     and compound commands that switch to main and then commit/merge/push.
  2. Shell-side writes into frozen test paths (redirects, sed -i, mv, rm, cp, git checkout -- , git rm).
  3. Pulling Synapse in as a dependency or copying from a Synapse checkout.
  4. Forcing the GPU for a harness run while Houdini is open or undetectable.
"""
from __future__ import annotations

import re

import sys as _s, pathlib as _p
_s.path.insert(0, str(_p.Path(__file__).resolve().parent))
from _common import block, frozen_paths, git, houdini_running, read_event

ev = read_event()
if ev.get("tool_name") != "Bash":
    raise SystemExit(0)

cmd: str = (ev.get("tool_input") or {}).get("command", "") or ""
low = cmd.lower()

# --- 1. branch protection -----------------------------------------------------------------
if re.search(r"\bgit\s+push\b", low):
    if re.search(r"\s(--force|-f|--force-with-lease)\b", low) or re.search(r"\bpush\b[^|&;]*\s\+\w", low):
        block("Blocked: force push. Plexus rule: never force-push.")
    if re.search(r"\bpush\b[^|&;]*\b(main|master)\b", low):
        block("Blocked: push to main/master. Plexus rule: branches only; main moves by PR.")

if re.search(r"\bgit\s+(checkout|switch)\s+(main|master)\b", low) and re.search(
    r"\bgit\s+(commit|merge|rebase|push|cherry-pick|reset)\b", low
):
    block("Blocked: switching to main and committing/merging in one command. Work on a branch.")

branch = git("branch", "--show-current").lower()
if branch in ("main", "master") and re.search(r"\bgit\s+(commit|merge|rebase|cherry-pick|am)\b", low):
    block(f"Blocked: you are on '{branch}'. Create or switch to a branch first (git switch -c <branch>).")

if re.search(r"\bgit\s+branch\s+(-d|-D|--delete)\s+(main|master)\b", low):
    block("Blocked: deleting main/master.")

# --- 2. frozen tests via the shell ------------------------------------------------------------
fz = frozen_paths()
if fz and any(fp.rstrip("/") in cmd.replace("\\", "/") for fp in fz):
    writers = (
        r"(^|[|&;]\s*)(sed\s+-i|perl\s+-i|mv|rm|cp|tee|truncate|python\s+-c|echo)\b",
        r">{1,2}\s*\S*(" + "|".join(re.escape(f.rstrip("/")) for f in fz) + ")",
        r"\bgit\s+(checkout|restore|rm|mv|update-index|clean)\b",
        # -k / --deselect with the frozen dir in play = skipping inside the judge. --ignore of a path *inside*
        # tests/acceptance/ likewise. --ignore=tests/acceptance (the whole dir) is legitimate: it is how the
        # comfy-cozy suite runs without the judge, and it skips nothing inside it.
        r"\b(pytest|python\s+-m\s+pytest)\b[^|&;]*\s(-k|--deselect)\b",
        r"--ignore(-glob)?[= ]\S*tests/acceptance/[^\s/]+",
    )
    if any(re.search(w, cmd, re.IGNORECASE) for w in writers):
        block(
            "Blocked: that command would modify, move, delete, restore, or selectively skip the frozen "
            "acceptance tests. The frozen tests define done. If one looks wrong, stop and tell Joe."
        )

# --- 3. Synapse stays out --------------------------------------------------------------------
if re.search(r"\b(pip|pip3|uv|poetry|cargo|npm|pnpm|yarn)\s+(install|add)\b[^|&;]*synapse", low):
    block("Blocked: installing a Synapse package. Nothing from Synapse comes into Plexus.")
if re.search(r"\b(cp|copy|xcopy|robocopy|rsync|mv|ln)\b[^|&;]*synapse", low):
    block("Blocked: copying from a Synapse checkout. Synapse is an architectural reference only.")
if re.search(r"\bgit\s+(submodule|subtree|remote\s+add)\b[^|&;]*synapse", low):
    block("Blocked: wiring a Synapse repo into Plexus git. Nothing from Synapse comes into Plexus.")

# --- 4. GPU discipline -------------------------------------------------------------------------
if re.search(r"\bharness\b", low) and re.search(r"(--gpu\b|--device[= ]cuda|plexus_device=cuda|force_gpu|cuda_visible_devices=\d)", low):
    h = houdini_running()
    if h is None or h:
        why = "Houdini is open" if h else "the Houdini check could not tell"
        block(f"Blocked: GPU forced for a harness run while {why}. Plexus rule: Houdini open or unknown → CPU.")

raise SystemExit(0)
