# Capsule — Plexus

**Where we are:** Mile 0 of ~4. Seed is on `main` (comfy-cozy history + blueprint v5.3). `harness/plexus-loop` carries the harness, the frozen tests (18 across phase1+phase2, T1b pending) and CONTRACT.md. Claude Code kit installed (hooks, agents, commands, program.md). No `plexus/` code yet.

**Next action:** merge the kit PR into `harness/plexus-loop`, open Claude Code in the repo, type `/mission acceptance`. It stops after `/doctor` and again after the plan.

**Blockers:** `ollama list` showed no `qwen3-coder:30b` on Nov 1 (not pulled, or Ollama down). `/doctor` will ask before pulling.

**Energy required:** medium for the plan review; low once the harness is running.

**Ideas parked:**
- `unit` gate narrowing — Claude proposes the subset, Joe decides.
- T8 grep scope vs seeded `agent/` code — read `test_t8_blindness.py` during setup; decide in mission `phase2`.
- `agent/stage` retirement — after T7, delete what the organ adapter does not reach.
- SALUS / Moneta / Hanish — Joe is leaning toward removing them from the seed entirely.
- `CLAUDE.cozy.md` — comfy-cozy's old CLAUDE.md, kept for `agent/`/`cognitive/` work; fold or delete later.
