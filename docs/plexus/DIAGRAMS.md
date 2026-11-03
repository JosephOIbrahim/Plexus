# Plexus · Diagrams

**Six pictures of how Plexus is meant to work.** Each one has a single job, stated above it.

They follow Blueprint v5.3 (`docs/plexus/PLEXUS_BLUEPRINT_v5.md`), with the Nov 1 Comfy-Cozy decision (draft v5.4, `BLUEPRINT_v5.4_DRAFT_CHANGES.md` B5), and Engineering Spec v2.1 (`PLEXUS_SPEC.md`). Where a diagram shows something not yet decided, it says so in its title.

GitHub draws these directly. In other viewers, paste a block into [mermaid.live](https://mermaid.live).

| # | Diagram | Answers |
|---|---|---|
| 1 | [Roadmap](#1--roadmap-you-are-here) | Where are we? |
| 2 | [Layers](#2--layers) | What sits on what, and in which language? |
| 3 | [The slice](#3--the-slice-phase-1) | What does Phase 1 prove? |
| 4 | [Wake pipeline](#4--wake-pipeline) | What happens when the stage changes? |
| 5 | [Notice path](#5--notice-path-rust-and-python) | Where does Python stop and Rust start? |
| 6 | [Build harness](#6--build-harness) | How does Plexus get built? |

---

## 1 · Roadmap: you are here

**Phase 0 is partly done** (the seed, the frozen tests, the harness and the `plexus/` + `crates/` scaffold exist; the four contracts don't yet). **Phase 1 is in progress.** The thicker the outline, the nearer the work; green is kept for done, and nothing here is done yet.

<!-- plexus:status -->
**Phase 1 · 2 of 11 frozen tests pass** (T0, the schema gate; T1, propagation) · Nov 3, 2026
<!-- /plexus:status -->

```mermaid
flowchart LR
    P0["Phase 0<br/>Seed + contracts<br/>(partly done)"]:::partial
    P1["Phase 1<br/>The slice<br/>tests T0 to T6<br/>(in progress)"]:::next
    P2["Phase 2<br/>Projection +<br/>ComfyUI organ<br/>tests T7, T8"]
    P3["Phase 3<br/>Safety"]
    P4["Phase 4<br/>Triage +<br/>foresight"]
    P5["Phase 5<br/>Simultaneity"]
    P0 --> P1 --> P2 --> P3 --> P4 --> P5
    classDef partial fill:#ececec,stroke:#6b6b6b,stroke-width:1.5px,color:#111
    classDef next fill:#f6f6f6,stroke:#1b1b1b,stroke-width:3px,color:#111
```

---

## 2 · Layers

**Each layer calls only the layer below it, or a contract.** Rust goes where code is hot, long-running or must be exact. Python stays where code must be flexible, or where what Plexus calls is Python-only: usd-core (Pixar ships no official Rust bindings) and the LLM SDKs.

```mermaid
flowchart TB
    L5["L5 · Surfaces<br/>MCP server · CLI · panel<br/>Python, written new · Comfy-Cozy as reference"]
    L4["L4 · Organs<br/>ComfyUI organ · any engine behind the organ contract<br/>any language, behind the contract"]
    L3["L3 · Projection<br/>stage prims to organ intent, pure functions<br/>Python, written new · Comfy-Cozy as reference"]
    L2["L2 · Nervous system<br/>scheduler · predicates · budgets · tools<br/>Rust, plexus-core"]
    L1["L1 · Contracts<br/>Safety · Memory · Ledger · Composer<br/>defined in Rust, owned by Plexus"]
    L0["L0 · Substrate<br/>composed stage · writer sublayers · exchange<br/>usd-core 26.5 of record · openusd in shadow"]
    L5 --> L4 --> L3 --> L2 --> L1 --> L0
```

**If a contract's backend is missing,** the call says so instead of pretending:

| Contract | When its backend is absent |
|---|---|
| Safety | **Fails closed.** Nothing runs. |
| Memory | **Narrows.** Answers from the local stage only, and says so. |
| Ledger | **Outbox.** The claim is kept and sent later. |
| Composer | **Fails closed.** No composer of record, no stage. |

---

## 3 · The slice (Phase 1)

**Two projects meet only through one shared exchange.** Project A changes a value. Project B sees it. A neuron wakes and writes a hint into its own layer, and B sees the hint too, with a stamp saying where it came from.

```mermaid
flowchart LR
    A["Project A<br/>any USD writer"]
    B["Project B<br/>projectB.usda"]
    N["Neuron runtime<br/>participant lookNeuron<br/>watches /Exchange/LookState"]
    subgraph EX["shared/exchange/"]
        X["exchange.usda<br/>defines /Exchange<br/>sublayers, strongest first"]
        FA["from_projectA.usda"]
        FN["from_lookNeuron.usda<br/>the neuron's own edit layer"]
        X --- FA
        X --- FN
    end
    A -->|"writes LookState.temperature"| FA
    N -->|"writes lookNeuron/Hints.grade_hint<br/>stamped plexus:sourceLayer"| FN
    B -->|"references the composed /Exchange<br/>weaker than B's own opinions"| X
    X -.->|"change notice"| N
```

**One writer per layer.** Nobody edits another writer's sublayer. Composition, not application code, decides whose opinion wins.

---

## 4 · Wake pipeline

**A neuron runs only when every check on the way says yes.** The order is fixed (Spec §6).

```mermaid
flowchart TD
    E["StageEvent<br/>changes coalesced over 50 ms"] --> S{"Inside the<br/>neuron's scope?"}
    S -->|no| Z["Nothing happens"]
    S -->|yes| P{"Predicate true?<br/>e.g. delta of temperature #gt; 0.2"}
    P -->|no| Z
    P -->|yes| G{"Budget allows<br/>another wake?"}
    G -->|"no, a trip"| T["Count the trip<br/>3 in a row: muted + flagged"]
    G -->|yes| R{"Risk gate<br/>every tool allowed?"}
    R -->|no| RD["Denied by construction"]
    R -->|yes| ACT["Act"]
    ACT --> PG{"Publication gate<br/>target path on the allowlist?"}
    PG -->|no| F["Write dropped<br/>plexus:flag on the neuron prim"]
    PG -->|yes| W["Author in the neuron's own layer<br/>stamp plexus:sourceLayer · save to disk"]
    W --> Q["Quiesce<br/>lastWake · delta cache · state dormant"]
```

**Three details that matter:**

- **The delta cache updates only on a wake.** Small changes add up until they cross the threshold.
- **A mute is never silent.** It is an opinion on the neuron prim, with a `plexus:flag…` attribute beside it.
- **Every opinion is saved as it lands.** Reopening the files reproduces the whole session.

---

## 5 · Notice path: Rust and Python

**Option A, decided by Joe on Nov 1. Option B (all Python for Phase 1) was the alternative.** Python keeps the threads and everything that touches `pxr`. Rust (`plexus._core`) keeps the pure logic: compiling and evaluating predicates, and counting budgets. Only plain data crosses between them.

```mermaid
sequenceDiagram
    participant W as Any USD writer
    participant U as usd-core stage
    participant C as Notice callback (Python)
    participant D as Dispatcher thread (Python)
    participant R as plexus._core (Rust)
    participant A as Action thread (Python)
    W->>U: author and save a layer
    U->>C: Usd.Notice.ObjectsChanged
    C->>D: enqueue StageEvent(paths, resynced, t)
    Note over D: coalesce for 50 ms
    D->>U: read composed values for the predicate's paths
    D->>R: predicate.eval(changed, values)
    R-->>D: wake or not
    D->>R: budget.admit(now)
    R-->>D: wake, trip or mute
    D->>A: run action(ctx)
    A->>U: ctx.author through the gate, into the edit layer, saved
```

**Option B** keeps all of this in Python for Phase 1 and moves predicates and budgets to Rust in the next mission, behind the same surface. The trade-off is in §4 of the [`acceptance` mission plan](https://github.com/JosephOIbrahim/Plexus/blob/mission/acceptance/harness/plexus_loop/missions/acceptance.plan.md) on the `mission/acceptance` branch.

---

## 6 · Build harness

**Claude plans and reviews. A local model makes the attempts. Joe decides what gets promoted.** An attempt is kept only when it is a strict gain.

```mermaid
flowchart TD
    BEST["Best commit so far"] --> WT["Fresh git worktree"]
    WT --> HD{"Houdini open,<br/>or can't tell?"}
    HD -->|yes| CPU["CPU profile<br/>no GPU layers · capped jobs"]
    HD -->|no| GPU["GPU profile"]
    CPU --> WK["Worker: Ollama qwen3-coder:30b<br/>replies with one diff"]
    GPU --> WK
    WK --> FZ{"Touched a frozen path<br/>or anything outside focus?"}
    FZ -->|yes| DROP["Drop it, with its worktree"]
    FZ -->|no| GT{"Every gate passes?"}
    GT -->|no| DROP
    GT -->|yes| MT{"Failing tests down by 1 or more,<br/>and none went missing?"}
    MT -->|no| DROP
    MT -->|yes| KEEP["Commit onto plexus-loop/acceptance<br/>it becomes the new best"]
    KEEP --> STOP{"Budget used, 8 drops in a row,<br/>stop file, or every test passes?"}
    DROP --> STOP
    STOP -->|no| BEST
    STOP -->|yes| REV["REVIEW.md for Joe<br/>nothing merges by itself"]
```

**Who may touch what:**

| Surface | Path | Who |
|---|---|---|
| **Judge** | `tests/acceptance/` | Joe only. Hooks and the harness both enforce it. |
| **Editable** | `plexus/**`, `crates/**`, `Cargo.toml`, `Cargo.lock` | The worker, through the harness |
| **Program** | `harness/plexus_loop/program.md`, mission files, plans, `CLAUDE.md` | Joe, and Claude when Joe says so |
