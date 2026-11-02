# Capsule — Plexus

**Where we are:** Mile 2 of ~4. Mission `acceptance`: phase1 at 10 failing of 11 (baseline 11; T0, the schema gate, passes). One kept commit so far, `4e494b3` (S1, the schema plugin; reviewer: keep). The ledger holds 15 attempts across four runs, all on the CPU beside Houdini; all 14 drops are step S2. Runs 1 to 3 averaged 11.0 min an attempt; run 4 averaged about 18 (24, 16, 17, 17, 18).

**Run 4** (09:48 to 11:22, from `242b3df`) kept 0 of 5, but four of its five S2 attempts passed every gate, `layers` included, for the first time. Each then failed all ten tests on one USD call: `Usd.Prim.AddReference` (attempt 2), `ApplyAPI('PlexusProjectAPI')` (attempts 3 and 4), `Usd.Plug` (attempt 5). Attempt 1 failed `layers` on a syntax error (`from_<id> = ...`). None of these could use the brief fixes, which landed after run 4 started.

**What run 5 gets** (all on `mission/acceptance`, each reviewed or checked live on usd-core 26.5):
- `950b997`: resubmit the whole step; package `__init__.py` files hold a docstring only; axon and stagekit never import each other.
- `3bfe08e`, `0b81c20`: syntax errors in changed files lead the dropped-attempt feedback, and the check can never end the run.
- `4f46bfc`, `cade53d`: each ledger row records `wall_s`, `route_s`, `worker_s`, each gate's seconds and `metric_s`.
- `f20392d`, `85a58b7`, `1fda679`: author the project reference and `PlexusProjectAPI` with `Sdf`; never `ApplyAPI`; register the plugin before the first schema lookup, with `from pxr import Plug`.

**Next action** (Joe, Nov 2: commit, push, release, then run 5): commit this capsule and the research doc → fast-forward `plexus-loop/acceptance` from `242b3df` to that tip → full Comfy-Cozy suite on it → push both branches → GitHub pre-release `plexus-0.1.0-alpha.2` (no leading `v`) → run 5, five Jev-routed attempts. No release if the suite fails.

**Blockers:** none hard. S2 now fails one USD call at a time, and the brief supplies each call as it surfaces.

**Energy required:** low. Nothing to decide.

**Decided (Joe, Nov 2):** the `layers` guard stays at `harness/plexus_loop/guards/test_layers.py` for this mission, and the gate keeps pointing there. It is already locked against the worker (`harness/**` is frozen). The move to `tests/acceptance/guards/` happens after the mission, from Joe's own terminal; the draft for it is `docs/plexus/drafts/test_layers.py`. Until then, any change to the guard is its own commit, shown to Joe before the next run, and never made mid-run. Full record: `acceptance.plan.md` §10.

**Ideas parked:**
- Goal for the organ mission (phase 2, the ComfyUI organ), Joe Nov 2: a desktop launcher that starts Plexus and its ComfyUI worker together, with `G:\COMFYUI_Database` as the model root.
- After the mission: Joe freezes the guard in `tests/acceptance/guards/`; Claude repoints the gate and deletes the harness copy and the draft.
- After run 5: read the new timing fields to see where an attempt's time goes (run 4 averaged about 18 min against 11 before it).
- Worker brief: say that a step touches only its own files (run 2 attempt 2 wrote `neuron.py` and `predicate.py` during S2).
- Three harness findings from `docs/plexus/ADVANCEMENT_RESEARCH_2026-11.md` wait on Joe: `max_consecutive_failures` 8 is inert under 5 attempts; Jev routing versus the `first` router (Jev has agreed with "earliest failing step" on every attempt, by construction); restore a contract-fixed file instead of dropping the attempt.
- The full Comfy-Cozy suite has passed four times (5,158, 5,175, 5,212 on `242b3df`, 5,212 on `ef158ea`); run it once more at mission end.
- Spec Patch 02 is approved; its document and T0-style frozen test still need writing before M4.
- `release.yml` is Comfy-Cozy's pipeline. Retarget or retire it before any `v` tag.
- Open decisions elsewhere: the Blueprint v5.4 draft's four (no-import hook, `comfyui-agent` MCP server, D6 licence reading, a fifth contract), and the 17 in the research doc.
- The seed (`agent/`, `cognitive/`): Joe decides whether it stays. SALUS / Moneta / Hanish: Joe is leaning toward removing them. `CLAUDE.cozy.md`: delete with the seed, or keep as history.
