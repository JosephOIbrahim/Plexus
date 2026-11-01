---
description: Run a Plexus harness mission with Claude as planner/reviewer (setup → plan → stop → run → review → report), per harness/plexus_loop/program.md
argument-hint: <mission name, e.g. acceptance>
allowed-tools: Bash(git *), Bash(python -m harness.plexus_loop *), Bash(python -m pytest *), Bash(pytest *), Bash(cargo *), Bash(maturin *), Bash(ollama *), Read, Grep, Glob, Agent, Write(harness/plexus_loop/missions/*.plan.md), Write(harness/CAPSULE.md)
---

## Pre-computed context

- Branch: !`git branch --show-current`
- Tree: !`git status --short | head -20`
- Mission file: !`ls harness/plexus_loop/missions/$ARGUMENTS.toml 2>/dev/null || echo "MISSING harness/plexus_loop/missions/$ARGUMENTS.toml"`
- Brief: !`ls harness/plexus_loop/missions/$ARGUMENTS.plan-brief.md 2>/dev/null || echo "(no brief)"`
- Existing plan: !`ls harness/plexus_loop/missions/$ARGUMENTS.plan.md 2>/dev/null || echo "(none yet)"`
- Metric target: !`grep -E '^target' harness/plexus_loop/missions/$ARGUMENTS.toml 2>/dev/null`
- Frozen test functions in target: !`t=$(grep -E '^target' harness/plexus_loop/missions/$ARGUMENTS.toml 2>/dev/null | sed -E 's/.*"(.*)".*/\1/'); [ -n "$t" ] && grep -rhoE '^\s*(async )?def test_' "$t" | wc -l || echo "?"`
- Harness check: !`python -m harness.plexus_loop check harness/plexus_loop/missions/$ARGUMENTS.toml 2>&1 | head -5`
- Last attempts: !`tail -3 .plexus_loop/$ARGUMENTS/attempts.jsonl 2>/dev/null || echo "(no attempts yet)"`
- Kept commits: !`git log --oneline harness/plexus-loop..plexus-loop/$ARGUMENTS 2>/dev/null | head -10 || echo "(no plexus-loop/$ARGUMENTS branch yet)"`

## Task

Run mission `$ARGUMENTS` exactly as `harness/plexus_loop/program.md` describes. Read `CLAUDE.md`, `program.md`, the mission `.toml`, the brief if there is one, and `tests/acceptance/CONTRACT.md` now.

Setup first: count the frozen tests in the metric target and name the spec IDs they cover. Branch `mission/$ARGUMENTS` off `harness/plexus-loop`. Run `/doctor`. Map comfy-cozy with the `cozy-mapper` agent for every module the brief names. Write `harness/plexus_loop/missions/$ARGUMENTS.plan.md`: ordered changes, each aimed at one frozen test; the scaffolding commits Claude must make first; every decision point reached; any mission-file diff you propose. Paste the `check` output into the plan.

Then **stop and show Joe the plan**. Do not `run` until he says go.

On his go: make the scaffolding commits, push `mission/$ARGUMENTS`, then `python -m harness.plexus_loop run harness/plexus_loop/missions/$ARGUMENTS.toml`. When it stops, read `.plexus_loop/$ARGUMENTS/REVIEW.md`, hand every kept commit to the `reviewer` agent, and run `/report`.
