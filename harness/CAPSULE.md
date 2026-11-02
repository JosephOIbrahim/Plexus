# Capsule — Plexus

**Where we are:** Mile 2 of ~4. Mission `acceptance`: phase1 at 10 failing of 11 (baseline 11; T0, the schema gate, passes). One kept commit, `4e494b3` on `plexus-loop/acceptance` (S1, the schema plugin; reviewer: keep). Seven attempts so far across two runs, all on the CPU beside Houdini, mean about 10.9 min each: run 1 (5 attempts, 1 kept, 4 dropped at `git apply`), run 2 (2 attempts, both applied cleanly and both failed the `layers` gate, stopped early by the stop file). Run 3 (5 attempts, first with gate feedback in the prompt) is in progress. The harness now saves raw replies, rebuilds diffs, accepts whole-file blocks, and shows the last dropped attempt's gate output (`15bc013`, `131fbdb`). Nothing is merged yet.

**Next action:** when run 3 stops: reviewer on any new kept commits → merge `plexus-loop/acceptance` into `mission/acceptance` (Joe approved) → check the merged tip (phase1, layers, Rust build, `cargo test`, harness tests, full suite) → push → cut the GitHub pre-release `plexus-0.1.0-alpha.1` (no leading `v`, so no workflow fires). Then the 4-hour refinement loop continues (Pentagram-lens doc review, Rust and USD checks of the mission steps and worker brief).

**Blockers:** none hard. Step S2 has failed six times: four at `git apply` (fixed), then twice on the `layers` gate. Attempt 1 put `pxr` imports in package `__init__.py` files; attempt 2 made `plexus/core/__init__.py` import its submodules while they import from the package, which the guard reads as an import cycle. Run 3's worker sees the failing rule for the first time.

**Energy required:** low. One decision (below), then the release runs unattended.

**Decision for Joe:** move the `layers` guard from its interim home (`harness/plexus_loop/guards/test_layers.py`) into `tests/acceptance/guards/`, so the rule now steering every attempt is judge-owned.

**Ideas parked:**
- Worker brief: say outright that package `__init__.py` files stay empty, and that a step touches only its own files (run 2 attempt 2 wrote `neuron.py` and `predicate.py` during S2).
- Jev routing has agreed with "earliest failing step" on every attempt so far (7 of 7); keep it in place but judge it once routes start to differ.
- The full Comfy-Cozy suite passed twice (5,158 then 5,175 tests); run it once more at mission end.
- Spec Patch 02 is approved; its document and T0-style frozen test still need writing before M4.
- `release.yml` is Comfy-Cozy's pipeline. Retarget or retire it before any `v` tag.
- Open decisions elsewhere: the Blueprint v5.4 draft's four (no-import hook, `comfyui-agent` MCP server, D6 licence reading, a fifth contract).
- The seed (`agent/`, `cognitive/`): Joe decides whether it stays. SALUS / Moneta / Hanish: Joe is leaning toward removing them. `CLAUDE.cozy.md`: delete with the seed, or keep as history.
