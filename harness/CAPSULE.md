# Capsule — Plexus

**Where we are:** Mile 1 of ~4. Mission `acceptance` setup is done and the plan is written, committed and pushed: `harness/plexus_loop/missions/acceptance.plan.md` on `mission/acceptance` (`f399183`). Baseline is 11 of 11 phase1 items failing. `/doctor` passed except the model. Nothing has run. The Plexus README and six Mermaid diagrams are on `harness/plexus-loop` (`486f37b`), not yet on `main`. No `plexus/` code yet.

**Next action:** Joe answers the plan's §8 decisions and says `go`. On go, Claude merges `harness/plexus-loop` into `mission/acceptance`, makes scaffolding commits C1–C5, verifies the pyo3 build on Python 3.14, pushes, then runs the harness.

**Blockers:**
- `qwen3-coder:30b` is not pulled. Joe runs `ollama pull qwen3-coder:30b` (about 19 GB). `check` prints `ready` without it, but every attempt would fail.
- Decisions pending: notice path A or B; narrow the `unit` gate (9 min 29 s → 49 s per attempt); C1–C5 plus the mission-file diff; no maturin in `pyproject.toml` this mission; whether to cut a release at all.

**Energy required:** medium for the decisions (about 10 minutes of reading the plan); low once the harness is running.

**Ideas parked:**
- `release.yml` is Comfy-Cozy's pipeline (tag must equal `v` + `agent.__version__`). Retarget or retire it before any Plexus release.
- README on GitHub shows `main`'s copy until a PR from `harness/plexus-loop` merges.
- T8 grep scope vs seeded `agent/` code — decide in mission `phase2`. Never import `agent.*` or `cognitive.*` from `plexus/`.
- The seed (`agent/`, `cognitive/`): Joe decides whether it stays. The Phase 2 organ is new (draft B8) and reaches none of it.
- SALUS / Moneta / Hanish — Joe is leaning toward removing them from the seed entirely.
- `CLAUDE.cozy.md` — comfy-cozy's old CLAUDE.md, kept for `agent/`/`cognitive/` work; delete with the seed, or keep as history.
