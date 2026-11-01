# PLEXUS — Blueprint from First Principles (v2)
**Working title.** Swap freely — a placeholder in the Moneta / Synapse / Octavius constellation (plexus: a braided network of nerves).

**One sentence:** A living network where projects compose into each other while running, agents wake only when needed, and execution engines are interchangeable organs.

**The idea, before the engineering:** a production is a nervous system. Not decoration — the organizing concept every section below derives from: state composes like tissue, intelligence fires like neurons, engines serve like organs, projects learn through a membrane. If an element of this document doesn't trace to that sentence, it doesn't belong here — the same rule the axioms apply to features.

*(v2.3 — consolidates the portfolio audit, the Cosmos/SIGGRAPH 2026 cross-reference, the AOUSD findings, the A9 boundary, and Spec Patch 01 (foresight advises, never vetoes). Market receipts in §11. Engineering companion — normative build detail, schemas, grammar, acceptance tests: `PLEXUS_SPEC.md`; diagnostic record: `PLEXUS_SPEC_PATCH_01.md`.)*

---

## 0 · Axioms

Every design decision below must trace to one of these. If a feature can't, it's scope creep.

**A1 — Composition is the runtime, and the runtime is a standard.**
The composed OpenUSD stage *is* the system state. No workflow JSON as source of truth; what the stage resolves to is what the system believes. LIVRPS is the arbitration law of the network. And the substrate is nobody's product: OpenUSD is AOUSD-governed, Core Specification 1.0 landing, ISO certification in motion, with the Alliance itself now framing OpenUSD as *the 3D data layer for agentic AI workflows*. Discipline that follows: **pxr and the Core Spec only.** No vendor SDK (Omniverse Kit or otherwise) ever touches the substrate layer.

**A2 — Projects are layers, not jars.**
Every workflow tool seals a project into a jar. Here a project is a layer stack: Project B references Project A's live state, and opinions cross the boundary by composition — while both run. The one capability no seat on the market map has.

**A3 — Intelligence is event-driven, and it imagines before it acts.**
Agents are dormant by default, gated by wake predicates; deterministic recipes do the routine work; an LLM call is the exception path. Prediction extends dormancy one step further: before an expensive organ fires, a world-model neuron can predict the outcome and annotate the stage (§3.4). Deterministic conditions may block; predictions may only advise. A cheap forecast is dormancy for the organs — never a veto.

**A4 — Execution engines are organs, each with an embodiment profile.**
Engines are demoted from "the application" to swappable backends behind one contract (§4). Two organs already exist in the portfolio: ComfyUI (via Comfy-Cozy, ~90% of the contract shipped) and Houdini (via Synapse, running *inside* the DCC interpreter). "Every embodiment speaks a different language" — NVIDIA's phrase for robots — is this axiom for engines: shared substrate, per-organ dialect, declared as stage data.

**A5 — Provenance is structural, and the exhaust is a product.**
Every asset carries the opinion chain that produced it. Corollary discovered in 2026: a provenance-complete stage records physics-grounded (world state → action → outcome) triples in USD — exactly the substance world-model training pipelines consume. PLEXUS emits grounded datasets as a side effect of people making shots.

**A6 — One writer per layer.**
Concurrency resolves by composition, never by locks. Each session/agent owns one edit-target layer; conflicts are opinions arbitrated by strength. Proven three ways in the portfolio: Cozy's per-session ContextVar isolation, Moneta's handle + URI-exclusivity registry (480-attempt TOCTOU stress, zero races), and the Moneta↔Octavius convention that systems share the stage, not Python imports.

**A7 — Grounded beats generic (market-proven, 2026).**
The intelligence that wins in production is bound to *this project's* state. The market priced it: Netflix paid $587M cash for InterPositive — sixteen people, pre-revenue — whose thesis was per-production models grounded in that production's own footage. PLEXUS grounds one level deeper: in the composed production structure, while it happens.

**A8 — Explicit and implicit world models drive each other.**
Cosmos-class models compress the world into weights (implicit). PLEXUS describes the world in composition (explicit). They are the two halves of one loop: predictions enter the stage as opinions; stage state exits as grounding. The exchange layer stack is the membrane where they trade. (This is the Synapse world-model refocus, given a mechanism.)

**A9 — The stage describes; it never contains.**
USD is the data layer for everything the system *knows* — never a container for heavy bytes. State, decisions, provenance, signals, memory, and rollouts scaffold **in** as prims and opinions; pixels, weights, and caches scaffold **out**, referenced by path + hash. This is not taste, it's measured physics: `Save()` cost scales with accumulated layer content (Moneta Phase 2), and the heartbeat — recomposition effectively free — survives only if prims stay light. One 2026 exception: Gaussian splats are first-class in USD (v26.03), the rare heavy payload that lives natively in the layer. Full boundary table in §2.5.

---

## The Anatomy — one naming system

The nervous-system vocabulary is the design system of this document: one term per mechanism, used only where the mechanics match.

| Term | Is | Never |
|---|---|---|
| **Stage** | The body of record — composed state, the only truth | A database beside the truth |
| **Neuron** | Scoped, dormant, budgeted agent (§3.1) | A resident copilot |
| **Axon** | `Tf.Notice` change propagation (§2.3) | A message bus |
| **Reflex** | Deterministic zero-LLM response (§3.2) | A model call |
| **Foresight** | The predict-before-dispatch advisor (§3.4) | A veto, or a tier that runs by default |
| **Organ** | Execution engine behind the contract (§4) | The application |
| **Membrane** | The shared exchange stack (§2.2, §5) | Ambient access to another project |
| **Sleep** | Moneta consolidation — decay, prune, keep | Deletion or a backup job |
| **Exhaust** | Provenance-complete grounded data emitted by use (A5) | A product that must be built |

Discipline: a mechanism that seems to need a *new* anatomy word probably needs an axiom check first.

---

## 1 · The Stack Inversion (50k view)

```
  BEFORE (every tool today)              AFTER (this system)
  ┌───────────────────────┐             ┌───────────────────────┐
  │  Workflow engine       │  center →  │  Composed USD stage    │
  │  (Comfy / Griptape)    │            │  state · memory ·      │
  │  owns state, UI, truth │            │  arbitration · record  │
  ├───────────────────────┤             ├───────────────────────┤
  │  Files on disk         │            │  Agent-neurons          │
  │  (dead snapshots)      │            │  dormant · predicate-  │
  └───────────────────────┘            │  gated · budgeted      │
                                        ├───────────────────────┤
                                        │  Organs (cargo holds)  │
                                        │  ComfyUI · Houdini ·   │
                                        │  neural preview · WFM  │
                                        └───────────────────────┘
```

The graph editor stops being the product. The composed stage is the product; engines hang off it like organs.

---

## 2 · Substrate Layer (OpenUSD 26.x)

**2.1 Stage anatomy.** One root stage per session; each project is a layer stack sublayered or referenced in. Typed schemas via the codeless-schema recipe Moneta already shipped for `MonetaMemory` (`plugInfo.json` + `usdGenSchema --skipCodeGeneration` + subprocess acceptance gate):

- `PlexusProjectAPI` — identity, status, root prims, provenance policy
- `PlexusAssetAPI` — generated assets: source opinions, engine, seed, model hash, colorspace
- `PlexusNeuronAPI` — scope, wake predicate, tool grants, budget, quiescence rule
- `PlexusOrganAPI` — an engine's embodiment profile: dialect, capabilities, cost curve
- `PlexusSignalAPI` — inter-agent messages as attribute opinions (§3.5)

**2.2 Layer discipline.**
```
session.usda                 ← session layer (strongest, ephemeral — human overrides)
 ├─ projectB/                ← live project stack
 │    ├─ opinions_agentX.usda   (agent edit target)
 │    └─ base.usda
 ├─ projectA/  ⇠ referenced by projectB where sharing occurs
 └─ shared/exchange/         ← a layer STACK: one sublayer per participant
      ├─ from_projectA.usda     (A6 preserved — every writer keeps its own URI)
      └─ from_agentY.usda
```
Muting a layer silences a participant. Strength ordering decides who wins. No locks anywhere.

**2.3 Change propagation.** `Tf.Notice` / `UsdNotice.ObjectsChanged` observers are the axons. A change in A that composes into B fires B-side observers natively — composition *is* the wire. Build pattern: the TopsEventBridge shape from Synapse (typed payloads, thread-defensive, hostile-tested), retargeted from `pdg` events to stage notices.

**2.4 Standards discipline.** Track the AOUSD Core Spec; keep schemas conformant so PLEXUS rides the interop wave rather than forking it. Two 2026 developments to exploit, not chase: OpenUSD v26.03's first-class 3D Gaussian splat schema (captured-world data — the implicit-world currency — now flows through the substrate natively, no side pipeline), and nanoUSD (a portable, embeddable Core Spec implementation — a future lightweight runtime for neurons at the edge). Neither blocks anything before Phase 5.

**2.5 What scaffolds in (A9 — the boundary).**

| Scaffolds IN — lives as USD data | Scaffolds OUT — referenced, never embedded |
|---|---|
| Project state, decisions, status (`PlexusProjectAPI`) | Rendered frames, EXRs, image sequences |
| Provenance chains, hashes, colorspace intent (`PlexusAssetAPI`) | Model weights, checkpoints, LoRAs |
| Neuron definitions, predicates, budgets (`PlexusNeuronAPI`) | Video and audio media |
| Organ embodiment profiles (`PlexusOrganAPI`) | Sim caches, engine caches, intermediates |
| Inter-agent signals (`PlexusSignalAPI`) | Anything whose bytes an organ produces |
| Agent memory (Moneta cold tier — typed prims, shipped) | — |
| Turn history and rollouts (variants / sibling prims) | — |
| Captured-world splats (v26.03 exception — heavy but native) | — |

The right column always enters the stage as *description*: asset path, SHA-256, generation metadata, colorspace. An asset without its description does not exist to the system (A5); a description that embedded its asset would kill the heartbeat (A9). The test for any new data type: does the system need to *reason* over it (in), or only to *locate and trust* it (out)?

---

## 3 · Nervous System Layer

**3.1 Neuron definition.** **Scope** (prim subtree watched) + **wake predicate** (cheap deterministic condition over composed attributes) + **action set** (MCP tools, gated by the Cozy-style default-deny risk classifier) + **budget** (max wakes / calls / tokens) + **quiescence rule**.

**3.2 Three response tiers (cost-ordered, always tried in order):**
1. **Reflex** — zero-LLM recipe (shipped in Cozy). Deterministic, instant, free.
2. **Wake** — predicate trips; one agent wakes, acts within budget, sleeps. Local model triage (the Synapse decision matrix: Nemotron-class triage, frontier-model leaf).
3. **Reason** — triage escalates to a reasoning model only on explicit request from tier 2.

**3.3 Async execution.** Neuron turns run on the TurnHandle pattern (Synapse): submit returns a Future-shaped handle immediately; nothing blocks the stage or a host's main thread.

**3.4 Foresight (Phase 3+, advisory).** Before an expensive organ dispatch, a world-model neuron may predict the outcome and author a `plexus:advisory` opinion into its own edit layer — Cozy's CWM predict step, industrialized. The socket is vendor-neutral: Cosmos-class WFMs are the default candidate (open weights, closed-loop predict-evaluate-converge), but any Coalition-class predictor fits. **Authority rule (from A3):** predicates gate — deterministic, they block; foresight annotates — heuristic, it warns, ranks, and informs a budget or a human, and never cancels a dispatch on its own. Hard constraint: the foresight neuron is the *most* aggressively predicate-gated and budget-bound in the system. "Predict before every dispatch" is the group-chat failure in a lab coat.

**3.5 Agent-to-agent talk.** No message bus. Agents author opinions into their edit layers; other predicates read the composed result. Conversation is composition — provenance, replay, and arbitration for free. (Already the documented Moneta↔Octavius convention: the stage is the interface.)

**3.6 Rollouts as composition.** Candidate futures — foresight predictions, alternative approaches — are authored as variant sets or weak-layer opinions ("rollouts as sibling prims," per the Synapse substrate spec). The arbiter's selection promotes one by strength; rejected branches remain as provenance. Speculation is just another opinion.

**3.7 Storm control.** Debounced notices (batch per recompose), per-neuron cooldowns, a global wake budget, and the Cozy self-healing ladder (TRANSIENT / RECOVERABLE / TERMINAL — only TERMINAL halts). A neuron that trips its budget is muted and flagged — visible, never silent.

---

## 4 · Organ Layer (Cargo Hold Contract)

Any execution engine qualifies if it can:

1. **Accept** a serialized job (graph/scene intent + inputs + seed + colorspace intent)
2. **Stream** progress and intermediates
3. **Return** assets with full generation metadata
4. **Be interrogated** for capability
5. **Declare** its embodiment profile (`PlexusOrganAPI`): dialect, capabilities, cost curve — so neurons choose organs the way a world-action model chooses embodiments

**Shipped organs:** ComfyUI via Comfy-Cozy (adapter, endpoint pooling, circuit breakers, run-report provenance — ~90% of the contract) and Houdini via Synapse (inside-out: the agent lives in the interpreter; perception bridges give sub-50ms event-to-agent latency). **Future organs:** a neural-render preview organ (DLSS-5-class instant previews before the expensive renderer wakes — a rendering reflex tier) and a world-model organ (§3.4).

**Vendor rule (from A1):** NVIDIA — or any vendor — *below* the adapter contract, freely and gratefully. *Above* it, never. CUDA muscle inside organs is fine and is today's practical reality; a CUDA assumption in a schema is a defect.

**Hard rule:** no engine internals leak upward. The stage never knows what a KSampler is.

---

## 5 · The Hard Problem — substantially de-risked

Composition semantics under concurrency remains the one genuinely hard piece — and Moneta Phase 2/3 already measured most of it, on this machine, against OpenUSD 0.25.5:

- Pcp recomposition: effectively free (0.1–2.6ms). `Save()` serialization is the real cost, bounded by sublayer rotation at 50k prims.
- Narrow writer lock (Sdf.ChangeBlock-only): p95 reader stall 0.6–0.8ms at typical batches (99.5% reduction vs wide lock).
- Concurrent Traverse + Save: ruled deterministic-safe across 775M prim-level assertions.

Remaining rules for the multi-stage case: one writer per layer (A6); cross-project writes land only in the shared exchange *stack*, one sublayer per participant; session layer strongest so a human's live overrides always win; every recompose observable, every opinion attributable. What's left to prove is the two-live-stages case — which is exactly what Phase 1 films.

---

## 6 · Build Phases — position, destination, distance

**Mile 0.5 of ~4** (revised down after the portfolio audit: ~85–90% of the system exists across Cozy, Synapse, and Moneta; Phase 0 closed with this document).

**Phase 0 — Paper.** *Done.*

**Phase 1 — The Slice.** Two Moneta-style handles, one shared exchange stack, one `Tf.Notice` observer (TopsEventBridge pattern), one neuron with one wake predicate. A change authored in A visibly lands in B mid-flight; the neuron wakes, acts once, sleeps.
*Done means:* filmable in one continuous take. No UI — usdview and code.
*Distance:* every component has a tested sibling in a repo you maintain. An afternoon of assembly plus a day of schema work.

**Phase 2 — Organ Retarget.** Not a build: point Cozy's existing adapter at the stage. A neuron's action submits a job; the result returns as `PlexusAssetAPI` opinions (workflow.lock generalized), visible in both projects.
*Done means:* generate in A, see it composed into B, read full provenance from the stage alone.

**Phase 3 — Reflex, Triage, Foresight.** Wire the three tiers (mostly assembly from Cozy/Synapse); add the budget-bound foresight gate and rollout variants; prove storm controls by provoking a wake storm and watching it fail safe.
*Done means:* a 30-minute three-neuron session costs pennies; the storm test fails closed; one gated prediction demonstrably vetoes one wasteful render.

**Phase 4 — Simultaneity.** Two genuinely different projects (look-dev + shot) running at once, exchanging through the shared stack, each with its own neurons — the second film.

**Phase 5 — Aperture.** Only now: minimal stage inspector + neuron status, README, public repo. UI last, always.

---

## 7 · Anti-scope (what this is NOT)

- **Not** a new node editor, ever. usdview and code until Phase 5.
- **Not** new samplers, model loaders, or inference code. That treadmill kills solo developers.
- **Not** an enterprise curation platform (seat taken) or a footage-enhancement tool (seat bought — InterPositive/Netflix; adjacent principle, different substrate, no collision).
- **Not** a Cosmos integration project. Foresight, rollouts, and embodiment profiles are Phase 3+; if world-model work appears before the Phase 1 film exists, that is the scope-balloon cue by name.
- **Not** a codebase merge. Unification = schemas + thin glue + one shared layer stack. The stage is the interface. If a task involves moving code between repos, stop and shrink it on paper.
- **Not** a general agent framework, and **not** multi-user (yet) — multi-*project*, one operator.

---

## 8 · Convergence — where the 2026 wave meets the substrate

Five integration points, each tracing to an axiom, none blocking Phase 1:

1. **Foresight gate** (A3, §3.4) — WFM predicts before organs fire. Lands Phase 3.
2. **Rollouts as composition** (A1, §3.6) — candidate futures as variants/weak opinions. Phase 3.
3. **Embodiment profiles** (A4, §4) — organ dialects as stage data. Phase 2–3.
4. **The exhaust** (A5) — provenance-complete sessions are world-model-grade grounded datasets. A value line, not a build item.
5. **Standards ride** (A1, §2.4) — Core Spec conformance, native 3DGS for captured-world data, nanoUSD as a future neuron runtime. Ongoing discipline, zero build cost now.

Frame for all five: PLEXUS is the *explicit* world model; Cosmos-class systems are the *implicit* one; the exchange stack is the membrane where they drive each other (A8).

---

## 9 · Risks, honestly

| Risk | Reality check | Mitigation |
|---|---|---|
| Agent chatter cost | Death by LLM-per-node | Tiered response (§3.2); budgets; reflex-first |
| Foresight cost | The expensive neuron | Most-gated, most-budgeted; Phase 3, never earlier |
| Notice storms | Recompose floods | Debounce, cooldowns, global budget, fail-closed ladder (§3.7) |
| Engine API drift | Upstream churn | All contact through the organ contract; Cozy already absorbs Comfy's |
| Concurrency bugs | The one hard problem | Substantially de-risked with Moneta's empirical envelope (§5); Phase 1 proves the multi-stage case smallest-first |
| Stage bloat | Heavy bytes creep into prims; `Save()` cost grows; heartbeat dies | A9 boundary (§2.5): describe and reference, never embed; sublayer rotation at 50k prims |
| Vendor gravity | CUDA everywhere | Vendor rule (§4): below the contract freely, above it never; pxr + Core Spec only |
| Scope balloon | The known loop | This document. No axiom citation → parked. Repo-merge urge → paper first |

---

## 10 · The Slice Spec (Phase 1, exact)

```
stages:      projectA.usda, projectB.usda, shared/exchange/ (stack)
reference:   projectB references the composed exchange
neuron:      scope = /Exchange/LookState
             predicate = attr "temperature" changed AND delta > 0.2
             action = author "grade_hint" opinion into its own exchange sublayer
             budget = 1 wake / 10s
demo beat:   edit temperature in A → recompose → B's view updates →
             neuron wakes → grade_hint appears in B → neuron sleeps
capture:     one continuous screen recording, two usdview windows side by side
```

That recording is the pitch — and, per the 2026 comps (§11), the due-diligence package. Everything else in this document exists to make those ninety seconds true.

---

## 11 · Position — where PLEXUS stands (August 2026)

**The map has four seats. Three are taken.**

| Seat | Held by | What they own | What they structurally can't do |
|---|---|---|---|
| The swarm | ComfyUI ($500M val, Apr 2026; 4M users, 60k community nodes) | Execution + community velocity; day-one model support | Source of truth is workflow JSON; live composition means rebuilding their state model under 4M users |
| The enterprise | Foundry × Griptape | Curated models, compliance, Nuke-side studio distribution; shipping agents + MCP fast | Can't demote their own orchestration product to an organ; can't ride the open swarm — curation *is* the pitch |
| The vertically integrated | Netflix × InterPositive ($587M cash, 16 people, pre-revenue, exclusive) | Project-grounded AI at production scale, locked in-house | Builds inward, not open. Its exclusivity started an arms race among rival strategics |
| **The open composition seat** | **Empty** | Live cross-project composition · dormant predicate-gated agents · engine-agnostic organs · structural provenance | — |

**Why the empty seat stays reachable only from here:** holding it requires all four properties at once, and each incumbent is structurally barred from at least one. Riding the swarm (A4) makes ComfyUI's 60k nodes inherited capability, not competition.

**The tailwinds.** AOUSD now frames OpenUSD as the 3D data layer for agentic AI, with Core Spec 1.0 and ISO certification in motion and members spanning Pixar, Apple, Adobe, Autodesk, NVIDIA, Unity, ByteDance, Huawei, and AMD — the substrate bet is co-funded by the industry and owned by no vendor. NVIDIA spent SIGGRAPH 2026 (a full physical-AI day, 21 papers joining 3D worlds to agent control) teaching the market that agents + USD is the future: category education, free. And the Cosmos Coalition put Runway, LTX, and Black Forest Labs in a robotics world-model alliance — the VFX↔robotics convergence PLEXUS's exhaust (A5) feeds is institutional now.

**The clock.** ComfyUI's Series B funds cloud collaboration/versioning — the outer shell of this thesis. Griptape shipped agent-piloted MCP within months. Realistic window before the story compresses: **12–18 months**, shortened by the strategic arms race. Phase 1 is not patient work.

**The comps ladder and what it says about Phase 1.** Griptape sold for distribution (undisclosed). ComfyUI priced on users ($500M). InterPositive priced on a grounded primitive plus the team that proved it — no users, no launch ($587M). Proof of primitive outranks traction. The §10 recording is three artifacts in one: the demo, the demand generation for a category nobody searches for yet, and the diligence package for the buyer class that paid $37M a head.

**The honest counterweight.** InterPositive's price included Ben Affleck — a talent-relations shield, priceless post-strikes. PLEXUS has no shield. The film must carry credibility alone: short, continuous, undeniable, every step attributable from the stage.

**Value paths, ranked honestly:** (1) strategic interest — precedent set twice in 2026, the buyer set now includes every streamer and studio group watching Netflix arm itself; (2) positioning — the person who filmed the un-filmable is who the labs and the new hybrid-role market want in the room; (3) the exhaust — grounded datasets as a by-product, saleable into a coalition-certified market; (4) direct revenue — the long shot, and nothing in §6–§7 depends on it.
