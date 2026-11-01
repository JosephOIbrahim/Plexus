# Mission `acceptance` — planning brief (Claude reads this before writing acceptance.plan.md)

**Done means:** every test under `tests/acceptance/phase1` passes (T0 schema gate + T1–T6). The harness metric is `pytest_failures` on that path, direction lower. T1 is single-process. T1b in `pending/` stays skipped and uncounted. T7 and T8 (`phase2/`) are the next mission.

**Expected count:** CONTRACT.md says 18 tests across phase1 + phase2 passed a throwaway prototype on Nov 1. Report the actual phase1 count at setup.

## Facts verified against comfy-cozy @ 7c04117 (verify they still hold at HEAD; do not re-derive)

- `agent/stage/cognitive_stage.py` emits `StageEvent` from inside `write()`. Nothing in the repo registers `Tf.Notice` / `ObjectsChanged`. CONTRACT.md's `plexus.core.axon.PlexusAxon` is a composition-side observer and must be built new. Restate the queue + dispatcher-thread idea in Plexus's own code (copy nothing); avoid the write-side emit.
- `agent/gate/risk_levels.py` is a static tool→risk map; unknown tools default to REVERSIBLE. The Rust Safety contract keeps the five levels, default deny. Mission `acceptance` needs only the path allowlist gate (CONTRACT.md §7.3 via `ctx.author`); the risk classifier comes later and is Plexus's own (draft v5.4 B19).
- `agent/engine/_base.py` (`IAIEngine`) is Comfy-Cozy's ComfyUI execution base class: the reference for the Phase 2 organ, which is written new against the organ contract and ComfyUI's own HTTP API (draft v5.4 B8). This mission does not touch it.
- Comfy-Cozy's environment fingerprint (`diagnose` tool, `agent/diagnosis`) is the reference; the new organ produces its own for Patch 01-B in phase2.
- `agent/stage/` is ~10k lines of ComfyUI-specific Python. `tests/acceptance/phase2/test_t8_blindness.py` is frozen; read it now to learn its grep scope so new code goes where T8 expects.
- `agent/integrations/moneta.py` is the old integration, not the Plexus adapter. Nothing imports it.

## The plan must settle these before Joe's go

1. **Schema rows.** `PlexusAssetAPI` carries `envFingerprint`, `organVersion`, `retryOf`, `retryReason`. Check whether `test_t0_schema_gate.py` asserts them. If not, say so; do not add a test.
2. **Scaffolding the worker cannot do.** The mission freezes `pyproject.toml` and `harness/**`. List the exact commits Claude makes first: maturin section + `plexus/` package skeleton + `crates/plexus-core` workspace, and the `[[gates]] cargo` block to add to the toml. Each is a proposed diff for Joe.
3. **The notice path.** CONTRACT.md fixes the Python surface (`PlexusAxon(stage, debounce_s)`, callbacks on the dispatcher thread, never inside the notice callback). Open: what sits below it in `plexus._core`. Propose the smallest split that passes T1 and T2 and state the alternative you rejected. Starting hypothesis to test, not assume: `Tf.Notice` registered in Python; the callback packs `(paths, resynced, t)` and hands it across PyO3; Rust owns debounce, scope filter, predicate compile/eval, budgets.
4. **The `unit` gate.** It runs the whole comfy-cozy suite per attempt (README: minutes; toml: 3600 s timeout). Propose a narrowed `cmd` — the Cozy tests that cover the modules this mission touches — and the full-suite run once at mission end. Joe decides.
5. **Worker reach.** The worker edits only `focus` paths. Confirm the plan never needs it to touch `agent/` or `cognitive/`. If it does, that is a `focus` change for Joe.

## Stop condition

Harness stop conditions, or a decision point above.
