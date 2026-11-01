# PLEXUS — Engineering Spec v2.1 (build baseline)

Companion to `PLEXUS_BLUEPRINT.md` (concept, market, axioms). The blueprint says *why*; this document says *exactly what*. Normative for Phases 1–2; Phase 3 items are sketched and marked. Anything not specified here and not derivable from an axiom is deferred, not implied. **v2.1 folds in Spec Patch 01** (ComfyUI developer-insights cross-reference: foresight advisory-only, env fingerprints, retry lineage, organ-owned correlation, no-resume contract); the diagnostic record with provenance marks lives in `PLEXUS_SPEC_PATCH_01.md`.

---

## 1 · Runtime & dependencies

- Python ≥ 3.11. OpenUSD 26.x via `pxr` **only** — no Omniverse Kit, no vendor USD forks (A1).
- Primary target: Windows 11 (reference machine: Threadripper PRO / RTX 4090). Organ processes may run anywhere reachable.
- LLM access via the existing Cozy provider abstraction (imported, not copied).
- **Thin-glue rule (A6 / §7):** no source files move between Cozy, Synapse, Moneta, and PLEXUS. Reuse = `pip install -e` imports, subprocess calls, or MCP. A copied file is a defect.
- **Stage in git from day one:** session, project, and exchange `.usda` layers live in a git repo from the first commit — the stage is the truth (T6), and text-based layers diff cleanly. Provenance of the provenance.
- **Envelope revalidation:** the Moneta performance envelope (§11 budgets) was measured on OpenUSD 0.25.5; re-run `usd_metabolism_bench_v2.py` once against 26.x before trusting the numbers.

## 2 · Repository shape

```
plexus/
├── schema/            # MonetaSchema-pattern codeless schemas + plugInfo.json
├── core/
│   ├── axon.py        # stage observer (§5)
│   ├── predicate.py   # grammar + evaluator (§4)
│   ├── neuron.py      # runtime, states, budgets (§6)
│   └── stagekit.py    # handle helpers (Moneta-style open/close, URI registry)
├── membrane/
│   ├── exchange.py    # stack layout, registration, strength order (§7)
│   └── gate.py        # publication gate v0 (§7.3)
├── organs/
│   ├── protocol.py    # Organ Protocol (§8)
│   └── cozy.py        # ComfyUI organ via Comfy-Cozy MCP (§8.2)
└── tests/             # acceptance tests T1–T8 (§9–§10)
```

## 3 · Schemas (normative)

Codeless applied-API schemas, Moneta recipe: authored `.usda` source → `usdGenSchema` with `skipCodeGeneration` → `plugInfo.json` + `generatedSchema.usda` committed → **subprocess acceptance-gate test** asserting `Usd.SchemaRegistry().FindConcretePrimDefinition/FindAppliedAPIPrimDefinition` is non-None and round-tripping every attribute. Names USD-camelCase. All timestamps ISO-8601 UTC strings.

**`PlexusProjectAPI`** (applied to a project root prim)

| Attribute | Type | Notes |
|---|---|---|
| `plexus:projectId` | `string` | UUID |
| `plexus:status` | `token` | allowed: `active`, `paused`, `archived` |
| `plexus:created` | `string` | ISO-8601 |
| `plexus:provenancePolicy` | `token` | allowed: `strict` (assetless opinions rejected), `advisory` |

**`PlexusAssetAPI`** (applied to each generated-asset prim)

| Attribute | Type | Notes |
|---|---|---|
| `plexus:assetPath` | `asset` | on-disk path — the stage references, never embeds (A9) |
| `plexus:sha256` | `string` | of the asset file |
| `plexus:engine` | `string` | organ id |
| `plexus:engineJobId` | `string` | organ-native id |
| `plexus:seed` | `int64` | |
| `plexus:colorspace` | `token` | allowed: `acescg`, `srgb`, `linear`, `raw` |
| `plexus:modelHashes` | `string[]` | workflow.lock lineage |
| `plexus:sourceLayer` | `string` | layer identifier of the authoring opinion |
| `plexus:createdAt` | `string` | |
| `plexus:envFingerprint` | `string` | environment hash from the organ's run report; the diff key for drift (baselines from day one — undiffable if backfilled) |
| `plexus:organVersion` | `string` | organ + adapter version at execution time (our moving part, drifts independently of the engine) |
| `plexus:retryOf` | `string` | prim path of the prior attempt; empty on first attempt |
| `plexus:retryReason` | `token` | allowed: `none`, `quality`, `transient`, `operator` |

**`PlexusNeuronAPI`** (applied to a neuron prim under `/Plexus/Neurons/`)

| Attribute | Type | Notes |
|---|---|---|
| `plexus:scope` | `string` | prim path watched (subtree) |
| `plexus:predicate` | `string` | grammar §4 |
| `plexus:tools` | `string[]` | MCP tool allowlist |
| `plexus:budgetWakes` | `int` | wakes per window |
| `plexus:budgetWindow` | `double` | seconds |
| `plexus:budgetTokens` | `int` | per wake; 0 = reflex-only neuron |
| `plexus:state` | `token` | allowed: `dormant`, `awake`, `muted` |
| `plexus:lastWake` | `string` | |

**`PlexusOrganAPI`** (applied to organ prims under `/Plexus/Organs/`)

| Attribute | Type | Notes |
|---|---|---|
| `plexus:organId` | `string` | |
| `plexus:kind` | `token` | allowed: `comfyui`, `houdini`, `neuralPreview`, `wfm` |
| `plexus:endpoint` | `string` | URL / MCP address |
| `plexus:capabilities` | `string[]` | interrogated at registration, cached here |
| `plexus:costHint` | `token` | allowed: `free`, `cheap`, `expensive` — v0 cost model |

`PlexusSignalAPI` is **deferred**: in Phases 1–2, inter-agent signaling is plain attribute opinions on membrane prims (§3.5 of the blueprint needs no schema to work). Revisit when a signal needs typed metadata.

## 4 · Predicate grammar v0

Design constraints, in order: deterministic, evaluable in microseconds against composed values, serializable in one string attribute, no allocation-heavy parsing at fire time (compile once at neuron registration).

```
predicate := clause { "AND" clause }
clause    := "changed(" path ")"
           | "delta(" path ")" cmp number
           | "attr("  path ")" cmp literal
           | "exists(" path ")"
cmp       := ">" | ">=" | "<" | "<=" | "==" | "!="
path      := USD attribute path, absolute, within the neuron's scope
literal   := number | quoted string | token
```

- **No `OR` in v0.** Two predicates = two neurons. Keeps evaluation branch-free and each wake attributable to one condition. (Deferred decision D1.)
- `changed(p)` — p appears in the recompose event's changed set.
- `delta(p)` — |composed(p) − cached(p)| for numeric attrs; cache is per-neuron, updated **only on wake** (so sub-threshold drift accumulates until it matters — intentional).
- Evaluation order: syntactic left-to-right, short-circuit. Paths outside `plexus:scope` are a registration-time error, not a runtime check.
- Compile target: a Python closure over `Usd.Stage.GetAttributeAtPath`; no `eval`, no regex at fire time.

## 5 · Axon (stage observer)

`PlexusAxon` — TopsEventBridge pattern, retargeted:

- Registers `Tf.Notice.Register(Usd.Notice.ObjectsChanged, cb, stage)` per session stage.
- **Callback discipline (thread-defensive, per Synapse):** the notice callback does exactly two things — extract `GetResyncedPaths()` + `GetChangedInfoOnlyPaths()` into a plain `StageEvent(paths, resynced, t)` dataclass, and enqueue it. No composition queries, no neuron logic, no logging I/O inside the callback.
- A single dispatcher thread drains the queue with a **debounce window of 50 ms** (configurable): events within the window coalesce into one `StageEvent` with a merged path set.
- Dispatcher → predicate evaluation (§4) → wake pipeline (§6). Neuron actions run on worker threads returning `TurnHandle`-style futures (Synapse Spike 2.4 pattern); the dispatcher never blocks on an action.
- Teardown mirrors SceneLoadBridge's reconcile fix: `cool()` re-runs if subscriptions mutate mid-handler.

## 6 · Neuron runtime

**Wake pipeline (strict order):**
```
StageEvent → scope filter → predicate eval → budget gate → risk gate → ACT → author → quiesce
```
1. **Scope filter:** event path set ∩ neuron scope subtree; miss → done.
2. **Predicate eval:** compiled closure against the *composed* stage.
3. **Budget gate:** sliding-window count (`budgetWakes` per `budgetWindow`) + a **global session wake budget** (default 60 wakes/min across all neurons). Trip → increment counter; 3 consecutive trips → `state = muted` + flagged prim opinion (visible, never silent).
4. **Risk gate:** every tool in the action passes the Cozy default-deny classifier (imported). Unclassified tool → denied, by construction.
5. **ACT:** reflex recipe if one matches the intent (tier 1); else agent turn within `budgetTokens` (tier 2/3 routing per the Synapse decision matrix).
6. **Author:** opinions land **only** in the neuron's own edit-target layer (A6). Any other edit target is a hard error.
7. **Quiesce:** update `lastWake`, delta cache, `state = dormant`.

**Retry authoring (Patch 01-D):** a retried organ job authors a *new* asset prim carrying `plexus:retryOf` and `plexus:retryReason` — never an overwrite of the prior prim. Two runs, two records, one intent; both carry the neuron's correlation id. Upstream idempotency, if it ever ships, becomes an organ-level dedupe optimization with no schema change.

**States:** `dormant → awake → dormant` normal path; `→ muted` only via budget trips or operator action; un-mute is operator-only (an opinion in the session layer — human overrides are strongest, per §2.2).

## 7 · Membrane (exchange stack)

**7.1 Layout.** `shared/exchange/` is a layer stack rooted at `exchange.usda`, whose sublayer list is the **explicit, human-ordered strength ranking** of participants — registration appends weakest; reordering is an operator edit to `exchange.usda` itself, never automatic. One sublayer per participant: `from_<participantId>.usda`. Every writer keeps exclusive ownership of its URI — Moneta's `_ACTIVE_URIS` discipline holds unmodified.

**7.2 Reference.** A project learns by referencing the *composed* exchange root (`/Exchange`) — never a sibling's project stack directly. Reference arcs sit weaker than local opinions (LIVRPS), so learned influence is advisory by arbitration law.

**7.3 Publication gate v0.** Before any opinion lands in a participant's exchange sublayer: the target prim path must match that participant's **allowlist** (default: `/Exchange/<participantId>/**` plus explicitly granted shared paths like `/Exchange/LookState`). Deny → the write is dropped and flagged on the neuron prim. The classifier-based egress gate is Phase 3 (D2); v0 is paths only — sufficient for the slice, honest about its limits.

## 8 · Organ Protocol

**8.1 Contract (v0):**
```python
class Organ(Protocol):
    def profile(self) -> OrganProfile            # → PlexusOrganAPI fields
    def capabilities(self) -> list[str]          # interrogation
    def submit(self, job: Job) -> JobHandle      # non-blocking
    def stream(self, h: JobHandle) -> Iterator[Progress]
    def result(self, h: JobHandle) -> AssetRecord  # path, sha256, metadata
```
`AssetRecord → PlexusAssetAPI` authoring is done by the caller (core), never the organ — no engine internals leak upward. **And no engine's missing guarantees leak upward either (Patch 01-C):** correlation is the organ's problem. `submit()` returns a `JobHandle` carrying the PLEXUS-side correlation id; reconstructing engine-job → correlation lives entirely inside the organ. Core never sees a `prompt_id` and never holds a side-table. When an engine gains native client metadata, the organ deletes its reconciliation layer and this contract does not change.

`JobHandle` promises submit / stream / result and **nothing** about resume, checkpoint, or replay (Patch 01-E): arbitrary graphs are not checkpointable and engine scheduling is request-level. An organ whose engine genuinely supports resumption may expose it as a capability string, never as part of the base contract.

**8.2 Cozy organ mapping (Phase 2):**

| Protocol | Comfy-Cozy surface |
|---|---|
| `profile/capabilities` | `inspect` + object_info cache |
| `submit` | validated execute path (validate-before-execute gate preserved) |
| `stream` | WebSocket progress events |
| `result` | run report + workflow.lock fields → `sha256`, `modelHashes`, timings |

Vendor rule enforced here structurally: everything CUDA lives behind this table.

**Poll for truth (Patch 01-C):** `result()` treats WebSocket completion as a responsiveness hint and `/history/{prompt_id}` as the source of truth — no `AssetRecord` is returned until history is readable and the asset file is stat-able. Emitting a result on the WS event alone reproduces a known race.

**Link-array invariant:** any parse → mutate → serialize round trip preserves `["node_id", output_index]` link references exactly. The number-one failure mode in ComfyUI agents; the graph looks correct and executes wrong. Tested explicitly in T7.

## 9 · Phase 1 acceptance tests (the slice, testable)

Reference hardware = the Threadripper. All timings p95 over 50 trials.

- **T1 — Propagation:** opinion authored in A's exchange sublayer is visible in B's composed value **< 250 ms** end-to-end (author → notice → B recompose read).
- **T2 — Predicate precision:** `delta(/Exchange/LookState.temperature) > 0.2` — a 0.3 change wakes the neuron exactly once; a 0.1 change wakes it zero times; two 0.15 changes wake it once (delta-cache semantics, §4).
- **T3 — Budget:** with `budgetWakes=1, budgetWindow=10`, a second qualifying change at t+2s produces no wake and no mute; a third and fourth trip mute the neuron with a visible flag.
- **T4 — Provenance:** the authored `grade_hint` opinion's prim carries `plexus:sourceLayer` naming the neuron's edit layer; `usdview` layer-stack inspection confirms.
- **T5 — Gate:** an action targeting a path outside the allowlist is dropped and flagged; nothing lands in the membrane.
- **T6 — Truth:** kill both processes mid-session; reopening the stages reproduces all composed state (the stage is the record — no hidden runtime truth).

**The film = T1–T4 run live**, two usdview windows, one continuous take, ninety seconds.

## 10 · Phase 2 acceptance

- **T7 — Round trip:** neuron action submits via the Cozy organ; result composes into both projects as a `PlexusAssetAPI` prim; `sha256` on stage matches the file on disk; `plexus:envFingerprint` is non-empty and matches the organ's run report; a graph round-tripped through the organ with no intended change is byte-identical in its link arrays.
- **T8 — Blindness:** grep the core for engine terms (`KSampler`, `cfg`, node class names) → zero hits outside `organs/cozy.py`.

## 11 · Performance budgets (defaults, tunable)

| Budget | Value | Source |
|---|---|---|
| Notice → wake decision (excl. action) | < 10 ms | axon + compiled predicate |
| A→B visibility | < 250 ms p95 | T1 |
| Debounce window | 50 ms | §5 |
| Global wake budget | 60 / min / session | §6.3 |
| Sublayer rotation | 50k prims | Moneta envelope |
| Exchange write batch | ≤ 500 prims, `Sdf.ChangeBlock` | Moneta narrow-lock envelope |

## 12 · Deferred decisions (explicit, not implied)

- **D1** — `OR` / grouping in predicates. Phase 3, only if two-neuron decomposition proves painful in practice.
- **D2** — Classifier-based egress gate on the membrane (v0 is path allowlists).
- **D3** — Foresight gate + rollout variants (blueprint §3.4/§3.6). Nothing in this spec blocks them; nothing here builds them.
- **D4** — `PlexusSignalAPI` typed schema. Plain opinions until a signal needs metadata.
- **D5** — Houdini organ registration (Synapse). Contract-ready; wiring is post-Phase-2.
- **D6** — License compatibility for publication. Cozy and Synapse are MIT; Moneta is not; PLEXUS imports all three. No issue for private build; must be resolved before the Phase 5 public repo.
- **D7** — The name. "PLEXUS" is a pending working title and collision-prone in the wild; trademark/name search is a Phase 5 gate, deliberately not earlier.
- **D8** — Resume / checkpointing. Blocked on a per-organ feasibility study (serializable outputs, deterministic replay, storage, invalidation). Output-backed and explicitly instrumented stage boundaries are the tractable subset; everything else gets observability without a promise.
- **Watch (deletes work if they land):** per-job client metadata in ComfyUI OSS core (echoed on `/history` + `/ws`) → the Cozy organ's reconciliation layer gets deleted; canonical asset identity upstream → `plexus:modelHashes` gains a first-party source of truth. Adopt, don't compete. Neither blocks Phase 1.

---

*Build order: schema/ (with gate test) → stagekit → axon → predicate → neuron → membrane → T1–T6 → film.*
