# Advancing Plexus — research, November 2026

> **Status: research for Joe, not a plan.** Nothing here is decided until Joe decides it. Facts carry the date they were checked (2026-11-02); anything unchecked is marked unknown.

## The answer

In 2027 Plexus is the exoskeleton on one artist's workstation: two stock, commit-pinned ComfyUI workers (the known v0.34 commit as fallback and a v0.43.x worker in its own venv, launched offline with partner nodes off) do every GPU job they do today, and Plexus owns the layer the engine was never built to own. Every model, pack and result has a content identity; a job ledger in the organ never reports a success it did not see and turns a lost job into Unknown; a CacheProvider salted with pack and model digests makes yesterday's sampling survive a reboot; and the USD stage, written at Houdini 22's floor, holds shots that reference recipes, takes that are content-addressed results marked 'Already made' on a repeat, notes and agent memory as opinions in their own layers, and a plate receipt (colour interop id read from the EXR header, model digests, licence verdict, repro class, authorship record) that a supervisor signs in seconds and Solaris reads natively. It wins because the obvious competitors are elsewhere: Comfy Org owns chat-builds-the-graph (Comfy Agent, Cloud GA, local in preview), App Mode and an asset panel with no versioning; AYON and Prism ship workfile bookkeeping; Krita proved an artist-native surface over a hidden stock ComfyUI sustains users, and nobody has done it for local, provable, colour-correct VFX shot work on a composition substrate. Rust sits exactly where exactness demands it (canon.rs keys, predicates, budgets) and in the openusd shadow where parity is measured; local models answer Wake questions, Claude reasons only on escalation, and every outbound call is declared and metered. The method is the harness: Joe freezes a test, a local worker lands one diff, Claude plans and reviews, and the first thing an artist sees is Plexus finding the duplicate 4.5 GB model on day one.

**What to do first.** Jev's "now" column is foundation, not features: the Houdini 22 USD floor guard, content identity for models and packs, the engine lock, a second (newer) ComfyUI worker, the authorship gate, and harness economics and decision gates. The first thing an artist would see is the duplicate-model report (`eng.model-index`). Shot, take, receipt and colour work follows in Q1 2027, once phase 1 and the ComfyUI organ exist.

**Where Jev and the synthesis disagree.** Two places, both worth Joe's eye:

- **`usd.incremental` tops Jev's "now" list (2.20)** but depends on M4 (Spec Patch 02) and M5, which are mission milestones, not nodes in the graph, so the dependency rule could not push it later. Read it as "next" until M4 exists.
- **`cto.harness-economics` is first on the synthesis's critical path but last in Jev's "now" list (0.97).** Jev scores artist impact (0.8) and trust (1.1) low, which is true of telemetry. The synthesis puts it first because every later mission's cost depends on it. Both readings hold; it is small (effort S) and Claude's to scaffold.

## How this was made

1. **Seven research lenses**, each run by its own agent against primary sources and Joe's own machine: `comfyui-exoskeleton`, `usd-substrate`, `rust-in-usd`, `vfx-production`, `local-and-frontier-ai`, `artist-ux-pentagram`, `cto-practice`.
2. **A skeptic pass per lens.** A second agent tried to refute every finding against the sources. The counts are below; refuted claims were dropped or corrected before synthesis.
3. **A synthesis** (Fable advisor model) into first principles, a capability graph, a critical path, traps and decisions.
4. **Jev scoring** (TypeSafe, `jev-latest`) of each capability: when to build it (now / next / later / park), artist impact, supervisor trust and how landable it is for the harness worker (0–4 each), and whether it is a trap (probability). Code policy on top: nothing is scheduled before what it depends on, and priority = 0.4 × artist + 0.3 × trust + 0.3 × landable − 1.5 × p(trap).

| Lens | Findings | Confirmed | Downgraded | Refuted |
|---|---|---|---|---|
| `comfyui-exoskeleton` | 17 | 8 | 6 | 5 |
| `usd-substrate` | 18 | 11 | 7 | 0 |
| `rust-in-usd` | 18 | 10 | 8 | 2 |
| `vfx-production` | 20 | 8 | 10 | 5 |
| `local-and-frontier-ai` | 18 | 10 | 6 | 2 |
| `artist-ux-pentagram` | 19 | 10 | 7 | 3 |
| `cto-practice` | 18 | 9 | 8 | 6 |

## First principles

1. Exoskeleton, not replacement. A stock ComfyUI worker, pinned by commit (today v0.34.0-21-g3216c62e, an untagged master commit) plus an allowed pack set, runs every GPU job it runs today; 43 of 59 packs import comfy.* and 9 monkeypatch internals, so the engine is hosted, never reimplemented. Plexus wins only in the layer the engine was never built to own: content identity, a job ledger that never reports a success it did not see, a cross-restart cache, provenance, and the graph plus shots, takes and notes as versioned USD. Vendor seams are adopted, not competed with (CacheProvider, client prompt_id, workflow_metadata, blake3 assets, App Builder selections, Comfy Agent's chat).
2. The stage is the truth, written at Houdini 22's USD floor. Every fact Plexus holds (receipts, takes, notes, organ capabilities, licences, agent memory) is an opinion in a single-writer layer that composition arbitrates; nothing lives in a side database that can disagree with the stage, and in-flight job state is the one exception, kept in-flight-only. Plexus writes layers that usd-core 26.5 (Houdini 22.0.466) opens, and reads the newest OpenUSD (26.11: AuthorshipAPI, UsdProfiles, validators, speedups) only as a measurement lane until Houdini moves.
3. Identity by content. A filename is not a model, a pack name is not code, a job id is not a result. Cache keys stay sha256 through canon.rs with golden vectors (decided Nov 1, env excluded); file identity for models, packs and assets leans blake3 for interop with ComfyUI's shipped asset and governance digests. Hashing is I/O-bound (3.58 GiB/s on four streams; a full 257 GB pass is about 72 s once), so the algorithm is an interoperability choice, not a speed one, and never a reason for Rust.
4. Unmeasured is Unknown, never Verified. Every receipt row, screen mark, job state, capability claim and phase gate fails toward Unknown; Outcome carries Ok, Unavailable or Blocked and the UI draws Unknown as its own mark. No Rust module, no scheduler thread, no cache, no threshold is promoted on a guess: a measurement on Joe's machine (10 ms dirty closure, GPU attempt median, VRAM handoff, repro class) promotes it or it stays Python and stays parked.
5. Rust where exactness or a measured hot path demands it, and inside USD only where Rust composes natively. canon.rs keys, predicates and budgets are Rust because every process must agree bit for bit; graph.rs waits for the 10 ms miss; hashing stays in Python threads; a C++ USD plugin is a trap because Joe's two USD binaries (usd-core's usd_ms.dll and Houdini's per-library SideFX fork) cannot share one; Rust-in-USD means the openusd 0.8.0 shadow behind a parity test, promoted only when shared layers ship and parity holds on Joe's scenes.
6. Artist first, in artist nouns, with colour spent on the work. The artist's question is 'is this shot right yet?', not 'what is the runtime doing?'. Surfaces are pure readings of the stage in a closed word table (shot, plate, recipe, take, pick, note), the five decided marks, two accents, mono for anything compared by eye, and the familiar (Houdini shot context, Nuke GSV, Unreal takes, ComfyUI App Mode) carries the novel (provenance, parked agents, content identity). The first visible wins come early: the duplicate-model report, the one-line receipt, 'Already made'.
7. Local first, fail closed, legal as guardrail. Locality is a property of each stage, not of the client (ten :cloud tags sit behind Joe's localhost Ollama; partner nodes and hosted model stages leave the machine; --offline is only a browser CSP), so every provider, worker and node declares where it runs and a local-only project blocks the rest. Licence and territory are data on a model's digest, folded over every weight a graph loads at publication; Plexus quotes the clause and parks, Joe rules.
8. The harness is the method and the economics. Each capability lands as one frozen acceptance test Joe writes, one mission, one diff per attempt from a local worker, min_delta = 1, nothing merging itself. Fix the brief and the structure before buying attempts or a bigger model (every drop so far was a harness or brief defect, not a test the worker could not pass); measure CPU versus GPU minutes per kept test before scheduling the next mission; the artist's frame time in Houdini is the first SLO.

## Roadmap, as Jev scored it

Higher priority is better. Scores are 0–4; trap is a probability. "Moved" means code pushed it later than Jev's pick because something it depends on lands later.

### Now — the next one or two missions (Nov–Dec 2026)

| Priority | Capability | Artist | Trust | Landable | Trap | Effort | Jev's pick |
|---|---|---|---|---|---|---|---|
| 2.20 | **`usd.incremental`** Incremental evaluation: Python edge index, empty change-fields mean dirty, Rust only on a measured miss | 2.6 | 2.0 | 3.2 | 0.27 | M | now (0.59) |
| 2.01 | **`usd.floor-guard`** USD floor guard: write at Houdini 22's USD, measure the newest | 1.9 | 2.1 | 3.3 | 0.26 | S | now (0.48) |
| 1.99 | **`eng.second-worker`** Second worker: ComfyUI v0.43.x in its own venv beside the fallback | 2.4 | 1.9 | 2.9 | 0.28 | M | now (0.59) |
| 1.93 | **`eng.model-index`** Model index: hash every model once, verify at dispatch, show the duplicates | 2.0 | 2.1 | 3.4 | 0.33 | M | now (0.60) |
| 1.67 | **`eng.pack-ledger`** Pack ledger and worker fingerprint: a content digest for every pack | 1.8 | 2.3 | 3.0 | 0.42 | M | now (0.48) |
| 1.61 | **`eng.lock`** Engine lock v0: the worker pinned as plain data, 'stock' defined | 1.3 | 2.1 | 3.4 | 0.38 | S | now (0.43) |
| 1.56 | **`usd.authorship-gate`** Authorship records and the publication gate as standard USD | 1.6 | 2.1 | 2.8 | 0.37 | S | now (0.48) |
| 1.48 | **`cto.decision-gates`** Decision ledger, risk register and numeric phase gates | 1.4 | 1.9 | 3.1 | 0.38 | S | now (0.93) |
| 1.29 | **`usd.shadow-parity`** The openusd shadow: Rust composing the same stacks, parity measured on Joe's scenes | 1.2 | 1.7 | 2.6 | 0.32 | L | now (0.29) |
| 1.28 | **`cto.repo-decouple`** Decouple the repo: conftest split, Plexus venv from a hashed lock, Plexus CI and release | 1.1 | 1.8 | 3.0 | 0.40 | M | now (0.68) |
| 0.97 | **`cto.harness-economics`** Harness economics: telemetry, knobs, prompt layout, worker bench | 0.8 | 1.1 | 3.4 | 0.46 | S | now (0.92) |

### Next — Q1 2027, once phase 1 and the ComfyUI organ exist

| Priority | Capability | Artist | Trust | Landable | Trap | Effort | Jev's pick |
|---|---|---|---|---|---|---|---|
| 2.45 | **`vfx.proof-of-change`** Proof of change: composite back, prove the matte, measure the repro class | 2.6 | 3.2 | 2.8 | 0.29 | M | next (0.64) |
| 2.38 | **`ux.shot-layer`** Shots reference a recipe and override locally: one recipe, many shots | 3.0 | 2.7 | 2.7 | 0.30 | M | next (0.53) |
| 2.35 | **`vfx.plate-receipt`** Plate receipt: the asset record a supervisor can sign, read from the file | 2.4 | 3.1 | 2.9 | 0.25 | M | next (0.69) |
| 2.32 | **`vfx.colour-ports`** Colour and compositing passes as typed ports, converted only at the edge | 2.9 | 2.9 | 2.4 | 0.27 | L | next (0.68) |
| 2.31 | **`ux.takes-notes`** Takes and notes as opinions: content-addressed results with 'Already made', review memory agents can wake on | 2.9 | 2.8 | 2.8 | 0.34 | M | next (0.41) |
| 2.12 | **`ux.state-model`** One state model: view-models as pure functions, the artist word table, and MCP tasks reading it | 2.7 | 2.1 | 3.0 | 0.33 | S | next (0.65) |
| 2.09 | **`vfx.dcc-handoff`** DCC and review handoff: Solaris reads Plexus, OTIO to RV, credentials on review media | 2.9 | 2.8 | 2.2 | 0.38 | L | next (0.63) |
| 2.04 | **`org.correlation`** Organ correlation: Plexus mints the job id and hashes the graph /history returns | 2.0 | 2.6 | 3.0 | 0.30 | M | next (0.59) |
| 1.99 | **`ux.viewer`** A minimal viewer for choosing takes, through the show's transform, with heavy review handed to RV | 2.0 | 2.3 | 3.1 | 0.28 | M | next (0.48) |
| 1.96 | **`ai.prompt-expand-op`** Prompt expansion as a pinned, content-addressed op | 2.4 | 2.4 | 2.9 | 0.38 | M | next (0.71) |
| 1.87 | **`ux.recipe-face`** The recipe face from native UsdUI hints, with the ComfyUI canvas as the graph-surgery tool | 2.7 | 1.6 | 2.8 | 0.33 | M | next (0.69) |
| 1.72 | **`org.job-ledger`** Job ledger in the organ: in-flight intent only, never a success it did not see | 2.0 | 1.8 | 3.2 | 0.40 | M | next (0.63) |
| 1.72 | **`ux.shot-view`** The shot view: Plexus's home surface is a shot, not a graph (model first, pixels last) | 3.1 | 1.4 | 2.0 | 0.36 | L | next (0.67) |
| 1.71 | **`usd.memory`** Memory as composition, with exact recall beside it | 2.5 | 1.8 | 2.7 | 0.42 | M | next (0.40) |
| 1.71 | **`ai.locality-posture`** Local means local: fail-closed locality and worker posture, from the harness today to projects later | 1.9 | 1.7 | 2.9 | 0.30 | M | next (0.35) |
| 1.66 | **`ai.providers-tiers`** Provider contract and the Reflex, Wake, Reason ladder, behind Outcome and budgets | 2.1 | 1.6 | 2.9 | 0.34 | M | next (0.45) |
| 1.63 | **`org.cache-provider`** Cache provider: ComfyUI's own cache survives restarts, keyed by what the bytes are | 2.2 | 1.6 | 3.1 | 0.43 | L | next (0.59) |
| 1.52 | **`org.capacity`** Capacity: static capabilities, a live snapshot, set-inclusion routing and one GPU lease | 2.5 | 1.7 | 2.4 | 0.47 | L | next (0.41) |

### Later — Q2–Q3 2027

| Priority | Capability | Artist | Trust | Landable | Trap | Effort | Jev's pick |
|---|---|---|---|---|---|---|---|
| 1.77 | **`vfx.licence-gate`** Licence and territory as data on each model digest, folded over the graph at publication | 2.4 | 1.8 | 2.7 | 0.36 | M | later (0.32) |

## Critical path (synthesis order)

The synthesis orders the work by dependency, not by score:

`cto.harness-economics` → `cto.decision-gates` → `ai.locality-posture` → `cto.repo-decouple` → `usd.floor-guard` → `eng.lock` → `org.correlation` → `eng.model-index` → `org.job-ledger` → `eng.pack-ledger` → `usd.incremental` → `usd.authorship-gate` → `vfx.plate-receipt` → `ux.state-model` → `ux.recipe-face` → `ux.shot-layer` → `ux.takes-notes` → `vfx.licence-gate` → `eng.second-worker` → `org.cache-provider` → `vfx.colour-ports` → `org.capacity` → `ai.providers-tiers` → `usd.memory` → `ux.viewer` → `vfx.proof-of-change` → `ux.shot-view` → `ai.prompt-expand-op` → `vfx.dcc-handoff` → `usd.shadow-parity`

## Capabilities in detail

### `usd.incremental` — Incremental evaluation: Python edge index, empty change-fields mean dirty, Rust only on a measured miss

**Horizon:** now · **Priority:** 2.20 · **Effort:** M · **Lands in:** python-host

**Depends on:** `M4 UsdShade encoding (Spec Patch 02)`, `M5 incremental`, `phase1 T0-T6 (frozen)`, `plexus._core (M2b Outcome)`

**What it is.** Worker mission at M5. A Python edge index with forward and reverse maps built at open (238 ms at 10k nodes, pxr-bound, stays Python in any design) and a dirty closure per notice. Correctness fix carried from the usd lens: an empty GetChangedFields tuple, which is what 26.5 emits for a time-sample edit, classifies as unknown inside the existing fields mapping and dirties the node plus everything downstream (no new StageEvent field); 26.08+'s 'timeSamples' maps the same way. Dirty is not run: keys are recomputed and only misses run, so over-dirtying costs one key recompute that hits the cache. graph.rs (CSR forward/reverse, dirty_closure in topological order, cycle as Blocked with the node paths) lands only if the per-notice p95 misses 10 ms on the frozen 10k-node/15k-edge fixture; the worker must not land it speculatively. The same checker rejects imported neutral-IR cycles.

**What the artist gets.** Touch a knob on a huge graph and only what it feeds lights up within a frame, and an animated parameter actually re-runs instead of serving a stale frame.

**Risk.** Python measured 13 ms at 10k nodes, close to the budget, so the promotion is a real possibility and the measurement decides it.

**First frozen test.** On a 3-node chain, inputs:strength.Set(0.5, time=10) on A marks A, B and C dirty within one dispatcher tick.

**Evidence.**
- t1_compose.py on usd-core 26.5: timeSample set reports fields []; CHANGELOG v26.11.1 line 896 (26.08 reports timeSamples); scaffold plan §3.4 scale table.

### `usd.floor-guard` — USD floor guard: write at Houdini 22's USD, measure the newest

**Horizon:** now · **Priority:** 2.01 · **Effort:** S · **Lands in:** harness

**Depends on:** `harness`, `phase1 T0-T6 (frozen)`

**What it is.** Claude drafts outside tests/acceptance/, Joe freezes. Layer gate: every layer Plexus writes opens under usd-core 26.5 with its crate or usda version no higher than 26.5 writes for the same content (26.5 itself writes usdc 0.10.0 once a path-expression collection is authored, so a fixed 0.8.x rule would reject the memory layer); every asset-valued attribute resolves with no leftover '${' or backtick (an unevaluated expression comes back unchanged and raises no composition error); no UTF-8 BOM (26.11 errors on it); no `${VAR:fallback}` form, spline loopBoundaryTime, GfTimeCode values or prim relocates. Code rule in the symbols or layers gate: no HasAPI or GetAppliedSchemas on AuthorshipAPI or ClaimsAPI under plexus/, because 26.5 drops unregistered schemas and reads them back only by attribute name. A 26.11 lane in a temp venv (Joe approval; pyproject needs >=3.11) re-opens the same fixtures and records differences as a measurement, not a gate.

**What the artist gets.** Anything Plexus writes opens in your Houdini 22 today and keeps opening when Houdini upgrades; you never get a broken stage from your own tool.

**Risk.** When Houdini moves past 0.26.5 the floor moves by a deliberate decision, not drift. The 26.11 wheel lacks pxr.UsdShaders and adds UsdLod and UsdProfiles, so the pinned symbol-table gate differs per lane.

**First frozen test.** For each .usda/.usdc a phase's fixtures write: Stage.Open under 26.5 succeeds, the format version is no higher than 26.5 writes for that content, and Get() on every asset-valued attribute returns a path containing no '${'.

**Evidence.**
- Skeptic probes 2026-11-02 (usdc 0.10.0 on membershipExpression; `${MISSING:D:/fb}` gives 0 composition errors); OpenUSD CHANGELOG v26.11.1 lines 237, 244, 253, 861 (fetched 2026-11-02).

### `eng.second-worker` — Second worker: ComfyUI v0.43.x in its own venv beside the fallback

**Horizon:** now · **Priority:** 1.99 · **Effort:** M · **Lands in:** process

**Depends on:** `eng.lock`, `cto.repo-decouple`, `Joe: engine pin and install outside the repo venv`

**What it is.** Joe decision and install; the organ side is a worker mission. A ComfyUI v0.43.x worker (latest 2026-10-27) in its own venv beside the current system-Python install, never upgraded in place; launched with --disable-partner-nodes and --offline plus HF_HUB_OFFLINE=1 and a per-process firewall rule (--offline is only a frontend CSP), Manager off, --enable-assets for blake3 asset ids. The old worker stays as the fallback, and the lock records which of the 59 packs load cleanly on each (none import the moved comfy_api_env, so #17307 does not block). This unlocks workflow_metadata (v0.40), half-float EXR (v0.39), ACEScg EXR and the colour-convert node (v0.43), Marigold v2 and MoGe 3, comfy-aimdo 0.6.0, and the home for the cache-provider pack.

**What the artist gets.** An upgrade is a second worker you can try on one shot, not a gamble on the one you have.

**Risk.** 9 packs monkeypatch internals and may break on v0.43; the fallback stays. The Comfy Compiler (comfy-aimdo allocation, v0.35+) changes VRAM behaviour, so the capacity measurement must include it. Pace is about one minor a week; pin v0.43.0 or wait is Joe's.

**First frozen test.** eng.lock reads both workers: the new lock carries a v0.43.x commit and argv containing --disable-partner-nodes; T7 passes against each worker in turn.

**Evidence.**
- Releases v0.39.0 (#16672 --offline, frontend CSP per cli_args help text), v0.40.0 (#16763 workflow_metadata), v0.43.0 (#17023 ACEScg; #17307 move) fetched 2026-11-02; grep of 59 packs for comfy_api_env: none.

### `eng.model-index` — Model index: hash every model once, verify at dispatch, show the duplicates

**Horizon:** now · **Priority:** 1.93 · **Effort:** M · **Lands in:** comfyui-organ

**Depends on:** `eng.lock`, `organ contract (plexus.organs.protocol, CONTRACT.md §8.1)`, `M3 canon.rs`, `M6 results`, `Joe: file-identity hash (blake3 for files)`

**What it is.** Worker mission at M1 (index, dedupe, rename-without-rehash); the `${PLEXUS_STORE}/<algo>/<2>/<hash>.<ext>` expression path lands at M6 and resolves through stock ArDefaultResolver (verified on 26.5, including across a reference arc with the outer stage's variable winning). Hash with hashlib on about 4 threads per NVMe (measured 1.37 GiB/s one stream, 3.58 GiB/s four, with Houdini open; a full 257.6 GiB pass is about 72 s), cached by (path, size, mtime, NTFS file id) with symlinks resolved (text_encoders/gemma_ltx23/model is one), in scope: folder_paths models, the 16 GB HF cache, pack-local weights such as models/sams. Integrity at dispatch: the organ re-verifies the digest (cheap on the cache) and returns Unavailable(hash_mismatch) before any GPU time. The first artist-visible output is the duplicate report on the inspector: clip/t5xxl and text_encoders/t5xxl are byte-identical 4.56 GiB files. Python only; blake3's Python package is already the Rust crate, and sha256 is kept only where M3 keys need it.

**What the artist gets.** Plexus shows the duplicate 4.5 GB file on day one, every render names the model bytes it used, and a LoRA swapped under the same filename is caught before it renders.

**Risk.** The first pass is minutes with Houdini open and must never block a run. Hardlinks only within one NTFS volume. ComfyUI's own blake3 asset seeding would hash the tree a second time, so the organ keeps a blake3-to-sha256 bridge rather than two passes.

**First frozen test.** Two byte-identical fixture files under a temp Models/ produce one digest with two source paths; renaming one source does not re-hash; one changed byte does; dispatch against a file whose bytes changed under the same path returns Unavailable with reason_code hash_mismatch.

**Evidence.**
- Measured 2026-11-02 on G:\COMFYUI_Database\Models (hashbench and skeptic re-run); cas_test.py on usd-core 26.5; app/assets/helpers.py:50 keys assets by blake3.

### `eng.pack-ledger` — Pack ledger and worker fingerprint: a content digest for every pack

**Horizon:** now · **Priority:** 1.67 · **Effort:** M · **Lands in:** comfyui-organ

**Depends on:** `eng.lock`, `M3 canon.rs`, `Joe: file-identity hash (blake3 for files)`

**What it is.** Worker mission after M3. One record per pack in the worker's custom_nodes, resolving the custom_nodes symlink and per-pack symlinks to their repo and commit: registry version (.tracking plus pyproject version; 12 of the 21 non-git packs have one), git commit or null, a blake3 content digest over the governance file set (.py .pyw .pyd .so .dll .dylib .js .mjs, ignoring __pycache__ and .pyc), requirements.txt hash, symlink flag. Five packs have no recoverable version and are identity-by-digest only. Composed with lock-v0 and the model index through canon.rs into the worker fingerprint published on /Plexus/Organs/<id>; envFingerprint stays out of the cache key (decision 4) and is the drift signal. The inventory also emits a node-id deny list for --disabled-nodes-config and flags what governed mode would refuse (symlinks, __pycache__ in all 59).

**What the artist gets.** A pack that changed underneath you shows up before it ruins a shot, even for packs that never had git, and a render from last month names the node code that made it.

**Risk.** ComfyUI's packdigest combination rule is not public, so comparability with governance policies is unknown; record the algorithm id. Cached by mtime, verified on demand.

**First frozen test.** Fixture custom_nodes under plexus/organs/cozy with one git pack, one registry pack and one symlinked pack: inventory() returns 3 records; the registry pack's digest changes on one .py byte and not on an added __pycache__/x.pyc; the symlinked record carries its resolved target and commit.

**Evidence.**
- Directory scan 2026-11-02: 21/59 without .git, 12 registry installs, 4 symlinks resolving to G:\Comfy-Cozy (ee34d9e) and G:\dyno; PR #16167 governance digest is blake3 (fetched 2026-11-02).

### `eng.lock` — Engine lock v0: the worker pinned as plain data, 'stock' defined

**Horizon:** now · **Priority:** 1.61 · **Effort:** S · **Lands in:** comfyui-organ

**Depends on:** `phase2 T7-T8 (frozen)`, `organ contract (plexus.organs.protocol, CONTRACT.md §8.1)`

**What it is.** Worker mission at M1, inside plexus/organs/cozy so T8 holds. lock-v0 is a leaf: ComfyUI commit (never a tag; Joe is on v0.34.0-21-g3216c62e with untracked audit files in the tree), frontend package version, Python/torch/CUDA, argv, the two site-packages roots, and an /object_info snapshot keyed by all of the above, read from /system_stats and /features. 'Stock' is defined as a commit plus an allowed pack set; today's custom_nodes symlink loads three Comfy-Cozy packs and a bug12047 hotfix, which the definition names. Drift from a recorded lock reports Unknown, never Verified. lock-v1 later embeds the fingerprint from eng.pack-ledger; the edge runs that way only, so there is no cycle.

**What the artist gets.** A shot that rendered last month names the exact engine it rendered on, and you can see what changed since.

**Risk.** /system_stats and /object_info shapes changed across the ten releases since v0.34.0; the snapshot is keyed by commit so a reader never mixes them.

**First frozen test.** Against T7's fake server: reading /system_stats twice yields byte-identical canonical lock bytes; changing one argv flag yields a drift report whose status is Unknown.

**Evidence.**
- git describe in G:\COMFY\ComfyUI (2026-11-02); ten releases v0.35.0 to v0.43.0 (github.com/Comfy-Org/ComfyUI/releases, fetched 2026-11-02).

### `usd.authorship-gate` — Authorship records and the publication gate as standard USD

**Horizon:** now · **Priority:** 1.56 · **Effort:** S · **Lands in:** python-host

**Depends on:** `M3 canon.rs`, `M6 results`, `M4 UsdShade encoding (Spec Patch 02)`, `usd.floor-guard`

**What it is.** Worker mission in two steps. (1) authorship.build_record() is a pure function with golden vectors, depending only on M3: the UsdMediaAuthorshipAPI (26.11) record authored by name on 26.5 (apiSchemas token `AuthorshipAPI:<runId>` plus uniform `authorship:<runId>:*` attributes, read back by attribute name), with softwarePackage = the model id (the host ComfyUI and its commit go in inputs[] as 'host'), instanceID = the output id or its digest (not the recipe), digitalSourceType declared per Sdr op def (compositeWithTrainedAlgorithmicMedia for inpaint on plates, algorithmicallyEnhanced for corrections, trainedAlgorithmicMedia only for pure generation), inputs[] mirroring the cache-key inputs under a per-project redaction policy, usageTerms unauthored unless Joe sets it. (2) At M6 the record attaches to result prims and memory episodes, and the publication gate runs as Python-registered UsdValidation validators under keyword plexus (MissingCacheKey; the key recomputes from the composed stage; the record exists with even inputs[]; memory writes stay in the writer's layer), run at the Sdf level over results layers or on a LoadAll stage because editing stages open LoadNone and never compose payloaded results, registered once in the rank-2 plugin module. This is interchange and AI disclosure, not proof: proof stays the recomputed cache key plus digests.

**What the artist gets.** Any frame you hand a client says which model, prompt and seed made it and that it is AI-made, readable in Houdini today and by usdauthors and 26.11+ tools tomorrow.

**Risk.** AuthorshipAPI is 'unverified' and 'not a cryptographic signature' by its own schema doc; whether Solaris keeps unregistered multi-apply records through LOP edits needs a Houdini session; validators are visible only inside the Plexus process.

**First frozen test.** build_record() for a fixture result returns the golden attribute set; `authorship:<runId>:inputs` has even length with names equal to the canonical cache-key input names; the op's declared digitalSourceType is carried through unchanged.

**Evidence.**
- t4_author_265.py / t5_read_2611.py (written on 26.5, read natively on 26.11, 2026-11-02); usdMedia/schema.usda at v26.11.1; t2_valid.py Python validator on 26.5; IPTC digitalsourcetype vocabulary (fetched 2026-11-02).

### `cto.decision-gates` — Decision ledger, risk register and numeric phase gates

**Horizon:** now · **Priority:** 1.48 · **Effort:** S · **Lands in:** process

**Depends on:** `harness`, `cto.harness-economics`, `layers guard`

**What it is.** Claude drafts, Joe owns. docs/plexus/DECISIONS.md in Nygard form, one row per decision (scaffold plan §7, acceptance.plan §9, v5.4 draft, UI_DESIGN) with an 'enforced by' test path or 'unenforced', and a 'last verified' date on every external fact, because the repo's own docs are already stale (Blueprint §13.2 says openusd transactions are unreleased; they shipped in 0.8.0; NEXTGEN §3.4 says property_stack is main-only; hydra-rs is 0.0.11). A risk register grown from Appendix D with owner and closing evidence: pyo3/3.14 closes on the verifier's import test, not on the core gate (which is a cargo build, not maturin). Numeric gates: M0 exits at 11/11 with layers, core and cargo green; no mission after M0 is scheduled until at least 3 GPU attempts in Houdini-closed windows give a median against the CPU median (today unknown); M1 exits on T7/T8 against the pinned commit plus one real workflow round-tripping with a receipt; unmeasured reads unknown and blocks green. Joe moves the layers guard into tests/acceptance/guards/. A hand-written mutation fixture for compile()'s scope check stands in for cargo-mutants until S3 lands and Joe approves the install.

**What the artist gets.** Every 'why does it work like this?' has one page naming the test that holds it; nothing you decided drifts while you're in Houdini.

**Risk.** Paperwork unless the row changes in the same commit as the decision. The GPU gate needs Joe's habit, not the harness: Houdini closed overnight.

**First frozen test.** Repo test: every DECISIONS.md row naming a path exists and collects at least one test; tests/acceptance/guards/test_layers.py exists.

**Evidence.**
- docs.rs openusd 0.8.0 StageEdit and Attribute::property_stack pages (fetched 2026-11-02); harness/plexus_loop/build_core.py:35-54 runs cargo build, not maturin; scratch import of plexus_core.dll as _core.pyd succeeded on 3.14.2.

### `usd.shadow-parity` — The openusd shadow: Rust composing the same stacks, parity measured on Joe's scenes

**Horizon:** now · **Priority:** 1.29 · **Effort:** L · **Lands in:** rust-usd

**Depends on:** `M9 plexus-usd`, `plexus._core (M2b Outcome)`, `eng.model-index`, `usd.floor-guard`

**What it is.** Worker mission at M9. crates/plexus-usd (lib plus the plexus-shadow binary) on openusd pinned =0.8.0 (shipped 2026-10-11; authoring transactions did ship there via Stage::edit and batch_edit; shared layers did not; a minor release about monthly), JSON lines over stdio, one owning thread because Stage is !Send. It resolves `${PLEXUS_STORE}` with openusd's DefaultResolver plus Stage::set_expression_variables, exactly as pxr does, with no custom Resolver (StageBuilder::resolver exists; a Resolver impl is reserved for something pxr cannot do, and models are asset-valued attributes USD never opens). Parity fixtures cover root, session-override and reference-arc expression variables, composition errors, resolved values and property_stack (shipped in 0.8.0, so T4-style provenance parity is possible now). The first unknown to measure is whether openusd loads Plexus's codeless plugInfo.json the way pxr does; applied-schema parity depends on it. Runtime code never reads the shadow (Blueprint §13.4); promotion needs shared layers in a release, zero-difference parity over Joe's corpus for a run length Joe sets, and Joe's reading of whether 0.8.0's transaction scope (no API-schema apply, no queued arcs yet) suffices. No build.rs under crates/, so any openusd-build codegen is pre-generated and diff-tested.

**What the artist gets.** Later, a composer that can't crash the session and can be fixed in-house; for now, a second opinion that catches composition errors before you see them.

**Risk.** Pre-1.0 API churn; compile time beside Houdini on the CPU worker; a prebuilt gate binary before M9 has no build owner. Preview and unknown: shared layers, custom file-format registration.

**First frozen test.** For one frozen fixture set, plexus-shadow and usd-core 26.5 report the same composition-error count and the same resolved value for every authored attribute, including a `${PLEXUS_STORE}` asset path set on the root layer and overridden on the session layer.

**Evidence.**
- crates.io openusd versions; docs.rs 0.8.0 StageBuilder::resolver, Stage::set_expression_variables, StageEdit, Attribute::property_stack; ROADMAP.md (all fetched 2026-11-02).

### `cto.repo-decouple` — Decouple the repo: conftest split, Plexus venv from a hashed lock, Plexus CI and release

**Horizon:** now · **Priority:** 1.28 · **Effort:** M · **Lands in:** process

**Depends on:** `harness`, `phase1 T0-T6 (frozen)`, `Joe: seed fate and unit-gate composition`

**What it is.** Claude scaffolding shown to Joe, in three commits. (1) Move Comfy-Cozy's autouse fixtures out of tests/conftest.py into a conftest scoped to the seed's tests, so the frozen judge no longer imports agent/cognitive; this is the highest-leverage missed node and is upstream of everything below. (2) A Plexus venv inside the repo from a uv hashed lock: usd-core 26.5, maturin, pytest + pytest-asyncio, OpenEXR>=3.5.3, opencolorio>=2.5.1; no torch, no comfy, no editable comfy-cozy or comfy-moneta-bridge. (3) Retarget ci.yml, release.yml and packaging-gate.yml to Plexus: Python 3.14, cargo test, a core build and import, every `uses:` pinned to a 40-char SHA, release on plexus-v* only, CI on plexus-loop/* and mission/* pushes, pip-audit and cargo-deny blocking. The stock ComfyUI worker venv on G:\ is an install outside the repo and is Joe's (see eng.second-worker).

**What the artist gets.** A sketchy custom node can't break Plexus, your USD stack or the Houdini exchange, and a version tag ships Plexus instead of the old product.

**Risk.** The `unit` gate composition and the seed's fate are Joe's calls. usd-core 26.5 on Python 3.14 on a clean Windows runner is unmeasured. Local tool installs (cargo-deny, newer uv) are outside the workspace and need Joe.

**First frozen test.** In the Plexus venv: `pytest tests/acceptance/phase1 --collect-only` succeeds; sys.prefix is under the repo; find_spec returns None for agent, cognitive, comfy and torch; pxr.Usd.GetVersion() == (0, 26, 5).

**Evidence.**
- tests/conftest.py autouse fixtures apply to test_t0_schema_gate.py (pytest --fixtures-per-test, 2026-11-02); 560 packages in one global interpreter incl. comfy-cozy 5.10.0 editable; release.yml fires on v*; CVE-2025-30066 (CISA alert 2025-03-18).

### `cto.harness-economics` — Harness economics: telemetry, knobs, prompt layout, worker bench

**Horizon:** now · **Priority:** 0.97 · **Effort:** S · **Lands in:** harness

**Depends on:** `harness`

**What it is.** Claude scaffolding, in its own commit before the next run. Each attempts.jsonl row gains wall_s, worker_s, per-gate {seconds, ok}, Ollama's prompt_eval_count/duration, eval_count/duration and load_duration, the model digest from `ollama show`, the base commit and judge_tree; options.seed is fixed so a dropped attempt replays. The mission knob max_consecutive_failures drops from 8 (inert under attempts = 5) to 2; package __init__.py files are scaffolded empty. The prompt puts static context first so Ollama's prefix cache can hit the 25-30k static tokens, measured by prompt_eval_count. A `bench` verb replays recorded prompts against qwen3-coder:30b, qwen3.8:27b, hrt-coder and gpt-oss:20b (gemma4 is the 8B E4B, a small-model baseline only), refusing any non-local model; Jev routing (jev-1.14.0 pinned, response model field logged) is A/B'd against the existing `first` router, since 9-of-9 agreement with earliest-failing-step is by construction. REVIEW.md gets a cost table: median minutes per attempt by device, CPU-minutes per kept test, drop share by cause.

**What the artist gets.** Plexus gets built faster on your own machine, and the table that justified any worker or routing change is in the repo, not in memory.

**Risk.** Old rows lack the new keys and must read as unknown, never zero. The bench competes with real missions for the CPU beside Houdini (about 3.7 h a pass).

**First frozen test.** Harness test: one fake-worker attempt writes a row with wall_s, worker_s, gates{seconds, ok}, prompt_tokens, eval_tokens, model_digest and judge_tree equal to `git rev-parse <base>:tests/acceptance`, with wall_s >= worker_s + sum(gate seconds).

**Evidence.**
- Ledger: 10 rows, 1 kept (4e494b3); rows that died at git apply ran zero gates yet took 8.7-12.4 min, so worker time dominates. Ollama /api/generate fields and prompt_eval_duration = uncached tokens (docs.ollama.com/api, fetched 2026-11-02). router.py:93-98 instructs 'choose the earliest step'.

### `vfx.proof-of-change` — Proof of change: composite back, prove the matte, measure the repro class

**Horizon:** next · **Priority:** 2.45 · **Effort:** M · **Lands in:** python-host

**Depends on:** `vfx.plate-receipt`, `M6 results`, `plexus._core (M2b Outcome)`, `M3 canon.rs`

**What it is.** Worker mission after the plate receipt. For a generative edit of a plate, Plexus composites back on the host (plate outside the matte, generated pixels inside), because ComfyUI's full-frame VAE decode changes every pixel and returns display-referred data; the proof then checks header survival (displayWindow, pixelAspectRatio, timeCode, chromaticities), the outside-matte delta against a per-show tolerance (lossy DWAA/LJ2K changes untouched pixels), and the inside region's colour conversion, in Python on OpenEXR 3.5.3 and numpy over bytes (no exr crate: it lacks DWA, deep and HTJ2K). Mattes address Karma Cryptomatte objects by prim path with the manifest hash. envFingerprint is canonicalised through M3 (GPU, driver, CUDA, torch, commit, pack digests, --deterministic, attention backend) and plexus:reproClass (bit-exact, same-env-only, nondeterministic, unknown) is set by a sampled byte-for-byte re-run budgeted like any organ job; a result reused from another fingerprint shows made-elsewhere (decision 4), and a delivery-tagged project may require a same-env re-run (Joe's policy). First measurement: with --deterministic, which of Joe's top five workflows re-run bit-exact, including the installed DeterministicNodes pack's 'ALWAYS identical' claim.

**What the artist gets.** The supervisor sees 'outside matte: 0 pixels changed, header intact', and before a client note you know whether frame 1042 will come back identical or the range needs re-rendering.

**Risk.** Video models re-render the whole frame, so this suits stills and inpaint; re-runs cost GPU time; a Rust promotion would add a dependency to plexus-core (Blueprint §13) and is not planned.

**First frozen test.** Source plate and result identical except one pixel inside the declared matte: Verified with outside_max_delta == 0.0; one pixel changed outside: Broken naming x,y; a differing displayWindow or timeCode: Broken naming the attribute.

**Evidence.**
- sd.py:506 clamp; exrs README (deep, DWA, HTJ2K unsupported; crate 1.74.2); PyTorch randomness notes 2.15 and cli_args.py:190 (fetched 2026-11-02); Karma Cryptomatte docs H22.

### `ux.shot-layer` — Shots reference a recipe and override locally: one recipe, many shots

**Horizon:** next · **Priority:** 2.38 · **Effort:** M · **Lands in:** usd-schema

**Depends on:** `M4 UsdShade encoding (Spec Patch 02)`, `M3 canon.rs`, `phase1 T0-T6 (frozen)`, `ux.recipe-face`, `Joe: PlexusShotAPI patch and the shot container (under /Project/Graphs or a Patch 02 amendment)`

**What it is.** Joe writes the Spec patch (a codeless PlexusShotAPI with frameStart, frameEnd and a pick relationship) and decides the container: /Project/Shots sits outside the decided NodeGraph root where sibling graphs cannot connect, so shots go under /Project/Graphs/Shots/<s> or Patch 02 is amended. The worker lands make_shot(). Each shot is a NodeGraph prim referencing a recipe and authoring only its own opinions (plate PlexusAssetAPI paths plus digests, frame range, seed, prompt, colour interop id); sequences are Scopes over shots; local opinions beat referenced ones (verified on 26.5) and the already-decided plexusBranch variantSet covers A/B. A recipe edit reaches every shot that hasn't overridden that input, and F7 means only shots whose intent hash changed re-run. The publication gate checks plate compatibility across shots sharing a recipe (channels, resolution, colour), the layer-breakdown caveat from Nuke GSV production. Houdini Shot Builder and Nuke 16 GSV vocabulary transfer at no learning cost.

**What the artist gets.** Fix the look once in the recipe and every shot picks it up; tweak sh020's seed and only sh020 changes; move between shots without opening another file.

**Risk.** The schema registry freezes at pxr load, so PlexusShotAPI must be in the plugin before any stage opens; 'take' and 'version' collide with AYON and Flow vocabularies and need an export mapping.

**First frozen test.** make_shot() twice from one recipe (seed 1), then override sh010's seed to 42: sh010 reads 42 with the shot layer winning its property stack, sh020 reads 1, and only sh010's M3 intent hash changed; after the recipe moves to seed 7, sh020 reads 7 and sh010 still 42.

**Evidence.**
- NEXTGEN_SCAFFOLD_PLAN.md:78, :175, :389; usd_meta.py composition probe on 26.5; Foundry GSV dev guide 17.1 and Houdini 22 Shot Builder docs (fetched 2026-11-02).

### `vfx.plate-receipt` — Plate receipt: the asset record a supervisor can sign, read from the file

**Horizon:** next · **Priority:** 2.35 · **Effort:** M · **Lands in:** usd-schema

**Depends on:** `M6 results`, `M3 canon.rs`, `org.correlation`, `eng.pack-ledger`, `eng.model-index`, `phase1 T0-T6 (frozen)`, `UI_DESIGN`, `Joe: Spec Patch 03 and its T0-style frozen test`

**What it is.** Joe writes Spec Patch 03 and its frozen test; the worker lands the organ side at M6 and the receipt rows after. PlexusAssetAPI gains plexus:colorInteropId (ASWF ColorInterop Recs 01-04 ids, whose _scene/_display suffix already carries referral, or 'unknown'), plexus:pixelType, channel names, data and display windows, compression, plexus:packDigests, plexus:licenceRefs and plexus:metadataStripped; the existing colorspace tokens stay so T0 holds. The organ fills them by reading the result file's header in the Plexus host (OpenEXR>=3.5.3 from the hashed lock, a pyproject scaffolding commit), never from node settings, because the installed SaveImage (Advanced) and its AI-generated docs disagree (half-float arrived in v0.39.0, ACEScg in v0.43.0) and radiance's 'ACEScg' passes tensors through and writes no chromaticities; OpenEXR 3.5's chromaticities-to-colorInteropID helpers give primaries, and referral stays Unknown unless the graph proves it. A missing field returns Outcome Unavailable(reason_code='no_chromaticities', missing=[...]) and the receipt's Colour row reads Unknown. The one-line receipt on the node and the fixed-order inspector rows carry the ComfyUI-side fields too: intent hash, the 'submitted graph (post-replacement)' hash, worker fingerprint, one digest per model a loader referenced, per-node ran/cached from execution_cached, wall time, and ComfyUI's blake3 asset id when assets are on. Prompt and workflow EXR metadata are stripped only at publication, keeping chromaticities and colorInteropID, since stripping at the worker loses colour identity.

**What the artist gets.** Drop a generated plate into comp and the inspector already says display-referred Rec.709 at 32-bit float, which model bytes and seed made it, and which pack versions ran; no more emails asking what colour space it is.

**Risk.** Header parsing is attack surface (OpenEXR 3.5.3 fixed 15 CVEs on 2026-10-31; Houdini 22 bundles 3.4.3; radiance uses the legacy API). Receipts for jobs before the ledger existed render Unknown.

**First frozen test.** T0-style subprocess gate: the new attributes register and survive save and reload; an organ result EXR with no chromaticities composes with colorInteropId 'unknown', the organ returns Outcome Unavailable, and the receipt's Colour row reads Unknown, never Verified.

**Evidence.**
- nodes_images.py:1003-1174 (installed) vs upstream tags v0.39.0 and v0.43.0 (fetched 2026-11-02); radiance nodes_io.py:60, 85; ColorInterop Recs 01-04 (github.com/AcademySoftwareFoundation/ColorInterop); OpenEXR 3.5.3 release 2026-10-31.

### `vfx.colour-ports` — Colour and compositing passes as typed ports, converted only at the edge

**Horizon:** next · **Priority:** 2.32 · **Effort:** L · **Lands in:** comfyui-organ

**Depends on:** `vfx.plate-receipt`, `M4 UsdShade encoding (Spec Patch 02)`, `M7 import`, `eng.second-worker`, `cto.repo-decouple`

**What it is.** Worker mission after M7 and the plate receipt. Image ports in the neutral IR carry an interop id as part of their type, with the vocabulary derived from the show OCIO config's interop_id values (OCIO>=2.5.1 for cp314 wheels; 2.6.0 adds interop-id helpers; ocio://studio-config-latest is ACES 2.0), never from pack labels; imported ports default to 'unknown'. The publication gate refuses an edge between mismatched ids unless plexus.op.colour_convert.v1 sits between them; the canvas keeps it advisory while working. Conversion runs at the organ edge with PyOpenColorIO, or engine-side on a v0.43+ worker, and the receipt names the config URI and OCIO version. Typed passes use the same mechanism: depth relative vs metric (Marigold v2 is affine-invariant by its own README), normals camera vs world, alpha, clean-plate, hdr-scene-linear, mesh, mapped from Marigold v2, MoGe 3, SAM 3, TRELLIS.2 and the LTX-2.5 IC-LoRAs (Alpha-Gen, Clean-Plate, SDR-To-HDR, gated, LTX-2.x licence) only where the node's output space is known; unmapped outputs stay untyped. The first measurement, before any label is trusted, is OCIO parity on the EXR the organ writes, since ComfyUI v0.34 has no OCIO dependency and v0.43's ACEScg path is unverified against Nuke's and Solaris's configs.

**What the artist gets.** You can't accidentally feed a display-referred SDXL frame into an ACEScg comp, and a depth map arrives in Nuke knowing whether it is metric and why the normals aren't flipped.

**Risk.** The default VAE clamps to [0,1] (display-referred) but Stage A, TAEHV and radiance's HDR decode do not, so referral is per graph; inverting display-referred into scene-linear is recorded as an assumption. ComfyUI's native AOVs travel as untyped IMAGE.

**First frozen test.** An output port typed lin_rec709_scene connected to an input typed lin_ap1_scene fails the publication gate with a reason naming both ids; with plexus.op.colour_convert.v1 between them it passes and that node's receipt records the OCIO config URI and library version.

**Evidence.**
- PyPI opencolorio 2.5.1+ cp314 wheels; OCIO 2.6.0 release 2026-10-01; sd.py:506 vs :559, :923-942, :1012; huggingface Marigold v2 README; grep of ComfyUI for OCIO: none (all 2026-11-02).

### `ux.takes-notes` — Takes and notes as opinions: content-addressed results with 'Already made', review memory agents can wake on

**Horizon:** next · **Priority:** 2.31 · **Effort:** M · **Lands in:** python-host

**Depends on:** `ux.shot-layer`, `M3 canon.rs`, `M6 results`, `org.job-ledger`, `Memory contract`, `UI_DESIGN`, `Joe: writer order for artist writes (is the session layer persisted?)`

**What it is.** Joe decides the writer order first: the scaffold plan says the session layer is in-memory and UI_DESIGN says it persists, and takes, picks, restores, notes and forgets each need a persisted single-writer layer named in that order. Then the worker lands it. Each finished run becomes a Take prim under its shot in the runtime layer, carrying plexus:intentHash, relationships to the content-addressed result prims, the resolved inputs at that moment, envFingerprint and the receipt rows; the same intent returns the existing take marked 'Already made', never a duplicate; the ordinal is derived from result order, not a counter; pick maps onto the existing runtime.usda acceptance opinion rather than a second relationship; restore writes the take's recorded values as opinions in the persisted human layer; the diff between two takes reads recorded values and reads Broken if they disagree with the cache key. Notes are prims in a persisted notes layer (author, text, target take, frame range, normalised region, created), resolved by opinion and never deleted, exported as OTIO markers, recalled through the Memory contract, and watchable by a predicate so the Wake tier can turn one into a parked proposal with a stage diff, never applied on its own. Radiance Workspace's .rad shot and version containers are prior art in Joe's own packs and the import-or-supersede call is named here.

**What the artist gets.** Every take on a shot newest first, each showing what changed from the one before; restore any take's settings in one click; write 'too hot in the highlights, frame 1012' and it stays with the shot for good, and a proposal arrives waiting for you.

**Risk.** Recorded values duplicate the cache key's inputs; results-layer rotation at 50k must not orphan takes; grammar v0 may need one neuron per shot without wildcard scopes.

**First frozen test.** With a test organ implementing the protocol (fixed asset path and digest), run sh010 twice identically and then once with seed 1 → 42: exactly two Take prims exist; the repeat returned the first with state 'Already made'; the second's diff against the first is exactly {'seed': (1, 42)}.

**Evidence.**
- NEXTGEN_SCAFFOLD_PLAN.md:185, :308 vs UI_DESIGN.md:239; radiance README.md:55, :58; Houdini 22 Render Gallery docs; Unreal takes docs (fetched 2026-11-02).

### `ux.state-model` — One state model: view-models as pure functions, the artist word table, and MCP tasks reading it

**Horizon:** next · **Priority:** 2.12 · **Effort:** S · **Lands in:** python-host

**Depends on:** `M4 UsdShade encoding (Spec Patch 02)`, `layers guard`, `phase2 T7-T8 (frozen)`, `UI_DESIGN`, `Joe: 'Made' vs the decided 'Verified' wording`

**What it is.** Worker mission after M4, no renderer needed. Every artist surface, the CLI and the MCP server read one state model: pure Python functions from the composed stage plus the session layer to frozen dataclasses of str/int/float/tuple at rank 7 (plexus.surfaces), with a frozen assertion that plexus.surfaces never imports plexus.organs.cozy (the drafted layers guard's hard edges do not cover this yet). One closed word table maps objects and states to artist words (Shot, Plate, Recipe, Take, Pick, Note; Working, Verified, Already made, Broken, Unknown, Parked, Stopping) onto the five decided marks through a state-to-mark table (Already made is Verified with a 'cache hit' reason; Parked and Stopping are rail states, not marks); renaming Verified to Made is Joe's one wording call; no word or tooltip matches T8's ENGINE_TERMS, imported from the guard rather than copied. The MCP surface exposes stage verbs (intent, receipts, park and approve, diff between runs) as MCP tasks per the 2026-07-28 spec (tasks/get polling, input_required mapping to a parked card, deterministic tools/list so Claude's prompt cache stays warm), never duplicating comfy-mcp's run and search tools; comfy-mcp (AGPL) is never vendored, runs at most as a separate process, and its launch_comfyui/stop_comfyui are not exposed because the organ owns the worker lifecycle. Plexus's agent competes on local-first, parked-and-diffed proposals, not chat (Comfy Agent: Cloud GA, local 0.1.0rc7 on PyPI, preview).

**What the artist gets.** What you see is always what's on the stage; no panel says 'done' while the take is cooking, and the words on screen are the words you'd say in dailies.

**Risk.** Pixels and legibility still need Joe's eye on a rendered build; a view-model made too generic becomes a second schema.

**First frozen test.** project_view(stage) on an in-memory stage with one shot prim and no results returns an object that walks to builtins and frozen dataclasses only, its status is the Unknown member of the closed enum, two calls return equal objects, and every state maps to exactly one word and one mark with Unknown and Verified distinct in both.

**Evidence.**
- UI_DESIGN.md:17-18 five marks; test_t8_blindness.py ENGINE_TERMS; MCP changelog 2026-07-28 (fetched 2026-11-02); comfy-mcp README (AGPL-3.0-or-later OR Commercial, 41 tools incl. launch_comfyui); PyPI comfy-agent 0.1.0rc7 2026-10-30.

### `vfx.dcc-handoff` — DCC and review handoff: Solaris reads Plexus, OTIO to RV, credentials on review media

**Horizon:** next · **Priority:** 2.09 · **Effort:** L · **Lands in:** python-host

**Depends on:** `M6 results`, `phase1 T0-T6 (frozen)`, `eng.model-index`, `vfx.plate-receipt`, `ux.viewer`, `usd.authorship-gate`

**What it is.** The first test is a harness check skipped when hython is absent and never recorded as passed: hython from Houdini 22.0.466 (pinned build; 22.0.400 carries a different SideFX fork revision at the same PXR_VERSION) opens a Plexus project with PXR_PLUGINPATH_NAME at plexus/schema, sees PlexusAssetAPI applied through the codeless plugin (the one plugin kind both USD binaries load), and resolves `${PLEXUS_STORE}` paths identically to usd-core 26.5, including a reference arc and the outer stage's override. Then, worker missions: approved results published as PlexusAssetAPI prims in an exchange layer Solaris sublayers; review goes out as plain .otio JSON (OTIO 0.18.1 has no cp314 wheel) for OpenRV 4.0.x; review proxies (MOV/MP4/PNG through an OCIO display/view) carry a C2PA manifest (c2pa-python 0.38.2 over the Rust crate; digitalSourceType from the graph; naming the stage prim and master-EXR digest) and a per-shot AI-use fact sheet rendered from the stage (models by digest and licence, frames, regions, approvals); the legal framing (EU Art. 50, the Omnibus's 2 Dec 2026 legacy deadline, provider vs deployer, Netflix and SAG-AFTRA terms unread in primary text) is Joe's guardrail question. Nuke 17.1 has shipped and its USD version is unknown; it must be measured before choosing usda-only, and the comparison with ComfyUI-for-Nuke v1.4 and ComfyUI-Nuke-Bridge must say what the receipt adds over a file path. Tracker publish (shotgun_api3 3.10.3, ftrack 3.1.0) is a thin adapter.

**What the artist gets.** Approve a version in Plexus and it's in your Solaris stage and your RV session with its receipt, and the QuickTime carries the credential itself.

**Risk.** hython needs a licence seat and never runs in the worker loop; C2PA signing identity is unresolved and EXR has no embed format (sidecars separate in handoffs); OpenRV is an install for Joe; OpenRV annotation export back is unverified.

**First frozen test.** hython 22.0.466 reads a fixture project: GetAppliedSchemas() on a result prim includes PlexusAssetAPI, and the asset path resolves to the same absolute path usd-core 26.5 resolves.

**Evidence.**
- Houdini 22.0.466 toolkit pxr.h fork revision b970560dc3b0 vs ee7b08cf5dae in 22.0.400; PyPI OpenTimelineIO 0.18.1 wheels; c2pa-rs supported-formats.md; github vinavfx/ComfyUI-for-Nuke v1.4 2026-10-10 (all fetched 2026-11-02).

### `org.correlation` — Organ correlation: Plexus mints the job id and hashes the graph /history returns

**Horizon:** next · **Priority:** 2.04 · **Effort:** M · **Lands in:** comfyui-organ

**Depends on:** `phase2 T7-T8 (frozen)`, `organ contract (plexus.organs.protocol, CONTRACT.md §8.1)`, `eng.lock`, `M3 canon.rs`

**What it is.** Worker mission at M1/T7. The organ mints a fresh canonical UUID per attempt as prompt_id; ComfyUI does not reject duplicates, so an id is never reused and the organ checks /api/jobs/{id} or /history/{id} before any resubmit. On a v0.40+ worker it sends workflow_metadata {plexus_i: intent-hash prefix, plexus_s: stage path}, asserted at the message top level including execution_error and preview frames with supports_preview_metadata (keys are spread, the message's own keys win, cap is 256 chars of json.dumps). The websocket is liveness only; /history is truth. The executed-graph hash is computed from the /history prompt and labelled 'submitted graph (post-replacement)'; loop projection and runtime expansion are reproducible only through the pack digests and the receipt says so. Sinks are targeted with partial_execution_targets. The raw /prompt transport keeps an adapter seam; Comfy API v2 through comfy-api-proxy is Joe's option, gated on a smoke test against the pinned commit, never a default. This is the run-confirmation that can retire Patch 01-C's reconciliation layer.

**What the artist gets.** Every progress tick and every frame knows which shot and which version of your graph made it, even after a crash.

**Risk.** Legacy /prompt, /history and /ws carry no compatibility promise (Comfy API v2 docs). Node replacement makes the executed hash differ from the intent's graph; it is shown, never hidden.

**First frozen test.** Against T7's fake server: submit with prompt_id X; /history/X exists and every prompt-scoped message carries prompt_id X; a graph containing a replaced class records a hash computed from /history/X, not from the request body; the same id submitted twice is refused by the organ before any second POST.

**Evidence.**
- server.py:1088-1133 (uuid validation, no duplicate check); PR #16763 and #16809 (metadata on messages and preview frames, v0.40.0); node_replace_manager.py:61-91; comfy-api-proxy 0.1.6 /workflow is pre-replacement (releases, fetched 2026-11-02).

### `ux.viewer` — A minimal viewer for choosing takes, through the show's transform, with heavy review handed to RV

**Horizon:** next · **Priority:** 1.99 · **Effort:** M · **Lands in:** surface-ui

**Depends on:** `ux.takes-notes`, `M6 results`, `vfx.colour-ports`, `cto.repo-decouple`

**What it is.** Worker mission after takes. The in-surface viewer does only what choosing a take needs: scrub an image-sequence or video take, A/B split and absolute-difference compare against another take (Houdini's Render Gallery compare), an OCIO display/view from the shot's declared interop id with the view name printed on screen (OCIO 2.6.0 cp314 in the lock; an ACEScg EXR shown raw reads wrong, and a declared space of none shows Unknown rather than a guessed transform), frame number and take id in mono. Proxies and thumbnails are content-addressed by result key (proxies/<key>/<frame>), made once and shared across shots that resolve to the same result; the proxy maker is Python and moves to Rust only on a measured hot path over Joe's takes. The same proxy encoder feeds review export and the C2PA credential in vfx.dcc-handoff. Full-resolution EXR playback and annotation sessions go to OpenRV through the .otio JSON export (OpenRV is Joe's optional install). Today 2 of Joe's 177 workflows write EXR and 95 write video, so most takes are display-referred PNG or MP4 and the viewer is frame-sequence first.

**What the artist gets.** Scrub and wipe two takes right where you pick them, viewed through the show's transform with its name on screen; when you need real review, one verb opens the sequence in RV with your notes on it.

**Risk.** Video decode needs a codec path; an OCIO transform on display-referred output misleads unless the assumed space is named.

**First frozen test.** proxy_paths(take) for a 3-frame fixture returns three paths under proxies/<result key>/, and a second call from a different shot resolving to the same key returns the same paths with mtimes unchanged.

**Evidence.**
- Workflow library scan 2026-11-02 (177 workflows, 2 EXR, 95 video); PyPI opencolorio 2.6.0 cp314 win_amd64 (2026-10-01); OpenRV 4.0.0 2026-07-17 OTIO annotation reader.

### `ai.prompt-expand-op` — Prompt expansion as a pinned, content-addressed op

**Horizon:** next · **Priority:** 1.96 · **Effort:** M · **Lands in:** python-host

**Depends on:** `M3 canon.rs`, `M4 UsdShade encoding (Spec Patch 02)`, `M6 results`, `M7 import`, `ai.providers-tiers`, `org.capacity`

**What it is.** Worker mission after M6, M7 and the provider contract. plexus.op.prompt_expand.v1 models the language-model stage that 2026 generators expect (FLUX 3 Klein's 9B Qwen3.5 upsampler, MiniMax's Context-IR, ComfyUI's own TextGenerate and LTX2 prompt nodes) as a typed op whose output text is a content-addressed asset; downstream keys hash the expanded text, so a rerun reuses the pinned expansion and gives the same frame. It is justified on cost (skip a 9B LLM pass), editability (the artist reads and edits the expansion in the inspector as a session opinion) and environment drift (envFingerprint is out of the key), not on nondeterminism alone, since TextGenerate takes a seed. Import lifts an in-graph upsampler out behind its enable switch or treats it as opaque; a hosted-only stage under local-only reports Unavailable; the op runs through the provider contract under the GPU lease, because the LLM stage can be a third tenant inside the ComfyUI worker.

**What the artist gets.** The long prompt the model actually used sits on the node where you can read it, change a word and re-render; last week's look comes back exactly because the expansion didn't silently change.

**Risk.** Templates embed the upsampler; MiniMax's IR and Regenerate-2K are cloud-only, so local H3 is 768p with two of three stages absent.

**First frozen test.** A two-node graph (prompt_expand → fake image op) run twice against a fake provider that returns a different string on every call yields the same result prim path k_<key> and exactly one provider call; authoring a new expansion on the session layer changes the downstream key.

**Evidence.**
- HF flux-3-image-klein-pup README; MiniMaxAI/MiniMax-H3 README (Regenerate-2K not open-sourced); comfy_extras/nodes_textgen.py in v0.34.0 (all 2026-11-02).

### `ux.recipe-face` — The recipe face from native UsdUI hints, with the ComfyUI canvas as the graph-surgery tool

**Horizon:** next · **Priority:** 1.87 · **Effort:** M · **Lands in:** python-host

**Depends on:** `M4 UsdShade encoding (Spec Patch 02)`, `M7 import`, `M3 canon.rs`, `ux.state-model`, `phase2 T7-T8 (frozen)`, `Joe: whether Plexus's own canvas edits at all`

**What it is.** Worker mission after M7. A recipe's exposed inputs are the NodeGraph inputs:* carrying native UsdUI hints on 26.5 (AttributeHints and PropertyHints: shownIf, displayGroup, valueLabels; PrimHints: displayGroupsShownIf and displayGroupsExpanded) plus displayName, documentation and propertyOrder; recipe_face(graph) returns ordered groups with conditional visibility evaluated by a small evaluator that is a subset of predicate grammar v0 (26.5 Python has no Sdf.BooleanExpression). The M7 importer, inside plexus/organs/cozy, carries ComfyUI App Builder selections (extra.linearData and *.app.json; 6 of Joe's 129 UI workflows) as exposed inputs and order only, dropping preview and upload widgets through an organ-side allowlist, since the real data holds no labels or groups. The ComfyUI round trip: 'Open recipe in ComfyUI' writes the recipe with the current shot's overrides through POST /userdata/{file} (a route that exists in 0.34; auto-opening the tab is unknown), and on save the importer reads it back; intent hashes name what changed and which shots it touches. Plexus builds no second graph editor (ten frontend releases in ten days, Nodes 2.0's compatibility warning, 16 packs whose web UIs render only there).

**What the artist gets.** Open a shot and see the handful of controls that matter, grouped and named in your words with a line of help on each; rewire in the ComfyUI canvas you know with every custom widget working, and come back to see exactly what changed.

**Risk.** extra.linearData is an internal frontend key; UI-format widget values are positional, so the round trip compares IR and intent hash, never JSON.

**First frozen test.** On usd-core 26.5 alone, a NodeGraph with inputs seed and strength (displayGroup 'Look:Variation') and debug (hidden) and propertyOrder [strength, seed]: recipe_face returns one group Look > Variation with controls ['Strength', 'Seed'] in that order and omits debug.

**Evidence.**
- UsdUI hints probe on 26.5 (skeptic scratchpad, 2026-11-02); app/user_manager.py:364 POST /userdata; LTX23_IC_LORA.app.json linearData shape; ComfyUI_frontend releases 2026-10-23 to 11-01.

### `org.job-ledger` — Job ledger in the organ: in-flight intent only, never a success it did not see

**Horizon:** next · **Priority:** 1.72 · **Effort:** M · **Lands in:** comfyui-organ

**Depends on:** `org.correlation`, `plexus._core (M2b Outcome)`, `phase2 T7-T8 (frozen)`

**What it is.** Worker mission after org.correlation. The job state machine lives in the organ (L4, Python), keyed by the Plexus correlation id, in stdlib sqlite in WAL mode with one handle owned by the conductor: submitted, running, succeeded, failed, cancel-requested, cancelled-confirmed, unknown. Transitions fire only on observed evidence (an /api/jobs status, classify_job_for_cancel, /history); succeeded fires only when /history is readable and the output file stats. It holds in-flight intent only, never results or provenance (those are opinions on the stage, per Blueprint §3), so there is one truth. On restart it polls every non-terminal job; anything missing from the worker's in-memory history (capped at 10,000, lost on restart) becomes Unknown and is never resubmitted on its own; authoring a new intent is the only path to a re-run. The F7 intent ledger stays in plexus-core later; a B24-style draft for Joe keeps it in Python until measured. Blueprint's L1 Ledger (Hanish precommit/settle) is a different thing and is not touched.

**What the artist gets.** After a crash or reboot the activity rail says plainly which renders finished, failed or are unknown; nothing quietly re-runs a 20-minute LTX job.

**Risk.** If Joe adopts comfy-api-proxy, its --state-dir also persists jobs; keep the ledger keyed by intent and treat the proxy as a transport so the two never disagree silently.

**First frozen test.** Submit 3 jobs to the fake organ, kill the conductor mid-run, restart: no job is resubmitted; a job reads done only where the fake /history has it and the stage holds its result prim; the rest read unknown; the ledger schema has no column holding a result path or hash.

**Evidence.**
- execution.py MAXIMUM_HISTORY_SIZE = 10000, in-memory (master, fetched 2026-11-02); Patch 01-C poll-for-truth; Blueprint §4 Ledger contract text.

### `ux.shot-view` — The shot view: Plexus's home surface is a shot, not a graph (model first, pixels last)

**Horizon:** next · **Priority:** 1.72 · **Effort:** L · **Lands in:** surface-ui

**Depends on:** `ux.state-model`, `ux.shot-layer`, `ux.takes-notes`, `ux.recipe-face`, `ux.viewer`, `UI_DESIGN`, `Joe: renderer (local web vs Qt, standalone vs sidebar) and the zero-build spike`

**What it is.** Split in two. shot-view-model (S, after M4 and takes; worker mission): the frozen view-model of the home screen: shot list by sequence with frame range and state word, the picked take, the take stack newest first in fixed receipt order, the recipe face and the Make verb, with the decided one-sentence status, rail and parked cards unchanged. shot-view-pixels (L, after M6 and M7): a typographic grid with the work as the only colour (two accents plus the muted verdict trio, hue-count tested; the five marks must stay distinct without colour next to full-colour output), four regions, the graph one click away, a virtualised list for hundreds of shots; the renderer is Joe's, with the frontend's churn arguing against a ComfyUI sidebar. Before pixels, a spike compares the zero-build option (Solaris and usdview read the same 26.5 stage and already have a viewer, Render Gallery A/B and Shot Builder vocabulary; Houdini is forbidden as host, not as a read-only viewer; Joe's own houdini-comfyui-connection pack exists) against a custom renderer, and records the result in the decision ledger.

**What the artist gets.** Open Plexus and see your shots and their latest takes; play them, compare two, change the three knobs that matter and make another take, without looking at a wire unless you want to.

**Risk.** The largest build; the harness tests view-models, not pixels, so every round needs Joe's eye; building the view before its checks exist tempts placeholder greens, which the Unknown-mark and hue-count tests prevent.

**First frozen test.** shot_view(stage) for sq01 with sh010 (two takes, t_0002 picked) and sh020 (no takes): shots in sequence order, sh010's takes newest first with the pick marked, sh020's state word Unknown (not Verified), every take row's fields in the fixed receipt order, and no string in the model matching the T8 pattern.

**Evidence.**
- UI_DESIGN.md:20, :55, :120; Blueprint §11 proposes the UI last; NEXTGEN_SCAFFOLD_PLAN.md:128 (Houdini not host); Krita AI Diffusion v1.53.0 2026-08-22 as precedent; Comfy App Mode 2026-03-10.

### `usd.memory` — Memory as composition, with exact recall beside it

**Horizon:** next · **Priority:** 1.71 · **Effort:** M · **Lands in:** usd-schema

**Depends on:** `Memory contract`, `M3 canon.rs`, `usd.authorship-gate`, `phase1 T0-T6 (frozen)`, `Joe: memory option (A now vs C) and the rule-4 reading of content ids`

**What it is.** Joe decides first (PLEXUS_MEMORY_OPTIONS makes the backend his; the lean was A now, C as destination); the worker lands it behind the frozen Memory contract. Option C shape as measured on 26.5: episodes as prims in one usdc per writer (under /Plexus/Neurons/<id>/Memory with a T5 allowlist grant, or a /Memory root by Spec patch), each named by intent_hash(record, writer, created) so identical records are never collapsed unless Joe reads rule 4 otherwise; facts as per-key dictionary customData where the strongest writer wins per key (walked as nested dicts); evidence links as append list-ops; tags via UsdSemantics LabelsAPI; recall scopes via CollectionAPI path expressions. remember() appends to an in-memory layer saved in batches on the heartbeat (a per-episode save costs about 160 ms and 40 KB of crate garbage at 10k episodes); compaction by TransferContent; readers reload on the writer-layer notice. Forget is an opinion (active=false) in a saved, Joe-owned forget layer strongest in the memory stack, never a deletion; the inspector reuses the decided opinion-stack element to show the winning writer and contesters. Recall: a Python flat numpy cosine index (0.36 ms at 10k, 30 ms at 1M) over `mem:embedding:<modelId>` float[] stored in USD, ties broken by prim path, a text embedder first; Rust only for bit-exact cross-machine scores or a measured miss. Visual recall waits on a 5-minute probe of whether Ollama 0.40.13 embeds an image at all (the documented /api/embed is text-only; the embeddinggemma-2 pull is Joe's; licence and date unknown).

**What the artist gets.** Plexus remembers what worked on your shots the way your scene remembers overrides; you can see who believed what, on what evidence, and veto it with one click you can undo.

**Risk.** Memory stage opens must not slow graph editing (own stage or payloads); a writer's usdc grows without bound without rotation; pxr extraction (1.06 s per 100k vectors) is the cold-start cost, not the search.

**First frozen test.** Neurons A and B each remember() a fact about the same subject into their own layers; recall(scope) returns both evidence links as a union, per-key values with the strongest writer winning and the winning layer per key; after a forget-layer opinion on one episode, recall excludes it and the writer's layer still holds its spec.

**Evidence.**
- t1_compose.py and the skeptic's corrected nested-customData probe; t3_scale.py and the 30-save measurement (2026-11-02); docs.ollama.com/api/embed input = text (fetched 2026-11-02).

### `ai.locality-posture` — Local means local: fail-closed locality and worker posture, from the harness today to projects later

**Horizon:** next · **Priority:** 1.71 · **Effort:** M · **Lands in:** python-host

**Depends on:** `harness`, `ai.providers-tiers`, `eng.lock`, `eng.pack-ledger`, `M7 import`, `Safety contract (Phase 3)`, `Joe: locality attribute (Spec patch)`

**What it is.** Today, Claude scaffolding in the harness: `check` and `run` refuse any worker or router model whose /api/tags entry has a non-null remote_host or whose host is not loopback (cloud tags do have digests, so the name and digest are not the signal), and the mission's outbound allowlist names api.typesafe.ai with the exact fields the router sends (failing test ids, the last 3,000 characters of pytest output, step text). Later, a worker mission with a project attribute local-only vs remote-allowed, checked by the Safety contract at three points: the provider contract refuses remote declarations (Claude, Jev, :cloud tags; hosted stages such as MiniMax Context-IR report Unavailable rather than being faked); the organ fails closed when the worker's argv lacks the offline flags its version supports, and partner and API node classes (Claude, Comfy Cloud GPU nodes) are rejected at import from /object_info metadata; Ollama runs with OLLAMA_NO_CLOUD=1. Backend egress is HF_HUB_OFFLINE plus a firewall rule, never --offline. The same opt-in contract carries worker posture: loopback or TLS; a live probe of /customnode/installed and /manager/* (Joe's legacy Manager 3.41 is live whatever --enable-manager says, and a 200 is Blocked); the pack set equal to the pack ledger; a deny list of raw-code-execution node classes seeded from the April 2026 campaign. Failures are a lasting per-organ Connection state in the status bar, T7's permissive default stays untouched, and every receipt records where each step ran.

**What the artist gets.** Flip a project to 'this stays on my machine' once and nothing can quietly send a frame or a prompt to a server, and no show job runs on a worker someone quietly added a pack to.

**Risk.** A custom pack can reach the network on its own; partner-node metadata shape varies by version; the deny list needs maintenance and will false-positive on utility packs.

**First frozen test.** Harness preflight on a mission naming 'glm-5.3-flash:cloud' raises RefuseToStart with a message containing 'remote inference' against a stubbed /api/tags with remote_host set; 'qwen3-coder:30b' with a local entry passes.

**Evidence.**
- curl /api/tags: ten entries with remote_host https://ollama.com (2026-11-02); router.py:79-105; nodes.py:2370-2373 and ComfyUI-Manager manager_server.py:780-1017; cli_args.py --offline help text (master, fetched 2026-11-02); THN 2026-04-07.

### `ai.providers-tiers` — Provider contract and the Reflex, Wake, Reason ladder, behind Outcome and budgets

**Horizon:** next · **Priority:** 1.66 · **Effort:** M · **Lands in:** python-host

**Depends on:** `plexus._core (M2b Outcome)`, `phase1 T0-T6 (frozen)`, `UI_DESIGN`, `Joe: B17 (fifth L1 contract vs internal L2 protocol)`

**What it is.** Joe decides B17; the worker lands it either way, written new with Comfy-Cozy's six-provider design as reference only. complete(request, budget) -> Outcome with a typed output schema; each provider declares where inference runs, a model identity (Ollama digest; a dated Claude id; jev-1.14.0 pinned with the response model field logged), licence, and a dated price table, and every call returns measured tokens, wall time and cost. Adapters: local Ollama (refuses any model whose /api/tags entry has a remote_host; ten :cloud tags are pulled today); Claude (API 2026-10-21 shapes: temperature and top_p removed, forced tool_choice rejected and thinking always on for Opus 5.5 and Fable 5.1; Haiku 5.5 for routing; the seed's haiku-4-5 default is past its earliest retirement date and sonnet-4-5 retires 30 Nov 2026); Jev (Noul probabilities against thresholds, never Score magnitudes; text-only and 64k context, so visual QC needs a local VLM such as qwen3.8:27b or qwen3-vl:30b already on disk). Tiers: Reflex is deterministic recipes over the stage with no model; Wake is one closed question with a probability from a local model or Jev; Reason is Claude only when a predicate permits it and a threshold measured on Joe's labelled cases says so; an unmeasured threshold parks a proposal; a model-variant choice is a parked proposal or a pinned session opinion, never a silent reflex, because it changes the hash. Budgets: budgetTokens per wake, 60 wakes per minute, and a per-project dollar ceiling from measured usage.

**What the artist gets.** Routine things just happen, small judgment calls get made quickly on your box, the expensive model comes in only when needed, and when the system isn't sure it asks you in the rail instead of guessing on your shot.

**Risk.** Price tables and ids go stale and must be dated data; local structured outputs are not calibrated like Jev; Jev on-prem is unknown, so it counts as remote.

**First frozen test.** A neuron with budgetTokens = 0 whose predicate fires runs its reflex and a fake provider that raises is never called; with budgetTokens = 100 and a 150-token request it returns Outcome Unavailable with a reason containing 'budget' and the provider is never called; a Wake answer of p = 0.55 with an unset threshold authors exactly one parked proposal prim and never calls the fake Reason provider.

**Evidence.**
- docs.ollama.com/cloud and /api/tags remote_host (2026-11-02); platform.claude.com models overview and deprecations (fetched 2026-11-02); docs.typesafe.ai/models.md and model-jaggedness/jev-1.13.md (fetched 2026-11-02); agent/config.py:152.

### `org.cache-provider` — Cache provider: ComfyUI's own cache survives restarts, keyed by what the bytes are

**Horizon:** next · **Priority:** 1.63 · **Effort:** L · **Lands in:** comfyui-organ

**Depends on:** `org.correlation`, `eng.pack-ledger`, `eng.model-index`, `eng.second-worker`, `M6 results`, `Joe: install a small Plexus pack into the second worker`

**What it is.** Joe decision first (the pack is an install into the worker's custom_nodes and a dent in 'stock'; it goes on the second worker only), then a worker mission. A CacheProvider registered through comfy_api.latest.Caching: the organ writes a per-prompt salt file before POST /prompt (ComfyUI commit, pack digests, and the digests of every model the prompt references; never env, per decision 4; one prompt at a time is assumed and checked); on_prompt_start loads it; key = sha256(salt || cache_key_hash). should_cache admits only allowlisted class_types whose outputs are plain tensors (never MODEL, CLIP, VAE), because lookup gets no value. on_store copies to CPU synchronously and hands off to a private thread pool before any await, since the fire-and-forget create_task is cancelled at loop teardown on Python 3.14; on_prompt_end flushes. The bridge refuses to run under --cache-none, a failed store reads Unknown rather than a hit, and the namespace is separate from F7 results. Later tests cover the restart round trip on a real worker and a model swapped under the same filename producing a miss.

**What the artist gets.** Reopen yesterday's shot, nudge one knob, and only the branch you touched re-renders, even after a reboot.

**Risk.** Correctness rests entirely on the salt; keys with NaN never reach providers; restored tensors land on CPU and downstream device placement is untested; disk growth needs rotation.

**First frozen test.** Unit, no GPU: on_store then on_lookup from a fresh provider instance returns a bitwise-equal 1x4x64x64 latent; should_cache is False for a non-tensor class; the stored entry records both cache_key_hash and the Plexus key read from the salt file; a store that raises leaves the entry absent and the receipt row Unknown.

**Evidence.**
- comfy_api/latest/_caching.py, comfy_execution/caching.py:159-300 (create_task never awaited; no value on lookup), execution.py:727/843, main.py:367 (--cache-none → NullCache); toy asyncio test on 3.14.2 showed to_thread cancelled at teardown (skeptic, 2026-11-02).

### `org.capacity` — Capacity: static capabilities, a live snapshot, set-inclusion routing and one GPU lease

**Horizon:** next · **Priority:** 1.52 · **Effort:** L · **Lands in:** comfyui-organ

**Depends on:** `eng.lock`, `eng.pack-ledger`, `M7 import`, `organ contract (plexus.organs.protocol, CONTRACT.md §8.1)`, `Joe: a snapshot() addition to CONTRACT.md`

**What it is.** Worker mission after M7. capabilities() keeps its frozen list[str] signature for static facts read at registration: comfy.node.<class> and comfy.pack.<name>@<digest> from the lock-keyed /object_info, engine version, package versions, argv. A separate snapshot() at the organ edge reads live vram_total/vram_free (ComfyUI has no loaded-model list; Ollama /api/ps has digests and size_vram) and never touches the stage. Graphs declare required capabilities in the UsdProfiles ClaimsAPI shape (apiSchemas ClaimsAPI plus customData.profilesInfo, authored on 26.5 and read natively on 26.11); organs keep Plexus attributes; routing is set inclusion and Unavailable names the missing pack. Admission is an exclusive Python lease per device: the bound is measured vram_free minus an unattributed bucket (Windows driver reports per-process VRAM as N/A; about 6 GB is Houdini and the desktop), one measured unload per tenant (POST /free then poll /system_stats until VRAM falls; keep_alive 0 for Ollama), Houdini open means CPU, lease state as an opinion on /Plexus/Organs so the rail can name the holder. The pool's first measurement is handoff latency for the 46.1 GB ltx-2.3-22b checkpoint; the 3D pack's existing venv is the first pooled second worker. Quant formats (fp8, int8_convrot, nvfp4) are listed only after a probe run measures them. Rust only after co-residency is measured.

**What the artist gets.** Plexus never sends your graph to a worker missing a pack, and while an LTX render holds the GPU the rail says so and the assistant waits or runs on the CPU instead of running out of memory halfway through a 4K pass.

**Risk.** /free returns 200 before anything is released; comfy-aimdo's behaviour with a second CUDA process is undocumented; LLM stages can run inside the ComfyUI tenant (TextGenerate, Gemma encoders). Measured with Houdini closed.

**First frozen test.** Organ prims A{x, y} and B{x} plus a graph requiring {x, y}: route() picks A; with only B present it returns Unavailable with a reason naming y.

**Evidence.**
- CONTRACT.md:46 capabilities() -> list[str]; server.py:686, :1192-1200; nvidia-smi --query-compute-apps used_gpu_memory [N/A] (2026-11-02); UsdProfiles ClaimsAPI customData round-trip measured both ways (skeptic, 2026-11-02).

### `vfx.licence-gate` — Licence and territory as data on each model digest, folded over the graph at publication

**Horizon:** later · **Priority:** 1.77 · **Effort:** M · **Lands in:** python-host

**Depends on:** `eng.model-index`, `M6 results`, `Safety contract (Phase 3)`, `M3 canon.rs`, `Joe: policy table, territory and revenue facts`

**What it is.** Worker mission at Phase 3 with M6; Joe owns the policy table (legal is a guardrail domain). A read-only licence layer keyed by model digest: licence id (SPDX where one exists, otherwise vendor and date: 'LTX-2.x Community 2026-08-11', 'Qwen Research 2026-09-20', 'MiniMax H3 Community 2026-08-02', 'FLUX.1-dev Non-Commercial 1.1.1'), source URL and read date, gating, and obligations as data: model-use, output-use, revenue threshold, excluded territories applying to use and to output delivery (H3 excludes the EU, UK, Korea and USA, and bars Outputs outside the territory), disclosure, watermarking, review and attribution duties (FLUX §2(e), LTX-2.x). The publication gate folds over every weight a graph loads (base, LoRA, text encoder, VAE, upsampler; Marigold v2 is a LoRA on Qwen-Image-Edit) against the project's declared use; a mismatch becomes a parked card quoting the clause; a digest with no record is Blocked (fail closed, F9), never Ok. Plexus shows clauses and never rules.

**What the artist gets.** Before a shot goes to a client, the inspector lists every model that made it and flags any whose licence doesn't fit this job, quoting the sentence; you find out in seconds, not in legal review a week before delivery.

**Risk.** Gated repos hide terms (FLUX 3 Klein's 'Kommunity' licence text); entries need re-check dates; the frozen test checks mechanism only and never bakes in a legal verdict (FLUX permits commercial Output while the model grant is non-commercial).

**First frozen test.** A policy-table entry mapping licence L under use U to Blocked makes Safety.check on an intent referencing digest X (licence L) return Blocked naming X and L; a digest with no record returns Blocked with a reason containing 'licence unknown'.

**Evidence.**
- LICENSE-2_x (Lightricks, 2026-08-11), MiniMax-H3 LICENSE line 42, Qwen-Image-2.1 LICENSE, FLUX.1-dev LICENSE.md §2(d)-(e), HF API metadata (all fetched 2026-11-02).

## Traps

Each looks like progress and is not, for a one-person studio on one workstation.

- Buying more attempts or a bigger worker before fixing the brief and the structure. Every drop on the ledger (10 rows, 1 kept) was a harness or brief defect: four at git apply before 15bc013, four on the layers gate from prose rules the 30B model did not bind to. DORA's finding that AI amplifies existing dysfunction applies; the operator's STOP file is the circuit breaker today while max_consecutive_failures = 8 is inert.
- Building the shot view's pixels, or any renderer, before M3, M4, M6 and M7 exist. It would be drawn against placeholder state and tempt green marks with no data behind them; the view-model and word table are the only UI work that can land now.
- A second graph editor. The ComfyUI frontend shipped ten releases across three lines in ten days, Nodes 2.0 warns packs may break, and 16 of Joe's packs render web UIs only there. Graph surgery is a round trip to ComfyUI's canvas; Plexus's canvas is a read-mostly map at most.
- Competing with Comfy Agent on 'chat builds the workflow'. Cloud is GA and a local release candidate has been on PyPI for 12 days; the vendor will own that surface. Plexus's agent is parked, diffed, budgeted proposals from local models, which is what the Stop and tab-switch bugs in Comfy Agent cannot do.
- Rust for throughput. Hashing is I/O-bound and parallel in Python already (3.58 GiB/s on four streams); blake3's Python package is the Rust crate; graph.rs waits for a measured 10 ms miss; a Rust GPU lease before co-residency is measured; redb or rusqlite in plexus-core for a workstation-scale ledger. Each looks like progress and amends rust.crate-split or the measure-first rule for nothing.
- A C++ USD plugin, OpenExec, or a custom Ar resolver. usd-core ships no headers or import libs, Houdini's HDK links a different fork build with different revisions per point release, OpenExec has no Python bindings and is in-process C++, and models are asset-valued attributes USD never opens, so a resolver verifies nothing. Codeless schemas and layers are the only seam both USD binaries share.
- Trusting a node's label or docs for colour. The installed SaveImage (Advanced) writes only 32-bit float with no ACEScg while its AI-generated docs say otherwise; radiance's 'ACEScg' path returns tensors unchanged and writes no chromaticities; --disable-metadata also strips chromaticities. Colour identity is read from the file header or it is Unknown.
- Treating --offline as backend egress control, or --enable-manager's absence as the installer being off. --offline is a frontend Content-Security-Policy; the legacy ComfyUI-Manager 3.41 pack loads and serves /manager/* routes whatever the flag says. Egress needs HF_HUB_OFFLINE and a firewall rule; posture needs a live route probe.
- Hashing what the organ sent instead of what ran. Node replacement rewrites class_type after the POST, comfy-api-proxy's /workflow is the pre-replacement graph, and even /history lacks loop projection and runtime expansion. The receipt field is 'submitted graph (post-replacement)' plus pack digests, and a websocket completion is a hint, never success.
- Two identity regimes drifting. ComfyUI's assets and governance use blake3; M3's cache keys are sha256 by decision; seeding ComfyUI's asset store and the Cozy organ's index would hash 257 GB twice beside Houdini. One file-identity algorithm plus a bridge, decided once.
- Putting results or provenance in the job ledger, or the job ledger in plexus-core's L1 Ledger. The Ledger contract is Hanish foresight; Patch 01-C says core never sees a prompt_id; a second store of results breaks 'the stage is the truth' and 'one handle per storage location'.
- Salting the cache with the environment. Joe's decision 4 keeps envFingerprint out of the key so results are shareable across machines; env goes on the receipt as the drift signal. The same mistake appears as a reflex that silently swaps an fp8 variant when VRAM is short, which changes the hash and the frame.
- Building on preview or unknown vendor pieces: comfy-api-proxy (beta, unreleased since 2026-08-19), openusd shared layers (unreleased), OpenExec Python bindings, pyisolate and the api-v2-runtime SDK seam (branch-only), Ollama image embedding (docs say text-only), a self-signed local governance policy (undocumented), comfy-agent local, Jev on-prem. Each is a watch item with a revisit trigger, not a dependency.
- Treating AuthorshipAPI, a licence id, or a same seed as proof. The authorship record is 'unverified' by its schema doc; FLUX permits commercial Output while the model grant is non-commercial; PyTorch guarantees no reproducibility across releases or platforms and ComfyUI's --deterministic is best effort. Proof is the recomputed cache key, the digests, and a measured repro class.
- Persisting into the session layer, or auto-deduplicating memory. The plan defines the session layer as in-memory while UI_DESIGN says it persists, and memory rule 4 forbids silent dedupe; a note, pick, forget or memory record that lands in the wrong layer disappears or collapses. Both are Joe's decisions before any artist write lands.
- Planning against the repo's own stale docs. Blueprint §13.2 says openusd transactions are unreleased (they shipped in 0.8.0), NEXTGEN §3.4 says property_stack is main-only (shipped), hydra-rs is 0.0.11 not 0.0.5, the task text's '3 of 13 kept' does not match the ledger's 1 of 10. External facts carry a last-verified date or they are not facts.
- Crediting Jev's 9-of-9 routing agreement. The prompt says 'choose the earliest step', so agreement with earliest-failing-step is by construction while each attempt pays an outbound call carrying pytest output. Jev earns its keep where routes can differ (Wake, UI choices) and in an A/B against the `first` router.
- Upgrading the engine in place, or calling the current install 'stock v0.34.0'. It is an untagged master commit with untracked files, a custom_nodes symlink loading three Comfy-Cozy packs and a hotfix. Pin by commit, define the pack set, and upgrade as a second worker.
- Vendoring comfy-mcp (AGPL-3.0-or-later OR Commercial) or registering under the comfyui.agent v1 entry point. The first is a licence problem; the second is co-tenancy with a 0.1.0rc API where two providers coexisting is unknown.
- Framework editing as progress: a decision ledger nobody updates, a risk register with no owner, a third mission-file rewrite in a day. A row changes in the same commit as the decision or the ledger is paperwork.

## Decisions for Joe

None of these is decided. Each changes what gets built; most can wait until the mission that needs it.

1. File-identity hash: cache keys stay sha256 (decided Nov 1, frozen at M3); for models, packs and assets lead with blake3 (interop with ComfyUI's shipped asset ids and governance digests; the Python package is the Rust crate) or store both, which doubles a one-time pass of about 1.5-3 minutes.
2. Engine pin: stand up a v0.43.x worker in its own venv beside the current untagged v0.34 commit (gets workflow_metadata, offline flags, ACEScg EXR, Marigold v2, MoGe 3, the cache-provider home) at the risk that 9 internals-patching packs break, with the old worker as fallback; or stay on v0.34 and give up those seams.
3. Install a small Plexus CacheProvider pack into the second worker's custom_nodes: a cross-restart cache keyed by content versus a dent in 'stock ComfyUI' and an install outside the repo venv.
4. Memory backend: Option A (append-only file now) versus Option C (memory as composition, measured working on 26.5), and whether a content id on each record that appends provenance instead of collapsing duplicates satisfies memory rule 4.
5. Writer order for artist writes: is the session layer persisted (UI_DESIGN) or in-memory (scaffold plan)? Name the persisted single-writer layers for takes, picks, restores, notes and forgets before any artist write lands.
6. Shot container and schema: shots under /Project/Graphs/Shots/<s> inside the decided NodeGraph root, or a Patch 02 amendment; plus the PlexusShotAPI patch (frameStart, frameEnd, pick) and its T0-style test.
7. Spec Patch 03 breadth: add colorInteropId, pixelType, windows, compression, packDigests, licenceRefs and metadataStripped to PlexusAssetAPI alongside the frozen colorspace tokens, and a project locality attribute and a snapshot() addition to CONTRACT.md; each widens the frozen surface T0 and T7 protect.
8. Plexus's own canvas: read-mostly map with graph surgery as a round trip to ComfyUI's canvas (no second editor to maintain against a frontend shipping weekly), or an editing canvas of its own (every custom widget from 16 packs stops working there). UI_DESIGN's 'Plexus owns its canvas' line depends on this.
9. Wording: keep the decided mark 'Verified' or rename it 'Made' in the artist word table; a decided element changes only by your call.
10. B17: LLM providers get a fifth L1 contract defined in Rust, or an internal L2 Python protocol; the provider contract works either way but its home and test location differ.
11. Seed fate: whether agent/ and cognitive/ stay, the conftest split, narrowing the `unit` gate that runs 5,158 Comfy-Cozy tests per attempt, and the pyproject name; these gate the venv split and CI retarget.
12. Organ transport: raw /prompt plus /history only (no compatibility promise, already in the plan) or also Comfy API v2 through comfy-api-proxy (versioned and durable, but beta, a separate process, unreleased since 2026-08-19, /workflow is pre-replacement) behind one organ contract.
13. Harness frozen files: restore an attempt's edit to a contract-fixed file (an empty __init__.py) and continue, or keep dropping the whole attempt.
14. Overnight Houdini-closed windows for the harness: the GPU attempt median, the VRAM handoff measurement and any mutation run need them, and Appendix D blocks scheduling missions after M0 until the GPU number exists.
15. Licence policy table, territory and revenue facts: which models are cleared for which show, where you work from (the H3 licence excludes the EU, UK, Korea and USA for use and output), and whether any client crosses the LTX-2.x USD 10M threshold; Plexus records and quotes, you rule.
16. Jev routing: keep paying one outbound call per attempt (carrying pytest output) for a route that agrees with `first` by construction, or switch to `first` until routes can differ and keep Jev for Wake and UI choices.
17. Installs outside the repo venv and Cargo workspace, each a separate yes: a usd-core 26.11 measurement venv, OpenRV, cargo-deny and cargo-mutants, a newer uv, the embeddinggemma-2 pull (licence and date unknown, image embedding through Ollama unverified).

## Operating model

- Roles, unchanged and enforced: Joe decides and freezes tests (tests/acceptance/, CONTRACT.md, Spec patches, installs outside the repo venv and Cargo workspace); Claude plans, reviews, writes mission files and worker briefs, and scaffolds only what the worker cannot reach (pyproject, harness/**, .github/**, empty package skeletons, conftest) in its own commits shown to Joe; the local worker writes implementation one diff at a time; nothing merges itself and nothing touches main.
- One capability, one frozen test, one mission. Each node above names its first test as one behaviour with the oracle embedded; min_delta = 1; no-regression gates are the phases that were green when the mission started. The critical path interleaves the existing mission graph: M0 S2-S8 (today 10 of 11 failing, 1 kept at 4e494b3, last commit 950b997 so run 5 sees the S2 fix) → M2b → M3 → M1 (T7/T8) → M4 → M5 → M6 → M7 → Phase 3 Safety → M9.
- Measure before scheduling, and unmeasured blocks green. GPU attempt median (needs Houdini-closed windows), the 10 ms dirty closure, hashing throughput (done), VRAM handoff and /free behaviour, the repro class of Joe's top five workflows, OCIO parity on organ EXRs, openusd parity. A Rust module, a scheduler thread, a cache or a threshold is promoted by a number on Joe's machine or it stays where it is.
- Fix the brief and the structure before buying attempts. Structural rules (frozen empty __init__ files, a layers gate, a reply format) bind a 30B worker; prose does not. Set max_consecutive_failures to 2 now; read the ledger, not memory, for yield; put static context first for the prefix cache; swap the worker only on the bench table.
- Economics in the open: a weekly capsule reports kept-per-attempt, CPU-minutes per kept test, median minutes by device, outbound calls made, and the open decisions. Claude's tokens go to planning and review; frontier calls in the product are an escalation tier with a per-project dollar ceiling from measured usage.
- The engine is pinned by commit and upgraded as a second worker lane, never in place; T7/T8 run against each worker; packs arrive through the pack ledger, and the posture contract refuses a worker whose pack set, routes or address differ. One mission at a time; Houdini open means the worker runs on the CPU; the artist's frame time in Houdini is the first SLO, ahead of attempt yield.
- Adopt, don't compete. Vendor seams and standards are consumed where they ship (CacheProvider, client prompt_id, workflow_metadata, blake3 assets, governance's file set, App Builder data, UsdUI hints, UsdMedia AuthorshipAPI, UsdProfiles ClaimsAPI shape, UsdValidation, ColorInterop ids, OCIO interop_id, OTIO, C2PA) and Plexus differentiates on composition, identity, provenance, shots and takes, and a calm artist-first surface. Preview items get a watch row with a revisit trigger.
- A decision ledger with teeth: every decision names the test that enforces it or says unenforced; every external fact carries a last-verified date; every risk has an owner and closes on evidence in the same commit. Stale rows in the Blueprint and scaffold plan are fixed through this ledger first.
- Local first, fail closed, legal as guardrail: the harness and the product refuse remote inference unless declared and allowlisted with the fields sent; a local-only project blocks remote providers, partner nodes and hosted stages; licence and territory are recorded as data and shown as clauses, and Joe rules on them, never the code.
- Artist-visible landings are scheduled early on purpose: the duplicate-model report (eng.model-index at M1), the one-line receipt (vfx.plate-receipt at M6), the word table and shot view-model (ux.state-model after M4, no renderer), and 'Already made' on a repeat run (ux.takes-notes after M6). A plan that is four phases of plumbing with nothing on screen fails the Pentagram test that the idea leads.

## Considered and dropped

- comfy.v2-contract-seam as a default second transport: comfy-api-proxy is beta, unreleased since 2026-08-19 with nine core minors since, its /workflow returns the pre-replacement graph so the 'same receipt on both transports' test fails by construction, and its metadata limits disagree between the release note and the spec. Kept only as Joe's option behind a smoke test.
- vfx.farm-organ: studio value, not Joe's (one workstation); farm job ids are farm-assigned so 'job id = intent hash' does not hold (Deadline Cloud returns job-<hex> and clientToken has no documented retention), and Thinkbox Deadline 10 has been in maintenance since 2025-11-07. Dedupe belongs in Plexus's own intent ledger whenever a farm arrives.
- rust-in-usd.rust-resolver-shadow / usd.rust-resolver-shadow as stated: models are asset-valued attributes USD never opens, expression variables are evaluated before any resolver runs, the settled design uses stock ArDefaultResolver, and a shadow-only error breaks parity by design. Integrity moved to eng.model-index (verify at dispatch); the shadow resolves `${PLEXUS_STORE}` natively with DefaultResolver plus set_expression_variables.
- rust-in-usd.free-threading-policy as a node: usd-core publishes no cp314t or abi3t wheels, so there is nothing to design for; reduced to one pure-Python check before any pxr import and a line in the decision ledger, with Joe answering whether py.rs declares gil_used = true.
- cto.structured-reply: the git-apply failure class has had zero occurrences since 15bc013 and whole-file blocks already exist; the useful part (options.seed) is folded into cto.harness-economics; revisit only if apply-stage drops return in the telemetry.
- cto.same-cause-breaker as designed: its (step, gate, test) key never repeated three times on the record (the longest streak is 2), it needed cross-run memory the harness lacks, and the operator's STOP file already broke runs 2 and 3. Replaced by the max_consecutive_failures knob and empty __init__ scaffolds in cto.harness-economics.
- cto.oracle-strength (cargo-mutants at mission end) as a node now: it cannot run before S3 and S7 land, and `cargo install` is outside the workspace (Joe's call). A hand-written mutation fixture for compile()'s scope check lives in cto.decision-gates until then.
- comfy.durable-job-ledger in plexus-core under the L1 Ledger contract: the Ledger contract is Hanish foresight (precommit/settle), Patch 01-C says core never sees a prompt_id, and ws events are hints not transitions. Rehomed as org.job-ledger in organ Python.
- rust-in-usd.durable-ledger-sqlite's hash-chained rows: duplicates F4's per-layer provenance chain; the in-flight-only sqlite outbox survives inside org.job-ledger without the chain.
- rust-in-usd.memory-record-identity's collapse of identical records into one prim: engages memory rule 4 ('never auto-deduplicate') and assumes Option C before Joe chose; folded into usd.memory as a content id that never dedupes without Joe's reading.
- usd.visual-recall as a standalone node: the documented Ollama /api/embed is text-only, embeddinggemma-2's licence and date are unstated, and the pull is an install for Joe; kept as a gated 5-minute probe inside usd.memory with a deterministic fake-embedder test.
- usd.version-floor-guard's fixed 'usdc 0.8.x' rule and `${` regex: 26.5 itself writes usdc 0.10.0 for path-expression collections (which the memory layer needs), and prompt text in authorship inputs[] would false-positive; replaced in usd.floor-guard by a rule relative to what 26.5 writes plus resolved-value checks.
- comfy.engine-lock's 'offline worker' premise and its cycle with worker-fingerprint: --offline is a frontend CSP; the lock is now a leaf (eng.lock) and the fingerprint lives in eng.pack-ledger with the edge running one way.
- ai.organ-capability-report's Outcome-returning capabilities() carrying live vram_free: contradicts CONTRACT.md §8.1 (list[str], interrogated at registration) and T0's cached string[]; split into static capabilities and a separate snapshot() in org.capacity, with quant formats listed only after a probe.
- ai.gpu-lease as a rank-2 Rust module with a 'never above vram_total' invariant: Windows reports per-process VRAM as N/A, /free's effect under comfy-aimdo is unmeasured, and the plan's own rule is Rust on a measured miss; replaced by a Python exclusive lease with an unattributed bucket in org.capacity.
- comfy.worker-pool's '/free handoff' as asserted: POST /free sets flags and returns 200 before anything is released; replaced by /free then polling /system_stats, with the 46 GB reload measured first.
- vfx.matte-bounded-proof's exr-crate promotion and its naive first test: the exrs crate lacks DWA, deep and HTJ2K, and a real inpaint changes every pixel through the VAE; replaced by host-side composite-back on OpenEXR in Python in vfx.proof-of-change.
- vfx.worker-hardening's '--enable-manager absent' check and S effort: the legacy Manager loads regardless; the posture check needs a live route probe and filesystem pack commits, and gating organ.submit would break frozen T7; merged into ai.locality-posture as an opt-in per-project contract.
- ux.artist-vocabulary's rename of the decided 'Verified' to 'Made' as a free choice and its seven-states-onto-five-marks with no table: Joe decided the marks; a state-to-mark table lives in ux.state-model and the wording is Joe's.
- ux.shot-layer at /Project/Shots: outside the decided NodeGraph container where sibling graphs cannot connect; moved under /Project/Graphs or a Patch 02 amendment, Joe's call.
- ux.notes-as-opinions in the session layer with a save-and-reopen test: the plan defines that layer as in-memory; notes move to a persisted notes layer in ux.takes-notes once Joe sets the writer order.
- ux.recipe-face's Sdr-metadata ShownIf and its claim that App Builder data 'arrives with its face': ShownIf belongs on attributes via UsdUI hints, and the real extra.linearData holds only node-id/widget pairs with no labels or groups.
- rust-in-usd.model-hash-once's 'one stream per NVMe' and 'Rust wins nothing' as proven: four streams measured 2.6x one stream, and sha2-vs-OpenSSL per-core was never compared; eng.model-index uses about four threads per NVMe and states the comparison as not measured.
- Tagging the current engine as 'stock ComfyUI v0.34.0': it is v0.34.0-21-g3216c62e with untracked files and Comfy-Cozy packs symlinked in; 'stock' is now defined in eng.lock as commit plus allowed pack set.
- Registering Plexus under the comfyui.agent v1 entry point: built for Comfy's own agent at 0.1.0rc7, whether two providers coexist is unknown, and it would mean co-tenancy with an unstable API.
- The Nuke premise 'USD 25.08, Python 3.13 through CY2027': Nuke 17.1 has shipped with an unknown USD version and 17.0 is CY2025 (Python 3.11); usda-only exchange is deferred until measured, and the two existing Nuke-ComfyUI bridges are the comparison baseline.
- comfy.result-receipt as a separate node: merged into vfx.plate-receipt with its 'executed-graph hash' relabelled 'submitted graph (post-replacement)', since loop projection and expansion are not in /history.
- vfx.disclosure-credentials as a standalone node: it needs a review-proxy encoder no node provided and a legal framing that is Joe's; folded into vfx.dcc-handoff behind ux.viewer's proxy maker.
- cto.worker-bakeoff's candidate list: gemma4:latest is the 8B E4B, not the 31B, and hrt-coder was missing; corrected and folded into cto.harness-economics as the bench verb, dropping its gpu-lease edge since profile.py already routes to CPU with Houdini open.

## Verification record: what the skeptic pass refuted

### `comfyui-exoskeleton`

- **Claimed:** workflow_metadata (v0.40.0, #16763) is 'not on binary preview frames' and is stamped on an enumerated list of seven prompt-scoped message types.
  **Found:** The same release that shipped workflow_metadata also stamps PREVIEW_IMAGE_WITH_METADATA frames, for clients that advertise supports_preview_metadata. Only the legacy UNENCODED_PREVIEW_IMAGE path is left unstamped. Stamping is not limited to a list of event types: any payload that carries prompt_id gets it, so execution_error (which carries prompt_id, local execution.py:701-712) is stamped as well. The metadata keys are spread at the top level of the message, and the message's own keys win on a collision. They are not nested under a 'workflow_metadata' key. The cap counts characters of the json.dumps output, which is ASCII by default, not raw bytes.
- **Claimed:** comfy-agent 'appears only as 0.0.0.dev0 in a bot report' on PR #17241.
  **Found:** An installable local release candidate has been on PyPI for 12 days. The status should stay preview, but the vendor's local agent is weeks away, not an abstraction. The blog (2026-10-01) says 'beta' and the current docs say Cloud is 'generally available', so the two sources disagree.
- **Claimed:** Open question: what the 'Comfy Compiler' (v0.35.0, #15861) does is unknown from the pages read.
  **Found:** This is answerable. It changes VRAM allocation behaviour, not output caching, so it does not affect a CacheProvider. It does affect the worker-pool GPU-handoff measurement. Whether it is on by default, and which flags control it, remain unknown from the page.
- **Claimed:** comfy-mcp tools include search_nodes.
  **Found:** The tool name is wrong. The two pages also disagree on the tool count (39 against 41). Version 0.10.0 was already current on 2026-08-11, so comfy-mcp has had no release in about 12 weeks, while comfy-cli shipped 1.15 to 1.24 over the same period.
- **Claimed:** Claim on node replacement, why_it_matters: provenance must hash the graph that '/history/{id} (or the proxy's GET /jobs/{id}/workflow) returns', treating the two as equivalent records of what ran.
  **Found:** The proxy records what it sent, which is the graph before replacement. ComfyUI rewrites class_type after it receives the POST, so the two graphs differ exactly in the case the claim exists to catch. Only ComfyUI's /history carries the graph after replacement. Even /history does not hold the runtime-expanded graph or the loop-projected nodes (PR #16227: iterations are 'fresh queued graph nodes'). So 'hash what actually ran' should read 'hash the graph as submitted after replacement, plus the pack digests that make expansion deterministic'.

### `rust-in-usd`

- **Claimed:** The openusd ROADMAP's 'authoring transactions on main only' means 0.8.0 has no authoring transactions, so 0.8.0 fails Blueprint §13.4 partly because transactions have not shipped in a release.
  **Found:** The ROADMAP's version column ('main') is stale. Property-level transactions, and an atomic multi-layer batch_edit, shipped in openusd 0.8.0 on 2026-10-11. Shared layers really are unreleased. The lens is still right that openusd is not promotable, but the blocker is shared layers plus parity, not transactions. One question is Joe's to answer, not settled: does 0.8.0's transaction scope meet §13.4's 'authoring transactions'? The ROADMAP still lists queued arcs, variants, API-schema apply and spec removal as remaining, and Plexus result authoring needs API-schema apply (PlexusAssetAPI) and payload arcs. Blueprint §13.2 ('Shared layers and authoring transactions are on main but unreleased') carries the same stale reading.
- **Claimed:** How a custom ar::Resolver or sdf::FileFormat is registered with an openusd 0.8.0 Stage is unknown (finding 4, open question 1, and the shadow-auditor risk).
  **Found:** The resolver half has a documented answer. The file-format half has a documented 'not yet'. A custom FileFormat can be implemented in 0.8.0 but cannot be plugged into a Stage, so 'the only place Rust can sit inside a USD composer natively today' narrows to a Resolver.

### `vfx-production`

- **Claimed:** Finding 4 (OCIO): 'The OCIO docs and GitHub notes disagree on 2.5.1 ABI compatibility.'
  **Found:** Both sources say the same thing today. The rest of finding 4 checks out: 2.4.2 dropped the Preview label (2025-03-19), 2.5.0 shipped built-in ACES 2 configs (2025-10-01), 2.5.1 2026-01-13, 2.5.2 2026-05-13, 2.6.0 2026-10-01, and ACES moved to ASWF on 2025-08-06.
- **Claimed:** Finding 8 (Cryptomatte): 'A user review says [CoCoTools] does not decode them into named object masks.'
  **Found:** The cited source has no review. The underlying point, that nothing decodes Cryptomatte IDs into masks, rests only on a search summary (a WebSearch on 2026-11-02 attributed it to the author's own notes). The Karma half is confirmed: https://www.sidefx.com/docs/houdini/solaris/support/cryptomatte.html (H22.0) says 'object name is the full path of the geometry prim', CPU and XPU.
- **Claimed:** Finding 11 (Nuke): 'No ComfyUI integration was found.'
  **Found:** Two third-party bridges exist, and one shipped a release three weeks ago. Comp artists already have a Nuke-to-ComfyUI path that bypasses USD. Plexus's handoff has to beat it, or interoperate with it.
- **Claimed:** Finding 5 why_it_matters: 'hython or Nuke, which run 3.13 through CY2027'.
  **Found:** Nuke 17.0 is on Python 3.11, not 3.13. The conclusion still holds, because abi3-py311 covers 3.11, but the version premise is wrong for Nuke. The Houdini half is right: Houdini 22 ships Python 3.13.17 (https://www.sidefx.com/docs/houdini/licenses/index).
- **Claimed:** Finding 15 (supply chain): 'ComfyUI v0.34.0 ... enables Manager only with `--enable-manager`', and the worker-hardening advancement built on it ('started without --enable-manager (no in-band installs)').
  **Found:** On Joe's machine the in-band installer is live whether or not the flag is set. A posture check that reads launch flags or /object_info cannot see it. The check has to probe the live worker for those routes, or refuse the pack by directory.

### `local-and-frontier-ai`

- **Claimed:** Finding 6: most installed video weights are larger than the card, the transformer-only fp8 (25.0 GB) and MiniMax-H3 int8 (21.0 GB) among them, and only the LTX-2.3 Q4_K_S GGUF (16.7 GB) fits with room to spare.
  **Found:** In the same unit, 25.0 GB and 21.0 GB are both smaller than the 25.76 GB card, so only three of the five files (46.1, 29.1 and 29.5 GB) are larger than it. The 'only one fits' line also leaves out the 15.7 GB LTXV-13B fp8. More important, file size was the wrong number to compare. Finding 2 says comfy-aimdo streams weights, so what matters is measured vram_free (18.0 GB today, with Houdini open) against measured peak VRAM per model, resolution and frame count. Nobody has measured that peak. The conclusion that a 17-18 GB LLM can't stay loaded during a hero render still holds, but on measured free VRAM, not on file sizes.
- **Claimed:** Finding 12 (the bake-off half): Gemma 4 31B-it is one of the Apache-2.0 local agent models on Joe's disk, and Qwen3.8-27B is a dense 27.8B model released 14 Aug 2026.
  **Found:** The 31B model isn't on disk. The local gemma4 has about 4.5B effective parameters, so it isn't a like-for-like agent or bake-off candidate. 27.8B appears in no source, and 14 Aug is a last-modified date, not a release date. The Apache-2.0 licences themselves are confirmed (HF tags, 2026-11-02).

### `artist-ux-pentagram`

- **Claimed:** Comfy Agent: 'Sources conflict on local availability' because comfyui-wiki 'claims local support'; status given as one 'preview'.
  **Found:** The two sources agree: Cloud now, local and desktop later. comfyui-wiki does not claim local support. The status also needs splitting. Shipped: Cloud beta, announced 2026-10-01 (comfyui-wiki gives that launch date, which the lens called unknown). Announced: desktop and local. Joe's 1.51.9 bundle has no agent string (re-grepped 2026-11-02), which fits that split. The positioning point (parked, diffed, local-first proposals vs Comfy Agent's Stop and tab bugs) still holds.
- **Claimed:** 'Prism is previewing a ComfyUI plugin' (cited as preview, undated, prism-pipeline.com/?p=8518).
  **Found:** The plugin has shipped: Early Access in v2.1.3 on 2026-07-09, then open-source release in v2.1.4 on 2026-10-15. The rest of the finding checks out. The AYON post dateline is 2026-05-06 with page metadata 2026-10-22, and it is on GitHub and becoming the official addon. Its quote 'No loose output folders. No guessing which graph made which result.' is verbatim, though it says outputs 'can be versioned', not 'published as versions'. comfy.org/solutions/vfx has no EXR, OCIO, ACES, shot versioning or USD. With two studio-pipeline vendors now shipping ComfyUI integrations, the competitive point is stronger than the lens put it.
- **Claimed:** ComfyUI Assets panel: 'The link back to the source workflow is only metadata embedded in PNG/WebP.'
  **Found:** PNG/WebP metadata is the route only for imported files. Generated files reopen their workflow from the asset library. The real gap Plexus fills is still there: no versioning, no shot, no content identity. But the claim about how Assets link back to their workflow is wrong.

### `cto-practice`

- **Claimed:** Finding 15: 'Three cloud-routed models are present in the local Ollama' (minimax-m3.1-flash, deepseek-v4.1-flash, glm-5.3-flash).
  **Found:** The count is wrong. Ten `:cloud` tags are pulled. GET /api/tags gives each of them `remote_host` https://ollama.com (or :443) and a size of 308 to 389 bytes: minimax-m3.1-flash, deepseek-v4.1-flash, glm-5.3-flash, deepseek-v4-flash, kimi-k3, glm-5.2, nemotron-3-ultra, deepseek-v4-pro, glm-5, kimi-k2.5. The point behind the finding (localhost does not mean local inference) still holds, and holds more strongly.
- **Claimed:** Finding 8 and cto.pack-ledger: for 21 of 59 packs 'no commit exists to pin them', so 'for a third of the library [a pack version] does not [exist]', and 'a content digest is the only version that exists for all of them'.
  **Found:** Of the 21 packs without .git, 12 are Comfy Registry installs. Each has a `.tracking` file and a `pyproject.toml` version: kjnodes 1.5.0, rgthree 1.0.2608312342, ipadapter_plus 2.0.0, WanVideoWrapper 1.4.7, essentials 1.1.0, controlnet_aux 1.1.5, ic-light, lora-manager, marigold, ollama, sam2 and flux-prompt-generator. The 4 symlinked packs resolve into git repos: three into G:\Comfy-Cozy (HEAD ee34d9e) and dyno_probe into G:\dyno (HEAD 0804312). Only 5 packs have no recoverable version at all: ComfyUI-DeterministicLLM, ComfyUI-VideoITG, bug12047_hotfix, comfyui-3d-viewport-bridge and comfyui_jet_nemotron. A content digest is still the right identity, because a registry version does not prove the files on disk. But the 'a third has no version' framing is false. The counts 21 of 59, 4 symlinks and __pycache__ in all 59 do check out.
- **Claimed:** Finding 6: 'the `core` (maturin build) and `cargo` gates passed at baseline' prove that PyO3 0.30 abi3 'builds and imports' on Python 3.14.2.
  **Found:** The core gate is not a maturin build. harness/plexus_loop/build_core.py runs `cargo build --release --features python -p plexus-core` and copies plexus_core.dll to plexus/_core.pyd. Maturin is installed but nothing uses it. Neither the gate nor any phase-1 test imports plexus._core, so the cited evidence proves the build, not the import. The conclusion is still true: I copied .plexus_loop/cargo-target/release/plexus_core.dll into a scratch package as _core.pyd, and `python -I` on 3.14.2 imported it and returned __version__ 0.1.0. That module body is a single `m.add`, so this proves the abi3 import works, not that any real API surface works.
- **Claimed:** Finding 10: 'Joe runs v0.34.0, whose own release date could not be verified from a primary source.'
  **Found:** Joe's own clone is a primary source. `git log -1 v0.34.0` gives 2026-08-25, and v0.34.1 (2026-08-26) and v0.34.2 (2026-08-27) also exist. More importantly, Joe is not on a release. `git describe` returns v0.34.0-21-g3216c62e, an untagged master commit from 2026-08-31, and the ComfyUI tree holds untracked files (DYNO_PROBE_DESIGN.md, LATENCY_AUDIT_REPORT.md, STABILITY_AUDIT_REPORT.md). comfyui_version.py says 0.34.0 only because it is generated.
- **Claimed:** cto.same-cause-breaker justification: '4 consecutive S2 drops on the same gate' would be caught by a breaker keyed on (step id, failing gate, first failing test id) after 3.
  **Found:** On the measured record that key never repeats three times. The four layers drops alternate. Run 2 attempt 1 put pxr in a package __init__ and run 2 attempt 2 hit an import cycle (per harness/CAPSULE.md). Run 3 attempt 1 failed test_python_has_no_import_cycles (plexus.core -> plexus.core.axon -> plexus.core) and run 3 attempt 2 failed test_pxr_only_from_rank_two_up. The longest same-key streak is 2. Those drops also span two runs 11 hours apart, and `_run()` starts with `attempts = []` and never reads the ledger back, so the breaker would also need cross-run memory, which the advancement does not list. Between run 2 and run 3 Claude had already re-planned (3ac9c54, 4c1439b), which is what the breaker is meant to force.
- **Claimed:** Finding 11: the Upscaler-4K ban was on '21 Oct after 790 downloads; the year is inconsistent in the source and unverified.'
  **Found:** The year can be resolved. The post is dated Jan 11, 2026, and its timeline gives 'Oct 17 – Oct 19, 2025' for the uploads and 'Oct 21, 2025' for the ban. The '2024' in the summary is a typo. So the ban was 21 Oct 2025, after 790 downloads.
