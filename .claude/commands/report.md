---
description: Write the mission report and refresh harness/CAPSULE.md from the harness REVIEW.md, the attempts ledger and git history
argument-hint: [mission name, default acceptance]
allowed-tools: Bash(git *), Bash(python -c *), Bash(python -m pytest *), Read, Write(harness/CAPSULE.md), Write(harness/plexus_loop/missions/*)
---

## Pre-computed context

- Mission: !`echo ${ARGUMENTS:-acceptance}`
- REVIEW.md: !`m=${ARGUMENTS:-acceptance}; cat .plexus_loop/$m/REVIEW.md 2>/dev/null || echo "(no REVIEW.md yet)"`
- Ledger tail: !`m=${ARGUMENTS:-acceptance}; tail -40 .plexus_loop/$m/attempts.jsonl 2>/dev/null || echo "(no ledger)"`
- Kept commits: !`m=${ARGUMENTS:-acceptance}; git log --oneline --stat harness/plexus-loop..plexus-loop/$m 2>/dev/null | head -60 || echo "(no kept commits)"`
- Claude's commits: !`m=${ARGUMENTS:-acceptance}; git log --oneline harness/plexus-loop..mission/$m 2>/dev/null | head -20 || echo "(none)"`

## Task

Read the ledger lines (one JSON object per attempt; field names are whatever the harness wrote — inspect before averaging) and compute attempt count, kept count, and mean wall time per device mode. Then write the report in the order `program.md` specifies: frozen tests passing now versus baseline; what changed, by file; what failed and why; average attempt time by mode; the full comfy-cozy suite result if the `unit` gate was narrowed (run it now: `python -m pytest -q tests --ignore=tests/acceptance -m "not integration"`); the one decision Joe needs. Plain sentences, one idea per paragraph.

Then rewrite `harness/CAPSULE.md`: Mile x of ~y, next action, blockers, energy required, ideas parked. Do not push.
