# program.md — Claude's protocol around the Plexus harness

This is the file Joe edits. It is shaped like Karpathy's autoresearch `program.md` — three surfaces and a ratchet — but the ratchet already exists: `harness/plexus_loop` runs the worker in throwaway worktrees, refuses frozen-path changes, runs the gates, keeps only attempts that lower `pytest_failures`, and writes the ledger. This file covers what the harness cannot do: setup, planning, review, reporting, and knowing when to stop and ask.

## The three surfaces

| Surface | Path | Who may touch it |
|---|---|---|
| **Judge** | `tests/acceptance/` (`CONTRACT.md` is the surface the tests call) | Joe only — hooks and the harness both enforce |
| **Editable** | the mission's `focus` (`plexus/**`, `crates/**`, `Cargo.toml`, `Cargo.lock`) | the worker, through the harness |
| **Program** | this file, `harness/plexus_loop/missions/*.toml`, `*.plan.md`, `CLAUDE.md` | Joe, and Claude when Joe says so |

The mission file also freezes `pyproject.toml` and `harness/**` for the worker. Anything the build needs there (the maturin section, a Cargo workspace, a `[[gates]]` for `cargo test`) is scaffolding Claude does before `run`, in its own commit on the mission branch, shown to Joe.

## Setup (once per mission, never skipped)

1. Read `CLAUDE.md`, this file, the mission `.toml`, `tests/acceptance/CONTRACT.md`, the blueprint, and the frozen tests for this mission. Count the test functions under the mission's `metric.target` and name the spec IDs they cover (phase1 = T0 schema gate + T1–T6; phase2 = T7–T8; `pending/` is uncounted). CONTRACT.md says all 18 passed a throwaway prototype on Nov 1.
2. Confirm the branch is `harness/plexus-loop` and the tree is clean. Create `mission/<name>` from it for Claude's own commits (scaffolding, plan, mission-file edits). The harness puts kept worker attempts on `plexus-loop/<name>`.
3. Run `/doctor`. Fix only what it reports, only inside the repo's venv or Cargo workspace.
4. **Map Comfy-Cozy as a reference** with the `cozy-mapper` agent for every module the mission brief names (the seeded `agent/` and `cognitive/` match `G:\Comfy-Cozy`; read `G:\Comfy-Cozy` for its July docs and tooling). Each gets one verdict, with file evidence: reference, rebuild in Python, rebuild in Rust, or drop. Nothing is copied or imported; a borrowed idea is restated in Plexus's own terms in the plan.
5. **Plan.** Write `harness/plexus_loop/missions/<name>.plan.md`: the ordered list of changes, each small enough for one worker attempt, each naming the frozen test it is aimed at. Name every scaffolding commit Claude must make first. Name every decision point from `CLAUDE.md` that the plan reaches. If the mission file needs changing (gate narrowing, a new gate, a `focus` path), propose the diff; do not apply it without Joe.
6. Run `python -m harness.plexus_loop check <mission.toml>` and paste its output into the plan.
7. **Stop and show Joe the plan.** Wait for his go.

## Run (after Joe's go)

1. Make the scaffolding commits on `mission/<name>`. Push the branch so the harness can start from it.
2. `python -m harness.plexus_loop run <mission.toml>`. Do not babysit; the harness has its own budget and stop conditions.
3. When it stops, read `.plexus_loop/<name>/REVIEW.md` and `.plexus_loop/<name>/attempts.jsonl`. Hand every kept commit on `plexus-loop/<name>` to the `reviewer` agent. A reviewer HARD failure on a kept commit is reported to Joe; Claude does not revert it alone.
4. If the stop reason is `max_consecutive_failures` on the same target test, that is a planning problem: revise the plan or the mission file, show Joe, and only then `run` again.

## Attempt time

CPU-mode speed is unmeasured. The ledger records wall time per attempt; `/report` averages it by mode. After the first run, propose `worker.timeout_s` and `budget.hours` values from the measured median, as a mission-file diff for Joe.

## Report (when the run stops)

Plain sentences, in this order: which frozen tests pass now versus baseline; what changed, by file; what failed and why; average attempt time by mode; the full comfy-cozy suite result if the `unit` gate was narrowed; the one decision Joe needs. Then rewrite `harness/CAPSULE.md`: Mile x of ~y, next action, blockers, energy required, ideas parked.

## Rules that are also hooks

Never edit the frozen tests. Never push to main. Never force-push. Nothing from Synapse. If a hook blocks you, the hook is right; do not route around it.
