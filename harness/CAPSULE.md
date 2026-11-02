# Capsule — Plexus

**Where we are:** Mile 2 of ~4. Mission `acceptance`: phase1 at 10 failing of 11 (baseline 11; T0, the schema gate, passes). One kept commit so far, `4e494b3` (S1, the schema plugin; reviewer: keep). Runs 1 to 3 made 10 attempts, all on the CPU beside Houdini, about 11 min each; run 3 kept nothing. `plexus-loop/acceptance` was merged into `mission/acceptance` as `242b3df`. On that tip the full Comfy-Cozy suite passed (5,212 passed, 2 skipped). Both branches are pushed, and the GitHub pre-release `plexus-0.1.0-alpha.1` points at `950b997`. Run 4 (5 Jev-routed attempts from `242b3df`) is in progress.

**Next action:** when run 4 stops:
- If it kept nothing: fast-forward `plexus-loop/acceptance` to the `mission/acceptance` tip, so run 5 gets the `950b997` brief fixes and the §10 decision record. Then start run 5.
- If it kept commits: the reviewer checks each one, then Joe decides on the merge into `mission/acceptance`. Promotion is his call each time. The fast-forward comes after.

**Blockers:** none hard. Step S2 failed 9 times before run 4: 5 at `git apply` (the patch handling is fixed) and 4 on the `layers` gate. Part of the `layers` noise was a guard bug: it read `from . import name` as an import cycle (fixed in `3ac9c54`, live from run 4). Under it were real faults: `pxr` in package `__init__.py` files (run 2), and `axon.py` and `stagekit.py` importing each other (run 3). `950b997` tells the worker both rules outright, and says that every attempt starts from the last kept commit, so the whole step is resubmitted. Run 4 started before `950b997`; run 5 is the first to see it.

**Energy required:** low. Nothing to decide unless run 4 keeps commits.

**Decided (Joe, Nov 2):** the `layers` guard stays at `harness/plexus_loop/guards/test_layers.py` for this mission, and the gate keeps pointing there. It is already locked against the worker (`harness/**` is frozen). The move to `tests/acceptance/guards/` happens after the mission, from Joe's own terminal; the draft for it is `docs/plexus/drafts/test_layers.py`. Until then, any change to the guard is its own commit, shown to Joe before the next run, and never made mid-run. Full record: `acceptance.plan.md` §10.

**Ideas parked:**
- After the mission: Joe freezes the guard in `tests/acceptance/guards/`; Claude repoints the gate and deletes the harness copy and the draft.
- Worker brief: say that a step touches only its own files (run 2 attempt 2 wrote `neuron.py` and `predicate.py` during S2).
- Jev routing has agreed with "earliest failing step" on every attempt so far; keep it, and judge it once routes start to differ.
- The full Comfy-Cozy suite has passed three times (5,158, 5,175, then 5,212 on `242b3df`); run it once more at mission end.
- The advancement research (7 lenses, then a Fable synthesis and a Jev roadmap) becomes `docs/plexus/ADVANCEMENT_RESEARCH_2026-11.md` when it finishes.
- Spec Patch 02 is approved; its document and T0-style frozen test still need writing before M4.
- `release.yml` is Comfy-Cozy's pipeline. Retarget or retire it before any `v` tag.
- Open decisions elsewhere: the Blueprint v5.4 draft's four (no-import hook, `comfyui-agent` MCP server, D6 licence reading, a fifth contract).
- The seed (`agent/`, `cognitive/`): Joe decides whether it stays. SALUS / Moneta / Hanish: Joe is leaning toward removing them. `CLAUDE.cozy.md`: delete with the seed, or keep as history.
