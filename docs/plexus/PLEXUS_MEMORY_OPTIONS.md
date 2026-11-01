# Plexus memory: what sits behind the Memory contract

Drafted Nov 1, 2026. Revised the same day for Blueprint v5.2 and Joe's independence rule. These are options, not a decision. The choice is Joe's.

**The rule this note follows:** SYNAPSE is an architectural reference only. Plexus takes no SYNAPSE code, imports, packages, shared contracts or dependencies. Where an idea below also appears in SYNAPSE, it is stated here in Plexus's own terms, with the reason it fits Plexus.

## The contract is Plexus's own

Plexus defines one Memory contract, in Rust, exposed to Python through `plexus._core`:

- `recall(scope, query) -> Outcome<Recall>`
- `remember(scope, record) -> Outcome<Receipt>`

Both return the Plexus envelope, `Outcome`, with status `Ok`, `Unavailable` or `Blocked`, a payload and a reason (Blueprint §4). Nothing in the contract names a backend, a file location or a host application.

**Absence shape: narrow.** When no memory backend is reachable, `recall` answers from the local stage only and says so in its payload, and `remember` returns `Unavailable` with the record handed back to the caller. A neuron reading memory should keep working on what it can see, because parts of a Plexus network are routinely offline.

Comfy-Cozy, which Plexus is seeded from, already has two memories of its own: the session memory in `agent/memory/session.py`, and the experience accumulator in `cognitive/experience/`, which starts biasing toward what worked after about 30 runs. Under every option below, the accumulator becomes a client of the Memory contract instead of keeping a private store.

## Option A · Plexus-local memory first

Plexus ships its own small backend behind the contract: an append-only record file per scope, plus an index Plexus rebuilds on start. No Moneta.

- **Good:** Plexus has working memory on day one with nothing external to install. Every test runs offline.
- **Cost:** recall is plain lookup with no ranking beyond recency and scope. Plexus will want something better once real projects accumulate history.

## Option B · Moneta through a Plexus-written adapter

Moneta is a separate repo and a memory engine in its own right. Plexus writes an adapter that implements the Memory contract on top of Moneta's public interface, and nothing else.

- **Good:** Plexus gets a real memory engine without owning one. The adapter is the only place that knows Moneta exists, so Moneta can be absent, swapped or upgraded without any caller changing.
- **Cost:** Plexus writes and maintains the adapter, including its own degraded mode and any backfill it needs. Moneta's interface has to be read fresh from Moneta's repo when the adapter is written, since this note hasn't checked it.

## Option C · Memory as composition

Memories become opinions in Plexus's stage: a "past" namespace layered into the exchange stack, so recall happens through composition instead of a query. This is the most on-thesis option, because composition is the runtime.

- **Good:** it's the real destination. Projects would remember into each other the same way they compose.
- **Cost:** it needs a backend that writes stable, addressable memory prims that composition can resolve. As of the September write-up, Moneta wrote one-shot prims with no composition arcs, and its stable-slot work was the prerequisite. That status may have moved, and should be checked in Moneta's repo before this option is planned.

## My lean

**Option A now, Option B when Plexus has real history to recall, and Option C as the destination.**

Option A keeps Phase 0 free of every external substrate, which the blueprint asks for. Option B slots in behind the same contract later without a caller changing. Option C stays reachable because the contract never promised a query engine, only `recall` and `remember`.

## Rules Plexus adopts for memory

These are Plexus rules, each with the reason it fits Plexus. SYNAPSE learned similar lessons, which is why they're worth stating early, but nothing here depends on SYNAPSE.

1. **One handle per store, one owner per handle.** Plexus runs many neurons at once on a tokio scheduler. Two handles writing one store would race, so the scheduler owns the handle and neurons borrow it through the contract.
2. **Observers never construct.** Any panel, inspector or dashboard reads memory through an existing handle and never opens a store itself. That keeps rule 1 true however many views Plexus grows.
3. **Backend swaps run in shadow first.** A new backend writes alongside the current one, behind a config flag that defaults off, and a parity diff gates the switch. This is the same discipline the blueprint uses for the openusd composer (§13.4), so Plexus has one way of promoting anything.
4. **Never auto-deduplicate a memory store.** Two records that look alike can carry different provenance, and provenance is part of Plexus's system of record (F1, F4). Deduplication, if it ever happens, is an explicit, reviewed operation.
