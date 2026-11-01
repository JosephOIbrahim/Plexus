# Plexus · Next-generation scaffold plan

Status: **draft for Joe, being written.** Nothing in this plan has been applied. Research agents are still reporting; sections marked _pending_ fill in from their findings.

**Goal (Joe, Nov 1):** create the next generation of ComfyUI, locally, using frontier and local AI, from the ground up — Rust where appropriate, OpenUSD as the substrate. Plexus is the next generation of Comfy-Cozy. Comfy-Cozy (`G:\Comfy-Cozy`) and SYNAPSE (`C:\Users\User\SYNAPSE`) are architecture references only; nothing is copied from either.

---

## 1 · First principles: what the product must be

_pending synthesis_

## 2 · The architecture as a graph

_pending synthesis_

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

Notice delivery 4 µs; a 500-edit ChangeBlock is one notice with 500 paths, extracted in 0.55 ms; one class edit fanned out to 1,001 paths. 50k result prims: 44 MB usda, LoadNone 15 ms, payload load 111 ms. **Python indexing breaks Spec §11's 10 ms at 10k nodes, so the edge index belongs in Rust** — the first measured case for Rust.

**`openusd` 0.8.0:** has usda/usdc, all arcs, composed `connectionPaths`, a `ConnectionGraph` (sources, sinks, resolve_chain), UsdShade views, StageSink notices with incremental invalidation, `composition_errors`. Missing: Sdr (read nodedef layers directly); schema registry, fallbacks and property-stack queries exist on `main` only, so shadow `property_stack` waits. `Stage` is `Rc` + `RefCell`, so `!Send`: one composer thread, plain data out. No stage cache, no parallel composition.

**OpenExec: watch, don't build on.** 25.08 preview; 26.08 supports one connection only and its IR is "not yet ready for production"; absent from the 26.5 Python wheel (no `pxr.Exec`/`ExecUsd`/`Vdf`). Computations are in-process C++ plugins, not 30-second GPU jobs. Take its shape: value-key requests, sparse invalidation, a cycle is an error. Revisit when Python bindings and multi-connection dataflow land.

**Rejected:** (1) one generated typed schema per op — the registry freezes at load, so a new op restarts every conductor, openusd can't see schema fallbacks (parity drift), and op versions become schema migrations. (2) plain prims + relationships, or workflow JSON in an attribute — breaks F8, no typed ports or validators, arcs can't reach into a blob. **Kept as fallback:** typeless prims + `PlexusNodeAPI` declaring `providesUsdShadeConnectableAPIBehavior` (codeless APIs get a default behaviour, `connectableAPIBehavior.cpp` v26.05 L640-650).

**T8 note for the encoding:** example op parameters must avoid engine terms (`cfg`, sampler names) anywhere under `plexus/` or `crates/`; neutral op ids live in the core, and the organ maps them.

## 4 · Constraints the scaffold must respect

_pending synthesis_

## 5 · Mission graph (harness)

_pending synthesis_

## 6 · What the scaffold team writes, and what it never writes

_pending synthesis_

## 7 · Decisions for Joe

_pending synthesis_
