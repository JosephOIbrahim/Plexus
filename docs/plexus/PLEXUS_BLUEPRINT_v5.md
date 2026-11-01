# PLEXUS · Blueprint v5.0

**Working title. Refactor of Blueprint v4.0 (Aug 21, 2026), with SYNAPSE as the architectural reference.**
Drafted Nov 1, 2026. Status: draft for Joe's review. Nothing here is ratified until he says so.

**Thesis (unchanged, his words):** a living network where projects compose into each other while running, agents wake only when needed, and execution engines are interchangeable organs.

**One sentence (v4.0, kept):** a deterministic, replayable, safety-gated runtime where OpenUSD composition is the authoritative scene-state and conflict-resolution domain, agents stay dormant until cheap predicates fire, execution engines are replaceable capability-declared organs, and every action is provenance-tracked and validated by a structural safety layer.

**Vendor rule (unchanged):** NVIDIA below the adapter contract freely, above it never. The same holds for any vendor runtime.

---

## How to read this version

Every change from v4.0 carries a tag in the text:

- **[v5 · fixed]** v4.0 said something that the actual repos contradict. The evidence is cited.
- **[v5 · from SYNAPSE]** a pattern lifted from SYNAPSE, with the file it comes from.
- **[v5 · new]** something v4.0 did not cover.
- **[OPEN · Joe]** a decision that is his. There is one.

Untagged text is v4.0 carried forward, sometimes tightened.

Two inputs were not reachable while drafting, and the gaps are named where they matter. `PLEXUS_SPEC.md` (acceptance tests T1 to T8, deferred decisions D1 to D5) and the Sept 9 `Plexus_StarterKit` zip were not read.

---

## 0 · What changed, in one screen

1. **[v5 · fixed] The repo roles in v4.0 don't match the repos.** v4.0 cast Hanish as a ComfyUI projection layer, Octavius as the neuron runtime, and Moneta as identity and permission. In SYNAPSE's own contract (`python/synapse/loop/ports.py`, THE LOOP v5.1 §4) they are something else. Hanish is the forecast ledger (`author_precommit`, forecasts/evidence/outcomes). Octavius composes the sanitized present-state stage (`compose_sanitized_stage`). Moneta is memory with a four-operation API (`query_and_filter`). SALUS is the path-safety gate (`evaluate_path`), and it reads but never writes. v5 puts each one back in its real seat.
2. **[v5 · from SYNAPSE] Every seam speaks one envelope.** `PortResult(status, payload, error_message)` with status `SUCCESS`, `UNAVAILABLE` or `BLOCKED`, exactly as SYNAPSE ships it. An absent substrate reports `UNAVAILABLE` with a reason and never a fabricated success.
3. **[v5 · from SYNAPSE] Absence has a shape.** Read-side absence narrows to a smaller true source. Write-side absence goes to a durable outbox. Gate-side absence fails closed.
4. **[v5 · from SYNAPSE] The safety model is atomic, idempotent and transactional,** translated from Houdini undo groups into USD sublayers. Plexus gets something SYNAPSE can't: real rollback, because each writer owns its own sublayer.
5. **[v5 · from SYNAPSE] The agent contract is SYNAPSE's Seven Laws,** restated for neurons and organs.
6. **[v5 · new] Projection moves into Plexus itself** and is seeded from Comfy-Cozy's existing stage-to-workflow mapping.
7. **[OPEN · Joe] Who runs the neurons** now that Octavius isn't the neuron runtime. See §9.

---

## 1 · First principles

F0 to F9 carry over from v4.0. Three are sharpened.

- **F0 · Deterministic resolution over imperative coordination.** The OpenUSD composition engine resolves conflicting opinions. Do not duplicate arbitration in application code.
- **F1 · The resolved stage is authoritative for scene state only.** Operational stores, caches and heavy assets are derived or out-of-band and never define semantic truth.
- **F2 · Least intelligence.** Reflex, then Wake, then Reason. Frontier models only on explicit, predicate-permitted escalation.
- **F3 · Organs, not applications.** Engines are pluggable workers that declare capabilities, constraints, cost and dialect.
- **F4 · Structural provenance.** Append-only, hash-chained lineage on every opinion: actor, intent, timestamp, parent hash, payload hash, tool signature.
- **F5 · Replay and observability.** Any resolved state can be rebuilt from layer history plus the provenance log.
- **F6 · Identity and permission are first-class.** **[v5 · fixed]** v4.0 gave this to Moneta. Moneta is a memory engine, not an identity service. In v5 identity is a small Plexus-owned registry (writer id, its sublayer, its scope) checked by the SALUS gate. It stays small on purpose: one writer, one sublayer, one scope.
- **F7 · Execution is a pure function of declared intent.** Job id equals the intent hash, so the same intent gives the same job id. **[v5 · from SYNAPSE]** This is SYNAPSE's idempotent guard, "check before mutate," lifted to the job level: before enqueueing, look up the intent hash, and reuse the result if it exists.
- **F8 · References, not embedding.** The stage stores references, hashes and metadata, never binaries or full workflow JSON.
- **F9 · Safety is a structural gate.** **[v5 · from SYNAPSE]** It fails closed. A gate that cannot evaluate blocks (`AGENTS.md` §2, gate-side absence). "Allow until the gate lands" is how a gate becomes decorative.

**[v5 · from SYNAPSE] F10 · Honest seams.** A capability whose substrate isn't installed reports `UNAVAILABLE` with the reason. A stub that returns `SUCCESS` is worse than no stub (`AGENTS.md`, Law 1).

---

## 2 · Layering

**[v5 · from SYNAPSE]** SYNAPSE separates transport, an audit and integrity bridge, handlers, and substrates reached only through ports. v5 gives Plexus the same spine, with USD in place of the Houdini scene.

```
 L5  Surfaces        MCP server · CLI · panel                    (from Comfy-Cozy)
 L4  Organs          ComfyUI organ · any engine behind the contract (from Comfy-Cozy)
 L3  Projection      stage prims -> organ intent, pure functions  (Plexus, seeded from Cozy)
 L2  Nervous system  neurons: scope · predicate · budget · tools  (owner: OPEN, §9)
 L1  Ports           Safety · Memory · Ledger · Stage            (SYNAPSE contract)
 L0  Substrate       composed OpenUSD stage · writer sublayers · exchange stack
```

Rules for the stack:

- A layer calls only the layer below it, or a port. Nothing above L1 imports a substrate package directly.
- **[v5 · from SYNAPSE] One handle per storage URI, one owner per handle** (`AGENTS.md` §3). SYNAPSE was bitten by competing singletons. Plexus starts with the rule.
- **[v5 · from SYNAPSE] One conductor per board** (Law 6). One live Plexus process owns a given stage root. A second one refuses to start and says which process holds it.

---

## 3 · L0 · Substrate (OpenUSD core)

- **Stage as authoritative scene state.** Composition and LIVRPS arbitrate. No locks, no manual merges.
- **Layer discipline.** Every writer (human, neuron or organ) writes only to its own sublayer. Shared exchange layers order opinions by explicit strength. No writer edits another writer's sublayer.
- **Data boundaries.** Heavy assets stay out-of-band. The stage holds references, hashes, schemas and metadata, so recomposition stays near-instant.
- **[v5 · fixed] Provenance lives in the stage, not in Moneta.** Each writer's sublayer carries its own hash-chained provenance as layer metadata, and every organ result arrives as an opinion with its provenance delta attached. Moneta can index provenance for recall (§5.2), but it isn't the system of record for it. That keeps F1 and F4 true with Moneta absent.
- **[v5 · new] Seed.** Comfy-Cozy already has a LIVRPS stage with reversible delta layers (`agent/stage/cognitive_stage.py`, `cognitive/core/delta.py`). L0 starts from that code rather than from zero.

---

## 4 · L1 · Ports

**[v5 · from SYNAPSE]** These are SYNAPSE's four port signatures (`python/synapse/loop/ports.py`), kept verbatim so one adapter can serve both products.

| Port | Signature | Substrate behind it | If absent |
|---|---|---|---|
| SafetyPort | `evaluate_path(agent_id, path_history_hash, recent_actions, proposed_action, scene_state_digest)` | SALUS | **Fail closed.** `BLOCKED`, nothing runs. |
| MemoryPort | `query_and_filter(relation_keys, task_context_tokens)` | Moneta | **Narrow.** Return the local stage's own facts, flagged `{"source": "local_stage"}`. |
| LedgerPort | `author_precommit(claim_predicate, probability, world_ref)` | Hanish | **Outbox.** Record the claim durably, return `UNAVAILABLE`, drain later. |
| StagePort | `compose_sanitized_stage(stage_identifier)` | Octavius | **Narrow.** Compose the local stage without sanitization, flagged on the payload. |

Every call returns `PortResult`. Callers branch on `status`, never on exceptions.

**[v5 · fixed] SALUS** keeps v4.0's pre-gate and post-gate, but both go through `SafetyPort`, and SALUS stays read-only (SYNAPSE `harness/substrate_loop/program.md`: "SALUS reads and never writes"). Denials are recorded as provenance by the caller, not by SALUS.

**[v5 · fixed] Hanish** is not a projection layer. It is where a neuron precommits a prediction before acting ("this render will pass the look check, p=0.7") and where the outcome settles as HIT, MISS, PARTIAL, INVALIDATED or UNRESOLVABLE. That gives Plexus measured foresight, which is what v4.0's Phase 4 "predictive gating" was reaching for.

---

## 5 · L2 · Nervous system (neurons)

### 5.1 · The neuron model (v4.0, kept)

A neuron has a watched scope, a deterministic wake predicate (a pure function of stage diff and external signal), cooldown and hysteresis, a resource budget, an allowed tool set, and explicit escalation rules. Tiers stay Reflex, Wake and Reason. Every agent turn is non-blocking, with backpressure, cancellation and max-pending queues.

### 5.2 · The agent contract **[v5 · from SYNAPSE]**

SYNAPSE's Seven Laws (`AGENTS.md` §1), restated for a neuron or an organ:

1. **Honest seam.** Missing capability reports `UNAVAILABLE` with a reason.
2. **Absence has a shape.** Degrade by which side of the seam is missing (§4 table).
3. **Runtime is truth.** Introspect the live stage before writing to a path you aren't sure exists.
4. **Unmeasured is UNKNOWN.** No estimated costs or latencies in a routing decision. Unknown routes to the cheapest organ that declares the capability, or escalates.
5. **Receipts or it didn't happen.** Every action leaves a provenance delta: what it touched, the intent hash, the verdict, and what it could not verify.
6. **One conductor per board.** One writer per sublayer, one owner per handle.
7. **Human gates are per act.** Some acts are never a neuron's. In Plexus that means publishing into a shared exchange layer another project reads, deleting or flattening any layer, an organ job over its declared cost ceiling, and installing or swapping an organ. Only Joe's own word for that act opens it, never another agent's relay.

### 5.3 · Memory for neurons

A neuron reaches memory only through MemoryPort. Where Moneta plugs in is a separate note (`PLEXUS_MEMORY_OPTIONS.md`) with options for Joe.

---

## 6 · Safety model **[v5 · from SYNAPSE]**

SYNAPSE's three anchors, translated from the Houdini scene to the USD stage:

| SYNAPSE (Houdini) | Plexus (USD) |
|---|---|
| **Atomic scripts:** one mutation per call | **One opinion-set per action.** A neuron action writes one edit target in its own sublayer, never several layers in one call. |
| **Idempotent guards:** check before mutate | **Intent hash first** (F7). Look up the hash, and reuse it if it exists. For stage writes, read the current opinion and skip if it already matches. |
| **Undo groups:** compound ops as one undo entry | **Layer transactions.** A compound action writes into a fresh anonymous sublayer, passes the SALUS post-gate, then is merged into the writer's sublayer in one step. On failure the anonymous layer is dropped. |

The third row is where Plexus improves on its reference. SYNAPSE's own docs are careful that `hou.undos.group()` groups but does not roll back: partial work stays until the artist undoes it. In Plexus the transaction layer is discarded whole, so a failed compound action leaves no partial state. That is a claim to prove in a test, not to assume.

**Emergency halt (from SYNAPSE `CLAUDE.md` §1.8):** a halt is immediate. In-flight organ jobs are cancelled through the contract. Pending transaction layers are dropped, and nothing half-written reaches a writer's sublayer.

---

## 7 · L3 · Projection **[v5 · new]**

v4.0 gave projection to Hanish. In v5 it is a Plexus-owned layer, with the same rules v4.0 set: pure functions, no LLM, no side effects, never writes the stage, never enqueues a job. It turns stage prims and parameters into organ intent (for ComfyUI, a workflow graph), and it runs in the Reflex tier.

Comfy-Cozy already has this kind of code: `agent/stage/workflow_mapper.py`, `workflow_signature.py`, and the `workflow.lock` provenance sidecars that pin model hashes and pack commits. Projection starts there.

---

## 8 · L4 · Organs

The organ contract and the `PlexusOrganJob` / `PlexusOrganResult` schemas carry over from v4.0 §4.1 unchanged: serialized intent in, progress stream, assets with metadata and provenance out, capabilities declared, idempotency keys, cancel and resume.

- **The first organ is Comfy-Cozy's ComfyUI path:** local execution, multi-worker endpoint pooling with failover, keyless run reports.
- **[v5 · new] The organ stays swappable by construction.** An Oct 3 chat noted that Comfy maintains official MCP servers for local and cloud ComfyUI (not re-checked for this draft). If so, either can be a second ComfyUI organ behind the same contract, which is the vendor rule doing its job.
- **[v5 · from SYNAPSE] Async boundary.** Organ calls never block the stage heartbeat. That mirrors SYNAPSE's async execution boundary (`CLAUDE.md` §1.5), where the payload runs off the event loop and a timeout voids it rather than hanging.

---

## 9 · The one judgment call **[OPEN · Joe]**

**Who runs the neurons?** v4.0 handed this to Octavius. Octavius is actually the present-state composer behind StagePort, so the job needs an owner.

- **Option A: Plexus owns a small neuron runtime** in its own `plexus/` package. Octavius stays narrow, behind StagePort, shared with SYNAPSE.
- **Option B: grow Octavius into the neuron runtime,** as v4.0 assumed, so it both composes present state and wakes agents.

It turns on one thing. A narrow Octavius stays a substrate that SYNAPSE and Plexus can share and that the substrate loop can keep improving on its own gates. A wider Octavius means one fewer component, but SYNAPSE then depends on a much bigger thing than it asked for.

The harness mission is drafted against Option A (its focus is `plexus/**`). That is reversible. Under Option B the mission's target becomes Octavius instead.

---

## 10 · Repository mapping

| Repo | Role in Plexus | Layer | Seam |
|---|---|---|---|
| **plexus** (seeded from Comfy-Cozy) | Stage, ports, projection, organs, surfaces, and the neuron runtime under Option A | L0 to L5 | owns the contracts |
| Comfy-Cozy | Origin. Stays where it is. Plexus diverges from its history. | n/a | none |
| SALUS | Path-safety gate | L1 | SafetyPort |
| Moneta | Memory | L1 | MemoryPort |
| Hanish | Forecast precommit and settlement | L1 | LedgerPort |
| Octavius | Sanitized present-state composition (plus neurons under Option B) | L1 | StagePort |
| SYNAPSE | Architectural reference and source of the port contract | n/a | shares the ports |

**[v5 · new] What Plexus keeps from Comfy-Cozy on day one:** the LIVRPS stage and delta layers, the gate (`agent/gate/`), zero-LLM recipes (a ready-made Reflex tier), `workflow.lock` provenance, the six LLM providers (the Wake and Reason tiers), and the MCP, CLI and panel surfaces. Nothing is deleted at seeding. New code lands in `plexus/`.

---

## 11 · Roadmap

Phases follow v4.0's order, with Phase 0 changed. Each phase's acceptance tests are the matching T-numbers in `PLEXUS_SPEC.md`. That file wasn't reachable while drafting, so the mapping is left for Joe to confirm.

- **Phase 0 · Seed and seams. [v5 · fixed]** Was "Moneta base." Now: plexus repo seeded from Comfy-Cozy with history, the four ports with honest `UNAVAILABLE` adapters, the identity registry, and the transaction-layer write path.
- **Phase 1 · The slice.** Two isolated project layers, one shared exchange stack, one Tf.Notice observer, one predicate-gated neuron proving live cross-project updates.
- **Phase 2 · Projection and the ComfyUI organ.** Stage to workflow through L3. Cozy's ComfyUI path behind the organ contract with idempotency, cancel and progress.
- **Phase 3 · SALUS through SafetyPort.** Pre-gate every neuron action, post-gate every organ result, fail closed when SALUS is absent.
- **Phase 4 · Triage and foresight.** Reflex, Wake and Reason with budgets and hysteresis. **[v5 · fixed]** Foresight is Hanish precommits through LedgerPort, measured by settlement rates.
- **Phase 5 · Simultaneity.** Concurrent projects across the exchange membrane, under permissioning, gating and replay.

Per-phase gates (v4.0, kept): recomposition latency, predicate false-positive rate, provenance coverage, organ failover time, replay fidelity, safety denial rate, recovery time. **[v5 · from SYNAPSE]** Any gate that hasn't been measured reads UNKNOWN, and a phase doesn't go green on an UNKNOWN.

---

## 12 · Building it while Houdini is open **[v5 · new]**

Plexus has no Houdini dependency, so it can build while Joe works in Houdini. The SYNAPSE substrate loop gets a `plexus` target marked `houdini_free` and a `plexus_acceptance` mission with `"on_houdini": "cpu"`. While Houdini is open, the local worker runs on the CPU with zero layers on the GPU, and it moves back to the GPU when Houdini closes. One mission at a time. The metric is the count of failing acceptance tests in `tests/acceptance` (T1 to T8), which are frozen. The loop commits only on its own branch, and promotion stays Joe's. This is drafted as a change to the harness, not merged.
