# PLEXUS · Blueprint v5.3

**Working title. Refactor of Blueprint v4.0 (Aug 21, 2026).**
Drafted Nov 1, 2026. v5.1 added Rust. v5.2 locks Joe's two decisions and his rule on SYNAPSE. v5.3 reconciles it with the document package Joe sent on Nov 1 (§14). Status: draft for Joe's review. Nothing here is ratified until he says so.

**Thesis (unchanged, his words):** a living network where projects compose into each other while running, agents wake only when needed, and execution engines are interchangeable organs.

**One sentence (v4.0, kept):** a deterministic, replayable, safety-gated runtime where OpenUSD composition is the authoritative scene-state and conflict-resolution domain, agents stay dormant until cheap predicates fire, execution engines are replaceable capability-declared organs, and every action is provenance-tracked and validated by a structural safety layer.

**Vendor rule (unchanged):** NVIDIA below the adapter contract freely, above it never. The same holds for any vendor runtime.

**Independence rule (Joe, Nov 1):** SYNAPSE is an architectural reference only. Plexus takes no SYNAPSE code, imports, packages, shared contracts or dependencies. Where Plexus uses an idea SYNAPSE also uses, Plexus states the idea in its own terms and defines its own contract for it.

---

## How to read this version

v5 draws on five references, and none of them is a template:

- **Joe's v4.0** is the base: the thesis, F0 to F9, the neuron model, the organ contract and the phase order.
- **Comfy-Cozy** is the seed code. Plexus is cloned from it with history, and its code becomes Plexus's own.
- **SYNAPSE** is a reference for design ideas learned while running agents in a live scene. No code or contract crosses over.
- **OpenUSD and the AOUSD Core Specification 1.0.1** define what composition means. Any composer Plexus uses has to agree with them.
- **The Rust ecosystem** (the `openusd` crate, PyO3, maturin, tokio) is the basis for §13.

Every change from v4.0 carries a tag:

- **[v5 · fixed]** v4.0 said something that the actual repos contradict. The evidence is cited.
- **[v5 · after SYNAPSE]** is an idea SYNAPSE also uses, restated in Plexus's own terms with the reason it fits Plexus. No code or contract is shared.
- **[v5 · from OpenUSD]** or **[v5 · from Cozy]** is a borrowed pattern, with the reason it fits.
- **[v5 · new]** is something v4.0 did not cover.
- **[v5 · Rust]** concerns where Rust sits (§13).
- **[DECIDED · Joe]** is a decision Joe made on Nov 1.

Untagged text is v4.0 carried forward, sometimes tightened.

`PLEXUS_SPEC.md` (Engineering Spec v2.1) arrived in Joe's Nov 1 package and now sits at the repo root. Its schemas, predicate grammar, organ contract and acceptance tests are normative, and §14 says how it and this blueprint fit together. The Sept 9 `Plexus_StarterKit` zip is still unread.

---

## 0 · What changed, in one screen

1. **[v5 · fixed] The substrate roles in v4.0 don't match the repos.** v4.0 cast Hanish as a ComfyUI projection layer, Octavius as the neuron runtime, and Moneta as identity and permission. Their own repos say Hanish is a forecast ledger, Moneta is a memory engine, SALUS is a path-safety gate, and Octavius is a stage sanitizer. v5 puts each one where it belongs, and Octavius leaves Plexus altogether (§9).
2. **[v5 · new] Plexus defines its own contracts.** There are four (Safety, Memory, Ledger, Composer), and every call returns one Plexus envelope, `Outcome` (§4).
3. **[v5 · after SYNAPSE] Absence has a shape.** Read-side absence narrows, write-side absence goes to an outbox, and gate-side absence fails closed.
4. **[v5 · from OpenUSD] Safety rides on layers.** Compound actions write into a throwaway layer and merge in one step, which gives real rollback.
5. **[v5 · new] Projection moves into Plexus itself** and is seeded from Comfy-Cozy's stage-to-workflow mapping.
6. **[DECIDED · Joe] Plexus owns its neuron runtime,** written in Rust (§9).
7. **[DECIDED · Joe] Shadow mode for composition.** Pixar's `usd-core`, pinned to 26.5 to match Houdini 22, is the composer of record. The pure-Rust `openusd` runs in shadow behind a parity test. The Composer contract is shaped for Rust from day one, so `openusd` can take over through a config change once it matches on Joe's real scenes (§13.4).
8. **[DECIDED · Joe] Plexus has its own build harness in its own repo** (§12).

---

## 1 · First principles

F0 to F9 carry over from v4.0. Several are sharpened.

- **F0 · Deterministic resolution over imperative coordination.** The OpenUSD composition engine resolves conflicting opinions. Do not duplicate arbitration in application code. **[v5 · Rust]** This also means **one composer of record per stage.** The shadow composer is checked, never believed (§13.4).
- **F1 · The resolved stage is authoritative for scene state only.** Operational stores, caches and heavy assets are derived or out-of-band and never define semantic truth.
- **F2 · Least intelligence.** Reflex, then Wake, then Reason. Frontier models only on explicit, predicate-permitted escalation.
- **F3 · Organs, not applications.** Engines are pluggable workers that declare capabilities, constraints, cost and dialect. Houdini is one possible organ, not the host.
- **F4 · Structural provenance.** Append-only, hash-chained lineage on every opinion: actor, intent, timestamp, parent hash, payload hash, tool signature.
- **F5 · Replay and observability.** Any resolved state can be rebuilt from layer history plus the provenance log.
- **F6 · Identity and permission are first-class.** **[v5 · fixed]** v4.0 gave this to Moneta, which is a memory engine and not an identity service. In v5 identity is a small Plexus-owned registry (writer id, its sublayer, its scope) checked by the Safety contract. It stays small on purpose: one writer, one sublayer, one scope.
- **F7 · Execution is a pure function of declared intent.** Job id equals the intent hash, so the same intent gives the same job id. Before enqueueing, look up the hash, and reuse the result if it exists. Organ jobs are the expensive thing in Plexus, so a repeated intent should cost nothing.
- **F8 · References, not embedding.** The stage stores references, hashes and metadata, never binaries or full workflow JSON.
- **F9 · Safety is a structural gate.** It fails closed: a gate that cannot evaluate blocks. Neurons act unattended, so "allow until the gate lands" would let them write before anything checks them.

**[v5 · after SYNAPSE] F10 · No pretend capability.** When something Plexus depends on is missing, the call says `Unavailable` and names what is missing. It never returns `Ok` from a stub. This matters more in Plexus than in most systems, because Phase 0 builds with every optional substrate absent. If stubs could report success, the early tests would pass against fakes and prove nothing.

---

## 2 · Layering

Plexus keeps every substrate behind a contract it owns, so that each one can be absent, swapped or upgraded without touching callers. **[v5 · Rust]** The column on the right says which language each layer is written in (§13).

```
 L5  Surfaces        MCP server · CLI · panel                     Python (from Cozy)
 L4  Organs          ComfyUI organ · any engine behind contract    any, behind the contract
 L3  Projection      stage prims -> organ intent, pure functions   Python (seeded from Cozy)
 L2  Nervous system  scheduler · predicates · budgets · tools      Rust (plexus-core)
 L1  Contracts       Safety · Memory · Ledger · Composer          defined in Rust, Plexus-owned
 L0  Substrate       composed stage · writer sublayers · exchange  usd-core of record, openusd in shadow
```

Rules for the stack:

- A layer calls only the layer below it, or a contract. Nothing above L1 imports a substrate package directly.
- **[v5 · after SYNAPSE] One handle per storage location, one owner per handle.** Layers are shared across projects by design. Two handles on the same exchange layer would be two writers arguing outside of composition. Pixar's `SdfLayer::FindOrOpen` and `openusd`'s `LayerRegistry::find_or_open` enforce the same rule at the library level.
- **[v5 · after SYNAPSE] One conductor per stage root.** One live Plexus process owns a given stage root, and a second one refuses to start and says which process holds it. Many Plexus processes can run at once, each owning a different root, and they meet only in exchange layers. That is the simultaneity in the thesis.

---

## 3 · L0 · Substrate (OpenUSD core)

- **Stage as authoritative scene state.** Composition and LIVRPS arbitrate. No locks, no manual merges.
- **Layer discipline.** Every writer (human, neuron or organ) writes only to its own sublayer. Shared exchange layers order opinions by explicit strength. No writer edits another writer's sublayer.
- **Data boundaries.** Heavy assets stay out-of-band. The stage holds references, hashes, schemas and metadata, so recomposition stays near-instant.
- **[v5 · fixed] Provenance lives in the stage, not in Moneta.** Each writer's sublayer carries its own hash-chained provenance as layer metadata, and every organ result arrives as an opinion with its provenance delta attached. Memory can index provenance for recall, but it isn't the system of record. That keeps F1 and F4 true when memory is absent.
- **[v5 · new] Sanitization is a Plexus step.** v4.0 never said who cleans a stage before an agent reads it. In v5 the Composer contract (§13.4) offers a sanitized view, written in Plexus: drop unresolved references, block-listed attributes and anything outside the reader's scope. Octavius is not involved.
- **[v5 · from Cozy] Seed.** Comfy-Cozy already has a LIVRPS stage with reversible delta layers (`agent/stage/cognitive_stage.py`, `cognitive/core/delta.py`), built on Pixar's `usd-core`. L0 starts from that code.

---

## 4 · L1 · Contracts **[v5 · new]**

Plexus defines four contracts of its own. Each is written for what Plexus needs, not to match another product, so no adapter is shared with anything outside Plexus.

**The envelope.** Every call returns `Outcome`: a status (`Ok`, `Unavailable` or `Blocked`), a payload, and a reason that is required whenever the status isn't `Ok`. It is defined once in Rust and exposed to Python through PyO3, so the Rust core and the Python layers share one type. Callers branch on the status, never on exceptions.

| Contract | Calls (Plexus terms) | Optional substrate behind it | If absent |
|---|---|---|---|
| Safety | `check(writer_id, intent_hash, proposed_edit, stage_digest)` | Plexus's own rules, plus SALUS through a Plexus-written adapter | **Fail closed.** `Blocked`, nothing runs. |
| Memory | `recall(scope, query)` · `remember(scope, record)` | Moneta through a Plexus-written adapter | **Narrow.** Recall answers from the local stage only, and the payload says so. |
| Ledger | `precommit(claim, probability, world_ref)` · `settle(claim_id, result)` | Hanish through a Plexus-written adapter | **Outbox.** The claim is kept durably and drained later. The call returns `Unavailable`. |
| Composer | §13.4 | `usd-core` (record) and `openusd` (shadow) | **Fail closed.** No composer of record, no stage. |

**Why these absence shapes fit Plexus.** Plexus is a network of projects, and parts of a network are routinely offline. A neuron reading memory should keep working on what it can see, so read-side absence narrows. A claim about the future shouldn't be lost because the ledger is down, so write-side absence goes to an outbox. A safety check must not be skipped because its checker is down, so gate-side absence fails closed. Each shape follows from what would go wrong with a different one.

**SALUS, Moneta and Hanish are separate repos, not SYNAPSE.** Each one is optional. Plexus reaches each one only through an adapter it writes against its own contract. Plexus runs with all three absent.

**[v5 · fixed] Hanish** is not a projection layer. It is where a neuron precommits a prediction before acting ("this render will pass the look check, p=0.7") and where the outcome later settles as a hit, a miss, partial, invalidated or unresolvable. That gives Plexus measured foresight, which is what v4.0's Phase 4 "predictive gating" was reaching for.

---

## 5 · L2 · Nervous system (neurons)

### 5.1 · The neuron model (v4.0, kept)

A neuron has a watched scope, a deterministic wake predicate (a pure function of stage diff and external signal), cooldown and hysteresis, a resource budget, an allowed tool set, and explicit escalation rules. Tiers stay Reflex, Wake and Reason. Every agent turn is non-blocking, with backpressure, cancellation and max-pending queues.

**[v5 · Rust]** Rust suits this part of Plexus best. Predicates run on every stage change and must be cheap, deterministic and exact. The scheduler is a long-lived loop that juggles cooldowns, budgets and cancellation without blocking. Rust gives both without a garbage collector or Python's global interpreter lock in the hot path. The scheduler runs on tokio, and wake events cross into Python only when a neuron actually wakes.

### 5.2 · The agent contract

These rules hold for any neuron or organ in Plexus. Each is kept because of what goes wrong in Plexus without it.

1. **No pretend capability** (F10). A missing capability says `Unavailable` and names what is missing.
2. **Degrade by the side that's missing** (§4).
3. **Read the composed stage before writing.** Other projects compose in while a neuron runs, so a path seen a second ago may no longer hold.
4. **Unmeasured is unknown.** No estimated costs or latencies in a routing decision. Unknown routes to the cheapest organ that declares the capability, or escalates. Routing decides spend, so a guessed number spends real money.
5. **Every action leaves a receipt.** A provenance delta records what was touched, the intent hash, the verdict and what couldn't be verified (F4).
6. **One writer per sublayer, one owner per handle** (§2).
7. **Some acts always need Joe.** No neuron may publish into a shared exchange layer another project reads, delete or flatten any layer, run an organ job over its declared cost ceiling, or install or swap an organ. Only Joe's own word for that act opens it, never another agent's relay.

### 5.3 · Memory for neurons

A neuron reaches memory only through the Memory contract. The options for what sits behind it are in a separate note (`PLEXUS_MEMORY_OPTIONS.md`).

---

## 6 · Safety model

Three anchors keep an unattended writer from leaving a scene half-changed. OpenUSD's layer model makes them cheap in Plexus.

| Anchor | In Plexus | Why it fits |
|---|---|---|
| **Atomic actions** | One opinion-set per action. A neuron action writes one edit target in its own sublayer, never several layers in one call. | Each action stays attributable to one writer and one provenance entry. |
| **Idempotent guards** | Intent hash first (F7). For stage writes, read the current opinion and skip if it already matches. | Neurons re-fire. A repeated wake shouldn't repeat spend or churn layers. |
| **Layer transactions** **[v5 · from OpenUSD]** | A compound action writes into a fresh anonymous sublayer, passes the post-check, then merges into the writer's sublayer in one step. On failure the anonymous layer is dropped. | Anonymous layers are native to USD, so rollback costs one dropped layer. `openusd` also ships authoring transactions and undo capture (§13.2). |

The third anchor is real rollback. A failed compound action leaves no partial state, because the transaction layer is discarded whole. That is a claim to prove in a test, not to assume.

**Emergency halt.** A halt is immediate. In-flight organ jobs are cancelled through the organ contract. Pending transaction layers are dropped, and nothing half-written reaches a writer's sublayer. In the Rust scheduler, the halt is one cancellation signal that every task listens on.

---

## 7 · L3 · Projection **[v5 · new]**

v4.0 gave projection to Hanish. In v5 it is a Plexus-owned layer, with the rules v4.0 set: pure functions, no LLM, no side effects, never writes the stage, never enqueues a job. It turns stage prims and parameters into organ intent (for ComfyUI, a workflow graph), and it runs in the Reflex tier.

**[v5 · from Cozy]** Comfy-Cozy already has this code: `agent/stage/workflow_mapper.py`, `workflow_signature.py`, and the `workflow.lock` sidecars that pin model hashes and pack commits. Projection starts there, in Python. **[v5 · Rust]** It moves to Rust only if a measurement shows it on the hot path.

---

## 8 · L4 · Organs

The organ contract and the `PlexusOrganJob` / `PlexusOrganResult` schemas carry over from v4.0 §4.1 unchanged: serialized intent in, progress stream, assets with metadata and provenance out, capabilities declared, idempotency keys and cancel. **[v5.3 · from Spec]** Resume is not in the base contract. Spec v2.1 §8.1 (Patch 01-E) drops it because arbitrary graphs can't be checkpointed. An organ whose engine really can resume declares it as a capability string (deferred decision D8).

- **[v5 · from Cozy] The first organ is Comfy-Cozy's ComfyUI path:** local execution, multi-worker endpoint pooling with failover, keyless run reports.
- **[v5 · new] The organ stays swappable by construction.** An Oct 3 chat noted that Comfy maintains official MCP servers for local and cloud ComfyUI (not re-checked for this draft). If so, either can be a second ComfyUI organ behind the same contract, which is the vendor rule doing its job.
- **[v5 · new] Houdini would be an organ.** If Plexus ever drives Houdini, it does so through a Houdini organ that Plexus writes against its own organ contract. It exchanges USD layer files with Houdini's USD 0.26.5, and it imports nothing from SYNAPSE.
- **Async boundary.** Organ calls never block the stage heartbeat, and a timeout voids a job rather than hanging it. **[v5 · Rust]** In the scheduler that is a tokio task with a deadline.

---

## 9 · Who runs the neurons **[DECIDED · Joe]**

**Plexus owns its neuron runtime, written in Rust in `plexus-core` (§13.3).** Octavius plays no part in Plexus.

The reason is independence. The thesis makes execution engines interchangeable organs, and Houdini is one of them, not the host. A runtime Plexus owns can run without Houdini, on the CPU beside other work, on its own release schedule and its own Python. Growing Octavius would have tied the core of Plexus to SYNAPSE and to Houdini's Python pin.

---

## 10 · Repository mapping

| Repo or package | Role in Plexus | Layer | How Plexus reaches it |
|---|---|---|---|
| **plexus** (seeded from Comfy-Cozy) | Everything Plexus is: stage, contracts, neuron runtime, projection, organs, surfaces, build harness | L0 to L5 | owns it |
| plexus `crates/` **[v5 · Rust]** | Rust core and Rust USD tooling (§13.3) | L0 to L2 | exposed as `plexus._core` |
| `usd-core` 26.5 (Pixar, PyPI) | Composer of record | L0 | Composer contract |
| `openusd` (external crate, MIT) | Layer tooling now, shadow composer | L0 | Composer contract |
| SALUS (optional) | Path-safety rules behind the Safety contract | L1 | Plexus-written adapter |
| Moneta (optional) | Memory engine behind the Memory contract | L1 | Plexus-written adapter |
| Hanish (optional) | Forecast precommit and settlement | L1 | Plexus-written adapter |
| Comfy-Cozy | Origin. Stays where it is, and Plexus diverges from its history. | n/a | none after seeding |

**Not in Plexus:** SYNAPSE (reference only), Octavius, and SYNAPSE's substrate-loop harness.

**[v5 · from Cozy] What Plexus keeps from Comfy-Cozy on day one:** the LIVRPS stage and delta layers, the gate (`agent/gate/`), zero-LLM recipes (a ready-made Reflex tier), `workflow.lock` provenance, the six LLM providers (the Wake and Reason tiers), and the MCP, CLI and panel surfaces. New Python lands in `plexus/`, and new Rust lands in `crates/`. One seeding fix: a Cozy workflow that told an agent to read a local SYNAPSE checkout was cut (`.claude/workflows/cozy-improve.workflow.js`).

---

## 11 · Roadmap

Phases follow v4.0's order, with Phase 0 changed. **[v5.3]** Phase 1's acceptance tests are the schema gate and T1 to T6 (Spec §3 and §9). Phase 2's are T7 and T8 (Spec §10). All of them are written and frozen in `tests/acceptance/`.

- **Phase 0 · Seed and contracts. [v5 · fixed]** Was "Moneta base." Now it covers the plexus repo seeded from Comfy-Cozy with its history, the four contracts with honest `Unavailable` adapters, the identity registry, the transaction-layer write path, and the build harness (§12). **[v5 · Rust]** It also stands up the Cargo workspace, the `Outcome` envelope, the identity registry and the intent ledger in `plexus-core`, built into Python with maturin.
- **Phase 1 · The slice.** Two isolated project layers, one shared exchange stack, one change observer, and one predicate-gated neuron proving live cross-project updates. **[v5 · Rust]** The predicate engine and scheduler are Rust from here on, fed batched stage diffs once per heartbeat.
- **Phase 2 · Projection and the ComfyUI organ.** Stage to workflow through L3, with Cozy's ComfyUI path behind the organ contract with idempotency, cancel and progress. **[v5 · Rust]** The `openusd` shadow composer and its parity test start here (§13.4).
- **Phase 3 · Safety.** Pre-check every neuron action, post-check every organ result, fail closed when the checker is absent.
- **Phase 4 · Triage and foresight.** Reflex, Wake and Reason with budgets and hysteresis. **[v5 · fixed]** Foresight is ledger precommits, measured by settlement rates.
- **Phase 5 · Simultaneity.** Concurrent projects across the exchange membrane, under permissioning, gating and replay.

Per-phase gates (v4.0, kept): recomposition latency, predicate false-positive rate, provenance coverage, organ failover time, replay fidelity, safety denial rate, recovery time. **[v5 · new]** Add **composer parity** (§13.4). Any gate that hasn't been measured reads unknown, and a phase doesn't go green on an unknown.

---

## 12 · The build harness **[DECIDED · Joe]**

Plexus builds itself with a harness in its own repo (`harness/plexus_loop/`), written fresh for Plexus. Nothing is copied from or imported from SYNAPSE's harness, and nothing is added to SYNAPSE.

The design is small on purpose, because Joe is a solo developer paying per token:

- **One mission at a time,** held by a lock file. A second run refuses to start.
- **Claude plans and reviews; a local model iterates.** A mission file says what to work on, which paths may change, which are frozen, which tests are the gates and what number counts as better. The default worker is Ollama running `qwen3-coder:30b`. The worker is a setting, so any command-line model can stand in.
- **Only strict gains are kept.** Each attempt runs in its own git worktree. It is kept only if every gate passes, no frozen path was touched, and the mission's number improves by at least the stated margin. Everything else is thrown away.
- **It steps aside for Houdini.** When Houdini is running, or when the harness can't tell, the worker runs on the CPU with no layers on the GPU, and the gates run with the GPU hidden. It moves back to the GPU once Houdini closes. When the Rust crates land, compile jobs are capped too, because builds beside Houdini compete for the same cores.
- **Hard stops.** Budgets on attempts and hours, a stop after too many attempts in a row that fail, and a stop file Joe can drop in.
- **Promotion is Joe's.** The harness commits only to its own branch and writes a review file. Nothing merges by itself.

The first mission scores the count of failing tests in `tests/acceptance/phase1` (the schema gate and T1 to T6), which are frozen. T7 and T8 in `phase2/` are the mission after it. A mission can't start until its tests exist, and it says so rather than running against nothing.

---

## 13 · Rust in Plexus **[v5 · Rust]**

Joe's direction (Nov 1): Rust matters on the USD side and in orchestration.

### 13.1 · The rule

Rust goes where code is hot, long-running or must be exact. Python stays where code must be flexible or is already written. In practice, Rust owns orchestration from Phase 0. Rust comes into USD in stages, at a pace set by the libraries' maturity.

### 13.2 · What exists today, checked Nov 1, 2026

These were read from crates.io, PyPI, the projects' own repositories, and the AOUSD v26.05 release notes.

| Piece | Latest release | Read |
|---|---|---|
| **`openusd`** (mxpv), pure Rust, no C++ | 0.8.0, Oct 11, 2026, MIT | **Experimental but serious.** It covers the full composition model: sublayers, references, payloads, inherits, variants, relocates, specializes, LIVERPS ordering and scene instancing. It is tested against the AOUSD Core Spec 1.0.1 baselines, with CI on Linux, macOS and Windows. Change notification, incremental invalidation, undo and diff capture, edit targets and namespace editing have shipped. Missing or partial: splines, color-space resolution, `file://` URIs and a stage cache. Parallel composition is planned. Shared layers and authoring transactions are on main but unreleased. APIs may change before 1.0. No Python bindings, no Hydra, not Pixar's. |
| **`usd-core`** (Pixar, PyPI) | 26.11; 26.5 is pinned | **Mature.** Pixar's own Python build. 26.5 ships wheels for Python 3.9 to 3.14 and matches Houdini 22's USD 0.26.5. |
| `rust-usd` and `hydra-rs` (voidreamer), bindings to Pixar's C++ | 0.0.5, Jun 10, 2026 | **Early.** It needs a C++ USD build. |
| `pxr` / `pxr_sys` (AndrejOrsula) | 0.2.0, Apr 2024 | **Stale.** Targets OpenUSD 22.11. |
| `usd` (luke-titley) · `openusd-rs` (FloatyMonkey) | Dec 2020 · Jul 2025 | **Abandoned** · **quiet work in progress.** |
| Pixar and AOUSD | n/a | **No official Rust bindings.** |
| **PyO3** · **maturin** · **tokio** · **rayon** | 0.30.1 · 1.16.0 · 1.54.1 · 1.12.0 | **Mature.** PyO3 is still numbered 0.x, so its minor releases can change its API. |

### 13.3 · How Rust meets Python

**One host process, one extension module.** Python stays the host, because Comfy-Cozy's stage code, organs, LLM providers and surfaces all run unchanged that way. Rust ships as one extension module, `plexus._core`, built with maturin. One process also keeps "one conductor per stage root" simple.

```
crates/
  plexus-core/   Outcome envelope · identity registry · intent ledger (F7)
                 provenance hash chain (F4) · predicate engine · scheduler (tokio)
                 Composer contract (trait + plain-data types)
                 PyO3 bindings behind a feature -> plexus._core
  plexus-usd/    openusd side: layer hashing for provenance, layer diff and
                 validation, the shadow composer
plexus/          Python: contract adapters, the usd-core composer, projection,
                 organs, surfaces (from Cozy)
harness/plexus_loop/   the build harness (§12)
```

Two crates, not more, because each extra crate is more for the CPU worker to compile beside Houdini.

**How a stage change flows.** The composer of record emits a change notice. Python batches the notices once per heartbeat into a plain-data diff and hands it to the Rust predicate engine, which evaluates every neuron's predicate outside the interpreter lock. Only woken neurons come back to Python as wake events. Organ jobs run as tokio tasks with deadlines. Results come back as opinions through a transaction layer (§6).

**Where the two USD worlds meet.** A pure-Rust stage and a Pixar C++ stage can't share in-memory objects. They meet at layers: `.usda` or `.usdc` files, or serialized anonymous layers. Writer sublayers are already Plexus's unit of exchange, so that is a natural seam. It is also how Plexus exchanges with Houdini, which runs its own build of Pixar's USD.

### 13.4 · The composer of record **[DECIDED · Joe]**

**Shadow mode.** `usd-core` 26.5 composes and is believed. `openusd` composes the same layer stacks in shadow from Phase 2, and a parity test compares the two. Promotion is a config change, not a rewrite.

**The Composer contract is shaped for Rust from day one.** It is a Rust trait in `plexus-core`, and only plain data crosses it. No `pxr` object and no `openusd` object ever leaves an implementation. The `usd-core` implementation is written in Python and registered through PyO3. The `openusd` implementation is native Rust.

```rust
pub trait Composer {
    fn open(&mut self, root: &LayerId, opts: &OpenOptions) -> Outcome<StageId>;
    fn resolve(&self, s: StageId, path: &str, t: TimeCode) -> Outcome<Resolved>; // value + winning site
    fn property_stack(&self, s: StageId, path: &str) -> Outcome<Vec<SpecSite>>;
    fn composition_errors(&self, s: StageId) -> Outcome<Vec<CompositionError>>;
    fn changes_since(&self, s: StageId, rev: Revision) -> Outcome<StageDiff>;
    fn author(&mut self, s: StageId, w: WriterId, edits: EditBatch) -> Outcome<Revision>;
    fn sanitized_view(&self, s: StageId, scope: &Scope) -> Outcome<StageId>;
    fn digest(&self, s: StageId, mask: &[String]) -> Outcome<Digest>;
}
```

`author` writes only through the writer's transaction layer (§6). `sanitized_view` is the Plexus sanitization step (§3).

**The switch.** Configuration names two roles, `composer.record = "usd-core"` and `composer.shadow = "openusd"`. Promotion swaps them. The shadow is never read by a neuron, an organ or a surface.

**The parity test.** On each heartbeat in shadow mode, both composers resolve the same sampled prims and attributes and report their composition errors, and any difference is logged with the layer stack that caused it. `openusd` is promoted when two things are true. First, parity holds with zero differences over a corpus of Joe's real scenes for a run length Joe sets. Second, the `openusd` features Plexus needs (authoring transactions and shared layers) have shipped in a release. Until then, parity is a measured gate, and unmeasured reads unknown.

---

## 14 · How this blueprint and the Nov 1 package fit together **[v5.3]**

Joe's package (`docs/plexus/package-2026-11-01/`) holds Blueprint v2.3 and Engineering Spec v2.1 with Patch 01, from August 14, plus the pitch. Its own README sets the rule: the axioms, schemas, contracts and acceptance tests stand as written, and the later direction (a standalone repo, Rust in composition and orchestration, sibling projects as references only) overrides the reuse framing in Blueprint §6 and Spec §1.

So the two documents split the work. **The Spec is normative for what gets tested:** the four schemas (§3), predicate grammar v0 (§4), the axon and wake pipeline (§5 and §6), the membrane (§7), the organ protocol (§8), T1 to T8 (§9 and §10) and the budgets (§11). **This blueprint is normative for architecture:** the layering, the contracts and their absence shapes, Rust, the composer of record, the harness and the independence rule.

### 14.1 · What stands, and where it lands in v5

| Package | In v5 |
|---|---|
| A1 Composition is the runtime; `pxr` and the Core Spec only | F0, L0 and §13.4. `usd-core` 26.5 is the `pxr` of record, and `openusd` runs only in shadow, checked against it. |
| A2 Projects are layers | L0 and the exchange membrane. Tested by T1. |
| A3 Event-driven intelligence; foresight advises, never vetoes | F2 and L2. Foresight is ledger precommits (Phase 4). |
| A4 Engines are organs with an embodiment profile | F3 and §8. |
| A5 Structural provenance | F4 and L0, stamped as `plexus:sourceLayer` per opinion (tested by T4) and hash-chained per sublayer. |
| A6 One writer per layer | L0 layer discipline and the one-handle rule. Tested by T4 and T5. |
| A7 Grounded beats generic | The thesis. No architectural change. |
| A8 Explicit and implicit world models | Deferred with the foresight gate (D3). |
| A9 The stage describes, never contains | F8. Tested by T7, where the asset prim holds a path and a hash, never bytes. |
| Spec §5 debounce of 50 ms | This is the heartbeat in §13.3. One batched diff goes to the Rust predicate engine per window. |
| Spec §11 budgets | Phase gates. The 50k-prim sublayer rotation and 500-prim write batch came from Moneta's measurements on USD 0.25.5, so Plexus re-measures them on 26.5 with its own benchmark. |

### 14.2 · What the package said that v5 supersedes

- **Thin glue and imports (Spec §1, Blueprint §6).** The package reused Cozy, Synapse and Moneta by importing them, and called a copied file a defect. Now Plexus is cloned from Comfy-Cozy, so that code is Plexus's own. SYNAPSE is a reference only, with nothing imported. Moneta, SALUS and Hanish are optional, behind Plexus-written adapters.
- **LLM access through Cozy's provider abstraction "imported, not copied" (Spec §1).** The six providers come with the clone and are Plexus's own.
- **The Houdini organ "via Synapse" (A4, D5).** If Plexus drives Houdini, it uses a Houdini organ that Plexus writes against its own organ protocol, and it imports nothing from SYNAPSE (§8).
- **License compatibility (D6).** "PLEXUS imports all three" no longer holds. Comfy-Cozy's MIT code comes with its license notice kept. SYNAPSE contributes no code. What's left of D6 is whether a Moneta adapter can ship publicly, and that stays a Phase 5 gate.
- **Phase 1 "assembled from tested siblings" (Blueprint §6).** It's still small, but it's written in Plexus. A throwaway prototype passed every acceptance test on Nov 1 in about 350 lines of Python, which is a fair read on the distance.
- **Phase order.** The package runs Paper, Slice, Organ, Triage and Foresight, Simultaneity, then Aperture. v5 keeps v4.0's order, which adds a Seed and contracts phase at 0 and a Safety phase at 3. **Proposed, not decided:** add the package's Aperture as Phase 6 (a minimal stage inspector, README and the public repo, with UI last).
- **Python ≥ 3.11 (Spec §1).** That stands for Plexus. The seed still says 3.10 because Comfy-Cozy did, and its CI tests 3.10. Both move to 3.11 when `plexus/` lands.

### 14.3 · Gaps in the Spec that the tests had to fill

The tests pin these, and `tests/acceptance/CONTRACT.md` records them. Each one can change if Joe says so.

- **The Spec names modules but not functions.** The tests pin a small Python surface (CONTRACT.md) and leave everything beneath it free, Rust included.
- **The Spec has no attribute for a flag.** T3 and T5 need a visible flag on the neuron prim, so any attribute whose name starts with `plexus:flag` counts.
- **The Spec's acceptance gate for §3 had no T-number.** It's tested as T0.
- **T1 is measured in one process.** That is the Spec's literal "author, notice, B recompose read". T6 runs the writer and the runtime as two processes, but it doesn't require the runtime to notice the other process's writes live. How events cross processes stays open, as Spec and v5 both leave it.
- **Authored prims must be defined, not just overridden.** Otherwise ordinary traversal skips them, and T6's dump would miss them.
