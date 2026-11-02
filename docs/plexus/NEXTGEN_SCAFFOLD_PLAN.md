# Plexus · Next-generation scaffold plan

Status: **draft for Joe.** Nothing in this plan has been applied. Written Nov 1 from four reference reports (§3) and one refinement round (three independent designs, a Fable-model judge, three critics). The full design-variable list is in the appendix.

**Goal (Joe, Nov 1):** create the next generation of ComfyUI, locally, using frontier and local AI, from the ground up — Rust where appropriate, OpenUSD as the substrate. Plexus is the next generation of Comfy-Cozy. Comfy-Cozy (`G:\Comfy-Cozy`) and SYNAPSE (`C:\Users\User\SYNAPSE`) are architecture references only; nothing is copied from either.

---

## 1 · First principles: what the product must be

**The goal, reduced to what can't be removed.** A local successor to ComfyUI has to do seven things. Everything else in this plan is a means to these.

1. **Run generative graphs on Joe's own GPU, against Joe's own models.** Local first; frontier models are an escalation, never a requirement.
2. **Keep the graph as data people and agents can author, diff, compose and branch.** That is USD layers, one writer per layer, with composition (not application code) deciding whose opinion wins.
3. **Never compute the same thing twice.** Same op, same version, same inputs, same models → same identity → reuse (F7). ComfyUI's cache can't survive a restart or be shared, because its identity is structural, not content-based (§3.3).
4. **Run the ecosystem that exists.** 43 of Joe's 59 custom-node packs import ComfyUI's own library, so existing nodes run in a stock ComfyUI worker behind the organ contract. The successor wins in the layer above it: identity, a durable queue, cross-run caching, the graph as versioned data.
5. **Let agents help without being trusted.** Neurons wake on cheap predicates, act within budgets, write only to their own layer through a gate, and park anything that needs Joe.
6. **Make every result provable:** which graph, which op versions, which model hashes, which environment.
7. **Never block.** Execution is asynchronous, progress is honest, cancel is a request until confirmed.

**Graph engineering, as rules rather than intentions:** typed ports and explicit edges; an acyclic module graph enforced by a frozen test, not a comment (Comfy-Cozy's cycles hid in function-scope imports, §3.1); identity by content; pure nodes with side effects only at the organ edge; incremental evaluation from change notices; the graph itself versioned in USD.

---

## 2 · The architecture as a graph

Refinement round 1 (Nov 1) produced this from three independent designs (harness-first 8/10, measurement-first 8/10, product-first 7/10), synthesised by the Fable advisor and attacked by three critics. The critics' seven blocking objections are applied below; the corrected text says so.

### 2.1 · Rust

- **Phase 1 and 2: one crate, `crates/plexus-core`** (`cdylib` + `rlib`; feature `python` → pyo3 0.30 with `extension-module` and `abi3-py311`; sha2 arrives with identity in M3). It never depends on openusd or tokio.
- **`crates/plexus-usd` joins only at M9**, as a library plus a `plexus-shadow` binary over openusd 0.8.0. It is never linked into `_core`. Python drives it over JSON lines on stdio, single-threaded, because openusd's `Stage` is `!Send`. The only allowed crate edge is `plexus-usd → plexus-core`; the reverse would be a Cargo cycle, because `plexus-usd` implements core's `Composer` trait.
- **Exactly two workspace members, ever** (Blueprint §13.3). No `[target.'cfg(...)']` table and no `build.rs` anywhere under `crates/` (T8 scans `.toml` unstripped).

**Module ranks inside `plexus-core`** — corrected after the critics found the first table contradicted itself (a `#[pymodule]` in `lib.rs` has to name pyo3; `canon` and `graph` return `Outcome` from the same rank):

| Rank | Modules |
|---|---|
| root | `lib.rs`: `mod` lines only, plus `#[cfg(feature = "python")] mod py;`. Exempt from the rank check. |
| 0 | `error.rs` |
| 1 | `outcome.rs` |
| 2 | `predicate.rs`, `budget.rs`, `canon.rs` (M3), `graph.rs` (M5, only if promoted) |
| 3 | `composer.rs` (trait + plain-data types, M9) |
| 4 | `py.rs`, the only file that names pyo3; `#[pymodule] fn _core` lives here. Nothing imports it. |

A module may `use crate::X` only for a strictly lower rank.

### 2.2 · Python

| Rank | Modules |
|---|---|
| 0 | `plexus._core`, `plexus.schema` (stdlib only) |
| 1 | `plexus.organs.protocol` (`Job`, `AssetRecord`, neutral vocabulary), `plexus.core.predicate` (re-exports `_core.PredicateError` and `compile_predicate`), `plexus.core.ports` (M4) |
| 2 | `plexus.membrane.gate` (stdlib; path strings in), `plexus.membrane.exchange` (pxr), `plexus.core.stagekit` (pxr) |
| 3 | `plexus.core.axon` |
| 4 | `plexus.core.neuron`, `plexus.graph.{encode, index, dirty, keys}` (M4–M6), `plexus.core.results` (M6) |
| 5 | `plexus.projection` (M4+) |
| 6 | `plexus.organs.cozy[.*]` — the only home for engine vocabulary (T8); imports only `organs.protocol` and stdlib |
| 7 | `plexus.surfaces` |

**Rule, corrected:** the critics showed modules at the same rank must import each other (`stagekit` → `exchange`; `dirty` → `index`; `results` → `keys`), so the Python rule is **no import cycles, plus the hard edges**, not strict rank. Hard edges, each its own assertion in Joe's frozen `tests/acceptance/guards/test_layers.py`: `plexus.core.*` never imports `plexus.organs.cozy`; nothing under `plexus/` imports `agent.*` or `cognitive.*` (module **or function** scope); only rank ≥ 2 imports `pxr`.

### 2.3 · What crosses the Python–Rust boundary

Rust owns the state of every pyclass; Python owns the stage, the clock, the threads and all I/O. Only `str`, `int`, `float`, `bool`, `bytes`, `None`, `list`, `tuple`, `dict` and Rust pyclasses cross — never a pxr or openusd object, a tensor, a callable or a file handle.

**Phase 1 (`plexus._core`):**

- `compile_predicate(source: str, scope: str) -> Predicate`, or raises `PredicateError` (a `ValueError` subclass; the message names the column or the offending path) for bad syntax, `OR`, a non-absolute path, or a path outside scope.
- `Predicate.paths() -> list[str]` — the attribute paths Python must read through pxr.
- `Predicate.seed(values)` — fills only empty delta slots; registering never wakes (T2).
- `Predicate.eval(changed: list[str], values) -> bool` — pure.
- `Predicate.commit_wake(values)` — the only overwrite of the delta cache, called after the budgets admit.
- `Budget(wakes: int, window_s: float)` with `peek(now) -> str` (pure) and `admit(now) -> str`, each `"wake" | "trip" | "mute"`; `now` comes from the runtime's injected clock, so T3's fake clock works.

### 2.4 · USD

- **Graph container:** `/Project` (typeless, `PlexusProjectAPI`) › `/Project/Graphs` (`def NodeGraph`) › `/Project/Graphs/<g>` (`def NodeGraph`; nested NodeGraphs are subgraphs) › `<g>/<n>` (`def Shader`). A NodeGraph root, not a Scope: the OpenUSD report found sibling graphs under a typeless parent can't connect (`CanConnect == False`). Isolation is publication-gate policy, not a prim type.
- **Node types:** Sdr node definitions, one `.usda` file per op, never runtime schemas (the schema registry freezes at pxr load). **Op ids use `plexus.op.<name>.v<major>`**, not `@<ver>`: `Sdf.Path.IsValidIdentifier('blur@2')` is False, the defaults class needs the id as a name fragment, and `@` is usda's asset-path delimiter.
- **Edges:** UsdShade connections only, one source per input unless the Sdr def marks it multi. Opaque ports (images, models, latents) are `asset`-typed, so the downstream input is a path plus hash (F8). Compatibility: exact port type or `any`, the controlled form of the `*` wildcard 10 of Joe's packs use.
- **Op defaults** come from `specializes` on a `/Project/Defaults/<op>` class; `inherits` is reserved for deliberate broadcast. Variants for authored branches; references for subgraph reuse; results payloaded.
- **Notice intake:** inside the callback (the only place the notice is valid), copy info-only and resynced paths, plus `GetChangedFields` per path (verified on 26.5), into a plain `StageEvent`. **Dataclass defaults use `field(default_factory=dict)`** — a literal `{}` default raises at class definition and would break `plexus.core.axon` and `organs.protocol` imports (a critic's catch).
- **Schema registration in-process** — a critic's blocking catch: T7 asserts `PlexusAssetAPI in GetAppliedSchemas()` in the pytest process, and 26.5 filters unregistered schemas out, so only T0's child process seeing them is not enough. Recommended: one rank-2 module every runtime entry point imports first calls `Plug.Registry().RegisterPlugins(str(plugin_dir()))`. **Measure before `run`** whether a registration made after the first stage use is still seen; if not, the ordering rule goes into the worker brief.

---
## 3 · References, and what each one teaches

### 3.1 · Comfy-Cozy (`G:\Comfy-Cozy`, `ee34d9e`, v5.10.0)

Report received Nov 1. **Bottom line:** the bones are sound (one dispatcher, a gate that costs microseconds, deterministic JSON, keyless rails). The trouble is duplicated authority, cycles hidden by lazy imports, and engine vocabulary everywhere. Plexus keeps the jobs and drops the shapes.

**Tangles found** (AST import scan, module-level vs function-scope): cycles broken only by laziness — tools↔brain, tools↔stage (`stage/stage_tools.py:17`), stage↔session_context, llm→brain (`llm/swap.py:123`), and gate→stage (`gate/checks.py:175`), so the safety gate depends on the substrate. The "cognitive never imports agent" rule holds only through function-scope imports (`cognitive/pipeline/autonomous.py:56-74`). Engine vocabulary sits in 13 of 39 stage files, 14 of 24 cognitive files, 8 of 17 brain files, and the "agnostic" engine base class (`engine/_base.py:57,61,72,85`).

| Job | What hurt | Where it lands in Plexus |
|---|---|---|
| Composition | Two arbiters: a dict LIVRPS engine whose "S" means Safety and sits on top (`cognitive/core/delta.py:20-27`), and a 1000-edit FIFO that silently reverts the oldest (`graph.py:19`) | One Composer contract in `crates/`, usd-core in `plexus/`; drop the dict composer (F0, F8) |
| Gate | Unknown tools default to REVERSIBLE (`risk_levels.py:249`) | Safety contract in Rust; unknown blocks (F9); never imports the substrate |
| `stage_write` | A prompt can set `sha256` and `source_url`, then provision against them | Writer sublayers with scope and protected attributes (F6) |
| Session state | Three stores diverged into a deadlock (CHANGELOG 5.0.0) | One writer, one sublayer, one scope, held in Rust |
| Engine | Base class names `prompt_id` and `class_type` | `plexus/organs/cozy*` only; job id = intent hash (F7) |
| CWM / arbiter / experience | Each exists twice | Drop now; foresight is Phase 4 ledger precommits |
| Ratchet / hyperagent / injection / constitution | Speculative, never audited | Ratchet already lives in the harness; drop the rest |
| LLM providers | Client captured once per conversation, so swaps reached half the app | `plexus/`, resolved on every call |
| Recipes, diagnosis, `workflow.lock` | Worked best: keyless, deterministic | Reflex tier; checks over plain data in Rust; hashing feeds F4/F7; engine facts belong to the organ |
| Surfaces | Three web bridges; unauthenticated `/agent/*` routes; blanket 120 s timeout | L5 with one bridge |

**Five lessons:** (1) one arbiter, one truth; (2) seam tests, not mocks — several things went green while broken; (3) boundaries are mechanisms, not comments: keep T8 and add an import-layer test for `plexus/` and `crates/`; (4) keyless deterministic rails are the product — build Reflex first; (5) measure, don't memorise, and pool transports from day one.

**Seed vs original:** identical `agent/` and `cognitive/` at v5.10.0 (CRLF only). `G:\Comfy-Cozy` alone has the July working-tree docs and tooling (REFACTOR_DIAGNOSIS_CHERNY_PASS.md, UNIFIED_HARNESS_7.2026.md, `tooling/harness/{aug3,cliorch,unified}`).

### 3.2 · SYNAPSE (`C:\Users\User\SYNAPSE`) — ideas only, in Plexus's terms

Research report received Nov 1. Paths are relative to the SYNAPSE checkout. Nothing below is code or a contract; each idea is restated for Plexus with its own reason.

**Ideas worth having**

| # | Idea, in Plexus's words | Lands in | Evidence it worked, or failed |
|---|---|---|---|
| 1 | **Waiting for Joe is a parked state, never a blocking wait.** A neuron records its proposal and goes dormant; Joe's approval is an opinion in the session layer, and the neuron's predicate wakes on it. | Rust scheduler + surface | Failed in SYNAPSE: its gate never fired, because a blocking poll slept on the thread that draws the approval card (`CLAUDE.md:66`; `tests/test_panel_consent_no_freeze.py:1-11`) |
| 2 | **Never block the thread that owns the stage.** A turn is a write-once future; cancel works per turn and globally; work that misses its deadline before it starts is dropped, not run late. | `plexus._core` boundary, the stage thread, organ deadlines | Worked: removed a 30 s-per-call deadlock (`docs/sprint3/spike_2_4_design.md:72, 96-97`; `python/synapse/host/turn_handle.py:28-35`) |
| 3 | **Notice intake rules:** copy each notice to frozen plain data; filter at the boundary; isolate consumer errors and count drops (and flag them visibly, not at debug level); flip an alive flag before detaching; re-check subscription ownership after any handler that loops; react only to settled events. | Python axon → Rust heartbeat (T2, T6) | Unit-tested against a fake event module only (`python/synapse/host/tops_bridge.py:386-388, 462-498`; `scene_load_bridge.py:194-206, 238-252`) |
| 4 | **Resolve a recipe's scene bindings in code before any model sees the task.** Missing or ambiguous → `Unavailable`, nothing built. | L3 projection, Reflex tier | A 2-call recipe took 11 rounds; a required setting landed in 2 of 3 runs (`LATENCY_PLAN.md:62-68`; `README.md:110-114`) |
| 5 | **Verified means every required check ran and passed.** A check that didn't run → Unknown; one that failed → Broken. | Rust `Outcome`, organ results (T7) | `python/synapse/recipes/contracts.py:110-144` |
| 6 | **Three limits per turn: rounds, wall-clock, input tokens.** The last round runs with no tools and names the limit hit; unreported usage counts as unknown, never zero. | Rust budget gate (Spec §6 step 3 lacks wall-clock and the closing message) | One turn ran 15 min and 5.77M tokens before the round limit stopped it (`python/synapse/panel/claude_worker.py:372-404`) |
| 7 | **Small tool sets, cacheable prompt prefixes, no-model answers first; measure connection overhead before model cost.** | Neuron definition, organ transport | 99 tools per turn, median 138k input tokens, 0 of 111 turns hit the prompt cache; on Windows `localhost` cost 2.01 s vs 9 ms for `127.0.0.1` (`LATENCY_PLAN.md:12-60`) — matters for the ComfyUI endpoint and T1 |
| 8 | **A hashed symbol table of the pinned libraries** (usd-core 26.5's `pxr`, `openusd`'s API); a gate fails on any call to a symbol that isn't there. | Harness gate, `plexus-usd` | Phantom APIs were the top failure class; a live-runtime table cut false phantoms from 0.667 to 0 (`AGENTS.md:45-46`; `SYNAPSE_RULEBOOK.md:124-128`). Directly relevant: the 30B worker will invent `pxr` calls. |

**Do not take:** Houdini as the host (daemon in Houdini, the hython pin, main-thread dispatch as architecture); two write paths to the scene (Plexus keeps one, Spec §6 step 6, and should test that it is the only one); gates that classify but never block (breaks F9); Houdini undo groups as rollback (Plexus's transaction layers are real rollback — prove it in a test); scene hashes that fall back to timestamps in test mode (pretend capability, breaks F10); self-promoting routing shortcuts with no outcome reporting; fake host modules planted in `sys.modules` for tests; persona "specialists" that are only prompt roles.

**Against the Blueprint's `[v5 · after SYNAPSE]` items**

- **Confirmed:** F10 and the absence shapes; add a fourth case, a store present but with two owners, pointed at the one-handle rule. One handle per storage location (a Rust-held registry survives the Python module reloads that duplicated SYNAPSE's singletons). One conductor (Plexus's refuse-to-start lock is stronger than SYNAPSE's convention).
- **Confirmed rule, weaker mechanism:** §5.2 item 7 (acts that always need Joe) — the wait must be the parked state of idea 1.
- **Weakened:** §6 "a halt is immediate". Stop is a request; a timeout is not proof of stopping. A halt should end with each organ job confirmed cancelled or marked unknown, and a restart never resumes work by itself (`INTENT.md:88-106`).
- **Contradicted:** Spec §6 step 5 cites a "Synapse decision matrix". **No such thing exists in SYNAPSE** (zero hits across .md/.py/.json/.yaml/.toml). What exists is a cheapest-first cascade with hand-set thresholds (0.8, 0.5) — the guessed numbers §5.2 item 4 forbids. Plexus needs its own rule: the F2 cascade, the tier pinned per intent hash (F7), any new router run in shadow first, and no learning from outcomes until something reports outcomes.
- **Restate:** Spec §5 uses SYNAPSE identifiers (TurnHandle-style, the event-bridge pattern, the reconcile fix). The discipline holds in Plexus for its own reason: usd-core notices fire synchronously on the authoring thread and their data is valid only during the callback. The 50 ms debounce is Plexus's own.

### 3.3 · ComfyUI, from first principles (`G:\COMFY\ComfyUI` v0.34.0, `3216c62`)

Report received Nov 1. Library read: `G:\COMFYUI_Database` — 59 packs, 140 UI-format and 30 API-format workflows.

**Bottom line: the ecosystem is not a node contract; it is an import of ComfyUI's Python library.** 43 of 59 packs import `comfy.*` or `folder_paths`, and 9 monkeypatch internals (easy-use swaps `comfy.samplers.sample` and `comfy.lora.calculate_weight`). So running existing nodes means hosting a stock ComfyUI as a worker behind the organ, not reimplementing it. **The successor wins in the layer above the worker:** content identity, a durable queue, cross-run caching, and the graph as versioned data.

**How it works today:** demand-pull from OUTPUT_NODE sinks (`execution.py:1163`), one node at a time off a topological sort (782-797), lazy inputs (504-520), runtime expansion (579-613). The cache key is structural — class, IS_CHANGED, sorted literals, links as ancestor ordinals (`comfy_execution/caching.py:101-148`); non-primitive inputs become NaN and never match (64). Ports are plain strings with unions, `*` and a tolerated `__ne__` hack (10 of Joe's packs use it). The V3 typed schema exists (`comfy_api/latest/_io.py:1678-1735`) but 1 of 59 packs uses it. History is an in-memory dict capped at 10,000 and lost on restart (`execution.py:1249`). Models are files identified by filename.

**Irreducible:** a typed DAG with demand-pull, lazy branches and runtime expansion; lossless import of both JSON dialects (40 of 140 UI workflows use subgraphs; widget values are positional); the `comfy.*` surface packs import and patch; the model-folder layout; per-node progress and previews; re-running only what a changed knob dirties; pack HTTP routes (12 packs) and JS extensions (27 packs).

**Accidental (where a successor does better):**
- **Identity.** No node-code version, no pack commit, models keyed by filename, tensors as NaN — so the cache can't survive a restart or be shared, and "same workflow" can't be proven. That is why Cozy grew `workflow.lock`.
- Stringly-typed ports; one process, one queue, one prompt at a time, history in RAM.
- In-process plugins with server privileges in one shared site-packages (LTXVideo broken by an internal rename; 3D-Pack and TensorRT disabled; real supply-chain incidents: LLMVISION, Impact-Pack via ultralytics, a Registry stealer).
- The workflow is a blob that needs live node definitions to decode.

**Rust candidates (unmeasured; §13.1 says a measurement promotes them):** intent hashing and key canonicalisation (exactness across processes, not speed); a content store for models and outputs (I/O-bound, rayon; measure by hashing Joe's Models tree); a durable multi-worker queue (tokio, deadlines); graph validation for imports (measure on Joe's largest LTX workflow). **Python stays** for `comfy/`, torch, every custom node and the worker. **Only plain data crosses:** graph JSON out; progress, asset paths and sha256 back. Never tensors or ModelPatcher.

**Compatibility under T8:**
- A stock ComfyUI in its own venv is the worker. Only `plexus/organs/cozy/` speaks its dialect. **The core holds a neutral IR** (op type, params, edges named by port) and the organ translates, so T8 holds by structure.
- Pass Plexus's correlation UUID into `/prompt`; `jobs.py:34-46` says it is stored and compared verbatim downstream. One empirical check (submit, watch ws, read `/history`) could delete Patch 01-C's reconciliation layer.
- Poll-for-truth stays on `/history`; the Plexus ledger owns durability, because both history and `/api/jobs` die with the worker.
- UI-format import needs `/object_info` from a live worker: cache it keyed by pack commits.
- Plexus caches across runs by content (F7); ComfyUI keeps within-run caching. Optional seam without a fork: an organ-side CacheProvider backed by the Plexus store.
- Conflicting packs become separate workers with separate venvs, pooled as organ endpoints.
- Imported graphs live on the stage as prims referencing a JSON sidecar (F8).
- **T8 traps:** the regex scans `.json`, `.usda`, `.toml`, so a workflow fixture anywhere under `plexus/` outside `cozy/` fails; `\bcfg\b` catches an ordinary variable named `cfg`; `SaveImage` matches `SaveImageWithMetaData`.
- Cozy's `WorkflowSignature` buckets values (`agent/stage/workflow_signature.py:132-190`), so it can't serve as the F7 hash.

### 3.4 · OpenUSD as the graph substrate (checked against usd-core 26.5)

Report received Nov 1. **Recommendation:** the graph is UsdShade — a `NodeGraph` container, `Shader` nodes, `info:id` = op id. Node **types** are Sdr node defs authored as `.usda` and registered at runtime, not schemas. One new codeless `PlexusNodeAPI`. This adds to Spec §3; the frozen `/Project` + `PlexusProjectAPI`, `PlexusAssetAPI`, `/Plexus/Neurons|Organs` and `/Exchange/<id>/**` stay.

**Proposed encoding**

| Thing | Encoding |
|---|---|
| Graph root | `/Project/Graphs` is itself a `NodeGraph` (under a typeless parent, sibling-graph `CanConnect` returned False) |
| Graph | `/Project/Graphs/<g>` NodeGraph; `inputs:*` exposed params, `outputs:*` graph results |
| Node | `<g>/<n>` `Shader`, `info:id = plexus.op.<name>@<ver>`, apiSchemas `PlexusNodeAPI` + `NodeGraphNodeAPI` |
| Param / edge | typed `inputs:<p>` / `inputs:<p>.connect = <…/<m>.outputs:<o>>` |
| Op defaults | class `/Project/Defaults/<op>`; each node `specializes` it |
| Subgraph | a `def` with `references = @lib/<name>.usda@</Name>` |
| Model | asset path `${PLEXUS_STORE}/sha256/ab/<hash>.safetensors`, with `expressionVariables` per machine on the root layer |
| Result | `/Project/Results/<g>/<n>/k_<key16>` with `PlexusAssetAPI` (+ `plexus:cacheKey`, a spec patch); retries `k_…_r1` + `retryOf`; the node's `outputs:<o>` names the accepted asset |
| Cache key | sha256(op@ver, canonical resolved inputs, asset inputs as sha256, upstream keys). **Recomputed from the composed stage, never trusted from it.** Result-prim existence is the F7 lookup. |

**Writers, strongest first:** session (Joe) > `graph.usda` (human / UI) > `from_<neuron>.usda` each (advisory) > `layout.usda` (`ui:nodegraph:*`) > `results/` (runtime only, payloaded, usdc, rotated at 50k) > `nodedefs/`, `lib/` (read-only). Exchange per Spec §7; cross-project flow is `PlexusAssetAPI` prims through `/Exchange`, consumed as values.

**First-principles findings (each checked)**

1. **Node types can't be runtime schemas.** The schema registry is a load-time singleton (no re-registration handler in v26.05); an unregistered applied API gave `GetAppliedSchemas() == []`. Sdr can: `AddDiscoveryResult` took a Shader def live, `GetShaderNodeByIdentifier` returned typed inputs, and `ShaderSdrCompliance` caught a type mismatch. Needs a real `.usda` file, and `info:plexus:sourceAsset` must resolve to an existing implementation (F8). Replacement untested → versioned ids.
2. **Specializes for defaults, inherits for broadcast.** A library-tuned value survived specializes; inherits overwrote it. Defaults are composed opinions, so both composers see them.
3. **References remap edges** correctly; local beats referenced; `GetPropertyStack` names the winning layer, so per-parameter provenance is free.
4. **Variants for authored branches** (model A/B): a switch is a prim resync, and the other branch's results stay cache hits. Seeds are values.
5. **Payload the results**, so editing never composes them. Layer relocates only (26.11 removed prim relocates).
6. `ConnectToSource` doesn't enforce `CanConnect`, so EncapsulationRules and `ShaderSdrCompliance` run at the publication gate.

**Notice → dirty mapping:** `default` on `inputs:*` (info-only) → node + downstream via a reverse index; `connectionPaths` (info-only) → update edges, node dirty; prim resync (new node, variant switch, first opinion from a fresh writer layer) → re-read the node; `subLayers` on `/` → full re-index; `outputs:*` from results → downstream ready, not re-keyed; `ui:*` and Results → ignore. **Dirty ≠ run:** recompute keys, run only misses.

**Scale (in-memory, compose only)**

| Nodes | usda | open | Python edge index | dirty closure |
|---|---|---|---|---|
| 100 | 0.06 MB | 4.8 ms | 7 ms | 0.1 ms |
| 1k | 0.56 MB | 2.5 ms | 24 ms | 1.1 ms |
| 10k (95k attrs, 15k edges) | 5.6 MB | 22 ms | **238 ms** | 13 ms |

Notice delivery 4 µs; a 500-edit ChangeBlock is one notice with 500 paths, extracted in 0.55 ms; one class edit fanned out to 1,001 paths. 50k result prims: 44 MB usda, LoadNone 15 ms, payload load 111 ms. **Corrected by the refinement round:** the 238 ms is mostly pxr extraction, which stays in Python in any design; the per-notice dirty closure (13 ms here) is what breaks Spec §11's 10 ms, so Rust `graph.rs` waits for that measurement (§7).

**`openusd` 0.8.0:** has usda/usdc, all arcs, composed `connectionPaths`, a `ConnectionGraph` (sources, sinks, resolve_chain), UsdShade views, StageSink notices with incremental invalidation, `composition_errors`. Missing: Sdr (read nodedef layers directly); schema registry, fallbacks and property-stack queries exist on `main` only, so shadow `property_stack` waits. `Stage` is `Rc` + `RefCell`, so `!Send`: one composer thread, plain data out. No stage cache, no parallel composition.

**OpenExec: watch, don't build on.** 25.08 preview; 26.08 supports one connection only and its IR is "not yet ready for production"; absent from the 26.5 Python wheel (no `pxr.Exec`/`ExecUsd`/`Vdf`). Computations are in-process C++ plugins, not 30-second GPU jobs. Take its shape: value-key requests, sparse invalidation, a cycle is an error. Revisit when Python bindings and multi-connection dataflow land.

**Rejected:** (1) one generated typed schema per op — the registry freezes at load, so a new op restarts every conductor, openusd can't see schema fallbacks (parity drift), and op versions become schema migrations. (2) plain prims + relationships, or workflow JSON in an attribute — breaks F8, no typed ports or validators, arcs can't reach into a blob. **Kept as fallback:** typeless prims + `PlexusNodeAPI` declaring `providesUsdShadeConnectableAPIBehavior` (codeless APIs get a default behaviour, `connectableAPIBehavior.cpp` v26.05 L640-650).

**T8 note for the encoding:** example op parameters must avoid engine terms (`cfg`, sampler names) anywhere under `plexus/` or `crates/`; neutral op ids live in the core, and the organ maps them.

## 4 · Constraints the scaffold must respect

- **The frozen tests define done.** CONTRACT's surface, T0's four schemas and types, T1's single-process p95, T2's wake-only delta cache, T3's visible mute, T4's property stack, T5's allowlist, T6's save-on-land, T7's poll-for-truth organ, T8's vocabulary scan.
- **T8 is structural.** `\bcfg\b` matches a Rust doc comment, a Python variable or a `[target.'cfg(windows)']` table (only `.rs` gets `#[cfg(` stripped); `SaveImage` matches by substring; any ComfyUI fixture or generated node def saved as `.json`, `.usda` or `.toml` under `plexus/` outside `plexus/organs/cozy*`, or anywhere under `crates/`, fails.
- **Two crates, ever** (Blueprint §13.3), because every crate is compile time beside Houdini.
- **usd-core 26.5 is the composer of record**; openusd stays in shadow behind a parity test.
- **The worker is a local 30B model on CPU,** one diff per attempt, kept only when one more frozen test passes. A step that needs five things to land at once is a planning risk (S3 is the known one).
- **Claude plans and reviews; the worker writes implementation.** Scaffolding Claude writes is limited to what the worker can't reach, in its own commits, shown to Joe.
- **No-regression gates are the phases that were green when a mission started** — never the current target or a later phase. A gate over all of `tests/acceptance/` would make M1 unrunnable, because the harness refuses to start when a gate fails at baseline (a critic's blocking catch).

---

## 5 · Mission graph (harness)

Every mission is one harness mission: the metric is a frozen test path that fails at baseline, `min_delta = 1`, and each frozen test holds one behaviour with its oracle embedded. Guards (T8, layers, symbols) run as `[[gates]]`, never as metric targets.

| Mission | Target | Lands | What Joe adds first |
|---|---|---|---|
| **M0 · acceptance** (planned) | `tests/acceptance/phase1`, 11 items | S1–S8 of the acceptance plan, Option A. Three brief corrections before `run`: plugInfo `bases: ["UsdAPISchemaBase"]` (not `/TfType`), the T8 `cfg`/Cargo.toml rule, and the peek-then-admit budget order. Plus the in-process schema registration above. | Nothing required. Optionally `tests/acceptance/guards/test_layers.py` now: it passes trivially and rides as a gate from the first attempt. |
| **M1 · phase2** | `tests/acceptance/phase2`, **7 items** (T7 ×5, T8 ×2; the plan said 6 — re-count at setup) | `plexus/organs/protocol.py` → `plexus/organs/cozy/` (correlation id into `/prompt`, poll `/history` for truth, `/view`, hashlib sha256, env fingerprint) → `ctx.author_asset` | Nothing; decide package vs single file for the organ. |
| **M2 · guards** (gates only) | — | Joe freezes `test_layers.py`; Claude commits the `pxr` symbol-table gate (SYNAPSE lesson 8) | The layers test. |
| **M2b · outcome** (new, from a critic) | a small frozen `Outcome` test | `outcome.rs` and its pyclass, on its own, because M3's NaN → `Unavailable` test needs it and Blueprint §11 already puts `Outcome` in Phase 0 | The `Outcome` test. |
| **M3 · identity** | `tests/acceptance/phase3/test_t9_identity.py` | `canon.rs` + sha2: `cache_key`, `intent_hash`, golden vectors, type-directed canonicalisation (pxr widens `0.1f` to `0.10000000149011612`) | The identity tests, and the envFingerprint-in-or-out decision. |
| **M4 · graph encoding** | `test_t10_graph_schema.py` (T0-style subprocess gate) | `PlexusNodeAPI`, `PlexusResultAPI`, Sdr defs, `add_node` / `connect`, compliance at the gate | Spec Patch 02 (the two schemas) and a new CONTRACT surface. |
| **M5 · incremental** | notice → dirty within 10 ms at 10k nodes | Python edge index first; Rust `graph.rs` only on a measured miss | The 10 ms p95 test. |
| **M6 · results** | content-addressed results, payloaded | the F7 lookup, rotation measured on 26.5 | The results layout decision. |
| **M7 · import** | ComfyUI workflow import into the neutral IR | the importer inside `plexus/organs/cozy/` | Import tests with fixtures inside the organ directory only (T8). |
| **M9 · shadow** | parity on Joe's scenes | `plexus-usd` + `plexus-shadow` | The parity corpus. |

---

## 6 · What the scaffold team writes, and what it never writes

**Claude (and Claude-run subagents) write:** plans, mission files, worker briefs, harness gates (the build gate, the symbol table), the empty package and crate skeletons a gate needs at baseline (C1–C6 of the acceptance plan), and proposed frozen tests as drafts for Joe outside `tests/acceptance/`.

**Claude never writes:** implementation under `plexus/` or `crates/` beyond those skeletons; anything under `tests/acceptance/`; anything copied from Comfy-Cozy or SYNAPSE.

**The worker writes:** everything else, one diff at a time, through the harness.

---

## 7 · Decisions for Joe

From the refinement round, in the order they block work:

1. **Notice path A or B** (acceptance plan §4). Jev's read was A at 0.98; still your call. The refinement round designed for A.
2. **`test_layers.py`** — write it before M0's `run` so it rides as a gate from the first attempt, or at M2.
3. **`Outcome` timing** — its own small mission before identity (recommended, and Blueprint §11 Phase 0), or folded into M4.
4. **Cache key: env fingerprint in or out** — before the first result persists. Out makes results shareable across machines; in is strict. Reversing it later changes the key domain and orphans every stored result.
5. **Canonicalisation rules** — accept folding `-0.0` to `0.0` and type-directed float narrowing, before the first key persists.
6. **Spec Patch 02** — `PlexusNodeAPI` (`plexus:nodeId`, `plexus:mode` active/bypass/muted) and `PlexusResultAPI` (`cacheKey`, `opId`, `nodeId`), signed before any node or result prim is authored.
7. **Results layout** — content-addressed (`/Project/Results/s_<2>/k_<32>`: rename-proof, cross-project hits) or a tree that mirrors the graph (readable).
8. **Two Blueprint deferrals** — tokio for the scheduler (§5.1) and the Phase 0 identity registry and intent ledger (§11) both move later in this design.
9. **The symbol-table gate** — approve the scaffolding commit before M4.

**One correction to this plan's own earlier text:** §3.4 called the 238 ms 10k-node edge-index time "the first measured case for Rust". The critics showed that number is mostly pxr extraction, which stays in Python under any design; the per-notice dirty closure (13 ms in the report's own table) is what breaks Spec §11's 10 ms. Rust `graph.rs` waits for that measurement.

---
## Appendix A · Design variables (refinement round 1, Nov 1)

Every variable the synthesis settled, with its status. **settled-by-evidence** means a file, test or measurement supports it; **needs-measurement** names what to measure; **needs-joe** is a decision. Where a critic's blocking objection changed a variable, §2 carries the corrected text.


### `usd.schema-plugin` — settled-by-evidence

- **Question:** What shape do the four codeless API schemas take on disk, and how does the worker produce them without usdGenSchema?
- **Value:** plexus/schema/__init__.py exposing plugin_dir() -> Path(__file__).parent; plexus/schema/plugInfo.json with one Plugins entry (Type "resource", Name "plexus", Root ".", ResourcePath ".", LibraryPath "") whose Info.Types holds PlexusProjectAPI, PlexusAssetAPI, PlexusNeuronAPI, PlexusOrganAPI, each {alias:{UsdSchemaBase:<Name>}, autoGenerated:false, bases:["UsdAPISchemaBase"], schemaIdentifier:<Name>, schemaKind:"singleApplyAPI"}; plexus/schema/generatedSchema.usda hand-authored with one `class "<Name>" (inherits = </APISchemaBase> customData = {token apiSchemaType = "singleApply"})` per API carrying exactly the Spec §3 attributes with allowedTokens where listed. No schema.usda source, no codegen. Later schemas (PlexusNodeAPI, PlexusResultAPI) are added to the same two files.
- **Why:** usdGenSchema is not in the usd-core wheel and T0 checks only registration, attribute type, allowed tokens and a round trip, so a hand-authored pair is the smallest passing file set. The `bases` value is what Pixar's own plugInfo uses for applied API schemas, and the worker brief must carry it exactly because a wrong base makes FindAppliedAPIPrimDefinition return None with no other symptom.
- **Evidence:** tests/acceptance/phase1/test_t0_schema_gate.py:17-57 (attribute table), :112-131 (plugin_dir, PXR_PLUGINPATH_NAME subprocess); C:/Python314/Lib/site-packages/pxr/pluginfo/usdShade/resources/plugInfo.json entry UsdShadeMaterialBindingAPI (bases ["UsdAPISchemaBase"], schemaIdentifier, schemaKind singleApplyAPI); acceptance.plan.md:188 says `bases: ["/TfType"]`, which does not match pxr and must be corrected in the worker brief
- **Rejected:** usdGenSchema from a Houdini hython: an install outside the repo venv (a stop-and-ask item) and a Houdini dependency for a build step.
- **When:** phase1 acceptance (S1); the worker-brief correction before `run`


### `usd.exchange-writer-order` — settled-by-evidence

- **Question:** How are writer layers ordered on the exchange and where does a runtime's opinion land?
- **Value:** exchange.usda subLayers listed strongest first; register_participant appends `from_<id>.usda` at the END (weakest), idempotent by id; reordering is a human edit of exchange.usda only. NeuronRuntime.edit_layer = Sdf.Layer.FindOrOpen(from_<participant>.usda), one handle per process. The runtime registers its participant BEFORE Usd.Stage.Open(exchange) so the sublayer append is not a root resync into the axon. Project roots reference </Exchange> of the composed exchange, weaker than local opinions.
- **Why:** CONTRACT freezes append-weakest and strongest-first reporting; T4/T5 need the opinion to come only from the edit layer; registering before open keeps the first axon event from being a '/' resync.
- **Evidence:** tests/acceptance/CONTRACT.md:13-21; PLEXUS_SPEC.md:142-146 (§7.1-7.2); acceptance.plan.md:188 (order rule)
- **Rejected:** Prepending new participants as strongest: contradicts Spec §7.1 and lets a fresh participant override an established one without a human edit.
- **When:** phase1 acceptance (S2)


### `usd.project-writer-order` — settled-by-evidence

- **Question:** Inside a project, what is the sublayer order of writers once graphs exist?
- **Value:** Project root subLayers, strongest first: session layer (Joe, in-memory; un-mutes and approvals) > graph.usda (human/UI) > from_<agent>.usda, one per neuron or frontier/local agent, appended weakest on registration, reordered only by Joe > layout.usda (ui:nodegraph:* only) > runtime.usda (runtime-only, small, NOT payloaded: `outputs:*` acceptance opinions naming the accepted result prim) > /Project/Results payloads to results/r_<NNNN>.usdc (runtime-only). Never sublayers: lib/ (by reference), nodedefs/ (by Sdr), /Exchange (by reference, weaker than local per Spec §7.2). Each layer has exactly one writer under the one-handle rule; removing an agent's layer is a clean undo of everything it did.
- **Why:** Joe's word beats UI beats agents beats layout beats derived data, which is LIVRPS strength expressing 'human overrides are strongest'. The acceptance opinion must be readable on a LoadNone stage, so it cannot live inside the payloaded results shard; that is why runtime.usda exists separately.
- **Evidence:** NEXTGEN_SCAFFOLD_PLAN.md:116 ('Writers, strongest first'); :124,137 (payload the results; LoadNone 15 ms vs payload load 111 ms); PLEXUS_SPEC.md:138 (un-mute is a session-layer opinion); PLEXUS_BLUEPRINT_v5.md:84-86 (one handle, one owner), :144 (item 7: promotion needs Joe)
- **Rejected:** Agents writing into graph.usda behind a lock: two writers on one sublayer, which Blueprint §2 forbids. Putting `outputs:*` acceptance in the payloaded results layer (product-first): invisible to a LoadNone-opened stage.
- **When:** later (M4 graph encoding for graph/layout/agent layers; M6 for runtime.usda and results payloads)


### `usd.authoring-path` — settled-by-evidence

- **Question:** How do ctx.author / ctx.author_asset write so T4, T5, T6 and T7 all hold?
- **Value:** Inside one Sdf.ChangeBlock on edit_layer: gate check (path allowlist, plexus/membrane/gate.py, strings in) first; on deny author `plexus:flagGateDenied` (string = denied path) on the neuron prim and return; on allow Sdf.CreatePrimInLayer for the target with specifier Def on it and every missing ancestor, author the attribute, author `plexus:sourceLayer` (string) = edit_layer.identifier on the target prim. author_asset applies PlexusAssetAPI via apiSchemas listOp prepend and writes the 13 Spec §3 attributes from the record (assetPath absolute as the organ wrote it). After the ChangeBlock: edit_layer.Save(). One Save per ctx call.
- **Why:** T6 calls Reload() on every layer before dumping, so unsaved opinions vanish and save-on-land is load-bearing; T6 dumps with PrimRange so ancestors must be `def`; T7 reads sourceLayer and PlexusAssetAPI from both projects. One ChangeBlock means one notice per action.
- **Evidence:** tests/acceptance/CONTRACT.md:36; tests/acceptance/phase1/test_t6_truth.py:197-199 (Reload before dump), :151-157 (PrimRange + GetAuthoredAttributes); tests/acceptance/phase2/test_t7_round_trip.py:299-310; acceptance.plan.md:29
- **Rejected:** Batching Save() at quiesce: a process killed between author and quiesce loses the opinion and T6 fails; it is also hidden runtime truth.
- **When:** phase1 acceptance (S4/S6/S8); author_asset in M1


### `usd.notice-intake` — settled-by-evidence

- **Question:** What exactly does the notice callback extract, and how does phase1 map a notice to a neuron?
- **Value:** Inside the callback (the only place the notice is valid): paths = frozenset(GetChangedInfoOnlyPaths()) | frozenset(GetResyncedPaths()); resynced = frozenset(GetResyncedPaths()); fields = {str(p): tuple(GetChangedFields(p)) for p in all paths}; t = time.monotonic(); put_nowait onto queue.SimpleQueue; nothing else. StageEvent gains a defaulted fourth field `fields: Mapping[str, tuple[str, ...]] = {}` (CONTRACT's three fields unchanged). The dispatcher coalesces within debounce_s (default 0.05) into one StageEvent (union of sets, merged fields, t of the last). Phase1 dirty rule: a neuron is a candidate iff any event path's prim path equals scope or has scope as a prefix, OR any resynced path is an ancestor of scope (covers sublayer adds and T6's Reload). Paths cross into Rust as str only, for the predicate's changed() set.
- **Why:** usd-core notices fire synchronously on the authoring thread and are valid only during the callback, so frozen plain data is the only safe copy; GetChangedFields (present on 26.5) later lets a value edit and a rewire be told apart with no composition query, and it costs nothing to capture now. The ancestor-resync clause is what lets T6's layer Reload wake the neuron.
- **Evidence:** PLEXUS_SPEC.md:117-118; tests/acceptance/CONTRACT.md:25-26; live probe: hasattr(Usd.Notice.ObjectsChanged, 'GetChangedFields') == True on usd-core (0,26,5); NEXTGEN_SCAFFOLD_PLAN.md:52 (idea 3), :127, :137 (500-path ChangeBlock extracted in 0.55 ms); test_t6_truth.py:196-199
- **Rejected:** Evaluating predicates or classifying inside the callback: holds the author's thread and runs composed queries during notice delivery, which Spec §5 forbids.
- **When:** phase1 acceptance (S2, S4); `fields` may land in S2 or at M5, both keep the frozen surface


### `usd.notice-to-dirty-graph` — settled-by-evidence

- **Question:** Once graphs live on the stage, which notice kinds dirty which nodes, and what runs on the notice path?
- **Value:** Stage 1, on the dispatcher thread inside the 10 ms budget, marks dirty and nothing else, keyed on (path, fields): `<node>.inputs:<p>` with `default`/`timeSamples` -> node + downstream closure; `<node>.inputs:<p>` with `connectionPaths` -> rebuild that node's in-edges, node + closure; prim resync under /Project/Graphs (new or removed node, variant switch, first opinion from a fresh writer layer) -> re-read that subtree, rebuild its edges, dirty subtree + closure; resync of '/' or a subLayers change on the root -> full re-index; `outputs:*` from runtime.usda -> mark downstream READY, no re-key; `ui:*`, anything under /Project/Results, layout.usda -> ignore. Stage 2 is lazy: cache keys are recomputed only when a run is requested, over dirty nodes intersected with the demand-pulled ancestors of the requested sinks. Dirty means 'recompute key', never 'run': a node runs only if its recomputed key has no result prim. Classification lives in Python (a string table); the closure lives wherever usd.edge-index decides.
- **Why:** Reading composed inputs is pxr work on the order of 20 µs per Get, so eager re-keying on every root edit breaks Spec §11 in any language; marking dirty is cheap, and a specializes default edit fans out to every instance (1,001 paths from one class edit in the report), which would multiply eager cost.
- **Evidence:** NEXTGEN_SCAFFOLD_PLAN.md:127 (notice -> dirty mapping, 'Dirty ≠ run'), :137 (one class edit fanned out to 1,001 paths); PLEXUS_SPEC.md:200 (< 10 ms notice -> wake decision)
- **Rejected:** Re-keying the whole graph on every notice: 10k nodes x 8 inputs is ~200 ms of pxr reads; a Rust classifier (product-first): string matching on a dozen tokens earns no exactness and adds a PyO3 crossing per path.
- **When:** later (M5 incremental)


### `usd.graph-container` — settled-by-evidence

- **Question:** What prim types hold a graph and a node?
- **Value:** /Project (typeless, PlexusProjectAPI) > /Project/Graphs (`def NodeGraph`) > /Project/Graphs/<g> (`def NodeGraph`; `inputs:*` exposed params, `outputs:*` graph results; nested NodeGraphs are subgraphs) > <g>/<n> (`def Shader`, `uniform token info:id = <op id>`, apiSchemas ["NodeGraphNodeAPI", "PlexusNodeAPI"]). Whether two sibling graphs may wire to each other is a publication-gate policy, not a prim-type choice. Fallback held in reserve if Shader semantics bite: typeless def + PlexusNodeAPI declaring providesUsdShadeConnectableAPIBehavior.
- **Why:** UsdShade gives typed ports, connections, encapsulation rules and Sdr compliance checks in 26.5, and openusd 0.8.0 reads the same encoding (UsdShade views, ConnectionGraph), so both composers agree. The report chose a NodeGraph root because a typeless parent made sibling graphs unconnectable; a Scope root would make graph->graph wiring inexpressible, while isolation stays available as gate policy.
- **Evidence:** NEXTGEN_SCAFFOLD_PLAN.md:106-108 (encoding rows; 'under a typeless parent, sibling-graph CanConnect returned False'), :139 (openusd UsdShade views, ConnectionGraph), :143 (fallback, connectableAPIBehavior.cpp v26.05 L640-650)
- **Rejected:** A Scope root (product-first) inverts the report's finding into a feature and forecloses graph composition. One generated typed schema per op: the schema registry freezes at load, so each new op restarts every conductor and openusd cannot see schema fallbacks.
- **When:** later (M4 graph encoding)


### `usd.node-type-registry` — needs-measurement

- **Question:** Where are node types (ops) defined and registered, and what is the op id grammar?
- **Value:** Sdr, not schemas. One file per op holding a single `def Shader` whose `info:id` equals the op id, typed `inputs:*` defaults and `outputs:*`, and `uniform asset info:plexus:sourceAsset` resolving to an existing implementation. Op id grammar `^[a-z][a-z0-9]*(\.[a-zA-Z][A-Za-z0-9_]*)+\.v[0-9]+$` (e.g. `plexus.image.blur.v2`); the major version is in the id, finer changes live in the implementation digest; ids are never replaced, a breaking change is `.v<major+1>`. Registered at conductor start via Sdr.Registry().AddDiscoveryResult(Sdr.NodeDiscoveryResult(...)) with an SdrVersion, not a string. Neutral core ops live in plexus/nodedefs/*.usda (read-only). Engine-derived ops (from a live ComfyUI /object_info) are generated at runtime into ${PLEXUS_STORE}/nodedefs/cozy/<objectInfoSha256[:16]>/*.usda with ids `cozy.<ClassName>.v<n>`, never under plexus/ or crates/. Type-level metadata is sdrMetadata: `plexus:effect` = pure|sink|source, `plexus:portType` per opaque port, `plexus:capability` (organ capability the op needs).
- **Why:** Sdr takes a definition while the process is live and ShaderSdrCompliance catches type mismatches; the schema registry is a load-time singleton. The `.vN` suffix is a legal prim-name fragment (the defaults class prim needs one) while '@' is not and is also the usda asset-path delimiter. Generating engine defs outside plexus/ is what keeps T8 green by structure.
- **Evidence:** NEXTGEN_SCAFFOLD_PLAN.md:100, :120 (AddDiscoveryResult live, typed inputs, needs a real file, replacement untested), :145; live probes on 26.5: Sdf.Path.IsValidIdentifier('blur@2') == False, Sdr.NodeDiscoveryResult exists and its ctor takes SdrVersion, Sdr.ShaderNodeDiscoveryResult does not exist; tests/acceptance/phase2/test_t8_blindness.py:14-20, :23-24 (.usda scanned; only organs/cozy* allowed)
- **Rejected:** `plexus.op.<name>@<major>` (report, harness-first, measurement-first): '@' is unproven in an Sdr identifier and invalid in a prim name. Reading types from a live engine's /object_info into the core: engine names in core data (T8) and a core type system that depends on the engine.
- **When:** M4: the first frozen test registers a file-backed def with this grammar and gets typed inputs back from GetShaderNodeByIdentifier; measure whether a `.usda` under ${PLEXUS_STORE} is discovered from an absolute path


### `usd.plexusnodeapi` — needs-joe

- **Question:** What do the new codeless schemas carry, without touching the four frozen ones?
- **Value:** Fifth and sixth classes in the same plugInfo.json + generatedSchema.usda. `PlexusNodeAPI` (on every node): `plexus:nodeId` (string, UUID, stable across rename/move/reference; provenance and UI only, never in the cache key) and `plexus:mode` (token, allowedTokens active|bypass|muted, fallback active). `PlexusResultAPI` (on result prims, alongside PlexusAssetAPI): `plexus:cacheKey` (string, 64 lowercase hex), `plexus:opId` (string), `plexus:nodeId` (string, provenance). PlexusAssetAPI stays exactly as Spec §3. Nothing else: no capability (type-level, on the Sdr def), no status, no layout, no stored key on nodes.
- **Why:** T0 asserts only the four listed APIs and their attributes, so additive schemas cannot break it, but Spec §3 is normative, so a separate PlexusResultAPI keeps the frozen asset table untouched. `mode` with three values is what ComfyUI UI workflows carry (always/mute/bypass), so import is lossless; a stored key on a node would be trusted state that can go stale.
- **Evidence:** tests/acceptance/phase1/test_t0_schema_gate.py:17-57 (checks presence of listed attributes only); PLEXUS_SPEC.md:35 ('normative'); NEXTGEN_SCAFFOLD_PLAN.md:100 ('One new codeless PlexusNodeAPI'), :113-114 ('plexus:cacheKey, a spec patch'; 'Recomputed, never trusted')
- **Rejected:** Adding plexus:cacheKey to PlexusAssetAPI (report, harness-first, measurement-first): passes T0 but edits a normative table; `plexus:pinned`/`plexus:cachePolicy` (product-first): no frozen test or mission needs them yet; `plexus:capability` on the instance (harness-first): duplicates type data.
- **When:** M4; it is a Spec §3 patch (Patch 02) either way, so Joe signs the schema list before any node or result prim is authored


### `usd.edge-storage` — settled-by-evidence

- **Question:** How are edges and port types stored?
- **Value:** Edges are UsdShade connections only: `<n>.inputs:<p>.connect = </Project/Graphs/<g>/<m>.outputs:<o>>`; one source per input unless the Sdr def marks `plexus:multi = true` (connection order significant). Value ports use real Sdf types (bool, int, int64, float, double, string, token with allowedTokens, float2/3/4, color3f, asset). Opaque ports (image, mask, latent, model, cond, tensor) are `asset`-typed, with sdrMetadata `plexus:portType = <neutral type>` from the vocabulary in plexus/core/ports.py; an opaque output's composed value is the content-addressed path of the accepted result, authored only by runtime.usda. Compatibility: equal portType, or either side `any`. Validation (portType, EncapsulationRules, ShaderSdrCompliance, acyclicity) runs at the publication gate, never at ConnectToSource.
- **Why:** Connections compose, remap through references and give per-layer provenance via GetPropertyStack; relationships and JSON blobs do none of that. Asset-typed opaque outputs make the downstream input literally a path plus a hash (F8), where a token would need a side lookup. `any` is the controlled form of ComfyUI's `*`, which 10 of Joe's packs rely on.
- **Evidence:** NEXTGEN_SCAFFOLD_PLAN.md:109 (edge row), :113 ('the node's outputs:<o> names the accepted asset'), :122 (references remap edges; GetPropertyStack), :125 (ConnectToSource does not enforce CanConnect), :75 (stringly ports, `*`, `__ne__` hack in 10 packs)
- **Rejected:** Token-typed opaque outputs (harness-first, measurement-first): carry no value, so F8's 'stage stores references and hashes' needs a side table. Relationships or edge prims: no typed ports, no UsdShade tooling, arcs cannot reach into them.
- **When:** later (M4)


### `usd.op-defaults-subgraphs-variants` — settled-by-evidence

- **Question:** Which arcs carry op defaults, subgraph reuse and authored branches?
- **Value:** Op defaults: `class /Project/Defaults/<opId with dots as underscores>`; every node of that op `specializes` it; Sdr defaults are the floor beneath. `inherits` is reserved for deliberate broadcast (`/Project/Broadcast/<...>`), opt-in per node. Subgraphs: `def NodeGraph "<n>" (references = @lib/<name>_v<N>.usda@</<Name>>)`, local opinions win, no `instanceable` (nodes inside must stay editable). Authored A/B branches: a variantSet `plexusBranch` on the use site; seeds and knobs are plain values, never variants. Cache keys are computed on the composed graph, so a node inside a referenced subgraph keys identically to the same node inlined.
- **Why:** In the 26.5 check a library-tuned value survived specializes and was overwritten by inherits, so specializes is the arc that behaves like a default. References remap edges correctly; a variant switch is a prim resync and the unselected branch's results stay cache hits.
- **Evidence:** NEXTGEN_SCAFFOLD_PLAN.md:110-111, :121-123 (findings 2-4), :77 (40 of 140 UI workflows use subgraphs)
- **Rejected:** inherits for defaults: clobbers values tuned inside shared library subgraphs. Copying defaults into each node: no single place to change a default and provenance cannot tell a default from a choice. Instancing subgraphs: instance proxies are read-only.
- **When:** later (M4; key invariance proven in M6)


### `usd.model-identity` — settled-by-evidence

- **Question:** How is a model or other heavy asset identified and resolved?
- **Value:** By content: asset path authored as the expression `` `"${PLEXUS_STORE}/sha256/<hex[0:2]>/<hex64>.<ext>"` `` with `expressionVariables = {PLEXUS_STORE: <per-machine absolute path>}` written by stagekit.create_project into every project root layer and by create_exchange into exchange.usda (overridable in the session layer). Resolver: stock ArDefaultResolver, no custom Ar plugin. The store is a directory of hard links or copies named by sha256; the Cozy organ keeps a filename<->sha256 index of its engine's model folders (cached by path, size, mtime) and materialises a hardlink model folder for the worker; an imported workflow naming an unindexed file yields Outcome Unavailable(missing=[<filename>]). Phase 2 (T7) authors an absolute path; the expression form arrives with M6.
- **Why:** Filename identity is why ComfyUI's cache cannot survive a restart or be shared; a sha256 path makes 'same model' provable across machines. Expression variables are native to usd-core 26.5 and compose through the exchange reference, so no C++ resolver is needed.
- **Evidence:** NEXTGEN_SCAFFOLD_PLAN.md:75, :80 ('models keyed by filename'), :112 (Model row); PLEXUS_SPEC.md:58 (plexus:modelHashes); live probe: hasattr(Sdf.Layer, 'expressionVariables') == True on 26.5; tests/acceptance/phase2/test_t7_round_trip.py:303-306 (reads resolvedPath or path)
- **Rejected:** A custom ArResolver for plexus:// URIs: needs a C++ plugin built against the wheel's USD and Houdini's separately, and openusd in shadow could not reproduce it.
- **When:** M1 uses absolute paths; expression form and store layout fixed in M6. Separate measurement (risk, not a design fork): SHA-256 wall time over Joe's Models tree on CPU with Houdini open, hashlib vs sha2+rayon, before hashing becomes a Rust candidate


### `usd.result-layout` — needs-joe

- **Question:** Where does a result prim live, and how is it loaded?
- **Value:** Phase 2 (frozen by T7): `/Exchange/<participant>/Assets/<name>`, def, PlexusAssetAPI, in the neuron's edit layer. Later: content-addressed and independent of graph topology: `/Project/Results/s_<key[0:2]>/k_<key[0:32]>` with PlexusResultAPI + PlexusAssetAPI (one child `o_<outputName>` per output when an op has several); retries are siblings `k_<key32>_r<N>` with plexus:retryOf / plexus:retryReason. Authored only into results/r_<NNNN>.usdc, rotated at 50,000 prims (re-measured on 26.5), attached as payloads on /Project/Results, opened with LoadNone in editing contexts. The node's `outputs:<o>` acceptance opinion lives in runtime.usda (usd.project-writer-order). F7 lookup is Sdf-level: for each results layer in strength order (own shards, then exchange participants' published results layers) layer.GetPrimAtPath(k_<key32>); a hit requires plexus:cacheKey == full 64-hex key and each output's plexus:sha256 to match the store file; a hit from another project is adopted by authoring a local result prim that `references` the foreign one.
- **Why:** F7 says look up the hash; the report says result-prim existence is the F7 lookup, and an existence lookup is cheapest when the path is the key. Node-path-keyed results miss on rename, move or cross-project reuse, which is exactly the reuse the thesis promises. Sdf GetPrimAtPath on an open layer avoids loading any payload; re-verifying key and file hash keeps the stage from being trusted blindly.
- **Evidence:** tests/acceptance/phase2/test_t7_round_trip.py:282-310 (phase-2 location pinned); NEXTGEN_SCAFFOLD_PLAN.md:113-114 (Result and Cache key rows), :124 (payload the results), :137 (50k result prims: 44 MB usda, LoadNone 15 ms, payload load 111 ms); PLEXUS_SPEC.md:136 (retry authoring), :204 (50k rotation, Moneta number); PLEXUS_BLUEPRINT_v5.md:65 (F7), :336 (re-measure 50k on 26.5)
- **Rejected:** `/Project/Results/<g>/<n>/k_<key16>` (report, harness-first, measurement-first): ties cache identity to a node path, and 16 hex is thin for a store shared across projects. A store-side manifest as lookup authority: a second source of truth beside the stage.
- **When:** M6; needs the PlexusResultAPI Spec patch and Joe's call on content-addressed vs node-path layout (trade-off: cross-project and rename-proof hits vs a results tree that reads like the graph)


### `usd.cache-key` — needs-joe

- **Question:** What exactly is a node's cache key, and where is it trusted?
- **Value:** key = sha256(b"PXK1" + enc(opId) + implDigest[32] + u32(n) + for each input declared by the Sdr def, sorted by name bytes: enc(name) + tag + body). Tags: 0x01 value (composed value after specializes resolve, else the Sdr default, encoded by declared Sdf type per rust.hashing-canonical); 0x02 asset (32-byte sha256 of the resolved file, never the path); 0x03 edge (upstream key[32] + enc(sourceOutputName)); 0x04 multi-edge (u32 count + edges in connection order). implDigest = sha256 of the op's `info:plexus:sourceAsset` file (for a cozy op: the organ's declared pack-commit + node-source digest). Excluded: prim path and name, plexus:nodeId, ui:*, undeclared attributes, which layer an opinion came from, envFingerprint and organVersion (recorded on the result for drift diffing). plexus:mode = bypass: no key, pass-through; ops with plexus:effect = source must declare `inputs:nonce` or never hit. Keys are always recomputed from the composed stage; plexus:cacheKey on a result is for verification only.
- **Why:** ComfyUI cannot prove 'same workflow' because it has no node-code version and keys models by filename; implDigest fixes the code half and content-hashed assets fix the model half. Keying on resolved content rather than structure makes the same intent anywhere (another graph, another project, inlined or referenced) a hit. Excluding envFingerprint keeps caches shareable across a driver update; drift stays visible as a diff on the recorded fingerprint.
- **Evidence:** NEXTGEN_SCAFFOLD_PLAN.md:75 (structural key with ancestor ordinals, caching.py:101-148; NaN at caching.py:64), :80 (no node-code version), :114 (Cache key row); PLEXUS_SPEC.md:61 (envFingerprint is 'the diff key for drift'); PLEXUS_BLUEPRINT_v5.md:65 (F7)
- **Rejected:** Including envFingerprint: every torch/CUDA update empties every cache, which defeats F7; Joe may still prefer strictness, which is why this is his call. Omitting implDigest (harness-first): a pack update that changes outputs would serve stale results forever.
- **When:** M3 defines the encoding, M6 the key; Joe decides envFingerprint in/out before the first result prim persists, because reversing it changes the key domain (PXK1 -> PXK2) and orphans every stored result


### `usd.limits` — needs-measurement

- **Question:** Which numeric limits are enforced, and which are re-measured?
- **Value:** Enforced from phase1: notice -> wake decision < 10 ms (excl. action); A->B visibility p95 < 250 ms over 50 trials; debounce 0.05 s; global wake budget 60 per 60 s per runtime; 3 consecutive trips -> muted. Later gates, as numbers a test can hold: per graph <= 10,000 nodes and <= 20,000 edges; notice -> dirty set p95 < 10 ms at 10k nodes; full index build at open reported, not gated (pxr-bound, ~240 ms at 10k); results shard rotation 50,000 prims; exchange write batch <= 500 prims per Sdf.ChangeBlock; an over-limit graph is Outcome Blocked(reason=limit) at the publication gate, not a slowdown. The 50k and 500 figures came from Moneta on USD 0.25.5 and are re-measured on 26.5 before they become gates.
- **Why:** The first five are frozen in tests or CONTRACT defaults. Named limits with a Blocked outcome are honest about what is supported; unmeasured is unknown (Blueprint §5.2 item 4).
- **Evidence:** PLEXUS_SPEC.md:196-205 (§11); tests/acceptance/CONTRACT.md:26,30 (debounce_s=0.05, global_wakes_per_min=60); tests/acceptance/phase1/test_t3_budget.py:189-208; test_t1_propagation.py:47-48,81; NEXTGEN_SCAFFOLD_PLAN.md:131-137 (scale table); PLEXUS_BLUEPRINT_v5.md:336 (re-measure on 26.5)
- **Rejected:** Adopting Spec §11's 50k/500 as gates now; 'no limits, degrade gracefully' (a silent slowdown at 30k nodes is the failure to avoid).
- **When:** phase1 for the first five; M5 measures notice->dirty at 10k; M6 benchmarks rotation size vs open/save time and batch size vs reader notice time on 26.5


### `rust.crate-split` — settled-by-evidence

- **Question:** How many crates exist in each phase, and how do they depend on each other?
- **Value:** Phase1 and phase2: one crate, crates/plexus-core (crate-type ["cdylib","rlib"], feature `python` = ["dep:pyo3"], no other dependency; M3 adds sha2). Root Cargo.toml `[workspace] members = ["crates/plexus-core"]`, resolver 3, `[profile.release] debug = 0, incremental = true`, `[profile.dev] opt-level = 0`. No `[target.'cfg(...)']` tables and no build.rs in any crate (T8 scans .toml and only strips `#[cfg(` from .rs). crates/plexus-usd joins the workspace only at the shadow mission (M9): lib + bin `plexus-shadow`, depends on openusd 0.8.0 and on plexus-core (for Outcome, canon and the Composer trait's plain types), never linked into `_core`; Python talks to it over JSON lines on stdio. Allowed crate edge: plexus-usd -> plexus-core. Forbidden: plexus-core -> plexus-usd, plexus-core -> openusd or tokio. The two-crate rule is a ceiling.
- **Why:** Each crate and dependency is CPU compile time beside Houdini on every attempt, and nothing frozen in phase1/2 touches openusd. Blueprint §13.3 puts the Composer trait in plexus-core and §13.4 makes the openusd implementation native Rust, so plexus-usd implements core's trait and core cannot link it back without a Cargo cycle; a process seam keeps the Blueprint's dependency direction, keeps openusd out of every `_core` build, and crash-isolates an experimental pre-1.0 crate whose Stage is !Send.
- **Evidence:** PLEXUS_BLUEPRINT_v5.md:268-290 (§13.3: crate roles, 'Two crates, not more', 'they meet at layers'), :291-316 (§13.4: trait in core, openusd impl native Rust, shadow never read by runtime code); acceptance.plan.md:228 (C2: members = plexus-core only); tests/acceptance/phase2/test_t8_blindness.py:19-20,47-48 (RUST_CFG applies to .rs only; .toml scanned); NEXTGEN_SCAFFOLD_PLAN.md:139 (Stage is Rc + RefCell, !Send)
- **Rejected:** In-process shadow thread with plexus-usd -> plexus-core (harness-first): Python cannot reach plexus-usd without core linking it, which is the cycle. Leaf plexus-usd adapted inside core behind a `shadow` feature (product-first): compiles, but puts openusd into the `_core` build and the conductor's process. Creating plexus-usd now as an empty member: `cargo test --workspace` compiles it every attempt for no test.
- **When:** phase1 acceptance (C2 scaffolding) for the manifest shape; plexus-usd at M9. Measure then: cold and warm `cargo build --release -p plexus-usd` with Houdini open and CARGO_BUILD_JOBS from the CPU profile


### `rust.module-dag` — needs-joe

- **Question:** What modules does plexus-core have, which may depend on which, and how is acyclicity enforced?
- **Value:** Flat single-file modules under crates/plexus-core/src/, ranked; a module may `use crate::X` only for strictly lower rank: 0 error.rs; 1 predicate.rs, budget.rs, canon.rs [M3], graph.rs [M5], outcome.rs [M4 or earlier]; 2 composer.rs (trait + plain types, M9 only); 3 py.rs (#[cfg(feature = "python")], the only file that may name pyo3; nothing imports it). lib.rs only declares modules and the #[pymodule] fn _core. Enforcement is a frozen Python test Joe owns, tests/acceptance/guards/test_layers.py: it regex-scans crates/plexus-core/src/**/*.rs for `use crate::(\w+)` and `crate::(\w+)::`, asserts rank(importer) > rank(imported) against a table embedded in the test, requires every .rs file to be in the table, asserts crates/plexus-core/Cargo.toml names neither openusd nor tokio and no crate has a build.rs, and that no file but py.rs mentions pyo3. The worker may add a belt-and-braces #[test] inside the crate, but the guard is the frozen one.
- **Why:** Rust permits module cycles, so acyclicity must be a test; a test inside the crate is editable by the worker in the same diff that breaks it, so it is not a guard. Flat one-file modules are what a 30B worker can read whole and change in one diff; a rank table makes 'acyclic' a property a regex can check.
- **Evidence:** NEXTGEN_SCAFFOLD_PLAN.md:23 (cycles hidden by lazy imports), :38 (lesson 3: 'boundaries are mechanisms, not comments ... add an import-layer test for plexus/ and crates/'); acceptance.toml:12 (harness/** and tests/acceptance/** frozen; crates/** is worker focus); harness/plexus_loop/loop.py:246 (baseline gates must pass)
- **Rejected:** A predicate/ submodule tree (lex, parse, ast, eval): four files the worker must keep consistent in the riskiest step (S3). cargo-deny or clippy: do not check module edges inside one crate and add tooling the worker cannot reach. Harness-first's in-crate ALLOWED test as the only guard: worker-editable.
- **When:** Joe writes tests/acceptance/guards/test_layers.py; it passes trivially before plexus/ exists, so it can ride as a [[gates]] entry from M0 if written before `run`, otherwise from M1


### `rust.pyo3-surface` — needs-measurement

- **Question:** What is the exact PyO3 surface and how is it gated?
- **Value:** pyo3 = { version = "0.30", optional = true, features = ["extension-module", "abi3-py311"] }; `[features] python = ["dep:pyo3"]`. Module `plexus._core` exports in phase1: `__version__: str`; exception `PredicateError` (create_exception!(_core, PredicateError, PyValueError)); `compile_predicate(source: str, scope: str) -> Predicate`; class `Predicate` with `paths() -> list[str]`, `seed(values) -> None` (fills only None delta slots), `eval(changed: list[str], values) -> bool` (pure), `commit_wake(values) -> None` (overwrites all slots); class `Budget(wakes: int, window_s: float)` with `peek(now: float) -> str` (pure), `admit(now: float) -> str` (mutating), both returning "wake"|"trip"|"mute", `state -> str` ("ok"|"muted"), `consecutive_trips -> int`, `unmute() -> None`. `values` is dict[str, float | int | bool | str | None]. plexus/core/predicate.py does `from plexus._core import PredicateError, compile_predicate` so pytest.raises matches by identity. Later: canonical/intent_hash (M3), Outcome (M4), EdgeIndex (M5, if promoted). No allow_threads, no `[tool.maturin]` in the root pyproject (cargo build + copy per plan C3). Phase 2 adds nothing to the surface.
- **Why:** This is the whole of Option A for phase1; abi3-py311 gives one .pyd for 3.11-3.14 and matches Spec §1's floor, so a Python change never forces a rebuild. `compile_predicate` avoids shadowing a builtin on re-export. Subclassing ValueError keeps an Option-B fallback type-compatible.
- **Evidence:** acceptance.plan.md:98-105 (Option A), :228-235 (C2/C3, no maturin in pyproject); tests/acceptance/CONTRACT.md:33,40; tests/acceptance/phase1/test_t2_predicate_precision.py:167-173; PLEXUS_SPEC.md:9 (Python >= 3.11); PLEXUS_BLUEPRINT_v5.md:265 (PyO3 0.30.1, 0.x API churn); live: Python 3.14.2, rustc/cargo 1.99.1
- **Rejected:** abi3-py312 (product-first): nothing needs 3.12 and Spec says 3.11. A Rust Runtime class owning the neuron table and calling Python actions: the rejected tokio-dispatcher option. Releasing the GIL around microsecond calls: costs more than it saves.
- **When:** phase1 acceptance: C2 builds an empty module, S3 adds the rest. Measure first, before `run`: pyo3 0.30 + abi3-py311 builds and `import plexus._core` succeeds on C:\Python314 (3.14.2) with cargo 1.99


### `rust.predicate-repr` — settled-by-evidence

- **Question:** How is a grammar-v0 predicate represented, parsed and evaluated?
- **Value:** struct Predicate { paths: Vec<String> (deduplicated, first-seen order), clauses: Vec<Clause>, cache: Vec<Option<f64>> (one slot per Delta clause) }; enum Clause { Changed(u16), Delta(u16, Cmp, f64), Attr(u16, Cmp, Lit), Exists(u16) }; enum Lit { Num(f64), Str(String), Tok(String) }; enum Cmp { Gt, Ge, Lt, Le, Eq, Ne }. Hand-written byte scanner and recursive descent, no regex, no parser crate. Rules: clauses joined only by the exact token `AND`; `OR`, parentheses or any other bare word is Syntax{col}; a path must be absolute, contain exactly one '.', and its prim part must equal scope or start with scope + "/" (component-wise, so /Exchange/LookStateX is outside /Exchange/LookState), else OutOfScope. Eval: left to right, short-circuit, pure; changed(i) = paths[i] in the changed set; delta(i) = |current - cache[i]| cmp k, false if either side is None or non-numeric; attr compares numbers to numbers and strings/tokens to strings, mismatch is false; exists(i) = value is not None. seed(values) fills only None slots (called at registration and after every eval of a candidate neuron, so an attribute that first appears later gets a baseline without waking); commit_wake(values) overwrites all slots and runs only after both budgets admit.
- **Why:** Conjunction-only means a flat Vec with no tree; interned path indices make eval allocation-free; seed-at-registration plus commit-on-wake is what makes 'registering must not wake' and 'two 0.15 changes wake once' both true, and keeping eval pure lets the dispatcher re-evaluate without side effects.
- **Evidence:** PLEXUS_SPEC.md:95-110 (§4 grammar, no OR, cache updated only on wake, registration-time scope error); tests/acceptance/phase1/test_t2_predicate_precision.py:149-173; tests/acceptance/conftest.py:30 (temperature set before start_neuron); test_t3_budget.py:189 (changed AND delta); CLAUDE.md 'predicates compile in Rust'
- **Rejected:** Spec §4's literal 'Python closure over GetAttributeAtPath': superseded by Blueprint v5.3. Lazy fill inside eval (measurement-first): mutates during a pure call. String-prefix scope check: a real prefix bug.
- **When:** phase1 acceptance (S3 parse + scope; S5 eval + cache)


### `rust.budget-clock` — settled-by-evidence

- **Question:** How are budgets, time and the global budget represented?
- **Value:** struct Budget { wakes: u32, window: f64, history: VecDeque<f64>, trips: u32, muted: bool }. peek(now) is pure; admit(now): if muted -> "mute"; drop history entries <= now - window (a wake at t counts while now < t + window); if history.len() < wakes { push now; trips = 0; "wake" } else { trips += 1; if trips >= 3 { muted = true; "mute" } else { "trip" } }. A `now` earlier than the last is clamped to the last, never raised. Time is f64 seconds passed in by Python from NeuronRuntime's injected clock; Rust never reads a clock. Two budgets per wake: the neuron's own and one global Budget(global_wakes_per_min, 60.0) per runtime. Python sequence: v = neuron.peek(now); if v != "wake": neuron.admit(now) (the trip counts toward mute; on "mute" author plexus:state = "muted" and plexus:flagBudgetMuted on the neuron prim in the edit layer); elif global.peek(now) != "wake": drop, charge nothing, count it; else neuron.admit(now), global.admit(now), predicate.commit_wake(values), run the action. A global trip never mutes a neuron.
- **Why:** T3's sequence (wake at t+0, trips at +2/+4/+6, muted on the third consecutive trip) and FakeClock fall out of this with no clock in Rust. Peek-then-admit means a globally denied wake neither records a phantom wake on the neuron nor counts toward its mute, which a single mutating call in either order cannot guarantee. Raising inside the dispatcher would kill a wake.
- **Evidence:** tests/acceptance/phase1/test_t3_budget.py:189-216; tests/acceptance/_support.py:252-262 (FakeClock); tests/acceptance/CONTRACT.md:30 (clock=time.monotonic, global_wakes_per_min=60); PLEXUS_SPEC.md:130 (§6 step 3); acceptance.plan.md:102
- **Rejected:** A Rust-owned Instant clock: T3 would sleep ten seconds and FakeClock could not drive it. Global-first with a wasted global slot on a neuron trip (harness-first) or neuron-first with a phantom neuron wake on a global trip (measurement-first, product-first): both leak state the Spec does not sanction.
- **When:** phase1 acceptance (S7); the global ordering and half-open window are assumptions recorded in the plan file


### `rust.hashing-canonical` — needs-joe

- **Question:** Which hash and which canonical encoding define content identity, and who implements them?
- **Value:** SHA-256, lowercase 64-hex, everywhere content-addressed (files, intents, cache keys). Files are hashed in Python with hashlib inside the organ (M1, T7). Key and intent canonicalisation has exactly one implementation, Rust canon.rs (sha2 is the only new dependency), exposed as plexus._core.intent_hash(obj, domain: str) -> str and cache_key(op_id, impl_digest: bytes, params: list[tuple[name, sdf_type, value]], upstream: list[tuple[input, source_output, key: bytes]]) -> Outcome[str]. Encoding is binary and type-directed, tag b"PXK1": every string is u32 LE length + UTF-8 bytes as authored (no Unicode normalisation); each value is enc(sdf_type_name) + payload by declared Sdf type: bool 1 byte, int i32 LE, int64 i64 LE, float f32 bits (exact for values that started as f32), double f64 bits, half f16 bits, string/token str, asset the 32-byte content sha256 never the path, arrays u32 count + elements, vecN native-width components. -0.0 encodes as +0.0. NaN or Inf -> Outcome Unavailable(code non_finite, missing=[field]); unknown Sdf type -> Unavailable(unsupported_type). A hashlib reference encoder embedded in the frozen test is the oracle.
- **Why:** Exactness across processes and languages is the point, so one implementation beats two that usually agree. pxr returns a float attribute as a widened Python double, so hashing reprs would split identity; carrying the declared type keeps float 0.3 and double 0.3 distinct and makes the organ's f32 the same bytes the stage read. SHA-256 is what plexus:sha256 and T7 already pin, so one hash family covers the stage and hashlib can verify it.
- **Evidence:** tests/acceptance/phase2/test_t7_round_trip.py:12, :230-231 (hashlib.sha256 on the file), :106-118 (links() canonical JSON); PLEXUS_SPEC.md:53 (plexus:sha256); NEXTGEN_SCAFFOLD_PLAN.md:75 ('non-primitive inputs become NaN and never match'), :85 ('intent hashing and key canonicalisation (exactness across processes, not speed)'), :96 (Cozy WorkflowSignature buckets values)
- **Rejected:** BLAKE3: faster on large files, but file hashing is I/O-bound, and it would put a second digest family on the stage and need a non-stdlib oracle. Tagged canonical JSON with float bit-hex (harness-first): correct but still needs the declared Sdf type to survive float widening, and a binary layout is shorter for the worker to get right. RFC 8785 JSON: float printing is exactly where cross-language drift hides.
- **When:** M3 (identity mission). Joe decides, before the first key persists, whether -0.0 folding and f32-narrowing are acceptable; the algorithm is frozen then because a change rewrites every key


### `rust.outcome-and-errors` — needs-joe

- **Question:** How do Outcome and Rust error types relate to the frozen exception contract?
- **Value:** Phase1: no Outcome. Hand-written std-only enums with Display (no thiserror, no anyhow): enum PredicateErr { Syntax { col: usize, found: String }, Unsupported { word: String }, OutOfScope { path: String, scope: String }, NotAbsolute { path: String } } -> PredicateError(str) in py.rs alone. Later: enum CanonErr { NonFinite(field), Unsupported(type) } and enum GraphErr { Cycle(Vec<String>), Unknown(path), Limit(&'static str) } become Outcome reasons with the variant name as snake_case `code`. Outcome (M4 or when the first contract call needs it): Rust enum Status { Ok, Unavailable, Blocked }; struct Reason { code: &'static str, detail: String, missing: Vec<String> }; struct Outcome<T> { status, payload: Option<T>, reason: Option<Reason> } built only via Outcome::ok(T), ::unavailable(code, detail, missing), ::blocked(code, detail); Python sees a frozen pyclass with .status in "ok"|"unavailable"|"blocked", .payload, .reason_code, .reason, .missing, .ok, and a broken invariant raises ValueError at construction. Rule: exceptions for caller mistakes detectable from the arguments alone (malformed predicate, out-of-scope path, wrong type); Outcome for world state (missing substrate, gate denial, limit exceeded, model not indexed, unhashable value). Library code carries #![deny(clippy::unwrap_used, clippy::expect_used)] so no panic crosses PyO3.
- **Why:** Blueprint §4 says callers branch on Outcome, never exceptions, while CONTRACT freezes pytest.raises(PredicateError) at registration; splitting by kind of call satisfies both without touching a frozen test. Fewer proc-macro crates is less for the CPU worker to compile.
- **Evidence:** PLEXUS_BLUEPRINT_v5.md:109 ('The envelope'), :67 (F10), :290 (compile cost); tests/acceptance/CONTRACT.md:33,40; tests/acceptance/phase1/test_t2_predicate_precision.py:167-173; NEXTGEN_SCAFFOLD_PLAN.md:54 (idea 5: Verified / Unknown / Broken)
- **Rejected:** Returning Outcome from compile_predicate: breaks the frozen test_bad_predicates_fail_at_registration. Outcome in the phase-1 surface (product-first): no phase-1 test rewards it under min_delta=1, so the worker's attempt would be dropped.
- **When:** phase1 (S3) for PredicateErr; Outcome at M4 (or an earlier outcome mission if Joe wants Blueprint §11 Phase 0's envelope first). The Blueprint-§4-vs-CONTRACT reading is Joe's to confirm


### `rust.edge-index` — needs-measurement

- **Question:** Where do the graph edge index and the dirty closure live?
- **Value:** Python first, promoted to Rust on a measured miss. plexus/graph/index.py holds two dicts keyed by node prim path: down[src] -> [(src_output, dst, dst_input)] and up[dst] -> same; a full build only at open and on a '/' subLayers change, every other notice updates incrementally by re-reading only the touched node's connections. The frozen M5 perf test measures notice -> dirty set p95 on a 10k-node / 15k-edge fixture and on Joe's largest real graph. If Python misses 10 ms, M5's second half lands graph.rs: struct EdgeIndex { ids: Vec<String>, fwd: CSR, rev: CSR }, build(nodes: list[tuple[str, str]], edges: list[tuple[str, str, str, str]]) (an edge is (src_node, src_output, dst_node, dst_input)), update(removed_nodes, added_edges, removed_edges), dirty_closure(seeds: list[str]) -> list[str] in topological order, topo() -> list[str], cycle() -> list[str] | None (an authored cycle is reported with its path and nothing runs). Python reads connections through pxr and hands strings in; Rust never sees a pxr object.
- **Why:** The report's 238 ms at 10k is the open-time build, which under Option A is dominated by pxr extraction no Rust port removes; Spec §11 budgets the per-notice path, and the report's own closure row at 10k is 13 ms in Python, which is the one plain-data step that breaks the budget and that a CSR closure takes to microseconds. Rust goes where a measurement says it is hot, not where a total time was read as one number.
- **Evidence:** NEXTGEN_SCAFFOLD_PLAN.md:131-137 (scale table: 10k nodes, Python edge index 238 ms, dirty closure 13 ms; 'the edge index belongs in Rust'); PLEXUS_SPEC.md:200 (< 10 ms); PLEXUS_BLUEPRINT_v5.md:250 (§13.1: Rust where hot or exact; measurement promotes). Measurement-first's 234/2.9 ms split is from its own session and is not in any file, so it is a hypothesis for the M5 test, not evidence
- **Rejected:** Rust EdgeIndex as a settled fact (harness-first, product-first): rests on reading the report's total as index cost. Reading edges from openusd's ConnectionGraph in Rust: the shadow is never read by runtime code (Blueprint §13.4).
- **When:** M5: measure Python notice -> dirty p95 at 10k nodes and on Joe's largest LTX graph, and the PyO3 crossing cost of 15k edge tuples in one call, before graph.rs is written. Also correct NEXTGEN_SCAFFOLD_PLAN.md:137's conclusion to say which part is slow


### `rust.threading` — settled-by-evidence

- **Question:** What threads does Rust own, and how is openusd's !Send Stage contained?
- **Value:** Phase1 through M8: none. No tokio, rayon or std::thread in plexus-core; every _core call is synchronous, microseconds, on the Python dispatcher thread holding the GIL; Predicate and Budget are plain #[pyclass] holding only Strings, f64 and VecDeque, no `unsendable` anywhere. The shadow (M9) runs as the single-threaded plexus-shadow process that owns every openusd Stage on its main thread; Python spawns it once per conductor and compares replies; no openusd type crosses anything. tokio enters only with an organ-deadline scheduler mission, after a measurement shows the Python action pool's p95 lag under >= 100 concurrent organ jobs is the bottleneck.
- **Why:** Python already owns the notice thread, dispatcher and action workers in Option A, so a Rust thread would only add GIL handoffs for the worker to debug; openusd's Stage is Rc + RefCell, so one owning thread (here, one process) is the only sound shape.
- **Evidence:** acceptance.plan.md:115-117 (Rust dispatcher rejected); NEXTGEN_SCAFFOLD_PLAN.md:139 ('Stage is Rc + RefCell, so !Send: one composer thread, plain data out'), :51 (idea 2: never block the thread that owns the stage); PLEXUS_BLUEPRINT_v5.md:132 (§5.1: scheduler on tokio, deferred not dropped); tests/acceptance/CONTRACT.md:52 (a 350-line Python prototype passed all tests)
- **Rejected:** `#[pyclass(unsendable)]` wrapping a Stage: panics if the dispatcher or an action thread touches it. allow_threads around eval: costs more than microseconds of work.
- **When:** phase1 acceptance; shadow process at M9; tokio revisited when the organ-queue measurement exists


### `rust.what-stays-python` — needs-joe

- **Question:** What stays Python (the notice-path split)?
- **Value:** Python: Tf.Notice registration, StageEvent, the dispatcher thread and debounce, action worker threads, wait_idle, composed-value reads (the values dict), ctx.author/author_asset and every Save, the §7.3 allowlist gate (plexus/membrane/gate.py, strings in), schema plugin, membrane, stagekit, notice classification, Sdr registration, graph encoding and the validator's USD half, projection (stage -> neutral IR), result authoring and lookup, the content store's file I/O and sha256, the usd-core Composer, all organs and the ComfyUI importer, LLM providers, surfaces. Rust: predicate compile/scope/eval/delta cache, budgets; later canonical encoding and keys, Outcome, the edge index and closure if promoted, the Composer trait types, the shadow process.
- **Why:** Only pxr can read a pxr stage, so Rust cannot evaluate a predicate alone and gets plain values. This is Option A, recommended by the plan and by Jev at 0.98, and it matches v5.3 'predicates compile in Rust' and §13.3 'Python batches notices into a plain-data diff'.
- **Evidence:** acceptance.plan.md:96-119 (§4), :249 (Jev A at 0.98), :264 (decision 2 open); PLEXUS_BLUEPRINT_v5.md:284 (§13.3 flow); CLAUDE.md 'Where v5.3 wins'
- **Rejected:** Option B (all Python for phase1): fewest worker failure modes but contradicts v5.3 for a whole mission and leaves a port as known debt. Moving the dispatcher to tokio now: unmeasured and on the riskiest path.
- **When:** phase1 acceptance, before `run` (acceptance.plan.md §9 decision 2)


### `boundary.plain-data` — settled-by-evidence

- **Question:** Exactly which values cross PyO3, and who owns each?
- **Value:** Only str, int, float, bool, None, bytes, list, tuple, dict and the Rust pyclasses cross; never a pxr or openusd object, tensor, callable or file handle. Paths are str(Sdf.Path). Composed values cross as dict[str, float | int | bool | str | None] with extraction order bool, int, float, str, and None meaning no attribute or no value; for cache_key a value travels as (name, sdf_type_name, value) so Rust does the type-directed encoding and Python never builds key bytes. Python owns the stage, StageEvent, the clock, threads and all I/O; Rust owns predicate state (paths, clauses, delta cache) and budget state (history, trips, muted), mutable only through seed/commit_wake/admit/unmute. The full per-call list is in boundary_types.
- **Why:** Plain data is the only seam both the usd-core and openusd composers can share, and it keeps the worker's PyO3 code to conversion only; one side canonicalises, or there are two canonicalisers.
- **Evidence:** PLEXUS_BLUEPRINT_v5.md:286-288 (§13.3 'they meet at layers'), :295 ('only plain data crosses it'); NEXTGEN_SCAFFOLD_PLAN.md:85 ('Only plain data crosses'); acceptance.plan.md:96,101
- **Rejected:** Passing a Usd.Stage handle into Rust: impossible across the two USD builds and ties Rust to usd-core's ABI. Python pre-encoding key bytes: two canonicalisers.
- **When:** phase1 acceptance; the (name, type, value) triple form at M3


### `boundary.neutral-ir` — settled-by-evidence

- **Question:** What does core hand an organ, given T7 sends ComfyUI's dialect?
- **Value:** Phase 2: nothing new; Job.graph is a dict the core never inspects (T7 constructs it in engine dialect inside the test), which is why T8 holds through M1. From M4 on, core's projection produces a neutral IR (plain dict): {"v": 1, "nodes": {nodeId: {"op": opId, "params": {name: value}, "inputs": {port: [srcNodeId, outPort] | [[src, out], ...]}}}, "sinks": [nodeId]}; the field is `op`, never the engine's word. Each organ adds translate(ir: dict) -> dict (below CONTRACT, free) returning its dialect, which becomes Job.graph. The Cozy organ's op map, importer (UI and API JSON -> USD graph) and nodedef generation from /object_info live in plexus/organs/cozy/ only; workflow fixtures live under tests/, never plexus/.
- **Why:** T8 then holds by structure, not by discipline: core never constructs a dialect dict, and T7's byte-identical link arrays are the organ's own job.
- **Evidence:** tests/acceptance/phase2/test_t7_round_trip.py:31-56 (GRAPH in engine dialect, built by the test), :235-245 (links and class map equal), :224-227 (Job(graph=...)); tests/acceptance/phase2/test_t8_blindness.py:23-24 (allowed paths); NEXTGEN_SCAFFOLD_PLAN.md:88 ('The core holds a neutral IR')
- **Rejected:** Core emitting ComfyUI API JSON directly: banned vocabulary in plexus/core.
- **When:** M1 needs nothing; translate(ir) and the IR shape at M4; the importer at M7


### `harness.gates-vs-metric` — settled-by-evidence

- **Question:** How does a guard test that already passes at baseline fit a min_delta=1 harness?
- **Value:** Guard tests (T8 blindness, the layering test, the pxr symbol gate) run as [[gates]], never as metric targets; the metric target of each mission is only tests that fail at baseline. In M1 the two T8 tests are already in the phase2 metric (they pass at baseline once plexus/core exists, so they can only regress and drop an attempt); from M2 on every mission file carries gate `blind` = pytest tests/acceptance/phase2/test_t8_blindness.py and gate `layers` = pytest tests/acceptance/guards/test_layers.py, ordered after `core` and `cargo` and before `unit`. Phase-2 item count to carry in the mission brief: 7 collected (T7: test_link_arrays x2 + 3; T8: 2), not the plan's 6.
- **Why:** A test that passes at baseline cannot move a min_delta=1 metric, so as a metric target it rewards nothing; as a gate it rejects any attempt that breaks it, which is what a guard is for, and loop.py already refuses to start if a gate fails at baseline.
- **Evidence:** harness/plexus_loop/loop.py:1-12 (kept only when gates pass, no frozen path, metric improves by min_delta), :216-217 (no gates -> RefuseToStart), :246, :302-303, :324; harness/plexus_loop/metrics.py:56-89 (failures + errors + skips all count); acceptance.toml:15-24; acceptance.plan.md:5,15; tests/acceptance/phase2/test_t7_round_trip.py:234 (parametrize x2)
- **Rejected:** Folding guards into the metric path: a guard regression and a real fix could cancel out inside one kept attempt.
- **When:** M1 mission file (blind as metric item), M2 onward (both as gates)


### `harness.symbol-gate` — needs-joe

- **Question:** How is the worker stopped from inventing pxr, Sdr and openusd APIs?
- **Value:** harness/plexus_loop/symbols.py builds a sha256-stamped JSON table of every public name reachable from pxr.{Usd, Sdf, Tf, UsdShade, Sdr, Ar, UsdUI} on usd-core 0.26.5 (dir() walk at check time, keyed by package version) and, at M9, of openusd 0.8.0's pub items from rustdoc JSON. A gate `symbols` parses changed .py files with ast and fails on any `<pxr module>.<Name>` attribute access whose Name is absent; it also lists constructor-arity facts the worker gets wrong (Sdr.NodeDiscoveryResult takes an SdrVersion, not a str). Claude's scaffolding in harness/**, committed before M4; optional for phase1, whose pxr surface is small.
- **Why:** Phantom APIs were SYNAPSE's top failure class and a live-runtime table cut false phantoms from 0.667 to 0; an invented pxr call costs a whole CPU attempt including a Rust build, and Sdr is rarely used API where phantoms concentrate (the product-first architect hit one itself).
- **Evidence:** NEXTGEN_SCAFFOLD_PLAN.md:57 (idea 8; AGENTS.md:45-46; SYNAPSE_RULEBOOK.md:124-128); live probe: hasattr(Sdr, 'ShaderNodeDiscoveryResult') == False, hasattr(Sdr, 'NodeDiscoveryResult') == True, ctor signature wants SdrVersion
- **Rejected:** Relying on the test failure: an AttributeError surfaces only after a full build and test run.
- **When:** before M4 (scaffolding commit shown to Joe); it is harness/** so Claude writes it, Joe approves


### `harness.t8-guards` — settled-by-evidence

- **Question:** What must the worker brief forbid so T8 stays green while the code grows?
- **Value:** No `[target.'cfg(...)']` table in any crates/*/Cargo.toml and no build.rs (`.toml` is scanned unstripped; `cargo:rustc-cfg` matches `\bcfg\b`). The word `cfg` may appear in .rs only inside `#[cfg(`, `#![cfg(`, `#[cfg_attr(` or `cfg!(`; never in a doc comment, string or identifier; never as a Python variable or file name (use `conf`). No ComfyUI fixture, nodedef or /object_info dump as .json/.usda/.toml anywhere under plexus/ outside plexus/organs/cozy/; generated cozy nodedefs go to ${PLEXUS_STORE}. Op ids and example params in core use neutral terms (`guidance`, not the sampler term); no name containing `SaveImage` or `LoadImage` (the regex is a substring match, so `SaveImageWithMetaData` fails). Every step of every mission keeps T8's rule from S1.
- **Why:** The regex is textual and case-sensitive across six suffixes, and its three traps (cfg, substring node-class names, fixtures) are structural; a 30B worker reaches for `cfg(windows)` and `cfg = ...` by reflex.
- **Evidence:** tests/acceptance/phase2/test_t8_blindness.py:14-17 (ENGINE_TERMS), :19 (RUST_CFG), :20 (SOURCE suffixes), :23-24 (allowed paths), :47-48 (strip applies to .rs only); NEXTGEN_SCAFFOLD_PLAN.md:95, :145; acceptance.plan.md:138
- **Rejected:** Waiting for phase 2 to find out.
- **When:** phase1 worker brief (C5), before `run`


### `harness.test-granularity` — needs-joe

- **Question:** How must Joe's new frozen tests be shaped for a one-diff 30B worker?
- **Value:** One behaviour per `def test_`, each passable by a diff of roughly <= 150 lines, ordered so a mission's tests can fall one at a time; golden vectors, rank tables and expected sets embedded in the frozen test file (never read from a path the worker can edit); the full tests/acceptance suite runs as a no-regression gate in every mission; the first Rust-touching test of each mission exercises only one new PyO3 symbol.
- **Why:** min_delta = 1 rewards whole tests only, so a ten-assert scenario test is unreachable for one CPU attempt and the mission stalls at baseline; S3 already shows the cost of a step that must land five things at once.
- **Evidence:** acceptance.plan.md:5 (min_delta 1), :113 ('honest counterweight'), :125 ('The metric only rewards whole tests'); harness/plexus_loop/loop.py:9,324
- **Rejected:** Few large scenario tests: read well, give the metric nothing to climb.
- **When:** before each mission's `run`, as Joe writes the mission's frozen tests


## Appendix B · How the disagreements were resolved

- Graph root prim type (usd.graph-container): product-first wanted a Scope root for isolation; the report's parenthetical (NEXTGEN_SCAFFOLD_PLAN.md:106) says a typeless parent made sibling graphs unconnectable, which is why it chose NodeGraph. Resolved: NodeGraph root; isolation is publication-gate policy, not a prim type.
- Op id grammar (usd.node-type-registry): report/harness-first/measurement-first `plexus.op.<name>@<major>` vs product-first `.v<major>`. Resolved for `.vN`: verified Sdf.Path.IsValidIdentifier('blur@2') is False and the defaults class prim needs the id as a name fragment; '@' is also the usda asset-path delimiter. Status needs-measurement at M4.
- PlexusNodeAPI contents (usd.plexusnodeapi): {capability, bypass} vs {nodeId, mode} vs {nodeId, bypass, pinned, cachePolicy} + PlexusGraphAPI + PlexusResultAPI. Resolved: PlexusNodeAPI {nodeId, mode active|bypass|muted} (mode is what ComfyUI UI workflows carry; capability is type-level and lives on the Sdr def) and PlexusResultAPI {cacheKey, opId, nodeId} instead of patching the normative PlexusAssetAPI table. pinned/cachePolicy dropped until a test needs them. Goes to Joe as Spec Patch 02 either way.
- Opaque port Sdf type (usd.edge-storage): token (harness-first, measurement-first) vs asset (product-first). Resolved for asset: the report says the node's outputs:<o> names the accepted asset, and an asset-valued output makes the downstream input a path plus hash (F8) with no side lookup. Compatibility rule: exact portType or `any` (harness-first's exact-only rejected; `any` is the controlled form of the `*` that 10 of Joe's packs use).
- Result prim layout (usd.result-layout): `/Project/Results/<g>/<n>/k_<key16>` (report, two designs) vs content-addressed `s_<2>/k_<32>` (product-first). Resolved for content-addressed under /Project/Results (not /Plexus): F7's lookup is cheapest when the path is the key and rename/cross-project reuse must hit. Needs-joe because it is a Spec patch and a visible layout choice; trade-off: rename-proof, cross-project hits vs a results tree that mirrors the graph.
- `outputs:*` acceptance opinion location: payloaded results layer (product-first) vs small runtime.usda (measurement-first). Resolved for runtime.usda: an opinion inside an unloaded payload is invisible to a LoadNone-opened stage.
- Edge index language (rust.edge-index): Rust (report, harness-first, product-first) vs Python (measurement-first). Resolved: Python first, Rust graph.rs only on a measured miss of the frozen 10 ms p95 test. Measurement-first's 234/2.9 ms split is from its own session and not in any file, so it is the hypothesis M5 tests; the report's own 13 ms closure row is what makes promotion likely. NEXTGEN_SCAFFOLD_PLAN.md:137 should be corrected to say which part is slow.
- Notice classification location: Rust diff::classify (product-first) vs Python (measurement-first). Resolved for Python: a dozen-token string table earns no exactness and would add a PyO3 crossing per path. Product-first's StageEvent `fields` from GetChangedFields (verified on 26.5) is kept, captured inside the callback.
- Shadow crate shape (rust.crate-split): in-process thread with plexus-usd -> plexus-core (harness-first) vs separate plexus-shadow process (measurement-first) vs leaf plexus-usd behind a core `shadow` feature (product-first). Resolved for the process seam: Blueprint §13.3/13.4 put the Composer trait in core with a native-Rust openusd implementation, so plexus-usd -> plexus-core is the only Blueprint-consistent direction, and core cannot link it back without a Cargo cycle (harness-first's shape does not compile); the leaf shape compiles but puts openusd in every `_core` build and the conductor's process.
- Module DAG enforcement (rust.module-dag): in-crate #[test] with an ALLOWED table (harness-first) vs frozen Python test with layers/ranks (measurement-first, product-first). Resolved: ranks in a frozen test Joe owns; an in-crate test is worker-editable in the same diff that breaks it. Timing: it passes trivially before plexus/ exists, so it can ride as a gate from M0 if written before `run` (product-first was right that this is feasible, per loop.py:246).
- abi3-py311 (harness-first, measurement-first) vs abi3-py312 (product-first). Resolved for py311: Spec §1 says Python >= 3.11 and nothing needs 3.12.
- Compile entry point name: `compile` (harness-first) vs `compile_predicate` (measurement-first, product-first). Resolved for compile_predicate; `compile` shadows a builtin on re-export. CONTRACT only fixes PredicateError.
- Delta cache fill: seed() at registration (harness-first), prime() (product-first), lazy first-value fill (measurement-first). Resolved: `seed(values)` fills only None slots and is called at registration and after each candidate eval, so eval stays pure and an attribute that first appears after registration gets a baseline without waking; commit_wake overwrites all slots. All three pass T2 because conftest sets temperature before start_neuron.
- Global budget order (rust.budget-clock): global-first (harness-first) vs neuron-first (measurement-first, product-first); Spec §6 step 3 does not say. Resolved with peek-then-admit so neither a phantom neuron wake nor a wasted global slot is recorded; a global trip never mutes a neuron. Recorded as a plan-file assumption, not a Joe question. Backwards `now` is clamped, not raised (measurement-first's raise would throw inside the dispatcher).
- Canonical encoding (rust.hashing-canonical): tagged JSON with float bit-hex (harness-first) vs binary PXK1 type-directed with f32 narrowing (measurement-first) vs binary with type name (product-first). Resolved: binary, type-directed, carrying the Sdf type name, -0.0 folded to +0.0, NaN/Inf as Outcome Unavailable (not an exception). Needs-joe on the folding/narrowing choice before the first key persists.
- implDigest in the cache key: absent (harness-first) vs present (measurement-first, product-first). Resolved: present, because a pack update that changes outputs must miss. envFingerprint stays out by default; Joe decides (all three agree it is his call).
- Outcome in the phase-1 surface (product-first) vs deferred (harness-first, measurement-first). Resolved: deferred to M4, since no phase-1 test rewards it under min_delta=1; the Blueprint §11 Phase 0 placement is a documented drift for Joe.
- Organ protocol import rule: core never imports plexus.organs (harness-first, duck-typed AssetRecord) vs organs.protocol at the bottom rank (measurement-first). Resolved: organs.protocol is rank 1 plain data with neutral vocabulary and core.neuron may import it; the hard edge becomes 'core never imports organs.cozy'. CONTRACT puts AssetRecord there and author_asset needs its fields.
- Mission naming and order: harness-first M2 layers/M3 identity/M4 graph/M5 incremental/M6 results/M7 Outcome/M8 shadow; measurement-first adds import and puts identity after dirty; product-first adds outcome, import and agent-writers missions. Resolved as M0-M9 above (guards, identity, graph, incremental, results, import, agents, shadow), with M3 before M6 and M5 before M6; import and agent-writers kept because they carry the product goal (frontier and local AI editing live graphs). Joe may reorder anything after M1.


## Appendix C · Every critic objection

Seven were blocking and are applied in §2, §4 and §5. The rest are listed so nothing is lost; they get fixed as each mission's brief is written.


**Lens:** Checked:

- **PyO3 surface: verified, not refuted.** pyo3 0.30.1 is in ~/.cargo/registry. Its Cargo.toml has the `extension-module` and `abi3-py311` features, and its CHANGELOG lists 3.14+ FFI entries and 3.15 support. C:\Python314 is 3.14.2 with Py_GIL_DISABLED=0, so it is a GIL build and abi3 applies. C:\Python314\libs\python3.lib exists for abi3 linking on Windows. Since pyo3 0.23 a #[pyclass] must be Sync; Predicate and Budget hold only Strings, f64 and VecDeque, so no `unsendable` is needed. Under the GIL, no _core method releases it, so borrows do not conflict across the dispatcher and test threads.
- **T8 regex.** `RUST_CFG` strips `#[cfg(`, `#![cfg(`, `#[cfg_attr(` and `cfg!(` in .rs only. The scan skips `/target/`. .toml is scanned unstripped, which confirms the Cargo.toml rule.
- **Harness.** metrics.py counts failures, errors and skips. loop.py requires gates and a baseline. acceptance.toml freezes harness/** and tests/acceptance/**. T7 runs offline against FakeComfy, so a full-suite gate does not need a live engine.
- **Plan.** acceptance.plan.md §4–§7 (Option A, S1–S8, C2/C3) read in full.
- **Blueprint.** §13.2–13.4 read; their "one host process" and "Composer registered through PyO3" lines contradict the shadow-process design.
- **Crate DAG.** The two-crate ceiling and the plexus-usd -> plexus-core direction are respected. The objections are in the rank tables and the process seam, not in a Cargo cycle.
- **Hand-writing.** No step has Claude writing implementation code directly. The risk is the authorship of the frozen oracles and tests that only Joe may write.

- **[blocking] `rust.module-dag`** — These three rules contradict each other. A #[pymodule] fn in lib.rs has to name pyo3 (Bound<PyModule>, PyResult, the macro itself) and has to reach py.rs's classes through crate::py or py::. The frozen guard as specified therefore fails on every correct build, and the worker cannot edit the guard. *Fix:* Put #[pymodule] fn _core inside py.rs, since PyInit__core is exported from any module. lib.rs then holds only `mod` lines plus `#[cfg(feature = "python")] mod py;`. Change C2 to match, and put lib.rs in the rank table as the root, exempt from the rank check. *Evidence:* Synthesis rust.module-dag value ('lib.rs only declares modules and the #[pymodule] fn _core'; 'py.rs ... the only file that may name pyo3; nothing imports it'); crate_graph (b) 'pyo3 named only in py.rs'; acceptance.plan.md C2 ('src/lib.rs with an empty #[pymodule] fn _core behind the feature').
- **[blocking] `rust.module-dag`** — cache_key is specified to return Outcome[str], and GraphErr and CanonErr 'become Outcome reasons'. So canon.rs, and graph.rs if it returns Outcome, must `use crate::outcome`, which is the same rank. The frozen guard rejects the design's own intended code. *Fix:* Move outcome.rs to rank 1 beside error.rs, or put it at rank 0. Then move predicate, budget, canon and graph to rank 2, composer to 3 and py to 4. *Evidence:* rust.hashing-canonical ('cache_key(...) -> Outcome[str]'); rust.outcome-and-errors ('CanonErr ... and GraphErr ... become Outcome reasons'); crate_graph rank 1 lists canon.rs, graph.rs and outcome.rs together.
- **[blocking] `rust.module-dag`** — The table puts modules that import each other at the same rank. plexus.core.stagekit and plexus.membrane.exchange are both rank 2, yet stagekit is declared to import exchange. plexus.graph.{encode, index, dirty, keys} and plexus.core.results are all rank 4, but dirty needs index and results needs keys. The frozen test (c) would fail on the intended code at S2, and again at M4 to M6. *Fix:* Give every module its own rank, or make the rule 'no cycles plus the listed hard edges' rather than strict rank. Fix the rank table before Joe freezes test_layers.py. *Evidence:* crate_graph PYTHON block: rank 2 lists 'plexus.core.stagekit (pxr, membrane.exchange)'; rank 4 lists 'plexus.graph.{encode, index, dirty, keys} [M4-M6], plexus.core.results [M6]'.
- **[should-fix] `rust.module-dag`** — The regex misses `use crate::{budget, error::E}` (grouped imports), `super::budget::X` (from a top-level module, super is the crate root) and `use self::...` re-exports through lib.rs. A lateral rank-1 to rank-1 edge can pass the frozen guard unseen, so the guard is not a mechanism. *Fix:* Have the test also parse `use crate::{...}` groups and `super::` paths, or add `#![deny(clippy::...)]`. Better still, have the test reject any `super::` and any `use crate::{` outright, so the regex stays complete. *Evidence:* rust.module-dag value (regex forms listed); Rust path syntax: `super::` from a module declared at the crate root resolves to `crate::`.
- **[should-fix] `rust.threading`** — !Send needs one owning thread, not one process. A Stage created on a dedicated std::thread and driven by channels of plain data is sound in-process. The design's own evidence says 'one composer thread, plain data out'. The process seam also contradicts Blueprint §13.3 ('One host process, one extension module'), and it breaks §13.4's 'Promotion is a config change, not a rewrite': with openusd behind a stdio process, promoting it to composer of record makes every runtime resolve an IPC round trip through a JSON protocol that was built for logging only. *Fix:* Either record this as an explicit Blueprint deviation for Joe to sign, or keep it in-process within two crates. For the in-process route, make plexus-usd the crate that depends on plexus-core and on openusd behind a `shadow` feature, run openusd on one owned thread, and build the shadow `.pyd` from plexus-usd only when the feature is on. That is still acyclic and still two crates. *Evidence:* NEXTGEN_SCAFFOLD_PLAN.md:139 (quoted in the synthesis as 'one composer thread, plain data out'); PLEXUS_BLUEPRINT_v5.md §13.3 ('One host process, one extension module'), §13.4 ('Promotion is a config change, not a rewrite'; 'The usd-core implementation is written in Python and registered through PyO3. The openusd implementation is native Rust.').
- **[should-fix] `rust.crate-split`** — There is a third topology the synthesis does not consider: the extension module is a cdylib whose bindings use both crates, with openusd feature-gated. Separately, the Blueprint wants the usd-core Composer 'registered through PyO3' against the Rust trait. The synthesis keeps the usd-core composer pure Python with no trait registration, so at M9 the trait in composer.rs has no in-process implementor on either side. *Fix:* State which implementor the composer.rs trait has at M9. If none crosses PyO3, either drop the trait from core until promotion or flag the §13.4 deviation for Joe. *Evidence:* PLEXUS_BLUEPRINT_v5.md §13.4 (trait in plexus-core; usd-core impl registered through PyO3); synthesis rust.what-stays-python ('the usd-core Composer' stays Python), rust.crate-split rejected list.
- **[blocking] `rust.outcome-and-errors`** — The mission order puts M3 (identity) before M4 (Outcome). M3's frozen test asserts that NaN gives Unavailable naming the field, which needs the Outcome pyclass. So M3's diffs must land Outcome, outside their declared scope, and the first Rust-touching M3 test exercises more than one new PyO3 symbol, against the design's own granularity rule. *Fix:* Land outcome.rs as its own small mission before M3 (it is Blueprint §11 Phase 0 anyway), or move the NaN/Unavailable test into M4. *Evidence:* mission_graph M3 ('NaN gives Unavailable naming the field'; lands canon.rs + cache_key) vs M4 ('Lands outcome.rs'); harness.test-granularity ('the first Rust-touching test of each mission exercises only one new PyO3 symbol').
- **[should-fix] `harness.test-granularity`** — M6's tests cannot be passed one at a time. 'The same graph twice gives exactly one submit' only passes once projection, cache-key wiring, result-prim authoring into a payloaded shard, the Sdf lookup, run() orchestration and organ integration all exist. That is far beyond 150 lines, and under min_delta=1 a CPU 30B worker earns nothing until all of it lands in one diff. M4's 'three-node graph through add_node/connect passes ShaderSdrCompliance' also needs nodedef files, Sdr registration and encoding together. *Fix:* Split M6 into ordered single-capability tests: author a result prim at the key path; Sdf lookup hit/miss on a hand-built layer; a forged cacheKey is rejected; LoadNone visibility; and only then the end-to-end one-submit test. Split M4's compliance test the same way. *Evidence:* mission_graph M6 and M4 test lists; acceptance.plan.md:113, :125 ('The metric only rewards whole tests'); loop.py min_delta semantics.
- **[should-fix] `rust.edge-index`** — Wall-clock p95 tests (M5 notice -> dirty, M6 lookup < 0.1 ms, phase1 T1 < 250 ms) run inside gates on a CPU-mode box that has Houdini open. Noise then decides kept versus dropped. A good attempt can be dropped by a T1 timing blip in the regression gate, and the 'promote to Rust on a measured miss' decision flips with machine load. 'Joe's largest real graph' must also be a fixture under frozen tests/, which the design does not provide for. *Fix:* Make the Rust-promotion measurement a one-off Claude-run benchmark that Joe reviews, rather than a metric test. Keep timing asserts out of no-regression gates, or give them retry plus margin. Copy the real-graph fixture into tests/ before the mission is frozen. *Evidence:* mission_graph M5/M6 timing tests; 'The full tests/acceptance suite runs as a no-regression gate from M1 on'; CLAUDE.md 'Houdini open ... -> CPU'; acceptance.plan.md attempt-time hypothesis (CPU, 8 threads).
- **[should-fix] `rust.hashing-canonical`** — The embedded reference encoder is a second complete implementation of the PXK1 encoding. It cannot be written by the worker, and CLAUDE.md forbids Claude from editing tests/acceptance. Joe is the only legal author of that encoder, of test_layers.py's ast/cargo-metadata walker and of the 10k-node fixtures. If Claude drafts them in practice, Claude has hand-written the canonicaliser and the worker only transliterates it to Rust. *Fix:* Use precomputed golden byte strings and hex digests, derived by hand from a short written spec table, instead of an executable reference encoder. Name explicitly who authors each frozen test and how Claude's drafts are kept out of the implementation path. *Evidence:* CLAUDE.md ('tests/acceptance/ ... Never edited ... by Claude or the worker. Joe may'; 'Claude does not hand-write implementation'); mission_graph M2/M3 ('Joe adds ... with a hashlib reference encoder in the test'); rust.hashing-canonical ('one implementation beats two').
- **[nit] `rust.outcome-and-errors`** — No gate runs clippy. The gates are cargo test --workspace, build_core and pytest, so the lint enforces nothing. Separately, PyO3 already converts panics into PanicException at the boundary. *Fix:* Add a `clippy` gate (`cargo clippy -p plexus-core -- -D warnings`, which costs a CPU build), or drop the claim. *Evidence:* acceptance.toml gates (unit; a commented-out cargo test); acceptance.plan.md C3 build_core (cargo build only).
- **[nit] `harness.gates-vs-metric`** — The harness only keeps attempts that improve a metric by min_delta. A mission with no failing target gives the worker nothing to do, and loop.py's setup assumes a metric. M2's work (Joe writes a test, Claude commits symbols.py) is scaffolding, not a harness run. *Fix:* Relabel M2 as a pre-M3/M4 scaffolding step (Joe commit plus Claude commit shown to Joe) outside the harness. *Evidence:* harness/plexus_loop/loop.py:1-12, :246-260 (baseline metric, kept only on improvement); mission_graph M2.
- **[nit] `rust.hashing-canonical`** — sha2 is not in the local cargo registry; only the pyo3 0.30.1 family is. The first M3 attempt therefore needs a network fetch inside an attempt worktree, plus a cold compile of sha2, digest, generic-array and cpufeatures on CPU. That failure mode looks like a worker failure rather than an environment one. *Fix:* In the M3 scaffolding commit (Claude, before `run`): `cargo fetch` with sha2 in Cargo.lock, a warm build in the shared CARGO_TARGET_DIR, or a pinned dependency stub. *Evidence:* ls ~/.cargo/registry/src/*/ shows pyo3-0.30.1, pyo3-ffi, pyo3-macros, pyo3-build-config; no sha2.

**Lens:** All probes ran on usd-core (0,26,5) in in-memory stages; nothing was written to disk.

**Confirmed (refutation failed):**
- **Specializes vs inherits:** specializes keeps a library-tuned value, including across a reference to a root-level /Project/Defaults class with no composition errors; inherits overwrote it. Both claims hold.
- **Notice fields:** GetChangedFields exists. A value edit is info-only with ['default']; ConnectToSource is info-only with ['connectionPaths'].
- **CanConnect:** sibling graph.inputs from graph.outputs is True under a NodeGraph root; node into node across graphs is False; node from its own parent graph's input is True.
- **Expression variables:** evaluate from the root layer, are overridden by the session layer, and follow the referencer-wins rule through a reference.
- **Sdr:** NodeDiscoveryResult takes Sdr.Version. Sdr keeps node-level and port-level sdrMetadata (plexus:effect, plexus:portType). The usdShadeValidators:ShaderSdrCompliance validator exists in UsdValidation and catches a float/int mismatch on a Shader whose info:id is the dotted id, once registered with subIdentifier.
- **Schema registry:** plugInfo bases ['UsdAPISchemaBase'] matches every applied API in the wheel.
- **Wheel contents:** the pxr modules list has no Exec.

**Refuted or amended:**
- Dotted Sdr identifiers need subIdentifier.
- ShaderDefUtils.GetDiscoveryResults keys on the prim name, not info:id.
- info:implementationSource is required for the plexus source type.
- The dots-to-underscores mapping collides.
- A fresh-layer first opinion is a property resync, not a prim resync.
- Sublayer appends and content replacement are never '/' resyncs.
- The session layer is not a sublayer and is per-process.
- Writes on action threads race with dispatcher reads.

**Not probed (would need files on disk):** codeless plugin registration and payload LoadNone. openusd claims were checked against the report text only.

- **[should-fix] `usd.node-type-registry`** — The usd-core 26.5 usda shader-def parser finds the def prim by using the discovery identifier as a prim name. A dotted identifier is an invalid prim name, so the node comes back invalid. It only works if the result also carries `subIdentifier` (the 12th positional ctor argument) set to the def prim's real name. `UsdShade.ShaderDefUtils.GetDiscoveryResults` is no workaround: it sets identifier = prim name (not info:id), discoveryType '' and an invalid version. So the obvious helper registers the wrong id, and Shader nodes whose info:id is the dotted id never resolve. *Fix:* State it in the variable and the M4 worker brief: def prim name = the mapped op id (see the collision objection), discoveryType 'usda', sourceType 'plexus', subIdentifier = def prim name, Sdr.Version(major, 0). Never use ShaderDefUtils.GetDiscoveryResults. Add the subIdentifier rule to the symbol gate's arity facts. Expect one harmless Tf warning per registration. *Evidence:* Live probe on 26.5, anonymous layers, nothing written. NodeDiscoveryResult('plexus.test.add.v1', Sdr.Version(1,0), 'plexus_test_add_v1', '', 'usda', 'plexus', id, id) gives a node with bool(node) == False and the warning "Invalid prim name 'plexus.test.add.v1'". The same call plus subIdentifier='plexus_test_add_v1' gives a valid node: GetShaderNodeByIdentifier True, typed inputs, and ShaderSdrCompliance reports "Incorrect type for /G/n.inputs:a. Expected 'float'; got 'int'." on a graph node. GetDiscoveryResults returned identifier='plexus_test_add_v1', discoveryType='', version invalid.
- **[should-fix] `usd.node-type-registry`** — Without `uniform token info:implementationSource = "sourceAsset"` on the def prim, UsdShade does not see the plexus source type. GetSourceTypes() returns [] and GetSourceAsset('plexus') returns None. Any code that finds the implementation file through UsdShade (for implDigest, or to check that it resolves) silently gets nothing. *Fix:* Add `uniform token info:implementationSource = "sourceAsset"` to the nodedef file shape in usd.node-type-registry and the M4 brief. Have the M4 test assert GetSourceAsset('plexus') resolves. *Evidence:* Live probe on 26.5. Def without implementationSource: GetSourceTypes() == [], GetSourceAsset('plexus') is None. With implementationSource = "sourceAsset": GetSourceTypes() == ['plexus'].
- **[should-fix] `usd.op-defaults-subgraphs-variants`** — The op-id grammar allows underscores inside segments, so the dots-to-underscores mapping is not injective. `plexus.a_b.c.v1` and `plexus.a.b_c.v1` both map to `plexus_a_b_c_v1`. Two different ops would then specialize the same class and share defaults silently. The Sdr def prim name / subIdentifier needs the same mapping and collides the same way. *Fix:* Choose an injective mapping, for example forbid '_' in id segments (tighten the grammar), or escape '_' as '__' before mapping '.' to '_'. Put a collision test in M4. Specializes itself checks out: a library-tuned 5.0 survived specializes across a reference to a root-level /Project/Defaults class, inherits overwrote it with 1.0, and no composition errors were reported. *Evidence:* Grammar in usd.node-type-registry: `^[a-z][a-z0-9]*(\.[a-zA-Z][A-Za-z0-9_]*)+\.v[0-9]+$` (segments may contain '_'). Sdf.Path.IsValidIdentifier rejects '.', so some mapping is needed.
- **[should-fix] `usd.notice-to-dirty-graph`** — On 26.5 it is not a prim resync. An over plus an attribute authored in a fresh layer for an existing node produced a resync of the property path only (fields ['default','typeName']). The prims /G and /G/b came back info-only with empty field lists. A classifier keyed on 'prim resync' never fires for this case. The (path, fields) table must also classify resynced property paths and ignore info-only prim paths with empty fields. *Fix:* Restate the table over the union of both path sets, keyed on (property name, fields), whether the path arrived resynced or info-only. A real prim resync (new def, variant switch, apiSchemas change) stays a subtree re-read. Add a golden tuple for 'fresh layer, first property opinion' to M5's test. *Evidence:* Live probe on 26.5, in-memory. Sdf.CreatePrimInLayer(strong, '/G/b') plus AttributeSpec inputs:p in one ChangeBlock gave resynced ['/G/b.inputs:p'], info-only ['/G', '/G/b'], fields {'/G/b.inputs:p': ['default','typeName'], '/G': [], '/G/b': []}. ConnectToSource gave info-only with ['connectionPaths'], and Set gave info-only with ['default'] (those two rows hold).
- **[should-fix] `usd.project-writer-order`** — The session layer is not a subLayer. It is per-UsdStage and in-memory, so an opinion Joe authors in his UI process's session layer is invisible to the conductor process's stage. 'Promotion needs Joe's session-layer opinion' (M8) cannot be observed across processes as written. Also, the project root layer itself beats every sublayer, so anything stagekit.create_project writes into the root layer (beyond layer metadata such as expressionVariables) silently overrides graph.usda and the agents. *Fix:* Name a file-backed `joe.usda` as the strongest root sublayer for cross-process human decisions. Reserve the true session layer for per-process transient state. Keep the project root layer opinion-free apart from layer metadata and the /Project PlexusProjectAPI stub. *Evidence:* Live probe on 26.5: the session layer identifier is not in root.subLayerPaths. A stronger sublayer's temperature=9 lost to the root layer's own 1.0 (Get() == 1.0). PLEXUS_SPEC.md:138 (un-mute is a session-layer opinion); M8 test list ('promotion without Joe's session-layer opinion stays parked').
- **[should-fix] `usd.authoring-path`** — UsdStage does not support a write concurrent with reads. An Sdf edit on a layer in the stage's layer stack recomposes the stage and delivers ObjectsChanged synchronously on the authoring thread. A dispatcher Get() running at the same moment is a data race. Nothing in the synthesis serializes the two. *Fix:* One stage lock per NeuronRuntime, held by ctx.author/author_asset (ChangeBlock plus Save) and by the dispatcher's value reads and paths() reads. Or marshal authoring onto the dispatcher thread through a queue. Put it in the S4 brief. *Evidence:* PLEXUS_SPEC.md:119 (actions run on worker threads; dispatcher never blocks on an action); acceptance.plan.md:100 (action workers author); rust.what-stays-python lists both 'action worker threads' and 'composed-value reads' with no lock; the notice probe shows notices arrive on the authoring call's thread.
- **[nit] `usd.notice-intake`** — Neither produces an ancestor resync on 26.5. Appending an empty sublayer is info-only on '/' (fields subLayers, subLayerOffsets). Appending a non-empty one resyncs only the property paths it carries, with info-only ancestors. Replacing a layer's content (ImportFromString/TransferContent, the same diff path Reload takes) is info-only on the changed property. The first clause (prim path equals scope or is under scope) is what actually wakes the neuron. The extra clause is harmless, but its rationale is false and could mislead the worker. *Fix:* Keep the clause for genuine '/' or reference resyncs, but correct the rationale in the plan and the brief so nobody relies on it for T6. *Evidence:* Live probe on 26.5: empty sublayer append gave ([], ['/']) fields ['subLayerOffsets','subLayers']; non-empty append gave resynced ['/Exchange/LookState.temperature'], info-only ['/', '/Exchange', '/Exchange/LookState']; content replace gave ([], ['/Exchange/LookState.temperature']).
- **[nit] `usd.exchange-writer-order`** — On 26.5 a sublayer append is never a '/' resync. It is info-only '/' (empty layer) or property-level resyncs (non-empty layer). Registering before open is still a fine ordering, but the stated reason is wrong. *Fix:* Keep the order and reword the reason to 'so the axon's first event is not our own registration'. *Evidence:* Same notice probe as the usd.notice-intake objection.
- **[nit] `usd.model-identity`** — The usd-core half holds. The openusd half is unsupported: the report lists what openusd 0.8.0 has (usda/usdc, all arcs, connectionPaths, ConnectionGraph, UsdShade views, StageSink, composition_errors) and says nothing about expressionVariables or asset-path expression evaluation. If it does not evaluate them, every model asset path in M9's parity corpus differs. *Fix:* Mark openusd expression support needs-measurement, and add an expression-variable case to the M9 parity corpus (or exclude it explicitly). Also note that `.path` on the returned Sdf.AssetPath is the backtick expression, so readers must use evaluatedPath/resolvedPath. *Evidence:* Live probe on 26.5: evaluatedPath 'C:/store/...' from root vars; the session layer override gives 'D:/other/...'; through a reference, the referencer's own var wins ('E:/projstore/...'), else the referenced layer's var applies. NEXTGEN_SCAFFOLD_PLAN.md:139 openusd capability list has no expression variables.
- **[nit] `usd.schema-plugin`** — That is the schema.usda source shape, not generatedSchema shape. Pixar's 26.5 generatedSchema.usda API classes (MaterialBindingAPI, NodeGraphNodeAPI) carry neither inherits nor apiSchemaType, because kind comes from plugInfo schemaKind. It is probably ignored by the registry, but it is unverified without a disk-backed plugin, and the worker should copy the proven shape. The plugInfo `bases: ["UsdAPISchemaBase"]` correction is confirmed: every singleApplyAPI in the wheel uses it. *Fix:* Brief: `class "<Name>" { <attrs> }` with no inherits or apiSchemaType, matching pxr's generatedSchema. *Evidence:* C:/Python314/Lib/site-packages/pxr/pluginfo/usdShade/resources/generatedSchema.usda:88-94; usdUI/resources/generatedSchema.usda:6-12; plugInfo scan of usd, usdGeom, usdLux, usdShade, usdUI and others: bases ['UsdAPISchemaBase'] for every singleApplyAPI.

**Lens:** I read CONTRACT.md, all phase1 and phase2 frozen tests, _support.py, conftest.py, acceptance.toml, acceptance.plan.md §1 and §4-§9, loop.py (preflight, baseline, keep rule), metrics.py, Spec §4-§7, and Pixar's usdShade plugInfo.json and generatedSchema.usda on 26.5.

Live probes (no files written):
- GetAppliedSchemas() filters out unregistered API schemas.
- A dataclass field with a dict default raises ValueError.
- Replacing a layer's content gives a fine-grained info-only notice, not a resync.

Claims that held up:
- Phase-2 item count is 7 (T7 x5 including the parametrize x2, T8 x2), which makes CONTRACT's 18 equal to 11 + 7, not 11 + 6 + 1.
- `bases: ["UsdAPISchemaBase"]` matches Pixar's plugInfo. The plan's `/TfType` is wrong.
- 26.5 generatedSchema classes carry no inherits or apiSchemaType customData, but the extra metadata is unlikely to matter for T0.
- No T0 token or Spec §3 text hits ENGINE_TERMS ('comfyui' is not banned).
- RUST_CFG strips `#[cfg(` and `#[cfg_attr(` in .rs only. The root Cargo.toml and target/ sit outside the T8 scan roots.
- T5 needs the gate check before CreatePrimInLayer, and the synthesis has that order.
- T3's timeline (wake, trips at +2/+4/+6, muted on the third) follows from peek-then-admit with the half-open window.
- T2's accumulate-until-wake follows from seed filling only None slots plus commit_wake.
- T4's single-layer property stack holds with one edit-layer handle.
- PredicateError re-export identity works for pytest.raises.
- T7's phase-2 asset location and absolute assetPath are kept.
- The expression-variable form at M6 stays compatible with T7's `resolvedPath or path` read.
- The neutral IR and generated cozy nodedefs outside plexus/ keep T8 green by structure.

- **[blocking] `usd.schema-plugin`** — T7 asserts `"PlexusAssetAPI" in prim.GetAppliedSchemas()` on both projects, in the pytest process. On usd-core 26.5, GetAppliedSchemas() filters out schemas that are not registered, so T7 fails even when author_asset prepends the listOp correctly. Both obvious fixes collide with other parts of the design. Setting os.environ inside plexus/__init__ is stdlib-only, so it fits rank 0, but it does nothing once pxr has loaded, and the T6 RUNTIME script imports pxr before plexus. Plug.Registry().RegisterPlugins(plugin_dir()) needs pxr, which the rank table forbids in plexus.schema (rank 0, 'stdlib only', and 'only ranks >= 2 import pxr'). *Fix:* Pick one mechanism and one module, and put it in the S1/M1 worker brief. Recommended: a rank-2 module that every runtime entry point imports first (membrane.exchange or stagekit, or allow pxr.Plug in plexus.schema and move it in the table) calls Plug.Registry().RegisterPlugins(str(plugin_dir())) at import. Before `run`, measure whether a RegisterPlugins call made after the first Usd.Stage use is still seen by UsdSchemaRegistry. If it is not, registration must happen before any stage opens, and that ordering rule goes into the brief. *Evidence:* Live probe on usd-core 0.26.5: a prim with apiSchemas prepend ['PlexusAssetAPI'] and no plugin gives GetAppliedSchemas() == [] and GetPrimTypeInfo().GetAppliedAPISchemas() == ['PlexusAssetAPI']. tests/acceptance/phase2/test_t7_round_trip.py (test_neuron_round_trip: `assert prim and "PlexusAssetAPI" in prim.GetAppliedSchemas()`). test_t0_schema_gate.py sets PXR_PLUGINPATH_NAME only in the child env. test_t6_truth.py RUNTIME runs `from pxr import Sdf, Usd` before `from plexus.core.neuron import NeuronRuntime`. The synthesis's own usd.node-type-registry says 'the schema registry is a load-time singleton'.
- **[blocking] `usd.notice-intake`** — A dataclass field with a dict default raises ValueError when the class is defined. Taken literally, plexus.core.axon fails to import, so T1 and every slice_ test that reaches the axon error out. The same mistake in Job breaks `from plexus.organs.protocol import Job` in every T7 test. CONTRACT writes `inputs: dict = {}` as a signature; the synthesis writes it as a dataclass, which a worker will copy as is. *Fix:* Specify `fields: Mapping[str, tuple[str, ...]] = field(default_factory=dict)` (or types.MappingProxyType({})) and `inputs: dict = field(default_factory=dict)` in the worker brief. *Evidence:* Live probe on Python 3.14.2: `@dataclass(frozen=True) class E: ... fields: Mapping[str, tuple] = {}` raises 'ValueError mutable default <class 'dict'> for field fields is not allowed: use default_factory'. tests/acceptance/CONTRACT.md:25 (StageEvent), :55 (Job).
- **[blocking] `harness.test-granularity`** — loop.py runs every gate on the baseline worktree and raises RefuseToStart if any gate fails. At M1 the baseline has phase2 failing by definition, because phase2 is the metric target, so a gate over tests/acceptance makes M1 unrunnable. The same holds for every later mission whose frozen tests live under tests/acceptance/phase3 or phase4. *Fix:* The no-regression gate is the set of phase directories (and guard files) that were green when the mission started. It never includes the current target or any later phase. Spell out the path list per mission file. *Evidence:* harness/plexus_loop/loop.py _run(): 'Baseline on the branch tip: the gates must already pass ... raise RefuseToStart(f"before any change, {why}...")'. _evaluate() returns on the first failing gate. tests/acceptance/phase2 is the M1 metric target.
- **[should-fix] `rust.module-dag`** — The rules contradict each other. (a) A `#[pymodule] fn _core(m: &Bound<'_, PyModule>)` in lib.rs names pyo3, and so does plan C2's scaffold lib.rs. A guard written as specified fails at baseline, and loop.py refuses to start. (b) The Python table puts stagekit (which imports membrane.exchange) and membrane.exchange both at rank 2, and puts graph.{encode,index,dirty,keys} and core.results all at rank 4 although dirty, keys and results consume index and encode. Strictly-lower-rank forbids every one of those edges. (c) On the Rust side, canon.rs (rank 1) returns Outcome from outcome.rs (also rank 1), and graph.rs turns GraphErr into Outcome reasons the same way. Both are same-rank imports. (d) 'Passes trivially' is false: `cargo metadata` errors when there is no Cargo.toml, and after C2 rule (a) fails. Because the guard is frozen, a contradiction written into it blocks every attempt until Joe edits it. *Fix:* Move the #[pymodule] fn into py.rs; lib.rs keeps only `#[cfg(feature = "python")] mod py;` and the other mod lines (PyInit__core is exported from any module). Either let canon and graph sit above outcome (outcome at rank 1, canon and graph at rank 2, composer at 3, py at 4) or do the Outcome conversion only in py.rs. Re-rank the Python table so that every listed edge goes strictly downward. Before Joe freezes the guard, run it against the C2 scaffold and confirm it passes at baseline. *Evidence:* acceptance.plan.md §7 C2 ('src/lib.rs with an empty #[pymodule] fn _core behind the feature'). crate_graph text: '3 py.rs ... the only file that may name pyo3' and 'lib.rs declares modules and #[pymodule] fn _core'. Python ranks 2 and 4 as listed. boundary_types: cache_key(...) -> Outcome[str]. loop.py baseline gate check.
- **[should-fix] `usd.authoring-path`** — T6 calls wait_idle, then Reload() on every layer, then dumps /Exchange and /Plexus from memory. The parent re-dumps from disk and asserts the two are equal. The wake in T6 happens after the Reload (the reload is what delivers project A's writes), so runtime-owned writes made after the action, such as plexus:state transitions, plexus:lastWake at quiesce and any plexus:flag*, show up in the child's `before` dump and are missing from `after` unless they are saved too. CONTRACT requires every opinion the runtime or its neurons author to be saved as it lands, not only ctx calls. *Fix:* State the rule as: every write to edit_layer (register's neuron prim and PlexusNeuronAPI attrs, state awake/dormant/muted, lastWake, gate and budget flags, ctx writes) is followed by edit_layer.Save() before wait_idle can return true. *Evidence:* tests/acceptance/phase1/test_t6_truth.py RUNTIME (wait_idle -> layer.Reload() for every layer -> wait_idle -> dump). The parent reloads and compares `after_x == before["exchange"]`. tests/acceptance/CONTRACT.md:31 ('every opinion the runtime or its neurons author lands here ... and is saved to disk as it lands'). Spec §6 step 7 (quiesce updates lastWake and state).
- **[should-fix] `rust.threading`** — test_bad_predicates_fail_at_registration builds two NeuronRuntimes whose register() raises. _support.start_neuron sets slice_.runtime only after rt.start(), so the fixture's teardown never stops them. If __init__ registers the Tf.Notice listener or starts a non-daemon dispatcher or action thread, the pytest metric process can hang at exit, the metric times out, and the attempt (or the baseline) is lost. *Fix:* Pin this in the brief: __init__ opens the stage and the edit layer only. The notice registration and the threads start in start(). Every thread is daemon=True. Leaked runtimes must not keep the interpreter alive. *Evidence:* tests/acceptance/_support.py start_neuron (rt constructed -> rt.register(...) raises -> rt.start() and `self.runtime = rt` never run). conftest.py teardown stops only s.runtime. harness/plexus_loop/metrics.py: 'metric run timed out' -> MetricResult(None).
- **[should-fix] `mission_graph`** — M3's frozen test cannot pass without an Outcome type that the mission graph only introduces at M4, so M3 either stalls at baseline or lands Outcome early without saying so. The M3 calls (intent_hash, cache_key) and M4's graph calls become test-called surface, and CONTRACT.md is the frozen file that pins that surface ('The tests only ever call what is listed here'). It sits under tests/acceptance/**, which the harness freezes, and the synthesis never says Joe must extend it. *Fix:* Land outcome.rs in M3 (or move the NaN case to M4), and reorder ranks to match. For every mission that adds test-called API, say that Joe extends tests/acceptance/CONTRACT.md together with the new frozen tests. *Evidence:* boundary_types M3: cache_key(...) -> Outcome[str], 'non-finite ... come back as Unavailable'. mission_graph M3 test list, and 'M4 ... Lands outcome.rs'. tests/acceptance/CONTRACT.md:3,5. acceptance.toml frozen = ['tests/acceptance/**', ...].
- **[should-fix] `usd.model-identity`** — T7's GRAPH names ckpt_name 'base.safetensors', and the fake engine has no model folders. If submit() or result() ever consults the index, T7 breaks: either submit returns Unavailable instead of a JobHandle (len(comfy.prompts) == 1 fails), or modelHashes resolution raises inside the action (records stays empty). The synthesis puts this behaviour in 'the Cozy organ' without limiting it to the M7 importer. *Fix:* Pin this: CozyOrgan.submit/result never gate on the model index. modelHashes is a list (possibly empty) authored as string[]. Unavailable for an unindexed model is raised only by the importer and projection (M7), never by the organ protocol calls T7 exercises. *Evidence:* tests/acceptance/phase2/test_t7_round_trip.py GRAPH node '4' ckpt_name 'base.safetensors'; FakeComfy serves no model files; test_link_arrays asserts len(comfy.prompts) == 1; the metadata only needs a 'modelHashes' key. CONTRACT.md: CozyOrgan(endpoint, output_dir).
- **[nit] `mission_graph`** — loop.py always measures the metric and keeps an attempt only on a strict gain. A guard that passes at baseline gives no metric to climb, so M2 cannot run as a mission. *Fix:* Call M2 what it is: Joe freezes the guard and Claude commits the symbols scaffolding. It is not a harness mission. *Evidence:* harness/plexus_loop/loop.py:1-12 and _evaluate(); harness/plexus_loop/metrics.py _pytest_failures.
- **[nit] `usd.notice-intake`** — Under the synthesis's own eval rule, changed(i) is exact membership of paths[i]. A '/' resync would make the neuron a candidate, but changed(TEMP) would still be false, so T6's `changed AND delta` predicate would never wake. A value-only content replacement actually arrives as a fine-grained info-only change on the attribute, so the prefix clause already covers T6. The stated rationale points the worker at a mechanism that would not produce the wake. *Fix:* Correct the rationale. Either drop the ancestor clause, or also define changed(i) as true when a resynced path is an ancestor of paths[i]'s prim, and state which one. *Evidence:* Live probe on 26.5: replacing layer content with ImportFromString yields info ['/Exchange/LookState.temperature'], resync []. rust.predicate-repr: 'changed(i) = paths[i] in the changed set'. test_t6_truth.py RUNTIME predicate 'changed(...) AND delta(...) > 0.2'.
- **[nit] `usd.authoring-path`** — AssetRecord carries only path, sha256 and metadata (engine, engineJobId, envFingerprint, organVersion, modelHashes). seed, colorspace, createdAt, retryOf, retryReason and sourceLayer are not in it. T7 needs plexus:sourceLayer == edit_layer.identifier and plexus:envFingerprint == metadata value. A worker reading 'from the record' may skip the stamp, or fail with a type error if it authors a non-list modelHashes as string[]. *Fix:* Give the exact field mapping in the M1 brief: sourceLayer from edit_layer.identifier, seed and colorspace from the Job or left unauthored, modelHashes as list[str]. *Evidence:* tests/acceptance/CONTRACT.md:56 (AssetRecord fields); test_t7_round_trip.py test_neuron_round_trip (sha256, envFingerprint, sourceLayer asserts).


## Appendix D · Risks named by the synthesis

- S3 is the first Rust diff. Under min_delta=1 it must land, in one kept attempt, the parser, the scope check, the PyO3 PredicateError, the predicate.py re-export and NeuronRuntime.__init__/register, all compiling on CPU beside Houdini, or it earns nothing. Mitigation: the worker brief carries the exact type signatures from rust.predicate-repr and rust.pyo3-surface so the worker writes bodies, not design.
- pyo3 0.30 with abi3-py311 is unproven to build and import on this machine's Python 3.14.2 with cargo 1.99.1. If it fails, `run` refuses at baseline. Measure during C2/C3 before `run`.
- The acceptance plan's worker brief (acceptance.plan.md:188) says plugInfo `bases: ["/TfType"]`; pxr's own plugInfo uses `bases: ["UsdAPISchemaBase"]`. A worker that follows the brief gets FindAppliedAPIPrimDefinition == None with no other symptom and burns attempts on S1. Correct the brief before `run`.
- The scaffold plan's one 'measured case for Rust' (NEXTGEN_SCAFFOLD_PLAN.md:137) reads a 238 ms open-time total as index cost. Under Option A the pxr extraction stays in Python in any design; the per-notice closure (13 ms in the report's topology) is the real budget breaker and the only part Rust fixes. If the plan line is not corrected, M5 could spend attempts porting the wrong thing.
- T8 traps are structural: `\bcfg\b` matches a Rust doc comment, a Python variable, or a `[target.'cfg(windows)']` table in Cargo.toml (RUST_CFG strips .rs only); `SaveImage` matches by substring; any ComfyUI fixture or generated nodedef as .json/.usda/.toml under plexus/ outside organs/cozy/ fails. Generated cozy nodedefs must go to ${PLEXUS_STORE}.
- Phantom pxr/Sdr APIs from the 30B worker are SYNAPSE's top failure class and one architect hit `Sdr.ShaderNodeDiscoveryResult` itself (it does not exist on 26.5; NodeDiscoveryResult does and wants an SdrVersion). Phase 1's pxr surface is small enough to survive; M4 is not, so the symbols gate must land before it.
- Sdr live registration is single-run evidence that needs a real .usda file; an id containing '@' is unproven and invalid as a prim name, which is why this synthesis uses `.vN`. If file-backed registration fails for a store path, the fallback (typeless prim + PlexusNodeAPI with connectable behaviour) costs Sdr's type validation.
- PlexusNodeAPI and PlexusResultAPI are Spec §3 patches. T0 tolerates them, but they need Joe's signature and a T0-style gate of their own; a worker attempt aimed at graph encoding before M4's tests are frozen is dropped by the harness, so graph work must stay out of every M0/M1 brief.
- Cache-key policy (implDigest in, envFingerprint out) can serve a stale result after an environment change that alters outputs without changing an op's implementation (a torch or CUDA kernel change). Joe must choose strict or shareable before results persist; reversing later changes the key domain and orphans every stored result.
- Float widening: pxr returns 0.1f as 0.10000000149011612. Any canonicaliser fed Python reprs instead of type-directed bytes splits F7 identity silently; the golden vectors in M3's test are the only guard.
- Two deferrals drift from Blueprint v5.3 and need Joe's word: §5.1 puts the scheduler on tokio (this design keeps all threads in Python through M8) and §11 Phase 0 lists Outcome, identity registry and intent ledger (this design lands Outcome at M4 and identity at M3). Documented deferral, not silent drift.
- The content-addressed result layout makes cross-project hits reference another project's results layer; an archived project breaks provenance of adopted results unless they are re-authored locally before archive.
- The 50k-prim rotation and 500-prim batch limits are Moneta numbers from USD 0.25.5. Until re-measured on 26.5 (M6) they are unknown, not defaults.
- Attempt time per mode is unmeasured; the plan's hypothesis is 25-30k tokens of prompt evaluation per attempt on 8 CPU threads. A warm shared CARGO_TARGET_DIR for every gate (plan C3) is mandatory, and the first run's ledger must report CPU vs GPU attempt time before any mission after M0 is scheduled.
- Phase-2 item count: the plan says 6, the files give 7 (T7 x5 including the x2 parametrize, T8 x2). Re-count at M1 setup so the mission report's 'tests pass versus baseline' is right.

