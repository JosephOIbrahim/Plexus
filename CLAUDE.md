# Plexus — CLAUDE.md

Plexus (working title): a living network where projects compose into each other while running, agents wake only when needed, and execution engines are interchangeable organs. USD composition is the runtime. A Rust core (PyO3/maturin, importable as `plexus._core`) owns the runtime, and new Plexus Python grows around it in `plexus/`. Plexus is the next generation of Comfy-Cozy, built from the ground up: Comfy-Cozy (`G:\Comfy-Cozy`) is an architecture reference only, not the codebase, and new Plexus code copies nothing from it and imports nothing from it. The repo still carries Comfy-Cozy's history and the seeded `agent/` and `cognitive/` code; whether that stays is Joe's call. Their conventions are in `CLAUDE.cozy.md`; read that only when touching `agent/` or `cognitive/`.

This file advises. The hooks in `.claude/settings.json` enforce. A rule that matters enough to be unbreakable is also a hook.

## Source of truth, in order

1. `tests/acceptance/` — frozen. `tests/acceptance/CONTRACT.md` is the Python surface the tests call; everything below it is free. Never edited, skipped or re-marked by Claude or the worker. Joe may.
2. `docs/plexus/PLEXUS_BLUEPRINT_v5.md` (v5.3). Overrides the August baseline wherever they conflict. Where v5.3 calls Comfy-Cozy the seed code, or says Plexus keeps or imports its code, the Nov 1 decision above wins until v5.4 lands (`docs/plexus/BLUEPRINT_v5.4_DRAFT_CHANGES.md`).
3. `PLEXUS_SPEC.md` (v2.1 + Patch 01) for what v5.3 does not cover: schemas, predicate grammar v0, organ contract, test definitions. Patch record: `docs/plexus/package-2026-11-01/04_PLEXUS_SPEC_PATCH_01.md`.

Where v5.3 wins over the spec: the runtime is Rust, not the spec's Python repo shape; predicates compile in Rust; usd-core 0.26.5 is the composer of record and the pure-Rust openusd crate stays behind its parity test; "resume" is not in the organ contract.

## The harness

`harness/plexus_loop/` is Plexus's own, written fresh. Verbs: `python -m harness.plexus_loop check|run|stop <mission.toml>`. Mission files live in `harness/plexus_loop/missions/`. Claude writes and revises mission files; the worker (Ollama, `qwen3-coder:30b`) only makes attempts inside one. Kept attempts land on `plexus-loop/<mission>`; the ledger is `.plexus_loop/<mission>/attempts.jsonl`; the summary is `.plexus_loop/<mission>/REVIEW.md`. Nothing merges by itself.

## Hard rules

- Nothing from Synapse comes into Plexus. No code, imports, packages, shared contracts or dependencies. Synapse is one architectural reference among several (the v4.0 blueprint, comfy-cozy, the AOUSD spec, the Rust ecosystem). A borrowed idea is justified on Plexus's own terms in the plan or commit message.
- Nothing from Comfy-Cozy comes into `plexus/` or `crates/` either: no `agent.*` or `cognitive.*` import, at module or function scope, and no copied file. Like Synapse, it is a reference. No hook enforces this yet.
- Plexus runs without SALUS, Moneta and Hanish. Nothing imports `agent/integrations/moneta.py`. Memory means the Plexus-local store.
- Branches only. Never push to main, never merge into main, never force-push.
- Claude plans and reviews. The worker writes implementation code. Claude does not hand-write implementation to rescue a stalled attempt; it revises the mission file or the plan. Scaffolding the worker cannot reach (the mission freezes `pyproject.toml` and `harness/**`) is Claude's, done before `run`, in its own commit, shown to Joe.
- Houdini open, or the check cannot tell → CPU. The harness does this itself. Never bypass it.
- One mission at a time. Start with `/mission acceptance`.

## Stop and ask Joe

- A frozen test looks wrong.
- The notice path below `PlexusAxon`: what lives in Python and what lives in `plexus._core`. Bring two options and the trade-off.
- Narrowing the `unit` gate in the mission file (it runs the whole comfy-cozy suite per attempt).
- Any install outside the repo's own venv or Cargo workspace.
- Anything that cannot be undone.

Do not ask about anything else mid-mission. Make the call, write the assumption into the plan file, keep moving.

## Reporting

Lead with the answer. Complete sentences, one idea per paragraph. A mission report says: which tests pass versus baseline, what changed by file, what failed and why, average attempt time per mode (CPU/GPU), the one decision needed. It ends with a capsule written to `harness/CAPSULE.md`.

## Mistakes become rules

When Joe corrects something, add one line here so it is not repeated.

- Plexus is the next generation of Comfy-Cozy, built from the ground up. G:\Comfy-Cozy, like SYNAPSE, is an architecture reference only: new Plexus code copies nothing from it and imports nothing from it, at module or function scope (Joe, Nov 1). Whether the seeded `agent/` and `cognitive/` stay is Joe's call.
