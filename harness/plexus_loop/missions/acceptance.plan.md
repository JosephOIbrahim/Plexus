# Mission `acceptance` — plan

Status: **draft for Joe. Nothing below has run.** Written Nov 1, 2026 on `mission/acceptance` (branched from `harness/plexus-loop` @ `e0792b6`).

Done means every test under `tests/acceptance/phase1` passes. The harness metric is `pytest_failures` on that path; direction lower; `min_delta = 1`.

---

## 1 · Setup facts

### Frozen tests in the target

- **Functions:** 9 `def test_` in 7 files. **Collected items:** 11, because T2's first test is parametrized three ways.
- **Baseline (measured on this branch):** 11 bad (1 failed, 10 errors). The 10 errors are the `slice_` fixture failing on `import plexus`.
- **Where CONTRACT.md's "18" comes from:** 11 phase1 items + 6 phase2 items + 1 pending T1b.

| Spec ID | File | Items | What it needs from `plexus/` |
|---|---|---|---|
| T0 · §3 schema gate | `test_t0_schema_gate.py` | 1 | `plexus.schema.plugin_dir()`, `plugInfo.json`, `generatedSchema.usda` for four codeless API schemas |
| T1 · propagation | `test_t1_propagation.py` | 1 | fixture (`exchange`, `stagekit`) + `PlexusAxon`; p95 < 250 ms over 50 trials |
| T2 · predicate precision | `test_t2_predicate_precision.py` | 4 | `NeuronRuntime`, `delta()` with cache updated only on wake; `PredicateError` at registration for `OR` and out-of-scope paths |
| T3 · budget | `test_t3_budget.py` | 1 | sliding-window budget, 3 consecutive trips → `muted` + `plexus:flag*`, written in the edit layer |
| T4 · provenance | `test_t4_provenance.py` | 1 | `ctx.author` stamps `plexus:sourceLayer`; the opinion comes only from the edit layer |
| T5 · gate | `test_t5_gate.py` | 2 | §7.3 path allowlist; drop + flag outside, land inside |
| T6 · truth | `test_t6_truth.py` | 1 | every opinion saved as it lands; two killed processes, reopen → identical dump |

**Brief Q1 (schema rows), settled.** `test_t0_schema_gate.py:35-38` asserts `plexus:envFingerprint` (string), `plexus:organVersion` (string), `plexus:retryOf` (string) and `plexus:retryReason` (token, `none|quality|transient|operator`). No test needs adding.

**No frozen test looks wrong.** I read all seven files against Spec §3–§7. T3's trip count, T2's accumulate-until-wake and T6's reload-then-dump are self-consistent. One consequence to note: T6 calls `Reload()` on the edit layer before dumping, so anything not saved is lost. "Save as it lands" is load-bearing, not a nicety.

### Environment (`/doctor`)

| Check | Result |
|---|---|
| usd-core | **(0, 26, 5)** ✓, in system Python 3.14.2 at `C:\Python314`. The repo has no venv. |
| Rust | rustc / cargo 1.99.1 stable ✓ |
| maturin | 1.12.6 ✓ (`develop --skip-install` available) |
| Ollama server | 0.40.13, answering `ollama ps`, nothing loaded ✓ |
| **`qwen3-coder:30b`** | **✗ not pulled.** `hrt-coder:latest` is a qwen3.8 27B dense build, not a substitute. |
| Houdini | running → every attempt runs on the CPU |
| harness `check` | `ready`. It does not check that the model exists, so `run` would fail every attempt with `ollama call failed` and stop after 8. |

**Install that needs Joe** (system-wide, outside the repo): `ollama pull qwen3-coder:30b` (about 19 GB).

**Hook note.** `.claude/hooks/guard_bash.py` rule 2 first blocked the mission's own `unit` gate command (`--ignore=tests/acceptance`) and a read-only `-p no:cacheprovider` run. The hook was revised mid-session to allow ignoring the whole directory, and I did not route around it before that. One false positive remains: a command that mentions `tests/acceptance` and also contains `; echo` trips the `echo` writer pattern. The harness runs gates as subprocesses, so `run` is unaffected either way.

### Gate timings (measured on this branch, CPU, Houdini open)

| Gate | Result | Wall time |
|---|---|---|
| `unit` as written (whole comfy-cozy suite) | 5,158 passed, 2 skipped, 46 deselected | **9 min 29 s** |
| `unit` narrowed (§6 proposal) | 38 passed | **49 s** |

### `check` output (pasted)

```
mission acceptance: worker ollama (qwen3-coder:30b), 1 gate(s), metric pytest_failures
Houdini: running; next attempt runs on the cpu
ready
```

---

## 2 · comfy-cozy map

| Module | Verdict | Evidence |
|---|---|---|
| `agent/gate/risk_levels.py` | not-needed-this-mission | Five levels READ_ONLY…DESTRUCTIVE (`:20-25`); unknown → REVERSIBLE (`:252`). No path allowlist anywhere in `agent/gate/`; §7.3 is new code in `plexus/membrane/gate.py`. |
| `agent/engine/_base.py` | not-needed-this-mission | `IAIEngine` (`:41`) is the ComfyUI execution ABC. Phase 2. |
| `agent/diagnosis` env fingerprint | not-needed-this-mission | Exists (`agent/cli.py:429`, `agent/tools/diagnose_tool.py:14-16`). Phase 2. |
| `agent/integrations/moneta.py` | not-needed-this-mission | **Brief fact corrected:** it *is* imported, by `agent/integrations/__init__.py:8`, `tests/integration/test_moneta_e2e.py:24` and `tests/test_cozy_persistence.py:585,617,649`. Nothing in `plexus/` or `crates/` will import it. |
| `agent/stage/cognitive_stage.py` | not-needed as a module; **copy the shape** into `plexus/core/axon.py` | Brief facts hold: `write()` emits `StageEvent` after the mutation (`:389-393`), and nothing registers `Tf.Notice`/`ObjectsChanged` in `agent/`, `cognitive/` or `tests/`. Shape to re-express: bounded queue + `put_nowait` (`_emit`, `:292-311`), one daemon dispatcher thread with a sentinel, subscribers snapshotted under a lock, each callback in try/except (`_dispatch_loop`, `:267-290`), shutdown via sentinel + join (`close_subscribers`, `:233-252`). **It has no debounce or coalescing**; that part is new. Its `StageEvent` fields differ from CONTRACT's. |
| `cognitive/core/delta.py` | not-needed-this-mission | Stdlib-only dataclass with no `pxr`, no sublayers and no edit targets. Its docstring holds the T8 term `class_type` (`:48-50`). |
| Sublayer / `def`-ancestor / `Save` helpers | none reusable | No helper defines ancestors as `def`. There are no `.Save(` calls in `agent/` or `cognitive/`. T6's save-on-land is new code. |
| Import rule | **never import `agent.*` or `cognitive.*` from `plexus/`** | `import agent.stage` pulls `anchors.py:22-31` (CheckpointLoaderSimple, LoraLoader, EmptyLatentImage) and `dag/compute_model_reqs.py:72` (KSampler). T8 greps text only, so it would pass while engine code became reachable. The worker brief states this rule. |

**Brief Q5 (worker reach), settled.** No step below touches `agent/` or `cognitive/`. Phase1 tests import nothing from them. No `focus` change is needed.

---

## 3 · Harness findings that block a useful run

These are problems in how the harness feeds the worker, found while reading `loop.py`, `workers.py` and `profile.py`. Each fix is scaffolding (Claude's, in `harness/**` or the mission file), shown to Joe before `run`.

1. **The worker would never see its own code or the tests.** `build_prompt` puts `context` files first, then focus files, under `context_chars = 60000`. Today's `context` (CONTRACT 5,951 + SPEC 16,873 + Blueprint 35,593 chars) is 58,417 chars. Once `plexus/` has any code, every focus file is left out, and no test file is ever in the prompt. → mission-file diff §6.
2. **Ollama will probably truncate the prompt from the front.** The payload sets no `num_ctx`, and `OLLAMA_CONTEXT_LENGTH` is unset. A ~15k-token prompt past the server default drops the head, which is where the Mission and Rules sections sit. → scaffolding commit C4.
3. **The worker never sees this plan.** Only the toml `goal` reaches it. → a short worker brief in `context` (§6).
4. **Nothing builds `plexus._core` inside an attempt's worktree,** and `target/` plus the built `.pyd` are not gitignored, so `commit_all`'s `git add -A` would commit build output. → C1, C3.

---

## 4 · Decision point: the notice path (`PlexusAxon` and below)

Fixed by CONTRACT: `PlexusAxon(stage, debounce_s)`, callbacks on the dispatcher thread, never inside the notice callback. Predicate eval reads composed values, and only `pxr` can read a `pxr` stage, so Rust cannot evaluate a predicate alone. Whatever crosses PyO3 is plain data.

### Option A — Rust owns the pure logic, Python owns threads and `pxr` (recommended)

- **Python** (`plexus/core/axon.py`): `Tf.Notice.Register(Usd.Notice.ObjectsChanged, cb, stage)`. The callback packs `(paths, resynced, t)` and enqueues. One dispatcher thread drains the queue and coalesces within `debounce_s`. Action worker threads, `wait_idle`, authoring and the gate stay in Python too.
- **Rust** (`plexus._core`): `compile(predicate, scope) -> Predicate` (grammar v0, scope check, raises `PredicateError`); `Predicate.paths()`; `Predicate.eval(changed: list[str], values: dict[str, float | str | None]) -> bool`; `Predicate.commit_wake(values)` for the delta cache; `Budget(wakes, window).admit(now) -> "wake" | "trip" | "mute"` with the consecutive-trip counter.
- **Clock:** Python passes `now` in. Rust owns no clock, so T3's `FakeClock` works.
- **Exception identity:** `plexus.core.predicate` re-exports `plexus._core.PredicateError`, so `pytest.raises` matches.
- **Cost:** first Rust attempt is the riskiest step. Every attempt compiles; a shared `CARGO_TARGET_DIR` keeps that warm.
- **Fits:** v5.3 "predicates compile in Rust"; §13.3's "Python batches notices into a plain-data diff for the Rust predicate engine."

### Option B — all Python for phase1, Rust in the next mission behind the same surface

- Same Python shape. `predicate.py` and the budget live in Python, as the Nov 1 prototype did in ~350 lines.
- **For:** fewest worker failure modes, no build gate, fastest to green.
- **Against:** contradicts v5.3 for the length of this mission and leaves a port as known debt.

**The honest counterweight to A.** `min_delta = 1` means S3 under Option A must land the grammar parser, the scope check, the PyO3 exception type, the `predicate.py` re-export and `NeuronRuntime.__init__/register` in **one applied diff** that compiles and passes a test, or the whole attempt is dropped. Under Option B, S3 is about 60 lines of Python.

### Rejected — Rust owns the dispatcher and debounce (tokio), calling back into Python

Callbacks must run Python on a thread holding the GIL. `wait_idle` would span both languages. That is PyO3 threading under the GIL, debugged by a CPU-bound 30B worker. It is not the smallest split that passes T1 and T2.

**Assumption written down:** the steps in §5 assume Option A. Under Option B, S3 and S7 lose their Rust parts and C2/C3 shrink to nothing.

---

## 5 · Ordered changes (one worker attempt each)

The metric only rewards whole tests. All slice tests share one fixture, so making the fixture work earns nothing by itself; the first slice attempt must also pass T1.

| Step | Aimed at | Gain | Paths |
|---|---|---|---|
| S1 | T0 | 11 → 10 | `plexus/schema/__init__.py` (`plugin_dir`), `plexus/schema/plugInfo.json`, `plexus/schema/generatedSchema.usda` (hand-authored codeless; `usdGenSchema` isn't in the usd-core wheel) |
| S2 | T1 | → 9 | `plexus/membrane/exchange.py`, `plexus/core/stagekit.py`, `plexus/core/axon.py` (pure Python) |
| S3 | T2 `bad_predicates` | → 8 | Rust grammar-v0 parser + scope check + `PredicateError` in `crates/plexus-core`; `plexus/core/predicate.py`; `plexus/core/neuron.py` with `NeuronRuntime.__init__` and `register` |
| S4 | T5 `inside` | → 7 | runtime `start/stop/wait_idle`; dispatcher → scope filter → `changed()` → action thread; `ctx.author` with `def` ancestors, gate and save; `plexus/membrane/gate.py` |
| S5 | T2 ×3, T4 | → 3 | `delta()` eval + wake-only cache in Rust; `plexus:sourceLayer` stamp; quiesce to `dormant` |
| S6 | T5 `outside` | → 2 | drop + `plexus:flag…` on the neuron prim |
| S7 | T3 | → 1 | Rust `Budget`; mute written to the edit layer and flagged |
| S8 | T6 | → 0 | save-on-author everywhere, `plexus:lastWake` (may already pass after S4–S5) |

Every step keeps T8's rule now, so phase 2 starts clean: no engine terms in `plexus/` outside `plexus/organs/cozy*`, or in `crates/`.

---

## 6 · Proposed mission-file diff (not applied)

```diff
 [mission]
-context = ["tests/acceptance/CONTRACT.md", "PLEXUS_SPEC.md", "docs/plexus/PLEXUS_BLUEPRINT_v5.md"]
+context = [
+  "harness/plexus_loop/missions/acceptance.worker.md",   # short brief: §4 split + §5 steps, ~4k chars
+  "tests/acceptance/CONTRACT.md",
+  "tests/acceptance/_support.py",
+  "tests/acceptance/conftest.py",
+  "tests/acceptance/phase1/test_t0_schema_gate.py",
+  "tests/acceptance/phase1/test_t1_propagation.py",
+  "tests/acceptance/phase1/test_t2_predicate_precision.py",
+  "tests/acceptance/phase1/test_t3_budget.py",
+  "tests/acceptance/phase1/test_t4_provenance.py",
+  "tests/acceptance/phase1/test_t5_gate.py",
+  "tests/acceptance/phase1/test_t6_truth.py",
+  "PLEXUS_SPEC.md",
+]
+# ~49k chars of context; the rest of the budget is for plexus/ and crates/ files.

 [worker]
-context_chars = 60000
+context_chars = 100000
+num_ctx = 40960
```

**Gates, as a full replacement of the `[[gates]]` block** (TOML order is run order; `core` goes first so a broken build fails before anything slower runs):

```toml
[[gates]]
name = "core"
cmd = ["python", "harness/plexus_loop/build_core.py"]
timeout_s = 1800

[[gates]]
name = "cargo"
cmd = ["cargo", "test", "--workspace", "--quiet"]
timeout_s = 1800

[[gates]]
name = "unit"
cmd = [ ...as decided below... ]
timeout_s = 3600
```

The Blueprint leaves `context` because §4 here and the worker brief carry what the worker needs from it. The worker brief also carries two things the worker would otherwise learn by failing: the exact codeless-schema file shape for S1 (`plugInfo.json` `Types` entries with `schemaKind: "singleApplyAPI"`, `bases: ["/TfType"]`, `alias.UsdSchemaBase`, `autoGenerated: false`; attributes as `custom` specs with `allowedTokens`), and the order rule "register the participant before opening the exchange stage", so the sublayer append doesn't fire a root resync into the axon.

**Attempt-time hypothesis, for the first run to test.** 100k characters is roughly 25–30k tokens of prompt evaluation per attempt on 8 CPU threads. That, not generation, is likely the main cost of each attempt. `worker.timeout_s = 1800` stays until the ledger measures it.

### Decision: narrowing the `unit` gate

The current gate runs 5,158 comfy-cozy tests per attempt and took **9 min 29 s**. At 40 attempts that is 6.3 hours of `unit` alone, more than the 6-hour budget. The narrowed set took **49 s**. The worker can only change `plexus/`, `crates/` and the two Cargo files, and the mapper found only two kinds of comfy-cozy test that could notice a new top-level package: repo-scanning tests and the harness's own tests.

```diff
 [[gates]]
 name = "unit"
-cmd = ["python", "-m", "pytest", "-q", "-x", "tests", "--ignore=tests/acceptance", "-m", "not integration"]
+cmd = ["python", "-m", "pytest", "-q", "-x", "-m", "not integration",
+       "tests/harness_plexus_loop", "tests/test_portability_guards.py",
+       "tests/test_workflow_patch_engine_live.py"]
```

The full suite runs once at mission end, and `/report` states its result. **Joe decides.**

---

## 7 · Scaffolding commits Claude makes before `run` (each shown to Joe)

| # | Commit | Contents |
|---|---|---|
| C1 | `gitignore: Rust build output` | `target/`, `plexus/_core*.pyd`, `plexus/_core*.so` |
| C2 | `scaffold: plexus/ package + crates/plexus-core workspace` | `plexus/__init__.py`; root `Cargo.toml` (`[workspace] members = ["crates/plexus-core"]`); `crates/plexus-core/Cargo.toml` (`cdylib` + `rlib`, `python` feature → `pyo3 = 0.30`); `src/lib.rs` with an empty `#[pymodule] fn _core` behind the feature, plus `__version__`. No behaviour; baseline stays 11. |
| C3 | `harness: build_core gate + shared cargo target` | `harness/plexus_loop/build_core.py`: `cargo build --release --features python -p plexus-core`, then copy the cdylib to `plexus/_core.pyd` (`.so` elsewhere). Honours `CARGO_BUILD_JOBS` from the CPU profile. `CARGO_TARGET_DIR` is set for **every** gate (so `cargo test` stays warm too), resolved against the main repo's git common dir as `<repo>/.plexus_loop/cargo-target`, never the worktree's cwd. One harness test for it. |
| C4 | `harness: worker num_ctx` | `WorkerSpec.num_ctx` in `mission.py`, sent in `payload()` options (`workers.py`), one test in `tests/harness_plexus_loop/test_plexus_loop.py`. |
| C5 | `mission: acceptance context, gates, worker brief` | the §6 diff (with or without the `unit` narrowing) + `acceptance.worker.md` + this plan |

**Before pushing, C2 and C3 are verified locally:** `python harness/plexus_loop/build_core.py`, `cargo test --workspace --quiet`, `python -c "import plexus._core"`, and the harness's own tests. If pyo3 0.30 doesn't build against Python 3.14, `run` would refuse at baseline, so this is checked first.

**Brief Q2 deviation, for Joe:** I propose **no `[tool.maturin]` section in `pyproject.toml` this mission.** `pyproject.toml` builds the comfy-cozy wheel with hatchling (`packages = ["agent", "cognitive"]`), and swapping its build backend for a dev loop risks the packaging gate. C3 builds `_core` with cargo and a copy. Maturin packaging can land with `plexus/` in the wheel, in its own commit. Alternative, if Joe prefers maturin now: `crates/plexus-core/pyproject.toml` with `[tool.maturin] module-name = "plexus._core"` and `maturin develop --skip-install` inside `build_core.py`.

---

## 8 · Decisions Joe needs before `go`

1. **Pull the model:** `ollama pull qwen3-coder:30b`. Required; without it every attempt fails.
2. **Notice path:** Option A (recommended) or B (§4).
3. **`unit` gate:** narrow as in §6, or keep the full suite per attempt.
4. **Mission-file diff and C1–C5:** approve as written, or edit.
5. **No maturin in `pyproject.toml` this mission** (§7).
