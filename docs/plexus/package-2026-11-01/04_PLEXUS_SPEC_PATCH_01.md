# PLEXUS — Spec Patch 01

**Source:** cross-reference of `PLEXUS_BLUEPRINT.md` v2.2 and `PLEXUS_SPEC.md` v2.0 against *ComfyUI Developer Insights* (14 Aug 2026).
**Status:** **APPLIED, 14 Aug 2026** — folded into `PLEXUS_BLUEPRINT.md` v2.3 and `PLEXUS_SPEC.md` v2.1. Retained as the diagnostic record and provenance trail; the [V]/[D]/[F]/[I] marks live here, not in the spec.
**Shape:** each patch states the first principle it derives from, the finding that exposed the gap, the exact edit, and the provenance mark of the evidence ([V] verified / [D] Discord / [F] field / [I] inference, per the source document's legend).

---

## Why a patch and not a rewrite

The insights document is a *ledger of what is true about a dependency*. The spec is a *contract for what we build*. Those decay at different rates — the ComfyUI platform will move again this quarter, the axioms will not. Keeping the delta in its own file means the next platform shift patches this document rather than reopening the spec, and the provenance marks survive instead of being flattened into confident-sounding prose.

**The one contradiction found.** Patch 01-A reverses a line in the blueprint. The rest are additions and sharpenings. Nothing in the cross-reference invalidates an axiom; A1–A9 all held.

---

## Patch 01-A — Foresight advises; it never blocks

**First principle:** authority must match epistemic status. A mechanism may only exercise the power its evidence justifies. (Restated from the source: *deterministic findings may block; heuristic findings may only warn* — **[I]**.)

**Finding.** Blueprint §3.4 and axiom A3 say the foresight gate "can predict the outcome and veto the dispatch." A world-model prediction is heuristic by construction. A false blocker on an artist's expensive render costs more trust than a missed warning, and a tool people disable protects nothing. **[I]**

**Edit — blueprint A3, replace:**
> *"...a world-model gate can predict the outcome and veto the dispatch (§3.4). A cheap forecast is dormancy for the organs."*

**with:**
> *"...a world-model neuron can predict the outcome and annotate the stage before the organ fires (§3.4). Deterministic conditions may block; predictions may only advise. A cheap forecast is dormancy for the organs — never a veto."*

**Edit — blueprint §3.4, add as the closing constraint:**
> *Authority rule: predicates gate (deterministic — they block). Foresight annotates (heuristic — it warns, ranks, and informs a budget or a human, and never cancels a dispatch on its own). A foresight neuron authoring a `plexus:advisory` opinion is the whole of its power.*

**Consequence for the spec:** the foresight tier (D3) is specified as an *authoring* neuron, not a gating one. It writes advisory opinions into its own edit layer like any other neuron. No new mechanism, one less power.

---

## Patch 01-B — `plexus:envFingerprint` on every asset

**First principle:** provenance answers "what changed?" by diff, not by memory (A5). A record that cannot be diffed against a prior successful state is a receipt, not provenance.

**Finding.** Environment drift is a named failure class: a workflow that worked last week fails with no change to the workflow — node pack updates, torch/CUDA/driver changes, core updates, all invisible. The remedy is a fingerprint captured on every *successful* run, and the critical detail is **capturing baselines from day one; a drift detector installed after the drift has no baseline**. **[F]/[I]** Comfy-Cozy already emits exactly this (one hash over os · python · torch · CUDA · driver · ComfyUI). Spec §3 `PlexusAssetAPI` omits it.

**Edit — spec §3, `PlexusAssetAPI`, add two rows:**

| Attribute | Type | Notes |
|---|---|---|
| `plexus:envFingerprint` | `string` | environment hash from the organ's run report; the diff key for drift |
| `plexus:organVersion` | `string` | organ + adapter version at execution time |

**Rationale for `organVersion` alongside:** the fingerprint covers the *engine's* environment; the organ adapter is our own moving part and drifts independently. Two fields, two owners.

**Cost of adding now:** one schema line. **Cost of adding later:** every asset authored before the change is undiffable forever.

---

## Patch 01-C — The organ owns correlation; poll for truth

**First principle:** A4 — engines are organs behind a contract, and *no engine internals leak upward*. Corollary made explicit here: **no engine's missing guarantees leak upward either.** If a substrate cannot carry identity, the organ reconstructs it; the stage never learns that the substrate had a gap.

**Finding.** ComfyUI accepts a job and returns a `prompt_id`; it does not accept arbitrary client metadata and does not echo client context onto outputs — the client must remember what it asked for. **[V]** Two independent workarounds exist in the wild for this one missing field (a Note-node metadata smuggle **[D]**; Comfy-Cozy's `prompt_id` + WS-filter + `/history` side-table **[F]**), which is strong evidence the gap is structural rather than misuse. **[I]** Separately: the WebSocket announces completion *before* `/history/{prompt_id}` is guaranteed readable, and third-party clients exist specifically to paper over that race. **[V]/[F]**

**Edit — spec §8, add to the Organ Protocol contract as a normative note:**
> **Correlation is the organ's problem.** `submit()` returns a `JobHandle` carrying the PLEXUS-side correlation id. Reconstructing engine-job → correlation is entirely inside the organ; core never sees a `prompt_id` and never holds a side-table. When an engine gains native client metadata, the organ deletes its reconciliation layer and the contract does not change.

**Edit — spec §8.2, add:**
> **Poll for truth.** `result()` treats WebSocket completion as a responsiveness hint and `/history/{prompt_id}` as the source of truth; it does not return an `AssetRecord` until history is readable and the asset file is stat-able. Emitting a result on the WS event alone reproduces the known race.
>
> **Link-array invariant.** Any parse → mutate → serialize round trip preserves `["node_id", output_index]` link references exactly. This is the number-one failure mode in ComfyUI agents, it does not announce itself, and the graph looks correct while executing wrong. Test it explicitly (add to T7). **[F]**

**Edit — spec §9/§10, extend T7:**
> **T7 — Round trip.** …plus: (a) `plexus:envFingerprint` on the resulting asset prim is non-empty and matches the organ's run report; (b) a graph round-tripped through the organ with no intended change is byte-identical in its link arrays.

---

## Patch 01-D — Retry produces lineage, never an overwrite

**First principle:** A5 — provenance is structural. Two executions are two facts. A record that silently replaces another destroys the diff A5 exists to preserve.

**Finding.** `requestId` was proposed as correlation *and* idempotency, but only the correlation half was picked up; retry semantics remain unspecified upstream as of 5 Aug 2026. **[D]/[I]** Unspecified means every client assumes differently — and an agent that retries on low quality or transient error is exactly our case (§6 tier 2).

**Edit — spec §6, add to the wake pipeline as a step-6 clause:**
> **Retry authoring.** A retried organ job authors a *new* asset prim carrying `plexus:retryOf` (the prior asset's prim path) and `plexus:retryReason` (`quality` | `transient` | `operator`). Never overwrite a prior asset prim. Two runs, two records, one intent — the intent being the neuron's correlation id, which both carry.

**Edit — spec §3, `PlexusAssetAPI`, add:**

| Attribute | Type | Notes |
|---|---|---|
| `plexus:retryOf` | `string` | prim path of the prior attempt; empty on first attempt |
| `plexus:retryReason` | `token` | allowed: `none`, `quality`, `transient`, `operator` |

**Consequence:** upstream idempotency, if it ever ships, becomes an *organ-level optimization* (dedupe before submit) with no schema change. We are not blocked on a decision we do not control.

---

## Patch 01-E — The contract promises no resume

**First principle:** A4 plus honest degradation. A contract must not imply a capability the substrate cannot deliver; unknown is a valid result, fabricated certainty is not.

**Finding.** Arbitrary graphs are not checkpointable, and scheduling is request-level — a workflow is a sequence of node executions, not a transaction. Any resume feature requires a feasibility study first (which outputs serialize, which operations replay safely, storage, invalidation). **[I]** The name `JobHandle` invites the assumption.

**Edit — spec §8.1, add below the Protocol block:**
> `JobHandle` promises submit / stream / result. It promises **nothing** about resume, checkpoint, or replay: arbitrary graphs are not checkpointable and engine scheduling is request-level. An organ whose engine genuinely supports resumption may expose it as a capability string, never as part of the base contract.

**Edit — spec §12, add:**
> **D8** — Resume / checkpointing. Blocked on a per-organ feasibility study (serializable outputs, deterministic replay, storage, invalidation). Output-backed and explicitly instrumented stage boundaries are the tractable subset; everything else gets observability without a promise.

---

## Patch 01-F — Two watch items that change the build if they land

Not edits. Standing checks, because both would delete work rather than add it — the good kind of dependency.

1. **Per-job client metadata in OSS core** (not cloud-only), echoed on `/history` and `/ws`. If it lands: Patch 01-C's reconciliation layer inside the Cozy organ can be deleted, and the `JobHandle` carries the correlation id natively. If it lands cloud-only, nothing changes for a local build. **[D]** — open as of 5 Aug 2026.
2. **Canonical asset identity / content-addressed models.** If it lands: `plexus:modelHashes` gains a first-party source of truth and any duplicative local asset bookkeeping should be deleted the day a stable equivalent ships. **[I]**

**Posture on both:** adopt, don't compete. Neither blocks Phase 1; both simplify Phase 2 if they arrive.

---

## What the cross-reference *validated* (recorded so it isn't re-litigated)

- **The root pattern is PLEXUS's thesis one layer up.** *"ComfyUI identifies things by where they happen to be rather than by what they mean"* **[I]** — node IDs, paths, filenames, and queue ids are addresses masquerading as identity. Prim paths and typed schemas (A1, §3) are the durable-meaning answer. The insight document and the blueprint are the same argument at two altitudes.
- **"Transport claims expire"** **[I]** — first-party local MCP in private test **[D]** would erase a transport-based position. PLEXUS holds no transport claim: it lives above the organ contract by construction (A4). Confirms the seat choice in §11.
- **Engine abstraction survives the platform fixing itself** **[I]** — the stated reason to build `IAIEngine` rather than patch ComfyUI is verbatim the reason A4 exists. Griptape's id-first orchestration is the same move; PLEXUS's differentiator is that the id lives in a composed, standard, inspectable stage rather than a vendor's orchestrator.
- **Typed absence** **[I]** — missing / skipped / cached / reused / evicted / invalid / failed are distinct, and a contract that permits silence eventually delivers it. Already load-bearing in §6 (muted neurons flag visibly) and §7.3 (denied writes flag rather than drop silently). No change needed; worth not losing.

---

## Application order

1. Blueprint A3 + §3.4 (Patch 01-A) — the contradiction, first.
2. Spec §3 schema rows (01-B, 01-D) — **before the first schema commit**; these are the backfill-impossible ones.
3. Spec §6 retry clause (01-D), §8/§8.2 organ notes (01-C, 01-E), §12 D8 (01-E).
4. Spec §9/§10 test extension (01-C).

Everything here is additive to the build order in the spec's closing line. None of it moves Phase 1.
