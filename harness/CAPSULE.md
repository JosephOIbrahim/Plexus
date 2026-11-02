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

**Done (13:10):** full Comfy-Cozy suite 5,256 passed, 2 skipped; `plexus-loop/acceptance` fast-forwarded from `92d3892` to `e50049b`; both branches pushed. **Run 6** (five Jev-routed attempts from `e50049b`, baseline 10) started 13:11 and should end near 14:30.

**Run 6** (13:09 to 14:29, kept 0 of 5, mean 15.6 min): attempt 1 sent all five S2 files and passed every gate, then T1 failed on a missing `Usd` import; attempts 2 and 3 sent only one and three files (the worker treats each attempt as an edit to its last); attempt 4 sent all five again, fixed the import, and failed on `layer.subLayerPaths = <proxy>` (brief fix `0e42c42`, checked on 26.5). Attempt 5 sent three files and failed on the missing `stagekit` again. Run 7 (Joe, Nov 2) starts from the tip with the hand-on in place. Joe approved (Nov 2) `71ab408` + `e75f3cc`: a gate-passing drop hands its files to the next prompt to resend in full, each shown once; reviewer: keep. Logo PR #2 (`docs/plexus-logo` into `main`, logo only) is open for Joe to merge. After run 6: fast-forward `plexus-loop/acceptance` to the reviewed tip, push both branches, run 7 with five Jev-routed attempts. Parked: a pyflakes undefined-name check on changed files.

**Run 7** (14:30 to 16:08, from `33e5d13`, kept 0 of 5, mean 19.3 min): every attempt sent all five S2 files and passed every gate; the hand-on worked (attempts 2-4 resent all five) but none changed the failing line: `FindOrOpen` returns `None` for a missing file in `stagekit.create_project` (brief fix `6e8ea0d`, checked on 26.5, reaches run 8). Prompts with handed-on files take about 20 min an attempt. Attempt 5 failed on the same line.

**Next action:** when run 7 stops: check and apply the fewer-approvals proposal (Joe approved: standing-authority block in CLAUDE.md, allowlist in .claude/settings.json, guard_bash fix with tests; own commit, reviewer) → commit this capsule → fast-forward `plexus-loop/acceptance` to the tip → push both branches → run 8 (five Jev-routed attempts), then autopilot within the new rules. Joe: merge PR #2 (logo onto `main`) when ready. Joe approved (Nov 2) the known-fix table: `ab518be` quotes the matching brief line under a recognised target failure (seven fixes in acceptance.toml), with `d97f9e9` adding the brief's Imports bullet; with the reviewer.

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
