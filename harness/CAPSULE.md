# Capsule — Plexus

**Where we are:** Mile 2.5 of ~4. Mission `acceptance`: phase1 is at 9 failing of 11 (baseline 11). T0 (the schema gate) and T1 (A-to-B propagation) pass. Two keeps so far: `4e494b3` (S1, the schema plugin) and `b18ebd0` (S2, membrane, stagekit and axon; run 9 attempt 4), merged into `mission/acceptance` as `ccee44c`. The ledger holds 45 attempts over 10 runs, 2 kept, all on the CPU beside Houdini. 30 have timing: 18.9 min mean, or 18.1 min without run 10's two timeouts.

**Run 11 is running** (started Nov 3, 08:21, from `0b5bef9`; five attempts). It is the first run with `[router] kind = "first"` (Joe, Nov 3), so every attempt goes to the earliest step with a failing target, which is S3 (the Rust predicate). The worker timeout is 3600 s, up from 1800; the gate timeout stays 1800 s. `0b5bef9` changes only `acceptance.toml`; the code is `ff998a0`'s. Output: `.plexus_loop/acceptance/run11.log`. Do not move `plexus-loop/acceptance` while it runs.

**Released:** `plexus-0.1.0-alpha.3` (pre-release, Nov 3) tags the commit that adds this capsule. Its notes cover runs 5 to 10.

**Run 10** (Nov 2, 21:03 to 23:12, Jev-routed) kept 0 of 5:
- Attempts 1 and 2: Jev sent them to S8 (0.33, 0.32). Each wrote only `neuron.py`; T6 failed with "child never printed 'STARTED'". S8 cannot pass before S3 to S7 exist.
- Attempt 3: S3 by fallback (Jev 0.27, under 0.3). It wrote only `predicate.rs`, passed every gate, and T2 failed on `No module named 'plexus.core.predicate'`. The worker took 1,498 s of 1,642 s.
- Attempts 4 and 5: S3 by fallback. Both hit the 1800 s Ollama timeout with no reply.

**Next action:** when run 11 ends, read `REVIEW.md` and the ledger, send any kept commit to the `reviewer` agent, then `/report acceptance`. Merging a keep into `mission/acceptance` is Joe's call.

**Watch in run 11:** whether S3 replies fit inside 3600 s, and whether the worker sends all five S3 files (`predicate.rs`, `lib.rs`, `py.rs`, `predicate.py`, `neuron.py`). Attempt 3 of run 10 sent one. If run 11 still sends partial S3 replies, the next lever is the brief (split S3, or shorten its pyo3 skeleton), not the router.

**Blockers:** none hard.

**Energy required:** none until run 11 ends; then low (read the review, one merge decision if anything is kept).

**Still waiting on Joe:**
- The fewer-approvals proposal: "do 1", "do 1 and 2", or "apply all as proposed". Not applied.
- PR #2 (the logo onto `main`), to merge.
- The worker seed and temperature proposal.

**Decided (Joe):**
- Nov 3: router `first`, worker timeout 3600 s (`0b5bef9`).
- Nov 2: `b18ebd0` merged (option 1). The `layers` guard stays at `harness/plexus_loop/guards/test_layers.py` for this mission; `docs/plexus/drafts/test_layers.py` carries the same rules, including the init check. Any guard change is its own commit, shown to Joe, never made mid-run. Full record: `acceptance.plan.md` §10.

**Ideas parked:**
- Mission 02 brief: `plexus/organs/cozy.py` is a module, not a package. The init guard would block a `cozy/__init__.py` that re-exports `CozyOrgan`.
- Organ mission goal (Joe, Nov 2): a desktop launcher that starts Plexus and its ComfyUI worker together, with `G:\COMFYUI_Database` as the model root.
- Speed: the worker is 83 to 91% of every attempt (a prompt of roughly 20-25k tokens on the CPU). Lever: put the static context first, so Ollama's prompt cache can reuse it.
- A pyflakes undefined-name check on changed files; stricter step-file path validation; show `missing` and `handed_on` in REVIEW.md.
- Restore a contract-fixed file instead of dropping the attempt. `max_consecutive_failures` 8 has no effect when a run has only 5 attempts.
- The full Comfy-Cozy suite last passed on `e50049b` (5,256 passed, 2 skipped). Nothing under `agent/`, `cognitive/` or `tests/` (outside the harness tests) has changed since. Run it once more when no run is live, and at mission end. Harness tests: 167 pass on `0b5bef9`.
- After the mission: Joe freezes the guard in `tests/acceptance/guards/`; Claude repoints the gate and deletes the harness copy and the draft.
- Spec Patch 02 still needs its document and its frozen test before M4. `release.yml` must be retargeted or retired before any `v` tag. The seed (`agent/`, `cognitive/`), SALUS, Moneta, Hanish and `CLAUDE.cozy.md` are Joe's calls.
