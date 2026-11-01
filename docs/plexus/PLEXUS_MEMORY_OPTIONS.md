# Where SYNAPSE's memory work plugs into Plexus

Drafted Nov 1, 2026 alongside Blueprint v5.0. These are options, not a decision. The choice is Joe's.

## What SYNAPSE's memory work actually is

It's three things, and they travel differently.

**The contract.** `python/synapse/loop/ports.py` defines MemoryPort (`query_and_filter`), LedgerPort, SafetyPort and StagePort, all returning `PortResult` with status SUCCESS, UNAVAILABLE or BLOCKED. Each one has a defined way to degrade when its substrate is missing. This code has no Houdini in it.

**The store.** `python/synapse/memory/` holds the `MemoryStore` interface with a backend flag (`SYNAPSE_MEMORY_BACKEND`: jsonl, moneta or shadow), the in-process Moneta adapter, shadow dual-write with a parity diff, backup-first backfill, and degraded-mode health. A lot of it is shaped by Houdini: the store lives next to the hip file, initialization belongs to Houdini's main thread, and scene memory and VEX capture are Houdini-specific.

**The lessons.** One handle per storage URI, one owner per handle. The panel observes and never constructs. Shadow first, flag-gated, default off. And never auto-deduplicate a memory store. These came from real incidents (`docs/HANDOFF_MEMORY_DUAL_WRITE.md`).

Comfy-Cozy, which Plexus is seeded from, has its own smaller memory: `agent/memory/session.py`, plus the experience accumulator in `cognitive/experience/` that starts biasing toward what worked after about 30 runs.

## Option 1 · Share the contract, not the code

Plexus adopts SYNAPSE's port signatures and `PortResult` verbatim, and Moneta sits behind MemoryPort through an adapter that Plexus owns. Comfy-Cozy's experience accumulator becomes a MemoryPort client instead of a private store. Plexus imports nothing from SYNAPSE.

- **Good:** small and clean. One Moneta adapter shape serves both products. Plexus can build and test with Moneta absent, because MemoryPort narrows to the local stage.
- **Cost:** Plexus re-earns some of the store hardening (degraded mode, backfill) when it needs it.

## Option 2 · Lift SYNAPSE's MemoryStore into Plexus

Copy or package `python/synapse/memory/` and run Plexus memory through the same `MemoryStore`, backend flag and shadow parity harness.

- **Good:** the most battle-tested path, available on day one.
- **Cost:** it brings Houdini-shaped assumptions (hip-dir storage, main-thread ownership, scene memory) into a system with no Houdini. Two products then share one large module, and every change has to keep both green.

## Option 3 · Memory as composition

Moneta's memories become opinions in Plexus's stage: a "past" namespace layered into the exchange stack, so recall happens through Pcp resolution instead of a query. This is the most on-thesis option, since composition is the runtime.

- **Good:** it's the real destination. Projects would remember into each other the same way they compose.
- **Cost:** as of the September write-up, Moneta writes one-shot `/Memory_<hex>` prims with no composition arcs, so Pcp has nothing to resolve yet. Moneta's Phase 1 stable-slot work is the prerequisite. That status may have moved since.

## My lean

**Option 1 now, with Option 3 as the destination, and skip Option 2.**

Option 1 costs almost nothing, keeps Plexus buildable while every substrate is absent, and doesn't foreclose Option 3. When Moneta's stable slots land, MemoryPort's adapter can switch from querying to composing without any caller changing. Option 2 would trade a week of saved hardening for a long-term coupling to Houdini-shaped code, and that's the wrong trade for a system whose point is not being Houdini.

The SYNAPSE lessons come along under any option. They're in Blueprint v5 §2 and §5.2 as rules, not code.
