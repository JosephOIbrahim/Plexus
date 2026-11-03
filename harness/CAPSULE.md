# Capsule — Plexus

**Where we are:** Mile 2.5 of ~4. Mission `acceptance`: phase1 at 9 failing of 11 (baseline 11); T0 and T1 pass. Run 13 starts from the commit that carries this capsule, on S3 (the Rust predicate), with Joe's "A + set" landed (Nov 3, after run 12). Run 13 is the last of S3's window: the Rust stop point is its end (plan §10).

**Next action:** run 13 is live (router `jev` over ready steps, which while S3 fails means S3 without a Jev call; worker timeout 3600 s; `context_chars` 120000, `num_ctx` 49152; started with `python -u` so `run13.log` fills as it goes). Watch each attempt; send any keep to the `reviewer`; merging a keep is Joe's call. If S3 is not kept by the end of run 13, stop and bring Joe the routes (plan §10). Two branches are ready for his word, neither landed: `prep/run14` (`f9dd868`: the full-signature `predicate.rs` skeleton in the brief, `cargo check`-clean, S3 without own tests, two known fixes from row 56) and `prep/option-b` (Option B: all-Python phase 1, `crates/**` frozen, the Rust facts in `docs/plexus/drafts/port_rust_brief.md`). Joe's four answers are open (build-speed report, Nov 3): the skeleton; tonight GPU night vs CPU night; the launcher (may Claude write it; `G:\COMFY\ComfyUI`); the pre-decided fallback.

**What run 13 carries** (all on `mission/acceptance`, Nov 3, each its own commit, reviewer passes noted):
- `a79f288` (from `385365f`; reviewer: keep): the prompt's same-every-attempt part first (header, rules, context files), per-attempt parts after it, `keep_alive` 15m, so Ollama's prefix cache can reuse the ~94% shared prefix. Compare run 13's `ollama.prompt_eval_s` with run 12's 709–857 s.
- `87bf7df` + `6a306d4` (from `3eb25d5` + `6bae7b8`; reviewer: keep with notes, applied): steps name `after`; a step is ready only when its prerequisites pass; Jev is asked only among two or more ready steps; every fallback goes to the earliest ready step. First Jev call comes after S5, between S6 and S7.
- `a2ba172` (reviewer pass in flight at start): a reply that leaves out any of its step's `files` is dropped before the gates with the names; what it sent is handed on; the next prompt says it left those files out and nothing it sent was built. A step's `files` now means every file each reply must send.
- The mission commit: `[router] kind = "jev"`, `min_confidence` 0.5; `after` on S2–S8 (S6 and S7 need S5: T5-outside and T3 assert `h.wakes == 1`); four brief lines with known fixes for run 12's rustc errors (E0106 lifetime on a two-`&str` parse function, with the one-input example gone; E0204 `Value` never `Copy`; E0308 `if let Ok` on a `Result`; E0277 no error type of the worker's own); `context_chars` 120000 / `num_ctx` 49152 (attempt 4's 100k prompt had cut `exchange.py` and the schema files); plan §10 record; the real-mission ready-steps test and five real-error known-fix cases.

**Run 13 so far:**
- Attempt 1 (35.1 min, row 56): all five files sent (the complete-reply rule held); dropped at `core` with 5 errors, none of them E0106, E0204 or E0277: three from one line (`*a as i32 < *b as i32`, parsed as generics; it would also have truncated the 0.15 steps) and two E0308 from `if let Some(Value::Num(n)) = value` on a `&Value`. Ollama: prompt 24,834 tokens in 717.7 s (attempt 1 pays the full prompt; the cache shows on attempt 2), reply 4,459 tokens in 1,363.6 s, load 19.6 s. Each draft still invents an error class the brief does not cover, which is the case for the skeleton.

**Watch in run 13:** (1) `prompt_eval_s` per attempt after the first: the cache either shows up as a drop from ~780 s to well under 100 s, or it does not (then the prefix is not byte-identical or the model was evicted between attempts). (2) Whether any reply is dropped as `reply left out step files`: expected for one-file replies like run 12's attempts 1 and 3. (3) The compile errors that remain once E0106 is gone. (4) Focus/frozen drops, now that the rules sit behind ~85k of files.

**Jev routing (Joe, Nov 3, "JEV for routing"):** landed as above. Parked: refuse to start when a step's targets match no collected test (a typo silently unlocks its dependants).

**Refinement campaign (Joe, Nov 3: "a 5x refinement pass for the Plexus additions from today"):** branch `refine/2026-11-03` in `scratchpad/wt-refine`, stacked on `3eb25d5`. Each pass: 4 scout lenses (robustness, simplification, truth, tests) -> adjudicator (cap 4, leverage >= 3 at risk <= 2) -> disjoint forge -> crucible (harness tests + guard, baseline 207 passed; ruff; check; status-line and jevcheck smokes). One commit per green pass; early stop on diminishing returns. Passes 1 and 2 green (`7e10070`, `b8f9052`); pass 3 in flight. Forbidden: plexus/**, crates/**, tests/acceptance/**, the guard, mission files, this capsule, CLAUDE.md, .claude/**, pyproject, .github. Lands on mission/acceptance only between runs, with Joe's go.

**S3 route brief (done ~13:45, 6 agents, challenge: sound with corrections; Jev-checked, no escalations):** recommended Option B for phase 1 (Python predicate and budget behind the same surface; `crates/**` frozen for phase 1; a named Rust port mission later, its frozen parity test Joe's to write). Joe chose "A + set" for run 13 instead, B staged. Corrections applied: B's 'green Nov 4-5' rests on S1/S2's record, which contradicts it (S2 took 38 attempts in Python), so B removes the Rust compile wall but S4 still sets the date; E0106 recurred three times (rows 46, 52, 53) on the brief's own one-input example. Verified by rebuilding attempt 4's prompt: the 100,000-char budget was binding once a file is handed on. Open from the brief: (2) cloud worker, recommended no, plus a local-only guard; (3) a Houdini-closed GPU night on the current worker.

**MoE swarm (done ~14:25, 12 agents; challenge: sound with corrections; Jev-checked, 2 escalations resolved):** saved as `scratchpad/moe_swarm_plan_2026-11-03.md` (+ `moe_swarm_roles_...` with every role's drafts). Findings: T7 runs against a fake ComfyUI inside the frozen test, so M1 needs no ComfyUI, GPU or install and can start the hour M0 ends; the CPU sits idle 9-11 h a night, so a bedtime-started run sized N = minutes-to-morning / 32 would add about 11 attempts a night (the hour cap counts from the run's own start); first user test nearer Nov 9-15 than 8-13 (challenge: S2 took 38 Python attempts). Joe's decisions: (1) night run sizing; (2) stage words before S4 (flag names `plexus:flag:publicationGate` / `plexus:flag:budgetGate`, state values, lastWake ISO 8601, mute release 'Restart the neuron runtime to unmute it', since session-layer unmute is spec'd but not built in phase 1); (3) M1 as drafted (organ layout, gates, and a raising-action frozen test Joe writes, with its CONTRACT line); (4) what the first user test is (one process; ComfyUI started as usual; whether Claude may write a driver script outside plexus/**); (5) release plumbing defaults (off the user-test path; challenge: hold for now). Corrections recorded: first light is a stop window; the organ's default deadline must suit the harness; phase1 as an M1 gate only if not flaky; two ComfyUI installs exist (G:\COMFY\ComfyUI, C:\ComfyUI).

**Build-speed review (Joe, Nov 3, "what would speed up and optimize this build"):** four analysts (edge weights, node odds, resources, DAG scheduler) over the ledger, the mission and the machine; report delivered in the session, ADHD-shaped. Its recommendations that need Joe: night-run sizing in `[budget]`, a Houdini-closed GPU night, Ollama service settings, the two launcher decisions.

**Waiting on Joe:** PR #2 then PR #3 (the logo, then the 87 KB 720 px JPEG; squash-merge #3). The fewer-approvals proposal. The worker seed and temperature proposal. The capsule reorder with the `/report` template and the mark kit (design review). `/dream apply`. The launcher: which ComfyUI (`G:\COMFY\ComfyUI` or `C:\ComfyUI`) and whether Claude may write it outside `plexus/`.

**Blockers:** none hard.

**Energy required:** none while run 13 runs; low after it (read the review, one merge decision if anything is kept, or the stop-point route choice).

---

**Run 12** (Nov 3, 11:44 to 14:07, from `e95a36f`, router `first`) kept 0 of 5, all S3. Mean 33.1 min. Ollama splits: prompt reads 709–857 s for 24–27k tokens, replies 742–1,626 s for 3–5.5k tokens, load 0.0 s.
- Attempt 1 (27.1 min): sent only `predicate.rs`; `lib.rs` lacked `mod predicate;`, so every gate passed vacuously; no gain.
- Attempt 2 (39.1 min): all five files; no duplicate `PredicateError`, no `crate::budget`. Dropped at `core` with 4 errors, all in `predicate.rs`: E0106 twice (`fn parse_clause(s: &str, scope: &str) -> Result<(Clause, &str), String>` needs a named lifetime once there are two `&str` inputs; the brief's one-input example elided it, the worker added `scope`), E0204 (`#[derive(Copy)]` on `Value`, which holds a `String`), E0308 (`if let Some(..)` on a `Result`).
- Attempt 3 (28.3 min): sent only `predicate.rs` again; the missing-files list named only `predicate.py` and `neuron.py`, never `lib.rs` or `py.rs`, because those exist as stubs at the run's base; every gate passed vacuously; no gain; handed on to attempt 4 as if it had worked.
- Attempt 4 (41.4 min): all five files; `core` failed with 4 errors: E0106 twice and E0277 twice (`compile` returned the worker's own `PredicateError` type, which pyo3 cannot convert).
- Attempt 5 (29.4 min): all five files; `core` failed with only 2 errors, both E0106. The crate was one lifetime fix from building.
- E0106 was in all three five-file replies (rows 52, 54, 55): the brief's one-input example was the cause. Pattern: full replies failed to compile; partial replies passed vacuously. Both are addressed in run 13 (the brief fix and the complete-reply drop).

**Run 11** (Nov 3, 08:21 to 11:06, from `0b5bef9`, router `first`) kept 0 of 5, all S3, every attempt sending all five files. Mean 32.6 min (worker 1,753 to 2,162 s; none timed out under the new 3600 s limit; attempt 1 would have under the old 1800 s).
- Attempts 1 to 3: dropped at `core` (cargo build), 6, 9 and 3 errors (rustc's own 'due to N previous errors' count; the clipped gate output showed only 3 of attempt 1's 6 and 6 of attempt 2's 9, a correction caught by the route brief's anatomy agent and checked against the ledger on Nov 3). E0255 (`PredicateError` defined twice in `py.rs`, from `use crate::predicate::{…, Error as PredicateError}`) in all three; also E0106 (missing lifetime), E0433 (`crate::budget` from the S7 `PyBudget` pieces), E0277 (`&f64` vs `f64`), E0599 (`.len()` on a `Clause`), E0308 (`f64` vs `Value`).
- Attempt 4: dropped at `layers`: `predicate.rs` wrote `use crate::py::Value;` (rank 2 naming rank 4). E0255 was still in `py.rs`, hidden behind the guard.
- Attempt 5: dropped at `core` with only 2 errors, both E0433 (`crate::budget`). The duplicate `PredicateError` was gone.
- `run11.log` stayed empty all run: `print` into a redirected file is block-buffered. Runs 12 and 13 use `python -u`.

**What run 12 ran on** (on `mission/acceptance`, all Nov 3):
- `cfa83ce` (cherry-pick of `159d582`; reviewer: keep): known fixes also match a failing gate's output, quoted under it. Drops for other reasons still match only target failures.
- `e45b979` (reviewer: keep; two tests added after review): each ledger row keeps `ollama` (prompt and reply token counts and seconds, load seconds), `failed_gate`, and `failing` (every failing junit id).
- `e95a36f`, the S3 mission commit: an S3-only `py.rs` block (S7's `PyBudget` pieces moved after it), five brief lines (E0255 `PredicateError`, E0277 `&f64`, E0599 parse functions return `(Clause, rest)`, E0308 `delta` holds an `f64`, plus the existing rank rule), five `[[known_fixes]]` entries matching rustc's and the guard's messages, five real-error test cases, and Joe's two decisions in plan §10.
- Docs (six commits, `67a3690` to `f54cfd9`, plus `25a74b2`, `ac7f85d`): UI design decisions 8-12 (the ordered line; the mark never shows state; Atkinson Hyperlegible Next + Mono at 13 px; holds stay rail states; accents `#8AA4FF` action, `#4FDCCB` presence), `docs/plexus/VOICE.md`, the README/DIAGRAMS front-door pass. The GitHub description is now the tagline.

**Ledger:** 55 attempts over 12 runs, 2 kept (`4e494b3` S1, `b18ebd0` S2), all on the CPU beside Houdini. 40 timed: 22.3 min mean; run 12's mean 33.1 min.

**Released:** `plexus-0.1.0-alpha.3` (pre-release, Nov 3), notes cover runs 5 to 10. Release plan page: https://claude.ai/artifact/ACC2nyghWEKizTD6wfcfVB (private; update it after run 13).

**Decided (Joe):**
- Nov 3 (after run 12): **"A + set"** for run 13: the prompt reorder, Jev routing with the corrected `after` graph, the four S3 brief fixes (E0106, E0204, E0308, E0277), the complete-reply check, `context_chars` 120000 / `num_ctx` 49152. Full record: plan §10.
- Nov 3: **1.0 = Blueprint Phases 0–3** green on frozen tests with every §11 gate for them measured against a written threshold; Phases 4–5 ship as 1.x. Open on that path: who writes the Phase 0-gap and Phase 3 frozen tests, B19 and D2, gate thresholds, the parity ruling, the release-plumbing bundle, and (before anything public) the licence and patent statement with counsel.
- Nov 3: **Rust stop point = end of run 13.** Routes then: split S3 (compile-first, then behaviour), full `cargo` output or an in-attempt compile retry, a stronger worker, or Option B (plan §4).
- Nov 3: UI design decisions 8-12 (above). The mark kit and the capsule reorder are still Joe's.
- Nov 3: router `first`, worker timeout 3600 s (`0b5bef9`). The harness change and the telemetry commit (Joe's go).
- Nov 2: `b18ebd0` merged (option 1). The `layers` guard stays at `harness/plexus_loop/guards/test_layers.py` for this mission; any guard change is its own commit, shown to Joe, never mid-run. Full record: plan §10.

**Desktop launcher (Joe, Nov 3; made 11:35, Joe ran the script):** `C:\Users\User\OneDrive\Desktop\Plexus.lnk`: Windows PowerShell titled "Plexus", started in `E:\Plexus`, runs `claude`; icon from the logo's disc in `%LOCALAPPDATA%\Plexus\plexus.ico`; its own AppUserModelID. Nothing in the repo. Joe pins it: right-click → Show more options → Pin to taskbar.

**Ideas parked:**
- Stop a run when an attempt repeats the previous attempt's first error; per-attempt seeds written to the ledger; Houdini-closed nights for GPU numbers (release-path review).
- `keep_alive: 0` on a GPU-to-CPU switch; repeat the focus and frozen paths in the per-attempt part if focus/frozen drops rise.
- Tighten S4's five-file `files` list when S4 becomes ready (every listed file must now be sent each attempt).
- Mission 02 brief: `plexus/organs/cozy.py` is a module, not a package.
- Organ mission goal (Joe, Nov 2): a launcher that starts Plexus and its ComfyUI worker together, with `G:\COMFYUI_Database` as the model root.
- A pyflakes undefined-name check on changed files; show `missing` and `handed_on` in REVIEW.md; restore a contract-fixed file instead of dropping the attempt.
- After the mission: Joe freezes the guard in `tests/acceptance/guards/`; Claude repoints the gate and deletes the harness copy and the draft.
- Spec Patch 02 needs its document and frozen test before M4. `release.yml` must be retired on every branch before any `v` tag (it publishes to PyPI). The seed (`agent/`, `cognitive/`), SALUS, Moneta, Hanish and `CLAUDE.cozy.md` are Joe's calls.
