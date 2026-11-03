# Capsule — Plexus

**Where we are:** Mile 2.5 of ~4. Mission `acceptance`: phase1 at 9 failing of 11 (baseline 11); T0 and T1 pass. Run 12 starts from the commit that carries this capsule, on S3 (the Rust predicate). Runs 12 and 13 are S3's window before the Rust stop point.

**Next action:** run 12 is live (router `first`, worker timeout 3600 s, started with `python -u` so `run12.log` fills as it goes). Watch each attempt; send any keep to the `reviewer`; merging a keep is Joe's call. If S3 is not kept by the end of run 13, stop and bring Joe the routes (plan §10).

**Waiting on Joe:** PR #2 then PR #3 (the logo, then the 87 KB 720 px JPEG; squash-merge #3). The fewer-approvals proposal. The worker seed and temperature proposal. The capsule reorder with the `/report` template and the mark kit (design review).

**Blockers:** none hard.

**Energy required:** none while run 12 runs; low after it (read the review, one merge decision if anything is kept).

---

**Run 11** (Nov 3, 08:21 to 11:06, from `0b5bef9`, router `first`) kept 0 of 5, all S3, every attempt sending all five files. Mean 32.6 min (worker 1,753 to 2,162 s; none timed out under the new 3600 s limit; attempt 1 would have under the old 1800 s).
- Attempts 1 to 3: dropped at `core` (cargo build), 6, 5 and 3 errors. E0255 (`PredicateError` defined twice in `py.rs`, from `use crate::predicate::{…, Error as PredicateError}`) in all three; also E0106 (missing lifetime), E0433 (`crate::budget` from the S7 `PyBudget` pieces), E0277 (`&f64` vs `f64`), E0599 (`.len()` on a `Clause`), E0308 (`f64` vs `Value`).
- Attempt 4: dropped at `layers`: `predicate.rs` wrote `use crate::py::Value;` (rank 2 naming rank 4). E0255 was still in `py.rs`, hidden behind the guard.
- Attempt 5: dropped at `core` with only 2 errors, both E0433 (`crate::budget`). The duplicate `PredicateError` was gone.
- `run11.log` stayed empty all run: `print` into a redirected file is block-buffered. Run 12 uses `python -u`.

**What run 12 runs on** (on `mission/acceptance`, all Nov 3):
- `cfa83ce` (cherry-pick of `159d582`; reviewer: keep): known fixes also match a failing gate's output, quoted under it. Drops for other reasons still match only target failures.
- `e45b979` (reviewer: keep; two tests added after review): each ledger row keeps `ollama` (prompt and reply token counts and seconds, load seconds), `failed_gate`, and `failing` (every failing junit id).
- The S3 mission commit: an S3-only `py.rs` block (S7's `PyBudget` pieces moved after it), five brief lines (E0255 `PredicateError`, E0277 `&f64`, E0599 parse functions return `(Clause, rest)`, E0308 `delta` holds an `f64`, plus the existing rank rule), five `[[known_fixes]]` entries matching rustc's and the guard's messages, five real-error test cases, and Joe's two decisions in plan §10. Replaying run 11's stored gate output quotes a fix for every error except E0106; the new `py.rs` block removes E0433's cause.
- Docs (six commits, `67a3690` to `f54cfd9`, plus `25a74b2`, `ac7f85d`): UI design decisions 8-12 (the ordered line; the mark never shows state; Atkinson Hyperlegible Next + Mono at 13 px; holds stay rail states; accents `#8AA4FF` action, `#4FDCCB` presence), `docs/plexus/VOICE.md`, the README/DIAGRAMS front-door pass. The GitHub description is now the tagline.

**Ledger:** 50 attempts over 11 runs, 2 kept (`4e494b3` S1, `b18ebd0` S2), all on the CPU beside Houdini. 35 timed: 20.8 min mean, 18.1 min without the seven over 29 min (run 10's two timeouts, all of run 11).

**Released:** `plexus-0.1.0-alpha.3` (pre-release, Nov 3), notes cover runs 5 to 10. Release plan page: https://claude.ai/artifact/ACC2nyghWEKizTD6wfcfVB (private; update it after run 12).

**Decided (Joe):**
- Nov 3: **1.0 = Blueprint Phases 0–3** green on frozen tests with every §11 gate for them measured against a written threshold; Phases 4–5 ship as 1.x. Open on that path: who writes the Phase 0-gap and Phase 3 frozen tests, B19 and D2, gate thresholds, the parity ruling, the release-plumbing bundle, and (before anything public) the licence and patent statement with counsel.
- Nov 3: **Rust stop point = end of run 13.** Routes then: split S3 (compile-first, then behaviour), full `cargo` output or an in-attempt compile retry, a stronger worker, or Option B (plan §4).
- Nov 3: UI design decisions 8-12 (above). The mark kit and the capsule reorder are still Joe's.
- Nov 3: router `first`, worker timeout 3600 s (`0b5bef9`). The harness change and the telemetry commit (Joe's go).
- Nov 2: `b18ebd0` merged (option 1). The `layers` guard stays at `harness/plexus_loop/guards/test_layers.py` for this mission; any guard change is its own commit, shown to Joe, never mid-run. Full record: plan §10.

**Desktop launcher (Joe, Nov 3, at this commit and push):** `C:\Users\User\OneDrive\Desktop\Plexus.lnk`: Windows PowerShell titled "Plexus", started in `E:\Plexus`, runs `claude`; icon from the logo's disc in `%LOCALAPPDATA%\Plexus\plexus.ico`; its own AppUserModelID. Nothing in the repo. Joe pins it: right-click → Show more options → Pin to taskbar.

**Ideas parked:**
- Stop a run when an attempt repeats the previous attempt's first error; per-attempt seeds written to the ledger; Houdini-closed nights for GPU numbers (release-path review).
- Put the static prompt first so Ollama's prompt cache can reuse it; measure with the new `ollama` fields first.
- Mission 02 brief: `plexus/organs/cozy.py` is a module, not a package.
- Organ mission goal (Joe, Nov 2): a launcher that starts Plexus and its ComfyUI worker together, with `G:\COMFYUI_Database` as the model root.
- A pyflakes undefined-name check on changed files; show `missing` and `handed_on` in REVIEW.md; restore a contract-fixed file instead of dropping the attempt.
- After the mission: Joe freezes the guard in `tests/acceptance/guards/`; Claude repoints the gate and deletes the harness copy and the draft.
- Spec Patch 02 needs its document and frozen test before M4. `release.yml` must be retired on every branch before any `v` tag (it publishes to PyPI). The seed (`agent/`, `cognitive/`), SALUS, Moneta, Hanish and `CLAUDE.cozy.md` are Joe's calls.
