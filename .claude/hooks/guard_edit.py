"""PreToolUse hook for Edit / Write / MultiEdit / NotebookEdit.

Blocks:
  1. Any edit to a frozen test path (belt; permissions.deny is the braces).
  2. Code or dependency content that imports Synapse, or that imports the old Moneta integration.
     Prose files (docs/, harness/, *.md) may name Synapse as a reference.
"""
from __future__ import annotations

import sys as _s, pathlib as _p
_s.path.insert(0, str(_p.Path(__file__).resolve().parent))
from _common import MONETA_OLD, SYNAPSE_CODE, block, is_frozen, is_prose, read_event, rel

ev = read_event()
tool = ev.get("tool_name", "")
ti = ev.get("tool_input") or {}

path = ti.get("file_path") or ti.get("notebook_path") or ""
if path and is_frozen(path):
    block(
        f"Blocked: '{rel(path)}' is a frozen acceptance test. The frozen tests define done and are never "
        "edited, skipped or re-marked. If the test looks wrong, stop and tell Joe."
    )

# Gather every piece of new content this call would write.
chunks: list[str] = []
for key in ("content", "new_string", "new_source"):
    v = ti.get(key)
    if isinstance(v, str):
        chunks.append(v)
for e in ti.get("edits") or []:
    v = e.get("new_string")
    if isinstance(v, str):
        chunks.append(v)

new_text = "\n".join(chunks)
if new_text and path and not is_prose(path):
    if SYNAPSE_CODE.search(new_text):
        block(
            f"Blocked: '{rel(path)}' would import or depend on Synapse. Nothing from Synapse comes into "
            "Plexus — no code, imports, packages, contracts or dependencies. Borrow the idea, justify it on "
            "Plexus's terms, write it fresh."
        )
    if MONETA_OLD.search(new_text) and not rel(path).startswith("agent/integrations/"):
        block(
            f"Blocked: '{rel(path)}' would import agent.integrations.moneta (the old integration). Plexus "
            "runs without Moneta; the future adapter is Plexus-written and starts from the Memory contract."
        )

raise SystemExit(0)
