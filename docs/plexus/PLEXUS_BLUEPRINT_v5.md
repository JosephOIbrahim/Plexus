# PLEXUS · Blueprint v5.1

**Working title. Refactor of Blueprint v4.0 (Aug 21, 2026).**
Drafted Nov 1, 2026, and revised the same day to add Rust and to treat SYNAPSE as one reference among several. Status: draft for Joe's review. Nothing here is ratified until he says so.

**Thesis (unchanged, his words):** a living network where projects compose into each other while running, agents wake only when needed, and execution engines are interchangeable organs.

**One sentence (v4.0, kept):** a deterministic, replayable, safety-gated runtime where OpenUSD composition is the authoritative scene-state and conflict-resolution domain, agents stay dormant until cheap predicates fire, execution engines are replaceable capability-declared organs, and every action is provenance-tracked and validated by a structural safety layer.

**Vendor rule (unchanged):** NVIDIA below the adapter contract freely, above it never. The same holds for any vendor runtime.

---

## How to read this version

v5 draws on five references, and none of them is the template:

- **Joe's v4.0** is the base: the thesis, F0 to F9, the neuron model, the organ contract and the phase order.
- **Comfy-Cozy** is the seed code: the LIVRPS stage, delta layers, the gate, zero-LLM recipes, `workflow.lock` provenance, the LLM providers and the surfaces.
- **SYNAPSE** contributes patterns that it learned while running agents inside a live scene: the port envelope, the shapes of absence, the agent laws and the safety anchors.
- **OpenUSD and the AOUSD Core Specification 1.0.1** define what composition means. Any composer Plexus uses has to agree with them.
- **The Rust ecosystem** (the `openusd` crate, PyO3, maturin, tokio) is the basis for the new §13.

Every change from v4.0 carries a tag:

- **[v5 · fixed]** v4.0 said something that the actual repos contradict. The evidence is cited.
- **[v5 · from SYNAPSE]**, **[v5 · from OpenUSD]** or **[v5 · from Cozy]** is a borrowed pattern. Each one says why it fits Plexus, not only where it came from.
- **[v5 · new]** is something v4.0 did not cover.
- **[v5 · Rust]** concerns where Rust sits (§13).
- **[OPEN · Joe]** is a decision that is his. There are two.

Untagged text is v4.0 carried forward, sometimes tightened.

Two inputs weren't reachable while drafting, and the gaps are named where they matter: `PLEXUS_SPEC.md` (acceptance tests T1 to T8, deferred decisions D1 to D5) and the Sept 9 `Plexus_StarterKit` zip.

---

## 0 · What changed, in one screen

1. **[v5 · fixed] The repo roles in v4.0 don't match the repos.** v4.0 cast Hanish as a ComfyUI projection layer, Octavius as the neuron runtime, and Moneta as identity and permission. Their own interfaces, as SYNAPSE calls them (`python/synapse/loop/ports.py`), say something else. Hanish is the forecast ledger. Octavius composes the sanitized present-state stage. Moneta is memory. SALUS is the path-safety gate, and it reads but never writes.
2. **[v5 · from SYNAPSE] Every seam speaks one envelope:** `PortResult(status, payload, error_message)`, with status `SUCCESS`, `UNAVAILABLE` or `BLOCKED`.
3. **[v5 · from SYNAPSE] Absence has a shape.** Read-side absence narrows, write-side absence goes to an outbox, and gate-side absence fails closed.
4. **[v5 · from OpenUSD] Safety rides on layers.** Compound actions write into a throwaway layer and merge in one step, which gives real rollback.
5. **[v5 · new] Projection moves into Plexus itself** and is seeded from Comfy-Cozy's stage-to-workflow mapping.
6. **[v5 · Rust] Rust owns orchestration now and enters USD in stages** (§13). Rust runs the neuron scheduler, predicates, budgets, the intent ledger, the provenance chain and the identity registry. On the USD side it starts with layer tooling and a shadow composer that is checked for parity before it is trusted.
7. **[OPEN · Joe] Who runs the neurons** (§9), now weighed with Rust in the picture.
8. **[OPEN · Joe] Which engine is the composer of record** (§13.4): Pixar's C++ USD now with Rust in shadow, or pure-Rust `openusd` from day one.

---

## 1 · First principles

F0 to F9 carry over from v4.0. Several are sharpened.

- **F0 · Deterministic resolution over imperative coordination.** The OpenUSD composition engine resolves conflicting opinions. Do not duplicate arbitration in application code. **[v5 · Rust]** This also means **one composer of record per stage.** Two engines composing the same stage and both being believed would be duplicated arbitration in its purest form (§13.4).
- **F1 · The resolved stage is authoritative for scene state only.** Operational stores, caches and heavy assets are derived or out-of-band and never define semantic truth.
- **F2 · Least intelligence.** Reflex, then Wake, then Reason. Frontier models only on explicit, predicate-permitted escalation.
- **F3 · Organs, not applications.** Engines are pluggable workers that declare capabilities, constraints, cost and dialect.
- **F4 · Structural provenance.** Append-only, hash-chained lineage on every opinion: actor, intent, timestamp, parent hash, payload hash, tool signature.
- **F5 · Replay and observability.** Any resolved state can be rebuilt from layer history plus the provenance log.
- **F6 · Identity and permission are first-class.** **[v5 · fixed]** v4.0 gave this to Moneta, which is a memory engine and not an identity service. In v5 identity is a small Plexus-owned registry (writer id, its sublayer, its scope) checked by the SALUS gate. It stays small on purpose: one writer, one sublayer, one scope.
- **F7 · Execution is a pure function of declared intent.** Job id equals the intent hash, so the same intent gives the same job id. Before enqueueing, look up the hash, and reuse the result if it exists. **[v5 · from SYNAPSE]** SYNAPSE calls this "check before mutate." It fits Plexus because organ jobs are the expensive thing here, and a repeated intent should cost nothing.
- **F8 · References, not embedding.** The stage stores references, hashes and metadata, never binaries or full workflow JSON.
- **F9 · Safety is a structural gate.** It fails closed: a gate that cannot evaluate blocks. **[v5 · from SYNAPSE]** It fits Plexus because neurons act unattended. "Allow until the gate lands" would let them write before anyone checks.

**[v5 · from SYNAPSE] F10 · Honest seams.** A capability whose substrate isn't installed reports `UNAVAILABLE` with the reason. A stub that returns `SUCCESS` is worse than no stub. This fits Plexus more than it fits most systems, because Phase 0 builds with every substrate absent. Without honest seams, the early tests would pass against fakes.

---

## 2 · Layering

Plexus needs a spine that keeps substrates behind seams, so that each one can be absent, swapped or upgraded without touching callers. SYNAPSE arrived at the same shape (transport, an audit bridge, handlers, substrates reached only through ports), and that agreement is evidence the shape holds up. It isn't the reason Plexus uses it. **[v5 · Rust]** The column on the right says which language each layer is written in (§13).

```
 L5  Surfaces        MCP server · CLI · panel                     Python (from Cozy)
 L4  Organs          ComfyUI organ · any engine behind contract    any, behind the contract
 L3  Projection      stage prims -> organ intent, pure functions   Python (seeded from Cozy)
 L2  Nervous system  scheduler · predicates · budgets · tools      Rust core (owner OPEN, §9)
 L1  Ports           Safety · Memory · Ledger · Stage             envelope in Rust, adapters per substrate
 L0  Substrate       composed stage · writer sublayers · exchange  composer of record OPEN (§13.4)
```

Rules for the stack:

- A layer calls only the layer below it, or a port. Nothing above L1 imports a substrate package directly.
- **[v5 · from SYNAPSE] One handle per storage URI, one owner per handle.** It fits Plexus because layers are shared across projects by design. Two handles on the same exchange layer would be two writers arguing outside of composition. Pixar's `SdfLayer::FindOrOpen` and `openusd`'s `LayerRegistry::find_or_open` enforce the same rule at the library level.
- **[v5 · from SYNAPSE] One conductor per stage root.** One live Plexus process owns a given stage root, and a second one refuses to start and says which process holds it. This fits Plexus as long as it's read per root. Many Plexus processes can run at once, each owning a different root, and they meet only in exchange layers. That is the simultaneity in the thesis.

---

## 3 · L0 · Substrate (OpenUSD core)

- **Stage as authoritative scene state.** Composition and LIVRPS arbitrate. No locks, no manual merges.
- **Layer discipline.** Every writer (human, neuron or organ) writes only to its own sublayer. Shared exchange layers order opinions by explicit strength. No writer edits another writer's sublayer.
- **Data boundaries.** Heavy assets stay out-of-band. The stage holds references, hashes, schemas and metadata, so recomposition stays near-instant.
- **[v5 · fixed] Provenance lives in the stage, not in Moneta.** Each writer's sublayer carries its own hash-chained provenance as layer metadata, and every organ result arrives as an opinion with its provenance delta attached. Moneta can index provenance for recall, but it isn't the system of record. That keeps F1 and F4 true when Moneta is absent.
- **[v5 · from Cozy] Seed.** Comfy-Cozy already has a LIVRPS stage with reversible delta layers (`agent/stage/cognitive_stage.py`, `cognitive/core/delta.py`), built on Pixar's `usd-core` Python package. L0 starts from that code rather than from zero.
- **[v5 · Rust]** Which engine composes is the second open decision (§13.4). Everything else in this section holds either way.

---

## 4 · L1 · Ports

**[v5 · from SYNAPSE]** Plexus starts from the four port signatures SYNAPSE already ships. They fit because the substrates behind them are the same repos, so one adapter per substrate can serve both products. Sharing them is a convenience, not a constraint. Where Plexus needs more than SYNAPSE does, it extends the signature in its own adapter.

| Port | Signature | Substrate behind it | If absent |
|---|---|---|---|
| SafetyPort | `evaluate_path(agent_id, path_history_hash, recent_actions, proposed_action, scene_state_digest)` | SALUS | **Fail closed.** `BLOCKED`, nothing runs. |
| MemoryPort | `query_and_filter(relation_keys, task_context_tokens)` | Moneta | **Narrow.** Return the local stage's own facts, flagged `{"source": "local_stage"}`. |
| LedgerPort | `author_precommit(claim_predicate, probability, world_ref)` | Hanish | **Outbox.** Record the claim durably, return `UNAVAILABLE`, drain later. |
| StagePort | `compose_sanitized_stage(stage_identifier)` | Octavius | **Narrow.** Compose the local stage without sanitization, flagged on the payload. |

Every call returns `PortResult`. Callers branch on `status`, never on exceptions. **[v5 · Rust]** The envelope is defined once in Rust, as a three-variant status with a payload, and exposed to Python through PyO3, so the Rust core and the Python adapters share one type rather than two copies.

**Why the absence shapes fit Plexus.** Plexus is a network of projects, and parts of a network are routinely offline. A neuron reading memory should keep working on what it can see (narrow). A claim about the future must not be lost because the ledger is down (outbox). A safety check must not be skipped because SALUS is down (fail closed). Each shape follows from what goes wrong if you pick a different one.

**[v5 · fixed] SALUS** keeps v4.0's pre-gate and post-gate, both through `SafetyPort`, and stays read-only. Denials are recorded as provenance by the caller, not by SALUS.

**[v5 · fixed] Hanish** is not a projection layer. It is where a neuron precommits a prediction before acting ("this render will pass the look check, p=0.7") and where the outcome settles as HIT, MISS, PARTIAL, INVALIDATED or UNRESOLVABLE. That gives Plexus measured foresight, which is what v4.0's Phase 4 "predictive gating" was reaching for.

---

## 5 · L2 · Nervous system (neurons)

### 5.1 · The neuron model (v4.0, kept)

A neuron has a watched scope, a deterministic wake predicate (a pure function of stage diff and external signal), cooldown and hysteresis, a resource budget, an allowed tool set, and explicit escalation rules. Tiers stay Reflex, Wake and Reason. Every agent turn is non-blocking, with backpressure, cancellation and max-pending queues.

**[v5 · Rust]** This is the part of Plexus that Rust suits best. Predicates run on every stage change and must be cheap, deterministic and exact. The scheduler is a long-lived loop that juggles cooldowns, budgets and cancellation without blocking. Rust gives both without a garbage collector or Python's global interpreter lock in the hot path. The scheduler runs on tokio, and wake events cross into Python only when a neuron actually wakes.

### 5.2 · The agent contract

These rules hold for any neuron or organ. Most come from SYNAPSE's Seven Laws, and each one is kept because of what goes wrong in Plexus without it.

1. **Honest seam.** A missing capability reports `UNAVAILABLE` with a reason (F10).
2. **Absence has a shape.** Degrade by which side of the seam is missing (§4).
3. **The composed stage is truth.** Introspect the live stage before writing to a path you aren't sure exists. In Plexus other projects compose in while you run, so the path you saw a second ago may not hold.
4. **Unmeasured is UNKNOWN.** No estimated costs or latencies in a routing decision. Unknown routes to the cheapest organ that declares the capability, or escalates. This matters because routing decides spend.
5. **Receipts or it didn't happen.** Every action leaves a provenance delta: what it touched, the intent hash, the verdict, and what it could not verify (F4).
6. **One writer per sublayer, one owner per handle** (§2).
7. **Human gates are per act.** Some acts are never a neuron's: publishing into a shared exchange layer another project reads, deleting or flattening any layer, an organ job over its declared cost ceiling, and installing or swapping an organ. Only Joe's own word for that act opens it, never another agent's relay.

### 5.3 · Memory for neurons

A neuron reaches memory only through MemoryPort. Where Moneta plugs in is a separate note (`PLEXUS_MEMORY_OPTIONS.md`) with options for Joe.

---

## 6 · Safety model

Three anchors keep an unattended writer from leaving a scene half-changed. SYNAPSE learned them in Houdini. OpenUSD's layer model makes them cheaper and stronger in Plexus than they are there.

| Anchor | In Plexus | Why it fits |
|---|---|---|
| **Atomic actions** | One opinion-set per action. A neuron action writes one edit target in its own sublayer, never several layers in one call. | Each action stays attributable to one writer and one provenance entry. |
| **Idempotent guards** | Intent hash first (F7). For stage writes, read the current opinion and skip if it already matches. | Neurons re-fire. A repeated wake shouldn't repeat spend or churn layers. |
| **Layer transactions** **[v5 · from OpenUSD]** | A compound action writes into a fresh anonymous sublayer, passes the SALUS post-gate, then merges into the writer's sublayer in one step. On failure the anonymous layer is dropped. | Anonymous layers are a native USD feature, so rollback costs a dropped layer. `openusd` also ships authoring transactions and undo capture (§13.2), which this can use directly. |

The third row is where Plexus goes beyond SYNAPSE. Houdini's undo groups bundle steps but don't roll back, so partial work stays until someone undoes it. In Plexus the transaction layer is discarded whole, and a failed compound action leaves no partial state. That is a claim to prove in a test, not to assume.

**Emergency halt.** A halt is immediate. In-flight organ jobs are cancelled through the contract. Pending transaction layers are dropped, and nothing half-written reaches a writer's sublayer. In the Rust scheduler, the halt is one cancellation signal that every task listens on.

---

## 7 · L3 · Projection **[v5 · new]**

v4.0 gave projection to Hanish. In v5 it is a Plexus-owned layer, with the rules v4.0 set: pure functions, no LLM, no side effects, never writes the stage, never enqueues a job. It turns stage prims and parameters into organ intent (for ComfyUI, a workflow graph), and it runs in the Reflex tier.

**[v5 · from Cozy]** Comfy-Cozy already has this code: `agent/stage/workflow_mapper.py`, `workflow_signature.py`, and the `workflow.lock` sidecars that pin model hashes and pack commits. Projection starts there, in Python. **[v5 · Rust]** It moves to Rust only if a measurement shows it on the hot path. Until then the rewrite isn't worth the cost.

---

## 8 · L4 · Organs

The organ contract and the `PlexusOrganJob` / `PlexusOrganResult` schemas carry over from v4.0 §4.1 unchanged: serialized intent in, progress stream, assets with metadata and provenance out, capabilities declared, idempotency keys, cancel and resume.

- **[v5 · from Cozy] The first organ is Comfy-Cozy's ComfyUI path:** local execution, multi-worker endpoint pooling with failover, keyless run reports.
- **[v5 · new] The organ stays swappable by construction.** An Oct 3 chat noted that Comfy maintains official MCP servers for local and cloud ComfyUI (not re-checked for this draft). If so, either can be a second ComfyUI organ behind the same contract, which is the vendor rule doing its job.
- **Async boundary.** Organ calls never block the stage heartbeat, and a timeout voids a job rather than hanging it. **[v5 · Rust]** In the scheduler that is a tokio task with a deadline. SYNAPSE has the same boundary for the same reason.

---

## 9 · Judgment call 1: who runs the neurons **[OPEN · Joe]**

v4.0 handed the neuron runtime to Octavius. Octavius is actually the present-state composer behind StagePort, so the job needs an owner.

- **Option A: Plexus owns the neuron runtime** as Rust in its own core crate (§13.3). Octavius stays narrow, behind StagePort, shared with SYNAPSE.
- **Option B: grow Octavius into the neuron runtime,** as v4.0 assumed, so it both composes present state and wakes agents.

**[v5 · Rust] Rust changes the weight of this call.** The neuron runtime is the main place Rust earns its keep (§5.1). Under Option A, the compiled code lives inside Plexus, the only product that needs it. Under Option B, there are two paths. If Octavius takes the Rust runtime, SYNAPSE, which runs inside Houdini's own Python, inherits a compiled dependency it didn't ask for, and its wheels have to match Houdini's Python build. The abi3 stable ABI eases that but doesn't remove it. If the runtime stays in whatever language Octavius uses today, Rust orchestration moves out of the neuron runtime altogether. That language isn't verified for this draft, because the Octavius repo wasn't reachable.

The call turns on one question: is the neuron runtime shared infrastructure, or Plexus's own engine?

The harness mission is drafted against Option A (its focus is `plexus/**`). That is reversible. Under Option B the mission's target becomes Octavius.

---

## 10 · Repository mapping

| Repo or package | Role in Plexus | Layer | Seam |
|---|---|---|---|
| **plexus** (seeded from Comfy-Cozy) | Stage, ports, projection, organs, surfaces, and the neuron runtime under Option A | L0 to L5 | owns the contracts |
| plexus `crates/` **[v5 · Rust]** | Rust core and Rust USD tooling (§13.3) | L0 to L2 | exposed as `plexus._core` |
| Comfy-Cozy | Origin. Stays where it is. Plexus diverges from its history. | n/a | none |
| SALUS | Path-safety gate | L1 | SafetyPort |
| Moneta | Memory | L1 | MemoryPort |
| Hanish | Forecast precommit and settlement | L1 | LedgerPort |
| Octavius | Sanitized present-state composition (plus neurons under Option B) | L1 | StagePort |
| SYNAPSE | One reference; source of the port signatures | n/a | shares the ports |
| `openusd` crate (external, MIT) **[v5 · Rust]** | Pure-Rust USD: layer tooling now, shadow composer later | L0 | behind a Composer seam |
| `usd-core` (Pixar, external) | Composer of record under §13.4 Option 1 | L0 | behind the same seam |

**[v5 · from Cozy] What Plexus keeps from Comfy-Cozy on day one:** the LIVRPS stage and delta layers, the gate (`agent/gate/`), zero-LLM recipes (a ready-made Reflex tier), `workflow.lock` provenance, the six LLM providers (the Wake and Reason tiers), and the MCP, CLI and panel surfaces. Nothing is deleted at seeding. New Python lands in `plexus/`, and new Rust lands in `crates/`.

---

## 11 · Roadmap

Phases follow v4.0's order, with Phase 0 changed. Each phase's acceptance tests are the matching T-numbers in `PLEXUS_SPEC.md`. That file wasn't reachable while drafting, so the mapping is left for Joe to confirm.

- **Phase 0 · Seed and seams. [v5 · fixed]** Was "Moneta base." Now it covers the plexus repo seeded from Comfy-Cozy with its history, the four ports with honest `UNAVAILABLE` adapters, the identity registry, and the transaction-layer write path. **[v5 · Rust]** It also stands up the Cargo workspace, the `PortResult` envelope, the identity registry and the intent ledger in `plexus-core`, built into Python with maturin.
- **Phase 1 · The slice.** Two isolated project layers, one shared exchange stack, one change observer, and one predicate-gated neuron proving live cross-project updates. **[v5 · Rust]** The predicate engine and scheduler are Rust from here on, fed batched stage diffs once per heartbeat.
- **Phase 2 · Projection and the ComfyUI organ.** Stage to workflow through L3. Cozy's ComfyUI path behind the organ contract with idempotency, cancel and progress. **[v5 · Rust]** The `openusd` shadow composer starts here, along with its parity test (§13.4).
- **Phase 3 · SALUS through SafetyPort.** Pre-gate every neuron action, post-gate every organ result, fail closed when SALUS is absent.
- **Phase 4 · Triage and foresight.** Reflex, Wake and Reason with budgets and hysteresis. **[v5 · fixed]** Foresight is Hanish precommits through LedgerPort, measured by settlement rates.
- **Phase 5 · Simultaneity.** Concurrent projects across the exchange membrane, under permissioning, gating and replay.

Per-phase gates (v4.0, kept): recomposition latency, predicate false-positive rate, provenance coverage, organ failover time, replay fidelity, safety denial rate, recovery time. **[v5 · new]** Add **composer parity** (§13.4). Any gate that hasn't been measured reads UNKNOWN, and a phase doesn't go green on an UNKNOWN.

---

## 12 · Building it while Houdini is open **[v5 · new]**

Plexus has no Houdini dependency, so it can build while Joe works in Houdini. The substrate loop harness gets a `plexus` target marked `houdini_free`, and a `plexus_acceptance` mission with `"on_houdini": "cpu"`. While Houdini is open, the local worker runs on the CPU with zero layers on the GPU, and it moves back to the GPU when Houdini closes. One mission at a time. The metric is the count of failing acceptance tests in `tests/acceptance` (T1 to T8), and those tests are frozen. The loop commits only on its own branch, and promotion stays Joe's. This is drafted as a change to the harness, not merged.

**[v5 · Rust]** When the Rust crates land, the target needs a `cargo test` gate. Its build jobs should be capped through the target's `gate_env` (`CARGO_BUILD_JOBS`), because compiles beside Houdini compete with the worker for the same cores. How fast the CPU worker writes and compiles Rust is UNKNOWN until it is measured. Keeping the crates small is the cheapest way to keep each iteration short.

---

## 13 · Rust in Plexus **[v5 · Rust]**

Joe's direction (Nov 1): Rust matters on the USD side and in orchestration. This section says where it sits, what's mature enough to lean on today, and how it meets the Python that Plexus inherits from Comfy-Cozy.

### 13.1 · The rule

Rust goes where code is hot, long-running or must be exact. Python stays where code must be flexible or is already written. In practice, Rust owns orchestration from Phase 0. Rust comes into USD in stages, at a pace set by the maturity of the libraries rather than by preference.

### 13.2 · What exists today, checked Nov 1, 2026

These were read from crates.io, the projects' own repositories, and the AOUSD v26.05 release notes, not from memory.

| Piece | Latest release | Read |
|---|---|---|
| **`openusd`** (mxpv), pure Rust, no C++ | 0.8.0, Oct 11, 2026, MIT | **Experimental but serious.** It covers the full composition model: sublayers, references, payloads, inherits, variants, relocates, specializes, LIVERPS ordering, and scene instancing. It is tested against the AOUSD Core Spec 1.0.1 baselines, with CI on Linux, macOS and Windows. Change notification, incremental invalidation, undo and diff capture, edit targets and namespace editing have shipped. Missing or partial: splines, color-space resolution, `file://` URIs and a stage cache. Parallel composition is planned. Shared layers and authoring transactions are on main but unreleased. The project warns that APIs may change before 1.0. It has no Python bindings and no Hydra, and it isn't Pixar's. |
| **`rust-usd`** and **`hydra-rs`** (voidreamer), bindings to Pixar's C++ | 0.0.5, Jun 10, 2026 | **Early.** Stage open, prim and mesh attributes, variants, sublayer authoring, UsdShade read and write, and a resolver hook. It needs a C++ USD build. |
| `pxr` / `pxr_sys` (AndrejOrsula), C++ bindings | 0.2.0, Apr 2024 | **Stale.** Targets OpenUSD 22.11 and says it isn't production-ready. |
| `usd` (luke-titley) | 0.0.9, Dec 2020 | **Abandoned.** |
| `openusd-rs` (FloatyMonkey), pure Rust | 0.1.0, Jul 2025 | **Work in progress, quiet.** |
| Pixar and AOUSD | n/a | **No official Rust bindings.** The v26.05 notes mention only C++ and Python. |
| **PyO3** | 0.30.1, Oct 14, 2026 | **Mature bridge** between Rust and Python, with about 291 million downloads. It is still numbered 0.x, so minor releases can change its API. |
| **maturin** | 1.16.0, Oct 29, 2026 | **Mature.** Builds PyO3 code into Python wheels, Windows included. |
| **tokio** | 1.54.1, Oct 21, 2026 | **Mature** async runtime for the scheduler. |
| **rayon** | 1.12.0, Apr 2026 | **Mature** data parallelism, for batched predicate evaluation. |

The summary: the Rust orchestration stack is mature, and the Rust USD stack is not. `openusd` is far enough along to build tooling on and to test against, but not yet to bet the composer of record on without a parity check. The C++ binding crates are behind it.

One more crate turned up in the search, `strata-platform` (a 2027 alpha). It wasn't evaluated.

### 13.3 · How Rust meets Python

**One host process, one extension module.** Python stays the host, because Comfy-Cozy's stage code, organs, LLM providers and surfaces all run unchanged that way. Rust ships as one extension module, `plexus._core`, built with maturin. One process also keeps "one conductor per stage root" simple.

```
crates/
  plexus-core/   PortResult envelope · identity registry · intent ledger (F7)
                 provenance hash chain (F4) · predicate engine · scheduler (tokio)
                 PyO3 bindings behind a feature -> plexus._core
  plexus-usd/    Rust USD side on `openusd`: layer hashing for provenance,
                 layer diff and validation, the shadow composer (§13.4)
plexus/          Python: ports' adapters, projection, organs, surfaces (from Cozy)
```

Two crates, not more. Each extra crate is more for the CPU worker to compile beside Houdini.

**How a stage change flows.** The composer of record emits a change notice. Python batches the notices once per heartbeat into a compact diff and hands it to the Rust predicate engine, which evaluates every neuron's predicate off the interpreter lock. Only woken neurons come back to Python as wake events. Organ jobs run as tokio tasks with deadlines. Results come back as opinions through a transaction layer (§6).

**Where the two USD worlds meet.** A pure-Rust stage and a Pixar C++ stage can't share in-memory objects. They meet at layers: `.usda` or `.usdc` files, or serialized anonymous layers. That is a feature here, because writer sublayers are already the unit of exchange in Plexus. It also means Houdini and Solaris interchange happens through files whichever composer Plexus picks, since Houdini runs its own build of Pixar's USD.

**The alternative host shape.** A Rust daemon could host the system, with Python organs as worker processes over a socket. It isolates crashes better, but it means rewriting Cozy's entry points before anything works. It's noted as a later option, not the starting point.

### 13.4 · Judgment call 2: the composer of record **[OPEN · Joe]**

F0 allows one composer of record per stage. There are two real choices.

- **Option 1: Pixar's `usd-core` composes now, with `openusd` as a shadow composer.** Comfy-Cozy's stage keeps working as it is. In Phase 2, `plexus-usd` composes the same layer stacks in parallel, and a parity test compares the resolved prims and values. The shadow is promoted to composer of record when parity holds on Plexus's own fixtures and the gaps Plexus needs (authoring transactions, shared layers) have shipped in a release. This is shadow-first and flag-gated, the same way SYNAPSE moved its memory backend, and it fits for the same reason: it swaps an engine of record without a flag day.
- **Option 2: `openusd` composes from day one.** The whole spine is Rust, with one composition engine and no parity harness to maintain. Pixar's USD appears only at the edges, as files exchanged with Houdini. The cost is building on a pre-1.0 API and porting Cozy's stage code before Phase 1 can run.

It turns on how much of the early roadmap Joe wants to spend on the USD side of Rust versus getting the slice live. This draft defaults to Option 1 because it's reversible. Option 2 isn't reversible in practice, because once Cozy's stage is ported, going back means porting it again.

**[v5 · new] Composer parity as a gate.** Whichever option is chosen, a parity test (the same layer stack composed by both engines, with resolved values diffed) is cheap insurance. It's also the honest way to say "Rust USD is ready" with a number rather than a feeling. It borrows the method `openusd` uses on itself, which is to test against the AOUSD spec's own baselines.
