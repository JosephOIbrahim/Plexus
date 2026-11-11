---
description: Draft, place, run and review a Plexus harness mission with Claude as planner and reviewer, per harness/plexus_loop/program.md
argument-hint: <mission-slug> [scope, when the mission is new]
allowed-tools: Bash(git *), Bash(python -m harness.plexus_loop *), Bash(python -m pytest *), Bash(pytest *), Bash(cargo *), Bash(maturin *), Bash(ollama *), Read, Grep, Glob, Agent, Write(harness/plexus_loop/missions/*.plan.md), Write(harness/CAPSULE.md)
---

## Pre-computed context

None of these commands reads the arguments. Claude Code pastes arguments into a shell command as raw text, so an apostrophe, a colon or a space in them breaks the command. On Nov 11, 2026, `/mission M3.2: close alpha.10's Still-open list …` failed that way before anything was drafted. The arguments are read below as text instead.

- Branch: !`git branch --show-current`
- Tree: !`git status --short | head -20`
- Mission files: !`ls harness/plexus_loop/missions/*.toml 2>/dev/null | sed -E 's#.*/##; s#\.toml$##' | tr '\n' ' '`
- Ledgers: !`ls .plexus_loop 2>/dev/null | tr '\n' ' '`
- Loop branches: !`git branch --list 'plexus-loop/*' --format='%(refname:short)' | tr '\n' ' '`
- Latest release tag: !`git tag --list 'plexus-*' --sort=-creatordate | head -1`

## The arguments

As typed: $ARGUMENTS

Read them as text. Never paste them into a shell command; put only the slug in commands, quoted.

1. **The slug** is the first word, kept only if it is lowercase letters, digits and hyphens, such as `organ-hardening`. Everything after the first word is the **scope**.
2. **An existing mission.** The slug names a mission file listed above: go to "Run a placed mission".
3. **A new mission.** The first word is not a valid slug (for example `M3.2:`), or it names no mission file. Make a slug from the scope: two or three lowercase words joined by hyphens, not used by any mission file, ledger or branch. Say the slug and why in one line. Then go to "Draft a new mission", and do not stop to ask for a slug.
4. **No arguments.** List the missions above with their state, and ask which one.

With the slug in hand, run each per-mission command yourself, for example:
- `ls "harness/plexus_loop/missions/<slug>.toml"`
- `python -m harness.plexus_loop check "harness/plexus_loop/missions/<slug>.toml"`
- `tail -3 ".plexus_loop/<slug>/attempts.jsonl"`
- `git log --oneline "mission/<slug>..plexus-loop/<slug>"`

## Draft a new mission

Read `CLAUDE.md`, `harness/plexus_loop/program.md`, `tests/acceptance/CONTRACT.md`, and the newest mission's `.plan.md` as the model.

1. **Decisions.** Every choice the scope reaches gets a numbered decision (D1, D2, …) with a recommended option, why, and what a different answer costs. These are the mission's assumptions until Joe says otherwise; they open the plan.
2. **The frozen draft.** Write the new test file and any CONTRACT lines in the session scratchpad only.
   - Every scope clause needs a case that fails on the base for its own reason.
   - Where no frozen case can read a clause on this machine (a race, a platform the harness does not run on, a fault that cannot be forced), the plan names the clause, says why, and names what covers it instead: verbatim step text, the reviewer, a WSL run.
3. **The reference.** Write the implementation the step text will carry verbatim, in the scratchpad. Never write it in `plexus/` or `crates/`.
4. **The proof.** Run it in a scratch worktree with `plexus/_core` built or copied:
   - the base fails, each case for its own reason;
   - the reference passes, three times;
   - phase 1 and phase 2 pass whole;
   - the guards and the six gates pass;
   - a mutant run, and an adversary pass in its own worktree.
5. **The mission files**, in the scratchpad: the toml (one step per change, the reference verbatim), the worker brief, the plan, and the program.md rule 2 diff.
6. **The placement script.** It pins each frozen file's sha256 and refuses anything else.
   - Dry-run it in a scratch clone, printing a marker the real run never prints.
   - Remove the dry-run copy afterwards.
7. **Stop and show Joe** the decisions, the frozen file, the plan, and one placement line for him to type at the Claude Code prompt: an exclamation mark, then `bash` and the script's path. Offer that line alone, with no Git Bash fallback. Nothing is placed, committed, pushed or run.

## Run a placed mission

Run it exactly as `program.md` describes, once Joe's placement commit is on `mission/<slug>`.

1. **Check the placement.** Confirm on disk the branch and each pinned sha256 before anything else. A message saying it was placed is not evidence.
2. **Scaffolding.** C1 copies the toml, brief and plan into `harness/plexus_loop/missions/`. C2 adds the rule 2 line. Each is its own commit.
3. **Check.** Run `python -m harness.plexus_loop check` and paste its output into the plan.
4. **Push.** Push `mission/<slug>` by name, after `git diff --name-only origin/<branch>...<branch>` lists nothing under `tests/acceptance/`. For a branch new on origin, compare with the branch it was cut from.
5. **Run** `python -m harness.plexus_loop run "harness/plexus_loop/missions/<slug>.toml"` in the background, and report each ledger row as it lands.
6. **Review.** When the run stops, read `.plexus_loop/<slug>/REVIEW.md`, hand every kept commit to the `reviewer` agent, and run `/report <slug>`.
