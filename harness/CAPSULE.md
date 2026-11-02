# Capsule — Plexus

**Where we are:** Mile 2 of ~4. Mission `acceptance`: phase1 at 10 failing of 11 (baseline 11; T0, the schema gate, passes). One kept commit so far, `4e494b3` (S1, the schema plugin; reviewer: keep). The ledger holds 20 attempts across five runs, all on the CPU beside Houdini; all 19 drops are step S2. Runs 1 to 3 averaged 11.0 min an attempt, run 4 about 18, run 5 14.9 (measured: 822, 876, 900, 1046, 818 s).

**Run 4** (09:48 to 11:22, from `242b3df`) kept 0 of 5, but four of its five S2 attempts passed every gate, `layers` included, for the first time. Each then failed all ten tests on one USD call: `Usd.Prim.AddReference` (attempt 2), `ApplyAPI('PlexusProjectAPI')` (attempts 3 and 4), `Usd.Plug` (attempt 5). Attempt 1 failed `layers` on a syntax error (`from_<id> = ...`). None of these could use the brief fixes, which landed after run 4 started.

**What run 5 got** (all on `mission/acceptance`, each reviewed or checked live on usd-core 26.5):
- `950b997`: resubmit the whole step; package `__init__.py` files hold a docstring only; axon and stagekit never import each other.
- `3bfe08e`, `0b81c20`: syntax errors in changed files lead the dropped-attempt feedback, and the check can never end the run.
- `4f46bfc`, `cade53d`: each ledger row records `wall_s`, `route_s`, `worker_s`, each gate's seconds and `metric_s`.
- `f20392d`, `85a58b7`, `1fda679`: author the project reference and `PlexusProjectAPI` with `Sdf`; never `ApplyAPI`; register the plugin before the first schema lookup, with `from pxr import Plug`.

**Run 5** (11:35 to 12:54, from `92d3892`) kept 0 of 5, all S2, mean 14.9 min (the worker is 86-89% of each attempt). Attempts 1, 2 and 5 sent `axon.py` and the `__init__` files only; attempt 3 added `stagekit.py`; attempt 4 sent all five files and passed every gate, then T1 failed on `Tf.Notice.ObjectsChanged` (does not exist; it is `Usd.Notice.ObjectsChanged`), an error the feedback never showed because the metric's tail was T6.

**What run 6 gets** (on `mission/acceptance`, Joe Nov 2): `b6c5aad` + `6a7db72` + `2d3d424` (each step lists its files; every prompt names the absent ones; reviewer: keep), `4406e71` (brief: `Usd.Notice.ObjectsChanged`), `2db613a` + `5e935fd` (feedback leads with the step's own target-test failures from the junit report, and a teardown error never hides a test's own failure; reviewer: keep). Also `c7f1aad`, `2b20bc5` (Plexus logo in both readmes) and `d0f8d42` (demos removed, pushed).

**Next action:** commit this capsule → fast-forward `plexus-loop/acceptance` from `92d3892` to the tip → push both branches → run 6, five Jev-routed attempts (Joe, Nov 2). After run 6: read the target failures in the ledger, add any missing fact to the brief.

**Blockers:** none hard. S2 now fails one USD call at a time, and the brief supplies each call as it surfaces.

**Energy required:** low. Nothing to decide.

**Decided (Joe, Nov 2):** the `layers` guard stays at `harness/plexus_loop/guards/test_layers.py` for this mission, and the gate keeps pointing there. It is already locked against the worker (`harness/**` is frozen). The move to `tests/acceptance/guards/` happens after the mission, from Joe's own terminal; the draft for it is `docs/plexus/drafts/test_layers.py`. Until then, any change to the guard is its own commit, shown to Joe before the next run, and never made mid-run. Full record: `acceptance.plan.md` §10.

**Ideas parked:**
- Goal for the organ mission (phase 2, the ComfyUI organ), Joe Nov 2: a desktop launcher that starts Plexus and its ComfyUI worker together, with `G:\COMFYUI_Database` as the model root.
- After the mission: Joe freezes the guard in `tests/acceptance/guards/`; Claude repoints the gate and deletes the harness copy and the draft.
- Timing, first answers (run 5 attempts 1 and 2): wall 822 s and 876 s, of which the worker is 711 s and 770 s (86-88%), the `unit` gate about 95 s, everything else under 10 s. The reply is only about 3 KB, so the time is the model reading a 76k-character prompt (about 20-25k tokens, inside `num_ctx` 40960) on the CPU. Lever to measure after run 5: static context first, so Ollama's prompt cache can reuse it between attempts.
- Run 5 attempts 1 and 2 each sent only the two package `__init__.py` files and `axon.py`, never `stagekit.py` or `exchange.py`, so every test failed on `cannot import name 'stagekit'`; the brief's USD fixes were never exercised. Run 4's replies (7-9 KB) sent all three modules. Joe approved a fix (Nov 2): `b6c5aad` gives every step a `files` list, shows it in the prompt, and names any step file a drop left out at the top of the next prompt. Reviewer pass, then fast-forward `plexus-loop/acceptance` to it after run 5 ends, before run 6.
- Worker brief: say that a step touches only its own files (run 2 attempt 2 wrote `neuron.py` and `predicate.py` during S2).
- Three harness findings from `docs/plexus/ADVANCEMENT_RESEARCH_2026-11.md` wait on Joe: `max_consecutive_failures` 8 is inert under 5 attempts; Jev routing versus the `first` router (Jev has agreed with "earliest failing step" on every attempt, by construction); restore a contract-fixed file instead of dropping the attempt.
- The full Comfy-Cozy suite has passed four times (5,158, 5,175, 5,212 on `242b3df`, 5,212 on `ef158ea`); run it once more at mission end.
- Spec Patch 02 is approved; its document and T0-style frozen test still need writing before M4.
- `release.yml` is Comfy-Cozy's pipeline. Retarget or retire it before any `v` tag.
- Open decisions elsewhere: the Blueprint v5.4 draft's four (no-import hook, `comfyui-agent` MCP server, D6 licence reading, a fifth contract), and the 17 in the research doc.
- The seed (`agent/`, `cognitive/`): Joe decides whether it stays. SALUS / Moneta / Hanish: Joe is leaning toward removing them. `CLAUDE.cozy.md`: delete with the seed, or keep as history.
