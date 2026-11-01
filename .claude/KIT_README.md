# Plexus Claude Code kit

Hooks enforce. CLAUDE.md advises. program.md is the loop. Install with `scripts/install_kit.ps1 -Repo C:\Users\User\repos\Plexus`; it lands on branch `harness/kit` and opens a PR into `harness/plexus-loop`. Never touches main.

| Piece | Role |
|---|---|
| `CLAUDE.md` | Short, living rules. Mistakes become lines at the bottom. |
| `.claude/settings.json` | permissions deny/allow + hooks wiring |
| `.claude/frozen_paths.txt` | the judge: `tests/acceptance/` |
| `.claude/hooks/guard_bash.py` | branches only, no shell writes to frozen tests, no Synapse installs, Houdini→CPU |
| `.claude/hooks/guard_edit.py` | no edits to frozen tests, no Synapse / old-Moneta imports in code |
| `.claude/hooks/guard_stop.py` | refuses to end a turn with frozen tests dirty or Synapse in the diff |
| `.claude/hooks/session_start.py` | prints branch, frozen count, capsule, last attempts, GPU state |
| `.claude/agents/reviewer.md` | read-only verdict on every kept attempt |
| `.claude/agents/cozy-mapper.md` | reference / rebuild in Python / rebuild in Rust / drop, per Comfy-Cozy module read as an architecture reference (haiku) |
| `.claude/commands/mission.md` | `/mission 01` — runs program.md end to end |
| `.claude/commands/doctor.md` | `/doctor` — environment check, repo-local fixes only |
| `.claude/commands/report.md` | `/report` — mission report + capsule from the ledger |
| `harness/plexus_loop/program.md` | Claude's protocol around the harness: setup → plan → stop → run → review → report |
| `harness/plexus_loop/missions/acceptance.plan-brief.md` | mission `acceptance` brief with the comfy-cozy facts (references only, per the Nov 1 decision) and the five things the plan must settle |

Verified against the repo on Nov 1: frozen tests at `tests/acceptance/`, harness verbs `python -m harness.plexus_loop check|run|stop`, blueprint v5.3 at `docs/plexus/PLEXUS_BLUEPRINT_v5.md`, spec at `PLEXUS_SPEC.md`.