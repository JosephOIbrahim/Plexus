# Blueprint v5.3 → v5.4 · proposed changes

**Status: draft for Joe's review. Nothing here has been applied to `PLEXUS_BLUEPRINT_v5.md`.**

**One decision drives every change:** Plexus is the next generation of Comfy-Cozy, built from the ground up. Comfy-Cozy (`G:\Comfy-Cozy`) is an architecture reference only, like SYNAPSE. New Plexus code copies nothing from it and imports nothing from it (Joe, Nov 1). The repo still carries Comfy-Cozy's history and the seeded `agent/` and `cognitive/` code; whether that stays is Joe's call.

v5.3 says the opposite in about a dozen places: Comfy-Cozy is "the seed code", "its code becomes Plexus's own", and Plexus "keeps" its stage, gate, providers and surfaces. Each change below fixes one of those places. Line numbers are v5.3's.

**How to read each change:** **Now** is v5.3's text, verbatim. **Proposed** is the v5.4 text. **Why** is one line.

---

## Summary

| ID | Where | What changes |
|---|---|---|
| B0 | §0, new item 9 | Records the decision itself |
| B1 | Header, line 4 | Version line mentions v5.4 |
| B2 | How to read, line 21 | Comfy-Cozy becomes a reference, not the seed code |
| B3 | How to read, line 30 | `[v5 · from Cozy]` means a borrowed idea, no code |
| B4 | §0 item 5, line 47 | Projection is written new |
| B5 | §2 diagram, lines 78 and 80 | L5 and L3 are new Python |
| B6 | §3, line 101 | L0 is written new; Cozy's stage is the reference, pitfalls named |
| B7 | §7, line 172 | Projection references Cozy's mapper and lock files |
| B8 | §8, line 180 | The first organ is a new ComfyUI organ; frozen names explained |
| B9 | §10 table, lines 199 and 206 | Repo mapping rows |
| B10 | §10, line 210 | "What Plexus keeps" becomes "what Plexus learns" |
| B11 | §11 Phase 0, line 218 | The seed is history, not a base |
| B12 | §11 Phase 2, line 220 | Phase 2 builds a new ComfyUI organ |
| B13 | §13.1, line 252 | Why Python stays, on Plexus's own terms |
| B14 | §13.3, line 270 | Why Python is the host, on Plexus's own terms |
| B15 | §13.3 diagram, lines 280–281 (the change is on 281) | Drops "(from Cozy)" |
| B16 | §14.2, line 342 | Thin glue: no imports and no copies |
| B17 | §14.2, line 343 | LLM providers are Plexus's own, written new; no fifth contract decided |
| B18 | §14.2, line 345 | License D6 (a legal reading for Joe to confirm) |
| B19 | §14.2, new bullet | Spec v2.1 lines that assumed Comfy-Cozy code |
| B20 | `PLEXUS_MEMORY_OPTIONS.md`, line 18 | The memory note still says Plexus is seeded from Comfy-Cozy |
| B21 | §14.2, line 348 | Python ≥ 3.11: the seed's packaging is Joe's call |
| B22 | §2 diagram, §5.1, §6, §8, §11 Phase 1, §13.3 | The scheduler stays in Python until measured (deferral accepted by Joe) |
| B23 | §11 Phase 0, line 218 (second sentence) | Phase 0's Rust pieces move to M2b, M3 and M6 (deferral accepted by Joe) |

**Verified Nov 1** by three independent read-only checks: every "Now" quote is verbatim at its stated line; a sweep of every Plexus document for leftover "reuse Comfy-Cozy" wording; and a red team against the frozen tests, `CLAUDE.md` and the rest of v5.3. Their findings are folded in below.

---

## B0 · §0, a new item 9

**Now:** §0 lists eight changes. None says what Comfy-Cozy is.

**Proposed** (append after item 8):

> 9. **[DECIDED · Joe] Comfy-Cozy is an architecture reference, not the seed code.** Plexus is Comfy-Cozy's next generation, built from the ground up. The repo keeps Comfy-Cozy's history, but new Plexus code copies and imports nothing from it (Nov 1).

**Why:** §0 is the one-screen list of decisions; this one belongs there.

---

## B1 · Header, line 4

**Now:**

> Drafted Nov 1, 2026. v5.1 added Rust. v5.2 locks Joe's two decisions and his rule on SYNAPSE. v5.3 reconciles it with the document package Joe sent on Nov 1 (§14). Status: draft for Joe's review. Nothing here is ratified until he says so.

**Proposed:**

> Drafted Nov 1, 2026. v5.1 added Rust. v5.2 locks Joe's two decisions and his rule on SYNAPSE. v5.3 reconciles it with the document package Joe sent on Nov 1 (§14). v5.4 makes Comfy-Cozy an architecture reference only (§0 item 9). Status: draft for Joe's review. Nothing here is ratified until he says so.

Also: the H1 title on line 1 becomes `# PLEXUS · Blueprint v5.4`.

**Why:** the version line says what each version changed.

**On ratification, also update** the files that name v5.3 as a source of truth: `CLAUDE.md` lines 10 and 13, `README.md` (status table and repo map), and `docs/plexus/DIAGRAMS.md` line 5. Until then, `CLAUDE.md` line 10 already says the Nov 1 decision wins over v5.3 wherever they conflict.

---

## B2 · How to read, line 21

**Now:**

> - **Comfy-Cozy** is the seed code. Plexus is cloned from it with history, and its code becomes Plexus's own.

**Proposed:**

> - **Comfy-Cozy** is the predecessor and an architecture reference. The repo was seeded with its history, but Plexus is built from the ground up and copies nothing from it and imports nothing from it.

**Why:** this is the sentence the decision reverses. The list it sits in already says "none of them is a template", so v5.4 makes the Comfy-Cozy bullet agree with its own heading.

---

## B3 · How to read, line 30

**Now:**

> - **[v5 · from OpenUSD]** or **[v5 · from Cozy]** is a borrowed pattern, with the reason it fits.

**Proposed:**

> - **[v5 · from OpenUSD]** is a pattern from OpenUSD, which Plexus runs (usd-core, and `openusd` in shadow), with the reason it fits.
> - **[v5 · from Cozy]** is a borrowed idea, restated in Plexus's own terms with the reason it fits. No Comfy-Cozy code comes with it.

**Why:** the two tags need different meanings now. OpenUSD code does run in Plexus (usd-core is the composer of record), so "no code" is true only of the Cozy tag, which now matches the `[v5 · after SYNAPSE]` rule.

---

## B4 · §0 item 5, line 47

**Now:**

> 5. **[v5 · new] Projection moves into Plexus itself** and is seeded from Comfy-Cozy's stage-to-workflow mapping.

**Proposed:**

> 5. **[v5 · new] Projection moves into Plexus itself.** It is written new, with Comfy-Cozy's stage-to-workflow mapping as the reference.

**Why:** "seeded from" means starting from that code.

---

## B5 · §2 layering diagram, lines 78 and 80

**Now:**

```
 L5  Surfaces        MCP server · CLI · panel                     Python (from Cozy)
 L3  Projection      stage prims -> organ intent, pure functions   Python (seeded from Cozy)
```

**Proposed:**

```
 L5  Surfaces        MCP server · CLI · panel                     Python (new; Cozy as reference)
 L3  Projection      stage prims -> organ intent, pure functions   Python (new; Cozy as reference)
```

**Why:** the language column said where the code comes from. It now says the code is new.

---

## B6 · §3, line 101

**Now:**

> - **[v5 · from Cozy] Seed.** Comfy-Cozy already has a LIVRPS stage with reversible delta layers (`agent/stage/cognitive_stage.py`, `cognitive/core/delta.py`), built on Pixar's `usd-core`. L0 starts from that code.

**Proposed:**

> - **[v5 · from Cozy] Reference.** Comfy-Cozy has a LIVRPS stage with reversible delta layers (`agent/stage/cognitive_stage.py`, `cognitive/core/delta.py`), built on Pixar's `usd-core`. Plexus's L0 code is written new on usd-core, and that stage is the reference, including what to avoid: it raises its events from inside its own mutating methods (`write()` and three others) and registers no `Tf.Notice`, so it cannot see a write made by any other writer.

**Why:** "L0 starts from that code" is the reversal. The pitfall is from the Nov 1 mapping (`cognitive_stage.py:389-393`, also `:457`, `:489`, `:638`; no `Tf.Notice` / `ObjectsChanged` registration anywhere in `agent/`, `cognitive/` or `tests/`). The axon (Spec §5) closes exactly that gap.

---

## B7 · §7, line 172

**Now:**

> **[v5 · from Cozy]** Comfy-Cozy already has this code: `agent/stage/workflow_mapper.py`, `workflow_signature.py`, and the `workflow.lock` sidecars that pin model hashes and pack commits. Projection starts there, in Python. **[v5 · Rust]** It moves to Rust only if a measurement shows it on the hot path.

**Proposed:**

> **[v5 · from Cozy]** Comfy-Cozy's `agent/stage/workflow_mapper.py`, `workflow_signature.py` and its `workflow.lock` sidecars (which pin model hashes and pack commits) are the reference for projection. Projection is written new, in Python. Anything that names ComfyUI node types lives in `plexus/organs/cozy.py` or `plexus/organs/cozy/` (T8); L3 itself stays engine-neutral. **[v5 · Rust]** It moves to Rust only if a measurement shows it on the hot path.

**Why:** "Projection starts there" is the reversal. The two reference modules are full of engine vocabulary (`workflow_signature.py` has 26 T8-term lines), so the T8 placement rule has to be stated next to them. The Rust rule is unchanged.

---

## B8 · §8, line 180

**Now:**

> - **[v5 · from Cozy] The first organ is Comfy-Cozy's ComfyUI path:** local execution, multi-worker endpoint pooling with failover, keyless run reports.

**Proposed:**

> - **[v5 · from Cozy] The first organ is a new ComfyUI organ,** written against the organ contract and ComfyUI's own HTTP API. Comfy-Cozy's ComfyUI path is the reference for what it must do: local execution, multi-worker endpoint pooling with failover, keyless run reports. The frozen names `plexus.organs.cozy` and `CozyOrgan` (CONTRACT.md, T7 and T8) stay. They name the organ, not Comfy-Cozy code.

**Why:** the frozen T7 already talks to ComfyUI's own endpoints (its fake server answers `/prompt`, `/history/<id>`, `/view`, `/object_info`, `/system_stats`), not to Comfy-Cozy. The names can't change without Joe editing frozen files, so the Blueprint says what they mean.

---

## B9 · §10 table, lines 199 and 206

**Now:**

> | **plexus** (seeded from Comfy-Cozy) | Everything Plexus is: stage, contracts, neuron runtime, projection, organs, surfaces, build harness | L0 to L5 | owns it |
>
> | Comfy-Cozy | Origin. Stays where it is, and Plexus diverges from its history. | n/a | none after seeding |

**Proposed:**

> | **plexus** | Everything Plexus is: stage, contracts, neuron runtime, projection, organs, surfaces, build harness | L0 to L5 | owns it |
>
> | Comfy-Cozy (`G:\Comfy-Cozy`) | Predecessor and architecture reference. Stays where it is; the Plexus repo carries its history and diverges from it. | n/a | read as a reference; nothing imported or copied |

**Why:** the table says how Plexus reaches each repo. For Comfy-Cozy that is "it reads it". "Stays where it is" and the divergence are still true, so they stay.

---

## B10 · §10, line 210

**Now:**

> **[v5 · from Cozy] What Plexus keeps from Comfy-Cozy on day one:** the LIVRPS stage and delta layers, the gate (`agent/gate/`), zero-LLM recipes (a ready-made Reflex tier), `workflow.lock` provenance, the six LLM providers (the Wake and Reason tiers), and the MCP, CLI and panel surfaces. New Python lands in `plexus/`, and new Rust lands in `crates/`. One seeding fix: a Cozy workflow that told an agent to read a local SYNAPSE checkout was cut (`.claude/workflows/cozy-improve.workflow.js`).

**Proposed:**

> **[v5 · from Cozy] What Plexus learns from Comfy-Cozy:** the LIVRPS stage and delta layers, the pre-dispatch gate (`agent/gate/`, including what to avoid: it classifies unknown tools as REVERSIBLE, `risk_levels.py:249-252`, which F9 forbids), zero-LLM recipes (the shape of a Reflex tier), `workflow.lock` provenance, the six-provider LLM design (the Wake and Reason tiers), and the MCP, CLI and panel surfaces. Mission by mission, each gets a `cozy-mapper` verdict: reference, rebuild in Python, rebuild in Rust, or drop. New Python lands in `plexus/`, and new Rust lands in `crates/`. The seeded `agent/` and `cognitive/` stay in the repo as history until Joe decides otherwise, and nothing in `plexus/` or `crates/` imports them. One seeding fix stands: a Cozy workflow that told an agent to read a local SYNAPSE checkout was cut (`.claude/workflows/cozy-improve.workflow.js`).

**Why:** "keeps from Comfy-Cozy on day one" is the strongest form of the old position. The gate keeps its path and gains its lesson, because "default-deny" would repeat a claim the evidence contradicts. The list stays, as a list of lessons, and the import rule is stated.

---

## B11 · §11 Phase 0, line 218

**Now (first sentence):**

> - **Phase 0 · Seed and contracts. [v5 · fixed]** Was "Moneta base." Now it covers the plexus repo seeded from Comfy-Cozy with its history, the four contracts with honest `Unavailable` adapters, …

**Proposed (first sentence; the rest of the bullet is unchanged):**

> - **Phase 0 · Seed and contracts. [v5 · fixed]** Was "Moneta base." Now it covers the plexus repo (which carries Comfy-Cozy's history as a record, not as code Plexus builds on), the four contracts with honest `Unavailable` adapters, …

**Why:** the phase name can stay ("Seed" is what happened to the repo). What it means changes.

---

## B12 · §11 Phase 2, line 220

**Now (first sentence):**

> - **Phase 2 · Projection and the ComfyUI organ.** Stage to workflow through L3, with Cozy's ComfyUI path behind the organ contract with idempotency, cancel and progress. …

**Proposed (first sentence; the rest of the bullet, the `[v5 · Rust]` sentence, is unchanged):**

> - **Phase 2 · Projection and the ComfyUI organ.** Stage to workflow through L3, with a new ComfyUI organ behind the organ contract with idempotency, cancel and progress. Comfy-Cozy's ComfyUI path is the reference. …

**Why:** matches B8.

---

## B13 · §13.1, line 252

**Now:**

> Rust goes where code is hot, long-running or must be exact. Python stays where code must be flexible or is already written. …

**Proposed (second sentence only):**

> Rust goes where code is hot, long-running or must be exact. Python stays where code must be flexible, or where what Plexus calls is Python-only: usd-core (Pixar ships no official Rust bindings, §13.2) and the LLM SDKs. …

**Why:** "already written" meant Comfy-Cozy's code. The reason Python stays is now on Plexus's own terms. PyTorch is not a reason under v5.3: torch and the custom nodes run in a separate ComfyUI worker behind the organ, never in Plexus's process.

---

## B14 · §13.3, line 270

**Now:**

> **One host process, one extension module.** Python stays the host, because Comfy-Cozy's stage code, organs, LLM providers and surfaces all run unchanged that way. Rust ships as one extension module, `plexus._core`, built with maturin. One process also keeps "one conductor per stage root" simple.

**Proposed:**

> **One host process, one extension module.** Python stays the host, because usd-core, the composer of record, is Pixar's Python build (§13.2), and the LLM SDKs are Python. Rust ships as one extension module, `plexus._core`, built with maturin. One process also keeps "one conductor per stage root" simple.

**Why:** the old reason was running Comfy-Cozy's code unchanged, which no longer applies. The conclusion holds for a different reason.

---

## B15 · §13.3 diagram, lines 280–281 (the change is on 281)

**Now:**

```
plexus/          Python: contract adapters, the usd-core composer, projection,
                 organs, surfaces (from Cozy)
```

**Proposed:**

```
plexus/          Python: contract adapters, the usd-core composer, projection,
                 organs, surfaces (all written new)
```

**Why:** same as B5.

---

## B16 · §14.2, line 342

**Now:**

> - **Thin glue and imports (Spec §1, Blueprint §6).** The package reused Cozy, Synapse and Moneta by importing them, and called a copied file a defect. Now Plexus is cloned from Comfy-Cozy, so that code is Plexus's own. SYNAPSE is a reference only, with nothing imported. Moneta, SALUS and Hanish are optional, behind Plexus-written adapters.

**Proposed:**

> - **Thin glue and imports (Spec §1, Blueprint §6).** The package reused Cozy, Synapse and Moneta by importing them, and called a copied file a defect. v5.4 keeps the second half and drops the first: Plexus neither imports nor copies Comfy-Cozy or SYNAPSE, and both are architecture references only. Moneta, SALUS and Hanish are optional, behind Plexus-written adapters.

**Why:** the v5.3 middle sentence is the reversal. The new position is stricter than both the package and v5.3.

---

## B17 · §14.2, line 343

**Now:**

> - **LLM access through Cozy's provider abstraction "imported, not copied" (Spec §1).** The six providers come with the clone and are Plexus's own.

**Proposed:**

> - **LLM access through Cozy's provider abstraction "imported, not copied" (Spec §1).** Neither. Plexus writes its own LLM providers in `plexus/` (the Wake and Reason tiers), with Comfy-Cozy's six-provider design as the reference. Whether providers sit behind an L1 contract is open.

**Why:** "come with the clone" no longer holds. v5.3 names exactly four contracts (§0 item 2, §4), so a provider contract would be a fifth, and that is Joe's decision, not a wording fix.

---

## B18 · §14.2, line 345

**Now:**

> - **License compatibility (D6).** "PLEXUS imports all three" no longer holds. Comfy-Cozy's MIT code comes with its license notice kept. SYNAPSE contributes no code. What's left of D6 is whether a Moneta adapter can ship publicly, and that stays a Phase 5 gate.

**Proposed:**

> - **License compatibility (D6).** "PLEXUS imports all three" no longer holds. Comfy-Cozy is Joe's own MIT code (the same copyright holder, `LICENSE` line 3 in both repos), so D6 has nothing to clear there: not for `plexus/` and `crates/`, which carry none of it, not for the seeded `agent/` and `cognitive/`, and not for the history a public repo would carry. SYNAPSE contributes no code. What's left of D6 is whether a Moneta adapter can ship publicly, and that stays a Phase 5 gate.

**Why:** "Plexus ships no Comfy-Cozy code" is not yet true — the root `pyproject.toml` still builds the comfy-cozy wheel from `agent/` and `cognitive/`, and git history carries that code into any public repo. The conclusion holds for a different reason, the shared copyright holder. **This is a legal reading for Joe to confirm**, not a settled fact.

---

## B19 · §14.2, a new bullet: Spec lines that assumed Comfy-Cozy code

**Now:** nothing. Spec v2.1 still says, in three places, that Plexus uses Comfy-Cozy code:

- §2, line 31: `cozy.py        # ComfyUI organ via Comfy-Cozy MCP (§8.2)`
- §6 step 4, line 131: "every tool in the action passes the Cozy default-deny classifier (imported)"
- §8.2, lines 163–170: the organ protocol mapped onto Comfy-Cozy surfaces (`inspect`, the validated execute path, run reports, `workflow.lock`)

**Proposed** (append to §14.2):

> - **Spec lines that assumed Comfy-Cozy code (v5.4).** Spec §2's "ComfyUI organ via Comfy-Cozy MCP", §6 step 4's "Cozy default-deny classifier (imported)" and §8.2's mapping onto Comfy-Cozy surfaces now read as references. The organ talks to ComfyUI's own HTTP API, as T7's fake server already expects. The risk gate is a Plexus-owned default-deny tool classifier (unclassified → `Blocked`, F9), landing with Phase 3 Safety (§11); where it sits relative to the §4 Safety contract, whose `check` takes no tool, is open. §8.2's table still says what the new organ must provide, and Comfy-Cozy's versions of those pieces are the reference.

**Why:** §14 is where the Blueprint overrides the Spec, so the Spec itself stays untouched. The frozen tests need no change.

---

## B20 · `docs/plexus/PLEXUS_MEMORY_OPTIONS.md`, line 18

This is outside the Blueprint, but it is the one `docs/plexus/` design note no other change reaches.

**Now (the parts that change):**

> Comfy-Cozy, which Plexus is seeded from, already has two memories of its own: the session memory in `agent/memory/session.py`, and the experience accumulator in `cognitive/experience/` … Under every option below, the accumulator becomes a client of the Memory contract instead of keeping a private store.

**Proposed:**

> Comfy-Cozy, the predecessor, had two memories: the session memory (`agent/memory/session.py`) and the experience accumulator (`cognitive/experience/`), which starts biasing toward what worked after about 30 runs. Both are references only. Whatever Plexus needs from them is rebuilt against the Memory contract, and neither is carried over.

**Why:** "becomes a client of the Memory contract" means carrying the accumulator forward.

---

## B21 · §14.2, line 348 (Python ≥ 3.11)

**Now:**

> - **Python ≥ 3.11 (Spec §1).** That stands for Plexus. The seed still says 3.10 because Comfy-Cozy did, and its CI tests 3.10. Both move to 3.11 when `plexus/` lands.

**Proposed:**

> - **Python ≥ 3.11 (Spec §1).** That stands for Plexus. The root `pyproject.toml` is still Comfy-Cozy's (3.10), and its CI tests 3.10 to 3.13. Plexus's own package requires ≥ 3.11 when `plexus/` lands; what happens to the seed's packaging and CI is Joe's call.

**Why:** "Both move" assumed the seed's packaging is maintained as Plexus's, which is now undecided.

---

## B22 · The scheduler stays in Python until a measurement moves it (accepted by Joe, Nov 1)

The refinement round (`NEXTGEN_SCAFFOLD_PLAN.md` §2, `rust.threading`) keeps every scheduler thread in Python through M8: the dispatcher, the debounce, action threads and organ deadlines. Rust holds the pure parts (predicates, budgets) and is called synchronously. Seven v5.3 places say otherwise.

| Line | Now | Proposed |
|---|---|---|
| 81 (§2 diagram) | `L2  Nervous system  scheduler · predicates · budgets · tools      Rust (plexus-core)` | `L2  Nervous system  scheduler · predicates · budgets · tools      Rust (plexus-core); scheduler in Python until measured` |
| 132 (§5.1, last sentence) | The scheduler runs on tokio, and wake events cross into Python only when a neuron actually wakes. | **[v5.4]** Until a measurement says otherwise, the scheduler's threads stay in Python and call the Rust predicate engine and budgets synchronously; tokio is revisited when organ-queue measurements exist. |
| 164 (§6, last sentence) | In the Rust scheduler, the halt is one cancellation signal that every task listens on. | In the scheduler, the halt is one cancellation signal that every action and organ job listens on. |
| 183 (§8) | **[v5 · Rust]** In the scheduler that is a tokio task with a deadline. | **[v5 · Rust]** In the scheduler that is a task with a deadline: a Python thread for now, a tokio task once the scheduler moves to Rust. |
| 219 (§11 Phase 1) | **[v5 · Rust]** The predicate engine and scheduler are Rust from here on, fed batched stage diffs once per heartbeat. | **[v5 · Rust]** The predicate engine and budgets are Rust from here on, fed batched stage diffs once per heartbeat; the scheduler joins them when a measurement shows it on the hot path. |
| 275 (§13.3 diagram) | `provenance hash chain (F4) · predicate engine · scheduler (tokio)` | `provenance hash chain (F4) · predicate engine · budgets · scheduler (tokio, later)` |
| 287 (§13.3) | …hands it to the Rust predicate engine, which evaluates every neuron's predicate outside the interpreter lock. … Organ jobs run as tokio tasks with deadlines. | …hands it to the Rust predicate engine, which evaluates every neuron's predicate in microseconds on the dispatcher thread. … Organ jobs run with deadlines: Python threads for now, tokio tasks once the scheduler moves. |

**Why:** "outside the interpreter lock" and "tokio" describe a scheduler Plexus hasn't measured a need for. Phase 1's Rust calls are microseconds; a tokio runtime and PyO3 threading under the GIL are cost a CPU-bound worker would pay first. The §5.1 sentence about avoiding the GIL "in the hot path" stays true as the reason to move it, once a measurement shows the hot path.

---

## B23 · Phase 0's Rust pieces move later (accepted by Joe, Nov 1)

**Now (line 218, second sentence; B11 changes the first):**

> **[v5 · Rust]** It also stands up the Cargo workspace, the `Outcome` envelope, the identity registry and the intent ledger in `plexus-core`, built into Python with maturin.

**Proposed:**

> **[v5 · Rust]** It also stands up the Cargo workspace in `plexus-core`, built into Python with maturin. **[v5.4]** The `Outcome` envelope lands in its own mission (M2b), intent hashing at M3 and the intent lookup at M6. The writer identity registry lives in Python in Phase 1 (the exchange's participant list and the publication allowlist) until a mission needs it in Rust.

**Why:** the harness rewards only frozen tests that pass. `Outcome`, the intent ledger and a Rust identity registry earn nothing in Phase 1's tests, so they would be work the worker can't keep. Each now lands in the mission whose frozen test needs it. The §13.3 crate diagram (line 274) still lists them in `plexus-core`, which stays true: the deferral is about when, not where.

---

## Decisions this pass surfaced, for Joe

1. **A hook for the no-import rule.** `CLAUDE.md` now has the rule ("no `agent.*` or `cognitive.*` import from `plexus/` or `crates/`"), but nothing enforces it: T8 greps text only, and `guard_edit.py` blocks only SYNAPSE and the old Moneta integration. `CLAUDE.md` says a rule that matters enough to be unbreakable is also a hook. The matching check in `.claude/agents/reviewer.md` (a hard failure for any such import or copied file) goes with it.
2. **The `comfyui-agent` MCP server** in `.claude/settings.json` runs Comfy-Cozy's own server from `G:\Comfy-Cozy`. It is dev tooling, not Plexus code. Keep it (and B9 adds "dev tooling may run it; Plexus code never does"), or remove it.
3. **The D6 reading in B18** (same copyright holder, so nothing to clear) is a legal judgment. Confirm it, or keep D6 open.
4. **A fifth contract for LLM providers** (B17): leave open, or decide now.

---

## Checked, no change needed

- **How to read, lines 18–24.** "v5 draws on five references, and none of them is a template" already agrees with the decision. B2 brings the Comfy-Cozy bullet into line with it.
- **§14, line 320.** "sibling projects as references only" already agrees.

## Not in this draft

- **The next-generation-ComfyUI goal** (a local, ground-up successor to ComfyUI on OpenUSD, with Rust where it pays). That is a thesis-level change, and it comes with the scaffold plan in `docs/plexus/NEXTGEN_SCAFFOLD_PLAN.md`, still being written from the research reports.
- **Whether the seeded `agent/` and `cognitive/` stay.** B10 and B18 leave it as Joe's call.
