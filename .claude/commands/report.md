---
description: Write the mission report and refresh harness/CAPSULE.md from the harness REVIEW.md, the attempts ledger and git history
argument-hint: [mission-slug; default: the mission on the current branch]
allowed-tools: Bash(git *), Bash(python -c *), Bash(python -m pytest *), Read, Write(harness/CAPSULE.md), Write(harness/plexus_loop/missions/*)
---

## Pre-computed context

None of these commands reads the arguments: Claude Code pastes arguments into a shell command as raw text, so an apostrophe or a space in them breaks it, and `${ARGUMENTS:-…}` is never filled in, so it always read `acceptance`.

- Branch: !`git branch --show-current`
- Ledgers, newest first: !`ls -t .plexus_loop 2>/dev/null | tr '\n' ' '`

## The mission

As typed: $ARGUMENTS

The slug is the first word, kept only if it is lowercase letters, digits and hyphens. With no valid slug:
- use the one in the current branch name (`mission/<slug>` or `plexus-loop/<slug>`);
- failing that, use the newest ledger above;
- say which you used.

Then run these with the slug, quoted, and use their output:
1. `cat ".plexus_loop/<slug>/REVIEW.md"`
2. `tail -40 ".plexus_loop/<slug>/attempts.jsonl"`
3. `git log --oneline --stat "harness/plexus-loop..plexus-loop/<slug>" | head -60`
4. `git log --oneline "harness/plexus-loop..mission/<slug>" | head -20`

## Task

Read the ledger lines (one JSON object per attempt; field names are whatever the harness wrote, so inspect before averaging). Compute the attempt count, the kept count, and the mean wall time per device mode.

Then write the report in the order `program.md` specifies, in plain sentences, one idea per paragraph:
1. the frozen tests passing now versus the baseline;
2. what changed, by file;
3. what failed and why;
4. the average attempt time by mode;
5. if the `unit` gate was narrowed, the full comfy-cozy suite result (run it now: `python -m pytest -q tests --ignore=tests/acceptance -m "not integration"`);
6. the one decision Joe needs.

Before the one decision, list what Claude did without asking since the last report: each push, fast-forward and run start, with the branch, its old and new commit from `git reflog show <branch>`, and how to reverse it.

Then rewrite `harness/CAPSULE.md`: Mile x of ~y, next action, blockers, energy required, ideas parked. Do not push.
