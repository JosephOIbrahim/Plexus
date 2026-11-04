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

## 2 · Comfy-Cozy as a reference

Re-labelled after the Nov 1 decision (Comfy-Cozy is an architecture reference only; nothing copied or imported). Verdicts are `cozy-mapper`'s: reference, rebuild in Python, rebuild in Rust, drop. Read from the seeded copy, which matches `G:\Comfy-Cozy` at v5.10.0.

| Module | Verdict | Evidence |
|---|---|---|
| `agent/gate/risk_levels.py` | reference (lesson: unknown tools default to REVERSIBLE; Plexus blocks them, F9) | Five levels READ_ONLY…DESTRUCTIVE (`:20-25`); unknown → REVERSIBLE (`:252`). No path allowlist anywhere in `agent/gate/`; §7.3 is new code in `plexus/membrane/gate.py`. |
| `agent/engine/_base.py` | reference | `IAIEngine` (`:41`) is the ComfyUI execution ABC. The Phase 2 organ is new (draft v5.4 B8). |
| `agent/diagnosis` env fingerprint | reference | Exists (`agent/cli.py:429`, `agent/tools/diagnose_tool.py:14-16`). The new organ produces its own (phase2). |
| `agent/integrations/moneta.py` | drop | **Brief fact corrected:** it *is* imported, by `agent/integrations/__init__.py:8`, `tests/integration/test_moneta_e2e.py:24` and `tests/test_cozy_persistence.py:585,617,649`. Nothing in `plexus/` or `crates/` will import it. |
| `agent/stage/cognitive_stage.py` | rebuild in Python as `plexus/core/axon.py`: **restate the idea, copy no code**; avoid its write-side emit | Brief facts hold: `write()` emits `StageEvent` after the mutation (`:389-393`), and nothing registers `Tf.Notice`/`ObjectsChanged` in `agent/`, `cognitive/` or `tests/`. Shape to re-express: bounded queue + `put_nowait` (`_emit`, `:292-311`), one daemon dispatcher thread with a sentinel, subscribers snapshotted under a lock, each callback in try/except (`_dispatch_loop`, `:267-290`), shutdown via sentinel + join (`close_subscribers`, `:233-252`). **It has no debounce or coalescing**; that part is new. Its `StageEvent` fields differ from CONTRACT's. |
| `cognitive/core/delta.py` | reference | Stdlib-only dataclass with no `pxr`, no sublayers and no edit targets. Its docstring holds the T8 term `class_type` (`:48-50`). |
| Sublayer / `def`-ancestor / `Save` helpers | no Comfy-Cozy source; written new | No helper defines ancestors as `def`. There are no `.Save(` calls in `agent/` or `cognitive/`. T6's save-on-land is new code. |
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

The Blueprint leaves `context` because §4 here and the worker brief carry what the worker needs from it. The worker brief also carries two things the worker would otherwise learn by failing: the exact codeless-schema file shape for S1 (`plugInfo.json` `Types` entries with `schemaKind: "singleApplyAPI"`, `bases: ["UsdAPISchemaBase"]` — corrected Nov 1 by the refinement round: `/TfType` was wrong, and pxr's own usdShade plugInfo uses `UsdAPISchemaBase`; `alias.UsdSchemaBase`, `autoGenerated: false`; attributes as `custom` specs with `allowedTokens`), the order rule "register the participant before opening the exchange stage", so the sublayer append doesn't fire a root resync into the axon, and in-process schema registration (`Plug.Registry().RegisterPlugins(str(plugin_dir()))` from one module every runtime entry point imports first), because T7 checks `GetAppliedSchemas()` in the pytest process, not a child. See `docs/plexus/NEXTGEN_SCAFFOLD_PLAN.md` §2.4 and §5 for the other refinement corrections (T8 `cfg` rule in Cargo.toml, peek-then-admit budget order, `field(default_factory=dict)` dataclass defaults).

**Step routing (Joe asked for Jev routing, Nov 1).** The harness now reads `[[steps]]` and `[router]` (commit C6, below). Code narrows the steps to those whose target tests still fail. Jev then picks one from the latest test output and the recent drop reasons, and the prompt gets a "This attempt: step Sx" section near the top. Any Jev failure, or a pick below `min_confidence`, falls back to the earliest eligible step. The route shapes the prompt only; gates and the metric still decide what is kept. *(Superseded Nov 3: steps now name their prerequisites in `after`, Jev chooses only among ready steps, and every fallback goes to the earliest ready step; see §10.)*

```toml
[router]
kind = "jev"            # "first" routes in code only
model = "jev-latest"
min_confidence = 0.3

[[steps]]
id = "S1"
targets = ["tests/acceptance/phase1/test_t0_schema_gate.py"]
text = "..."            # one block per row of §5, S1 to S8, with the same targets
```

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

| C6 | `harness: Jev step routing` | `router.py` (new), `[[steps]]` + `[router]` in `mission.py`, failing-test ids from the junit report in `metrics.py`, the step in the prompt and the ledger (`loop.py`), a Step column in `REVIEW.md`. 16 new tests in `tests/harness_plexus_loop/test_router.py`; all 46 harness tests pass; ruff clean. No network in tests. |

---

## 8 · Jev advisory pass (Nov 1, `jev-1.14.0`, advisory only)

Joe asked for Jev's read on the open decisions, shown before anything is applied.

| Decision | Jev's pick | Probability | Matches the plan's recommendation? |
|---|---|---|---|
| Notice path | **A** | 0.98 (B 0.02) | yes |
| `unit` gate | **narrow** | 1.00 | yes |
| Rust build in the dev loop | **cargo + copy** | 0.84 (crate pyproject + maturin 0.15) | yes |
| Release | **none** | 0.92 (v5.10.0 0.05, marker tag 0.03) | yes |
| "C1–C5 are sound and sufficient" | **no** | p(yes) 0.34 | see below |

**Why Jev said no to the scaffolding.** A follow-up asked which gaps it saw: the model not installed (0.81), no per-attempt step routing (0.79), no build check before the run (0.76), no worker brief (0.73), no cargo tests (0.54). The summary Jev was given left out that the plan already includes the build check (§7), the worker brief (§6) and the `cargo` gate (§6). The other two are now closed: the model is pulled, and C6 adds routing. So every gap it named is covered.

**Routing checked live against Jev** on three made-up mission states with the S1–S8 steps: nothing built → **S1** (0.83); S1 and S2 kept, neuron module missing → **S3** (0.98); S3 kept but the axon broken → **S2** (0.98). In all three cases Jev agreed with the code rule "earliest step whose tests fail". These cases don't yet show Jev adding anything over that rule; the first run's ledger will, because each attempt records whether Jev or the fallback routed it.

---

## 9 · Decisions Joe needs before `go`

1. ~~**Pull the model**~~ — done Nov 1 on Joe's word: `qwen3-coder:30b` (18 GB) is installed.
2. ~~**Notice path**~~ — **Option A**, decided by Joe (Nov 1). Also decided: Joe writes `tests/acceptance/guards/test_layers.py` before `run`; it joins the mission file's `[[gates]]` as `layers`, ahead of `core`. (Where the guard lives was changed for this mission by Joe on Nov 2: see §10.)
3. ~~**`unit` gate**~~ — **narrowed as in §6**, decided by Joe (Nov 1). The full suite runs once at mission end.
4. ~~**Mission-file diff and C1–C6**~~ — **approved as written** by Joe (Nov 1), with `budget.attempts = 5` for the first run and the `layers` gate first. C1–C4 landed as `6a2d0bd`, `fc2d772`, `a3ce57c`, `db7ff02`; C5 is the mission-file commit; C6 (Jev routing) is `282af78`. The pyo3 build was checked first: pyo3 0.30.1 builds in 11.7 s with `CARGO_BUILD_JOBS=4` and `plexus._core` imports on Python 3.14.2.
5. ~~**Maturin**~~ — **no maturin in `pyproject.toml` this mission**, decided by Joe (Nov 1). `core` builds with cargo and a copy.

**Go: Joe, Nov 1.** The `layers` guard is an interim file at `harness/plexus_loop/guards/test_layers.py` (frozen for the worker under `harness/**`), because Joe's decision put it before M0's run and only Joe writes under `tests/acceptance/`; Joe may move it to `tests/acceptance/guards/`.

---

## 10 · Decisions made during the mission

**The `layers` guard stays in the harness for this mission (Joe, Nov 2).** The guard stays at `harness/plexus_loop/guards/test_layers.py`, and the `layers` gate keeps pointing there (`python -m pytest -q harness/plexus_loop/guards`) until mission `acceptance` ends.

*Why.* The guard is already locked against the worker, because the mission freezes `harness/**`. What the move to `tests/acceptance/guards/` would add is Joe's ownership of the rule set. Joe's copy into that folder did not reach `E:\Plexus` on the tries made on Nov 2, and runs 4 and 5 should not wait on it, so the move happens after the mission.

*What stays ready.* The copy-in version is `docs/plexus/drafts/test_layers.py`: the same rules and code, plus `test_guard_sees_the_repo`, with a docstring written for its frozen home. It is kept until the move.

*What it costs, and the rule that covers it.* Until the move, Claude can still edit the rules that steer every attempt. So any change to the guard during this mission is its own commit, shown to Joe before the next run, as the `3ac9c54` cycle fix was. Claude does not change the guard while a run is going.

*After the mission.* Joe copies the draft into `tests/acceptance/guards/` (with an empty `__init__.py`) and commits it from his own terminal. Claude then repoints the `layers` gate to `tests/acceptance/guards`, deletes the harness copy and the draft, and updates this section.

**Run 9's S2 keep is merged, and the guard now enforces docstring-only package inits (Joe, Nov 2: option 1).** `b18ebd0` (run 9 attempt 4, T1 passes, 10 → 9) is merged into `mission/acceptance` as `ccee44c`. The reviewer's verdict was keep-with-note: one hard-ish gap and several S4 notes.

*The gap.* Both new package inits carried `__doc__ = __file__` after the docstring, which the brief has forbidden since `950b997` but nothing checked. The `layers` guard now fails any `plexus/**/__init__.py` with code after its docstring (`test_package_inits_hold_a_docstring_only`), except `plexus/schema/__init__.py`, where CONTRACT.md puts `plugin_dir()`. The draft copy in `docs/plexus/drafts/` carries the same check.

*The one edit in worker files.* Claude deleted the two `__doc__ = __file__` lines in the same commit as the check. Without that the tree fails its own guard, and the worker could not land the fix: an attempt that only deletes them gains nothing on the metric, and any other attempt drops at `layers` first. phase1 stays at 9 failing after the deletion (checked). This is the only time in the mission Claude has edited worker-written code, and it is limited to package-marker lines.

*The S4 notes.* The brief gains "What the kept S2 code still owes S4" (polling list instead of `queue.Queue`, no real 50 ms window, no pending counter or `idle()`, a lock in the notice callback, swallowed subscriber errors, `cool()` dropping queued events, the missing `def "<id>"` child, a hand-built plugin path, inner `Path` imports). S4's `files` now include `plexus/core/axon.py` and `plexus/membrane/exchange.py`, so the step prompt names them.

*Reviewer follow-up (Nov 2).* The pending-counter line now subtracts the notices drained into each window (one `-1` per window would never return to 0), stagekit.py joins S4's files, and the guard parses bytes so a BOM passes and a bad encoding is named. Parked for mission 02: the guard blocks `plexus/organs/cozy/__init__.py` re-exporting `CozyOrgan`, so that brief must say `plexus/organs/cozy.py` is a module.

**What 1.0 means, and a stop point for the Rust steps (Joe, Nov 3).** Two decisions from the release-path review (five agents over the ledger and docs, with an adversarial check).

*1.0 is Phases 0–3.* Plexus 1.0 means Blueprint v5.3 Phases 0 to 3 green on frozen tests, with every §11 gate for those phases measured against a written threshold (a phase does not go green on an unknown, `PLEXUS_BLUEPRINT_v5.md:225`). Phases 4 (triage and foresight) and 5 (simultaneity) ship as 1.x. Still open before 1.0 can be dated: who writes the frozen tests for the Phase 0 gaps and Phase 3 (`NEXTGEN_SCAFFOLD_PLAN.md:273` says Joe), B19 and D2 before any Safety test is frozen, the gate thresholds, the composer-parity ruling, ratifying the Blueprint (v5.4), and, if 1.0 is public, the licence and patent statement with counsel.

*The Rust stop point is the end of run 13.* If S3 is not kept by the end of run 13, Claude stops and Joe chooses the next route instead of another run of the same shape. The options to bring: split S3 into a compile-first step and a behaviour step; show the worker the whole `cargo` output (today only its first 1500 and last 2500 characters reach the prompt) or let it retry the compile inside one attempt; a stronger worker model; or Option B for phase 1 (all-Python behind the same surface, §4; CONTRACT.md leaves the language open). Context at the decision: S3 was 0 for 8 after run 11 (run 10's three S3 attempts and all five of run 11's). Every run 11 attempt sent all five files; four dropped at `core` on compile errors and one at `layers` (`predicate.rs` naming `crate::py`). E0255 (`PredicateError` defined twice) was in attempts 1 to 4; attempt 5 had only the two `crate::budget` errors from the S7 pieces. Run 12 starts with the S3-only `py.rs` block, five brief fixes and five known fixes matched against gate output.

**Run 13 carries "A + set" (Joe, Nov 3, after run 12).** Run 12 ended at 14:07, 0 of 5 kept, 9 failing. Attempts 1 and 3 sent only `predicate.rs`; `lib.rs` existed as a stub at the run's base, so the missing-files list never named it, nothing declared the module, and every gate passed vacuously. Attempts 2, 4 and 5 sent all five files and dropped at `core`: E0106 in all three (the brief's one-input `parse_clause` example elides its lifetime; the worker adds `scope: &str` and the elision no longer holds), E0204 and E0308 in attempt 2 (`#[derive(Copy)]` on `Value`; `if let Some(..)` on a `Result`), E0277 twice in attempt 4 (the worker's own `PredicateError` type, which pyo3 cannot convert); attempt 5 had only the two E0106. Joe chose Option A with the set, over the S3 route brief's Option B recommendation, and run 13 carries five things, each its own commit on `mission/acceptance`:

1. The prompt's same-every-attempt part first (header, rules, context files), per-attempt parts after it, `keep_alive` 15m, so Ollama's prefix cache can reuse the ~94% shared prefix (`a79f288`, from `385365f`). Run 12's prompt eval cost 709–857 s per attempt; run 13's `ollama.prompt_eval_s` says what the cache saved.
2. Jev routing over ready steps only: steps name `after` (S2←S1, S3←S2, S4←S3, S5←S4, S6←S5, S7←S5, S8←S5, S6, S7; S6 and S7 need S5 because T5-outside and T3 assert `h.wakes == 1`, which only S5 builds), `after` is closed transitively at load, a step is ready when its targets fail and every prerequisite's targets pass, Jev is asked only among two or more ready steps with each option's own failing tests and recent drops, and every fallback goes to the earliest ready step (`87bf7df`, `6a306d4`; `min_confidence` 0.5). While S3 fails it is the only ready step, so Jev is not called in run 13.
3. Four brief lines with known fixes matched against `core`'s output: E0106 (a two-`&str` parse function names its lifetime; the one-input example is gone), E0204 (`Value` derives `Debug, Clone, PartialEq` and nothing else), E0308 (`if let Ok` on a `Result`, never `if let Some`), E0277 (`predicate.rs` defines no error type; `compile` returns `Result<Predicate, String>` and `py.rs` maps it with `PredicateError::new_err`).
4. The complete-reply drop (`a2ba172`): a reply that leaves out any of its step's `files` is dropped before the gates with the names, what it sent is handed on, and the next prompt says it left those files out and nothing it sent was built. A step's `files` therefore means every file each reply must send, sent before or not. S4's five-file list stays as written; it may be tightened when S4 becomes ready.
5. `context_chars` 120000 and `num_ctx` 49152: attempt 4's rebuilt 100k prompt cut `plexus/membrane/exchange.py` and the schema files; 120k holds every run 12 prompt whole (~32k tokens at the measured ~3.7 chars per token), and 49152 leaves room for a 6k-token reply.

The Rust stop point stays at the end of run 13. Option B gets staged on its own branch (`prep/option-b`: mission file and brief only, no implementation) while run 13 runs, so a switch at the stop point costs no wait.

**The skeleton run is the bounded Option A try (Joe, Nov 3, 17:00: "1 yes · 2 GPU · 3 yes, G: · 4 yes").** The build-speed review's node-odds analyst rebuilt run 12's three five-file drafts with run 13's fixes applied by hand: two of three hit a second layer of errors no brief line covers (E0282, E0382), both drafts that compiled failed their own `#[cfg(test)]` tests (they expect a wake from a 0.0 delta, S5's semantics), and row 55 fixed would have been a hollow keep (`one-0.1-never-wakes` passes for any runtime that never wakes). Run 13 attempt 1 (row 56) confirmed the pattern: all five files sent, no E0106, E0204 or E0277, and five new errors, three from one line (`*a as i32 < *b as i32`, parsed as generics) and two from matching `Some(Value::Num(n))` on a `&Value`. Estimated odds per attempt as run 13 stands: five files 0.75 × compiles 0.35 × guard 0.9 × own tests 0.35 × metric 0.65 ≈ 5%, so about 25% per five-attempt run.

The branch carries, for Joe's yes: (1) a full-signature skeleton of `predicate.rs` in the brief, `cargo check`-clean as written, with every body `todo!()`, no logic, no `crate::`, no tests and no error type, which the worker starts from with signatures unchanged. This goes one step past the brief's approved `py.rs` block by prescribing the private parser shapes, where E0106 and E0599 lived; `todo!()` is the line, and the worker still writes every line that does anything. (2) S3's step text no longer asks for `#[cfg(test)]` tests (S5's text says "a bug T2 shows"). (3) Two brief lines with known fixes for row 56's errors (never cast with `as` to compare; match `values.get(path)` in one step). Estimated odds with (1) and (2): p(compiles) from 0 of 7 to about 1 in 2 and p(cargo | compiles) to about 1, so roughly 25–30% per attempt and 75–80% per run. Joe said yes: run 13 is stopped after attempt 3 lands (its two measurements are in: the prefix cache cut the prompt read from 718 s to 116 s, and the complete-reply check caught a one-file reply before the gates), this lands as one mission commit, and the skeleton run, run 14, is the bounded Option A try. **The Rust stop point moves to the end of run 14.**

*Joe's other three answers, same message.* (2) **Tonight is a GPU night:** Joe closes Houdini at bedtime, sets `OLLAMA_KV_CACHE_TYPE=q8_0` on the Ollama service and relaunches the app before the run starts (never mid-run; at `num_ctx` 49152 the KV cache fits the 4090 only quantised), and the night run is sized from its start: `hours` = window − 1.1, `attempts` = window × 60 / minutes per attempt (about 6 min on the GPU, estimate), `max_consecutive_failures` raised so one error class does not end the night in 50 minutes; that sizing is its own mission commit at bedtime, shown to Joe. (3) **The launcher:** Claude may write the launcher and a small driver script outside `plexus/`, and it starts `G:\COMFY\ComfyUI` (its `comfyui_launcher.bat`; `/system_stats` returns `comfy_package_versions` and `argv`), with models at `G:\COMFYUI_Database`; written during M1, exercised once S4–S5 exist. (4) **The fallback is pre-decided:** if run 14 keeps nothing, the next run starts from `prep/option-b` (rebased on the tip) with no further ask, and the GPU night runs whichever mission file is current at bedtime.

**Run 14 attempt 2 was a false keep; the loop branch moves back (Nov 3, 18:50).** `d626436` (run 14 attempt 2, 9 -> 8) was kept because `test_bad_predicates_fail_at_registration` passed, and the reviewer showed why it passed: `parse_clause` (predicate.rs:218-246 at `d626436`) handed the raw clause to `parse_path`, which requires the input to begin with `(`, so every grammar-v0 clause fell to the catch-all `Err("Invalid clause")`. The two frozen bad predicates were rejected by the same path as every valid one; probed in a throwaway crate, all five predicates the frozen tests use came back `Err`. Three more defects sat behind it: `in_scope` never split the path at its first `.`, so `/Exchange/LookState.temperature` was out of scope; the rest after `)` was never trimmed, so `> 0.2` with spaces failed; the clause kind was inferred from the literal, not the keyword. With `d626436` merged, S4 could not pass under the mission's own rules: its target registers `changed(TEMP)`, which raises, and S4's files exclude `predicate.rs`.

*The decision, made by Claude on the reviewer's verdict (do not merge) and recorded here for Joe to overrule:* `d626436` is not merged and `plexus-loop/acceptance` moves back to the mission tip before run 15, so S3 is attempted again from the skeleton with six new brief lines (keyword dispatch in `parse_clause`; clause kind from the keyword; `in_scope` splits at the first `.`; `trim_start` before the comparator and the number; propagate `parse_path`'s `Err`; empty source and a dangling `AND` are errors), S5's rule that an unseeded `delta` clause is false, and the `neuron.py` lines the reviewer listed as owed (per-neuron record; `prim_path` as `Sdf.Path`; `def` ancestors; `time.monotonic`; top-level import). The commit stays reachable as `d626436` for the record. Run 14 was stopped after attempt 3, which was on S4 and could not gain.

*A positive gate, `predicate_smoke`.* This class of false keep has no error text, so no known fix could catch it, and a rejection-only target cannot see it. `harness/plexus_loop/predicate_smoke.py` runs after `core` has built `plexus._core`: once `plexus/core/predicate.py` exists, the three predicates the frozen tests register under scope `/Exchange/LookState` must compile and name the attribute once in `paths()`, and the two bad ones must raise `PredicateError`; before S3 lands it has nothing to check and passes. The compile and raise checks are the frozen tests' own, asserted at S3 instead of at S4 and S5, where the harness can act on them; the `paths()` check (the attribute named, as a set) is the brief's Option A contract that S5's `seed` reads, the one assertion here that is the brief's and not a frozen test's. The gate runs with `-I`, as its test does, so the harness directory cannot shadow a stdlib module. Its output names the predicate, so a known fix quotes the keyword-dispatch line under it.

*The night budget (Joe, decision 2).* `attempts` 120, `hours` 11, `max_consecutive_failures` 30, sized from a 19:15 start to about 07:30 (a running attempt is never cut, so `hours` = window - 1.1; 120 covers a GPU night at about 6 min per attempt; the cap is high because no stop-on-repeat exists). Run 15 starts on the CPU; the harness checks Houdini before every attempt, so closing Houdini at bedtime moves the next attempt to the GPU by itself. `OLLAMA_KV_CACHE_TYPE=q8_0` needs an Ollama relaunch, which kills the attempt in flight (one worker error; the run continues); without it, `num_ctx` 49152 offloads partially on the 4090, still several times faster than the CPU. Reset the budget to 5 / 6 / 8 for a day run.

**S3 is kept: `9d7bb5f` (run 15 attempt 1, Nov 3 19:57, 9 -> 7). Reviewer: keep with notes, merge-ready for phase 1; merging into `mission/acceptance` is Joe's.** The `predicate_smoke` gate passed (the frozen tests' three predicates compile and name the attribute; OR is rejected at the AND loop, the out-of-scope path at `parse_path` through `in_scope`, each for its own reason), the skeleton held (every header and derive verbatim, two private helpers added, no tests, no `crate::`), `py.rs` is byte-identical to the brief's block, and `test_bad_predicates_fail_at_registration` passes with `one-0.1-never-wakes` (which passes because nothing can wake yet). Probed: seed 1.0, eval 1.1 false, 1.3 true, commit, 1.45 false, 1.0 true; unseeded false; clause kind from the keyword; whitespace tolerant; paths() once in order. What it still owes S4 is in the brief (`NeuronHandle` frozen with `wakes=0` baked in, no per-neuron record, `/Plexus` ancestors left `over`, `changed` an exact match the dispatcher must expand, the dispatcher itself, `wait_idle`, the lock, `ChangeBlock`); S5's delta pins are there too, and S5's text now lets it fix `in_scope`'s missing descendant branch. Run 15 was stopped after attempt 2 so the night's S4 attempts carry these lines; it restarts on the same night budget from the loop branch at `9d7bb5f`, with `mission/acceptance` ahead of it by the capsule and this commit until Joe merges the keep. Parked for mission 02: `AND` glued to a clause compiles; bare tokens and booleans do not parse as `attr` literals; `!=` across kinds is false.

**Run 16 attempts 1 and 2 missed S4 the same way; the brief names the dispatcher (Nov 3, 22:10).** A diagnosis agent read both replies against T5 and the fixture. The one break: `_on_event` stayed the S3 placeholder `pass`, so no action ever ran and `/Exchange/lookNeuron/Hints` never existed on stage B; the ledger shows it on its own (`Slice(..., wakes=[])`, and the fixture appends to `wakes` before `ctx.author`). A second break waited behind it: `gate.py` built the allowlist as `Sdf.Path("/Exchange/lookNeuron/**")`, which is ill-formed on 26.5, becomes the empty path, and denies every write. Why the first was missed twice: the S4 step text names "What the kept S2 code still owes S4" by title and the worker applied that list; it never named the S3 list, which the worker skipped whole. The null-prim failure matched no known fix, so the drop section quoted the traceback with nothing under it.

*Landed for run 17:* the S4 step text names the S3 list and says `neuron.py` goes whole with `_on_event`'s `pass` replaced; the allowlist is described as `Sdf.Path` prim paths checked with `HasPrefix`, `/**` being wording; the brief's S3-owes-S4 section spells out the dispatcher in order, the per-neuron record with `_run_action` and `wait_idle`, the allowlist, `ctx.author`'s order (`ChangeBlock`, `def` ancestors, the `.get or` idiom for a second wake, `Save()`), and the pending-counter rule; a known fix quotes the dispatcher bullet under `invalid null prim ... lookNeuron/Hints`. Run 16 was stopped after attempt 4 and the night run restarts as run 17 on the same budget from the loop branch at `9d7bb5f`. *Escalation rule, decided now:* if two run-17 attempts miss T5 the same way, the S3 precedent applies and the brief gets a short Python skeleton of `_on_event`, `_run_action` and `_Ctx.author` with the signatures fixed and the bodies to fill.

**Run 17 attempt 1: the dispatcher landed and one type broke it (Nov 4, 00:05).** The reply filled `_on_event` (scope filter, `values`, `eval`, `_run_action` on a thread), wrote `self._neurons[name]`, un-froze the handle, and built the allowlist as the bare `/Exchange/<participant>` prefix: everything the named S3 list asked for. It passed `list(event.paths)`, a list of `Sdf.Path`, as `changed`, and `predicate.eval` raised `TypeError: 'Path' object is not an instance of 'str' while processing 'changed'` on the axon's dispatcher thread, so the action never ran and T5 saw the same null prim as run 16. The traceback is in the metric's output tail, which the next prompt shows under "This is what it printed", but no known fix fires on it: known fixes match only the junit failure text for a metric drop, and the junit text is the assertion. Behind it, two more: `wait_idle` polled `axon.idle()` alone (a race with the action thread), and the wake count went to a dict entry rather than the handle object the tests hold. Three brief lines now say each plainly, with the TypeError text quoted.

*Harness candidate, Claude's, not landed:* let `[[known_fixes]]` also match the metric output tail when a no-gain drop's tail holds a `Traceback` from under `plexus/`: a worker-thread exception is the one failure shape the junit text cannot carry. Between runs, with a reviewer pass.

*Harness, Claude's, on `prep/run22` for the next boundary (Joe, Nov 4: wider): the failure router.* `c2d6d37` plus the wider commit asks Jev which brief line fixes each full drop's failure, whether or not a known fix matches, and the next prompt quotes the pick when it clears the floor: on its own when no known fix matched, under the known fixes as a second candidate when it is another line, and not at all when a known fix already quotes that line. Joe's first rule, a matching known fix means no call, reached Jev on 1 of S4's 9 full attempts, and on rows 67 to 69 the known fix named the wrong cause while Jev's pick was right. The calls made while building it: the options are the brief's list items plus its prose lines over 40 characters, outside fences, because the floor was judged on that set; a routed line is quoted whole up to 1,000 characters, not at a known fix's 700, because the router has no anchor to cut from; the loop asks on any drop the gates or the metric ran on that printed something, which includes a no-gain drop whose own targets pass (routed on the metric tail, unmeasured under today's code), and never on a drop that ran nothing; a known fix and a routed line count as the same line when their whole brief lines match, because a quote keeps the list marker, can start at a later sentence and clips at 700; a second candidate's lead says to apply it to your own code, not to the line the failure points at, because 19 of the 33 recorded target failures end at a frozen test, where a right line about the code does not fit (the known fix's lead and the no-known-fix lead keep their words, and so keep that weakness); a line the attempt's own prompt already quoted, as a routed line or as a known fix, is quoted again with a sentence saying it did not clear the failure, and a known fix's quote counts though it can hold only part of its line, as 9 of the 30 known fixes do; the model is pinned to the one the floor was judged on, with a 10 s deadline on the whole call.

*What the wider form changes, from stored picks only (no live call), on run 19's mission file and brief at the 0.7 floor:* 56 of the 58 full attempts have failure output, so calls go from 21 to 56, one per such drop. Of the 35 extra calls, 30 pick the line the known fix already quotes, so nothing is added; row 37's wrong pick stays below the floor (0.35 to 0.39); rows 38, 67, 68 and 69 gain a line, on all three stored calls each. Rows 38 and 67 carry the judge's label on the same text; rows 68 and 69 the second reviewer's, not blind. All four are right, and no wrong line appears. Over the 18 runs those rows came from, that is 0 to 5 extra calls a run, 1.9 on average. Three limits. On today's mission file the idle regex is anchored, so row 67 no longer matches a known fix: the first rule already asks on it, and the wider form adds nothing there. Today's brief rewords the dispatcher line, so run 19's picks on rows 63, 64, 65, 72 and 73 cannot be compared with it; only a run can say whether Jev still picks the known fix's line there. And a routed line can push a context file out in one state: S7 after a drop that passes every gate, with the reply's files handed on, a 1,400-character target message and a 4,000-character detail and metric tail. On the mission at 83d22ec, with the S7 proof tree's files handed on, that state has 309 characters of room under a known fix and 591 with none, so 60 or 10 of the 100 offered lines leave out `plexus/schema/plugInfo.json`; at row 80's 14,797 characters that file is out before any route, and 4 or 1 of the lines leave out `generatedSchema.usda` too. S7 writes neither file. Raising `context_chars` is a `[worker]` change, so it goes to Joe at a boundary.

*What to read in the next runs' ledger:* rows with `shown_before` true and `known_fix` other. If the line is one of the nine a known fix quotes only in part, count a known fix's form as shown only when it holds the whole line. If the worker repeats a failure the line names, reword only the second lead's already-shown form, which marks the guess down while the known fix above it still says apply it.

*The escalation rule, revised:* the S3 skeleton was signatures with `todo!()` bodies and Joe approved it as a rule clarification. For S4 the misses are in bodies, so a bodies-to-fill skeleton would not fix them; what would is the brief's own bullets as a copyable Python block (the `py.rs` precedent: the one measured cure of a recurring error came from exact code in view). That block is drafted in the plan's own words above and is held for Joe's yes in the morning, because it goes a step past the S3 skeleton: it is the dispatcher, written out. Until then the night runs on the three lines.

**Runs 16 to 18 never saw the S4 brief lines; the block lands with the loop branch moved (Joe, Nov 4).** A correction first. `build_prompt` reads the brief, the other context files and the known-fix anchors from the attempt's worktree, which is cut from the tip of `plexus-loop/acceptance`; only the toml comes from the main tree. From run 16 to run 18 the loop branch stayed at `9d7bb5f`, whose brief is `fb66215`'s, while `c65c169`, `2e6151e` and `8569214` put the S3-owes-S4 section, the dispatcher lines and the "`changed` is `str`" line on `mission/acceptance`. So 10 attempts (rows 64-73, about 4.7 hours) ran without them. The entries above that say the worker "ignored" or "skipped" that list, and the diagnosis of run 16, are wrong on that point; what reached the worker was the S4 step text, which is why run 17 filled in the dispatcher. The escalation to a code block was argued on that wrong reading. Joe was told, and chose to keep the block. Rule until a guard exists: never restart a run with the mission branch ahead of the loop branch on anything the worktree reads.

*What landed (one mission commit, on his word).* S4's `neuron.py` and `gate.py` as whole blocks in the brief, with a lead sentence in the wording that produced the byte-identical `py.rs`; the S4 step text pointing at them; the bullets the block now covers cut or shortened, each fact moved into the block or kept elsewhere; S5's text naming the two comments it fills; S7's text naming the axon's pending count if T3 reports "runtime did not go idle"; two known fixes for those; the carry-union harness change (after a left-out drop the next prompt carries the last full attempt's files and failure); Jev's floor 0.1 (at 0.5 it lost its first real choice, S7 at 0.36, and any ready step is now safe); `context_chars` 135000. `9d7bb5f` and `refine/2026-11-03` are merged just before it.

*The proof, on a scratch export of the merged tree.* With the worker's own axon, exchange and stagekit from run 18 attempt 3 plus the block: 7 failing to 5 in 5 of 5 runs, T5 inside and T5 outside both pass, nothing regressed, the layers guard and `predicate_smoke` pass, each mutant fails where it should (no dispatch, `changed` as paths, always allow, never allow, no flag, wakes not counted). The attack also ran 10 of 10 under pinned load with no flake. Filling S5's two comment lines gives 1 failing (T3); adding a Python stand-in for S7 and S8's writes gives 0, so the seams hold, though the stand-in is not the real Rust `Budget`. What the proof cannot show is whether the worker copies the block faithfully: only run 19 can.

*Shape.* The first draft spliced into the kept `neuron.py` and the rules attack broke it: a worker obeying its lead sentence keeps the S2 axon and goes to 15 failing, and three literal readings of the splice reach 9. So `neuron.py` is shown whole, 9,041 characters, which adds the worker's own kept S3 lines to what it copies.

*Open, for Joe.* (1) The deny flag is a bare `plexus:flag` holding `denied: <path>`, provisional, because the stage words are his; a bare name means S7 reusing it overwrites a deny flag, and changing it costs one string. (2) S8 can no longer be reached: T6 passes once S5's two lines are in, so phase 1 can read 0 failing with no `plexus:lastWake` and no quiesce-time `plexus:state`, which Spec section 6 step 7 asks for. Accept and park it, give it a frozen test, or move those writes into S5's text. (3) Grants have no way into the runtime: CONTRACT's constructor takes none and `register_participant` ignores its argument. (4) `timeout_s` 3600 leaves room for about 4,460 reply tokens on a cold CPU attempt at the slowest rate seen, against about 3,780 for a faithful reply; 4800 is the reviewer's proposal and Joe's number.

*Watch list.* When S4 keeps: stop after the attempt in flight, cut the block and "as the block shows" from the dispatcher line, move the loop branch and restart, because until then every later prompt holds `neuron.py` twice and the brief's copy goes stale once S5 keeps. On any S4 keep the reviewer runs `scratchpad/s4_block/final_check/conc_probe.py <tree> two_notices`, which must print True, pending 0: no frozen test sees a once-per-window axon until S7. On any S5 keep it runs `... delta_semantics`, which must print wakes 1, 1, 1, 2: no frozen test notices a missing `commit_wake`. The S4 report says T2's one-0.1 case still proves nothing at S4: an unseeded delta is always false.

*Parked, with reasons.* `register()` while actions run kills the interpreter (exit 3, 3 of 3); the block's docstring states the limit and the frozen tests register before `start()`. A second runtime on the same exchange raises in `register()`, because the kept lines use a bare `Sdf.AttributeSpec`. The worker's axon window closes after about 10 ms of quiet, not the spec's 50 ms; once S7 lands each extra wake is another budget charge. `stop()` returns after 5 s while a longer action keeps running. An in-process writer that takes no lock can kill the interpreter while actions author, so a demo or film script writing project A in the runtime's process must settle between writes or run in its own process.

**S4 and S5 kept on run 19's first two attempts; the block comes out (Nov 4).** Row 74 kept S4 (`0c54a10`, 7 -> 5, 177 of 177 block lines verbatim, 53.8 min); row 75 kept S5 (`3594ff7`, 5 -> 1, the two comments filled, 24.6 min), flipping `one-0.3-wakes-once`, `two-0.15-wake-once`, T4 and T6. They are the first two attempts that could see the brief lines, after S4 had gone 0 for 10 without them. With S5 kept, the brief's copy of `neuron.py` no longer matches the tip, so the block is cut and S7's text says to start from the kept file. The known fix for "runtime did not go idle" is anchored, because the adversary on the failure router showed the bare form firing on source text in a traceback (row 67). The restart merges the mission branch into the loop branch, so the worker sees this brief while Joe's merge of the keeps into the mission stays his call.

**S4's review (Nov 4): keep with notes, no hard findings.** The reviewer's export of `0c54a10` scored 5 failing on every run of the harness's own metric, quiet and with the CPU pinned. `two_notices` printed True, pending 0, 300 cycles of the idle contract showed no violation, and `neuron.py` and `gate.py` match the block byte for byte. Three S2 items were not honoured: the real 50 ms drain (medium), `cool()` revoking first, and `plugin_dir()`. Not re-run by the reviewer: `cargo` and `unit`, which the ledger shows passing, and no Rust file changed.

The window is the one decision. Five writes 20 ms apart wake five times as kept and twice with a real drain. T1's p95 holds either way against 250 ms: 14 to 15 ms and 54 to 55 ms quiet, 66 ms and 98 ms at the pinned worst. Phase 1 reads 0 failing with a real drain and Python stand-ins for S7 and S8; the real Rust budget is not in those runs. No frozen test sees the window, and S7 is the last step with a failing target, so nothing carries the fix after S7 keeps. Joe's options: a frozen burst test (the reviewer's pick and Claude's; only Joe can add it), S7's text carrying the fix (one more whole file in every S7 reply, and a restart), or parking it as an S4 miss.

Also from that review. For the S7 reviewer: on an S5-filled copy, removing the deny flag's `Save` or removing `commit_wake` leaves the score at 1 failing, so a disk read and `delta_semantics` are the only checks on those two. `test_write_inside_allowlist_lands` passes under pytest's assertion rewriting and fails under `--assert=plain`, because its prim comes from a temporary stage; the metric runs with rewriting on, and the test is Joe's. With overlapping actions `handle.state` reads dormant while another action still runs (the block's own line; no frozen test sees it). A direct `cool()` with a notice queued during a dispatch dropped it in 20 of 20 trials, and the runtime only meets that when an action outlasts `stop()`'s 5 s wait. The review scripts are in `scratchpad/s4_block/review-keep`.

**S5's review (Nov 4): keep with notes, no hard findings.** None of the four flips is false. The commit adds the two lines S5 names, and an export scored 1 failing on five of five runs, always T3 at its second wake. T2's file, T4 and T6 together were clean on 20 of 20 repeats, and 8 of 8 with the CPU pinned. T6 flipped at S5 because its child predicate needs the seed; the Save it depends on is S4's. Not re-run: `unit`, which the ledger shows passing. All S7 evidence in both reviews uses a Python budget stand-in; no real Rust `Budget` has been built.

What T6 cannot catch on this code: opinions never authored. After a full wake `plexus:state` and `plexus:lastWake` read None on the stage and on disk, so the dumps agree vacuously. It also runs no deny and no mute, kills after `wait_idle`, reopens stages without restarting a runtime, and never compares the wake count after reopening.

**Run these on any S7 keep, because no frozen test covers them.** A missing Save on the mute scores 0 and leaves neither state nor flag on disk. Dropping `commit_wake`, or moving it above the budget check, scores 0. `TREE` is the export.
- `scratchpad/s4_block/final_check/conc_probe.py TREE delta_semantics` prints wakes 1, 1, 1, 2.
- `scratchpad/s4_block/review-s5/scripts/s5_probe.py TREE delta_after_trip` ends at a count of 2.
- `scratchpad/s4_block/review-s5/scripts/s5_probe.py TREE mute_on_disk` shows `disk plexus:state muted` with a non-empty flag.

**S7's text has three gaps, staged and not landed.** A bare mute flag and the deny flag overwrite each other; `plexus:flag:budget` satisfies T3 and keeps both, so that is the provisional name (Claude's call; the stage word stays Joe's). Nothing tells S7 to set `record.handle.state = 'muted'`, and T3 fails on `'dormant' == 'muted'` without it. The last sentence says the kept axon subtracts once per window, which is false at this tip. The fix is toml only, on `prep/run21`: the step text comes after the context files in the prompt, so the cached prefix survives, the brief stays byte for byte and the loop branch does not move.

**Why it is not landed yet.** A stop file went down at 05:14 to land it after attempt 1, and came out again at 05:19. `carried` and `recent` live in `_run`, so a restart drops the handed-on files and the failure text. On a Rust step that costs more than the text gaps, which T3's assertion and the handed-on files correct by themselves. It lands at the next boundary with nothing worth carrying, such as a one-file reply, or on a repeat of the same failure. If S7 keeps first with a bare flag, the name goes to Joe with the keep.

**S8 can no longer be reached, Joe's decision.** Spec line 134 asks quiesce to update `lastWake`, the delta cache and `state = dormant`. The kept code does the delta cache, at wake time, and writes nothing else to the stage. Phase 1 forces `plexus:state == "muted"` on the stage and in the in-memory edit layer, a non-empty `plexus:flag…`, and `handle.state` in memory. It no longer forces `plexus:lastWake` authored at all, `plexus:state` as awake or dormant, any mute or flag write saved to disk, or recovery of the wake count, budget state or delta cache. A saved quiesce write scores no gain, so S8 alone could never keep. Options: accept and park it, and say so in the mission report; a frozen test that reads state, last wake, the mute and the flag from a copy of the file on disk, which is the reviewer's pick and Claude's, because only that is enforced by the metric; or move the writes into S7's text, which nothing forces a reply to include, and whose `dormant` write needs the guard `_run_action` already has or it can overwrite a mute.

**The window now has measured weight.** Five writes 20 ms apart at a budget of one wake per 10 s, three runs each, on the stand-in: the kept window gives 1 wake, handle muted, `plexus:state` muted; a real 50 ms drain gives 1 wake, handle dormant, no state written. Un-mute is operator-only (spec line 138), so one burst is a permanent mute once S7 lands. The metric reads 0 failing with either window.

**Parked from that review.** `in_scope` still rejects descendants, against its own doc comment and spec line 70; S5's text allowed the fix, the worker did not make it, and no later step lists `predicate.rs`, so brief line 369's "S5 may fix it" gets reworded at the next brief change. A delta-only clause on an attribute absent at registration never wakes; it follows the brief's rule, and the frozen slice always sets a value first. The delta cache moves at wake, before the action, not at quiesce as spec line 134 lists it: this is a deliberate departure that S5's text and Budget order both ask for, and by the reviewer's reading a raising action still uses up its delta. The anchored known fix for "runtime did not go idle" still quotes the axon's pending-counter line, and `axon.py` is not in S7's file list, so an idle failure from another cause could mislead; it gets changed if it ever fires. The review scripts are in `scratchpad/s4_block/review-s5`.

**Row 77, and S7's text lands for run 21 (Nov 4).** Run 20's attempt 1 sent all four step files and then a diff for `plexus/core/axon.py`, with no-op hunks and a duplicate `_on_notice`. It failed to apply, so nothing was built and nothing was handed on (48.8 min, `prompt_eval_s` 1134.5, reply 4,184 tokens). The only mention of that file in the step section was the sentence the S5 reviewer called false. The diff was not the only fault. The reply's `lib.rs` and `py.rs` are right, but its `peek` always says wake and its `admit` stores a timestamp on a trip. Its `neuron.py` calls `peek` on `record.compiled`, never creates a budget, adds a required `_Record` field the call does not pass, writes no mute, and starts the thread on a trip.

So S7's text now spells out `peek`, `admit`, where the budgets live and the check in `_on_event`, in prose, and the worker still writes every file. This is closer to implementation than most step text; S5's named its two lines the same way. Joe has been told, and can have it pulled back. A throwaway worktree filled from that text (Claude's scratch, never lands; `lib.rs` and `py.rs` from row 77's reply) proves it with a real Rust budget for the first time: the Rust test passes, the guards pass, `predicate_smoke` passes, the metric reads 0 of 11 on 3 of 3 runs, and the three probes print wakes 1, 1, 1, 2, a count of 2, and state and flag on disk.

Attempt 2 had started on the old text with nothing carried, so Claude ended the harness about 2.5 minutes into it instead of spending about 35 minutes. Ollama cancelled the request and kept the cached prefix. It leaves no ledger row, the harness's stale-lock check handles the lock, and its worktree was removed. This overrides "why it is not landed yet" above: row 77 was the boundary with nothing to carry.

Parked for the harness: a diff that fails to apply drops the reply's whole-file blocks with it and hands nothing on, which is how a reply with all four step files carried nothing forward.

**Joe's answers (Nov 4).** Merge yes: S4 and S5 go into the mission at the next boundary, by merging `f26b39d`, which holds both and no later keep, so an S7 keep stays out until it is reviewed and he says so. Tests yes: Claude drafts a burst test and a disk test in `scratchpad/frozen_drafts`, proves them against kept, fixed and mutated scratch trees, and Joe places them after S7 keeps; the mission then re-aims S8 at the disk test and adds a step for the window, and the loop branch takes the merge so the metric can see them. Router wider: `c2d6d37` lands at the next boundary with the wider form, on `prep/run22`: Jev is asked on every full drop with failure output, a known fix still prints first, and a routed line is added when it clears the floor and differs from what the known fixes quote.

**Stage words, on Joe's word (Nov 4).** `plexus:flag:publicationGate` holds a dropped write and `plexus:flag:budgetGate` holds the mute. `plexus:lastWake` is wall-clock ISO 8601, `datetime.now().astimezone().isoformat(timespec="seconds")`. The mute's release text is "Restart the neuron runtime to unmute it." The rename lands in S8's step text after the disk test goes in, so until then S7's text keeps the provisional `plexus:flag:budget` and the kept deny flag stays bare. The sentences, from the swarm's plan:
- Dropped write: `f"Write dropped at the membrane: {target} is outside {participant_id}'s allowlist, so nothing landed. {participant_id} writes only under {allowed}."`
- Mute: `f"Neuron muted: 3 wakes in a row refused (budget {budget_wakes} per {budget_window:g} s). Restart the neuron runtime to unmute it."`

That release text is not true as built, and S8's text has to carry the fix. The swarm called it true because `register()` would write dormant and start a fresh budget. The kept `register()` writes no state, and both reviews reproduced a second runtime raising there on the specs it finds already in the layer. So S8's text also makes `register()` reuse existing specs and write dormant, or the flag promises an unmute that raises. Joe has been told.

**Rows 78 and 79: the same E0596, so S7's text says how `peek` counts (Nov 4).** Both replies sent all four files with no diff, and `neuron.py` follows the text: budgets on the record and the runtime, the handle state, the saving helper, the suffixed flag, the check above `commit_wake`. Both failed at `core` on one error, `peek` calling `pop_front` through `&self`; row 79 repeated it with the compile error in its prompt, and neither took rustc's hint of `&mut self`, which would have broken `py.rs`. A gate-failed drop hands nothing on, so a restart cost only the failure text the new line replaces, and attempt 3 had run about a minute on the old text. Claude ended the harness there, merged `f26b39d` into the mission on Joe's word, and restarted as run 22 with the line in the step text. The brief is unchanged, so the prefix stays cached. The failure router is not in this boundary: its workflow has not finished, so it lands at the one after.

**Rows 80 to 82: E0596 cleared, then a stuck loop, so run 23 starts fresh (Nov 4).** Row 80 was one line from a keep: its only fault was its own Rust test asserting `peek` says mute at t = 6. On a throwaway tree with that line removed, the reply scored 0 of 11 on 2 of 2 runs and passed all three probes, the first time the worker's own Rust budget has passed T3. Row 81 fixed the test and lost the mute branch: every gate passed, and T3 failed on `'dormant' == 'muted'`. Row 82 had those four files handed on and T3's failure in its prompt, and its reply is byte-identical to row 81's, so handing on files anchored the worker to the code without the mute. A fifth prompt that close would most likely repeat it, so Claude ended the harness about 1.5 minutes into attempt 4, and this one restart did give up handed-on files, deliberately. The text now pins the test assert and says the mute branch must be there, and a fresh prompt close to row 80's is the best odds. The brief is unchanged. The failure router's workflow is still in repair, so it lands at the next boundary. Row 82 also read its prompt cold (`prompt_eval_s` 1,018.3 for 35,308 tokens against 170.6 on row 81), and its reply ran at 1.54 tokens per second against about 2.2; the workflows' test loops were running beside it.

**Row 83: one wrong test line again, so S7 stops writing its own tests (Nov 4).** Run 23's first reply had the mute branch and a correct budget, and failed `cargo` on the same assert as row 80, `peek` says mute at t = 6, with text in its prompt telling it not to. With that line removed on a throwaway tree it scored 0 of 11 on 2 of 2 runs and passed all three probes. The worker's own test is the only thing between that code and a keep, and a repair prompt lost the mute branch the last time (row 81). So S7's text now asks for no tests, as S3's does: frozen T3 checks the sequence, and the probes check what T3 cannot. All four fresh replies since the text spelled out the budget (rows 78, 79, 80, 83) had the mute branch. Claude ended the harness about 2 minutes into attempt 2 and restarted as run 24; `cargo test` then runs no budget test, and the S7 reviewer reads `budget.rs` by hand. The failure router's workflow is still in repair.

**S7 kept on row 84, and it should not merge as it stands (Nov 4).** Run 24's first reply kept: 1 -> 0, `81843dc`, with no Rust test of its own. An export reads 0 of 11 failing on 3 of 3 runs, and `delta_semantics`, `delta_after_trip` and `mute_on_disk` all print what they must. But the reply sent `neuron.py` as a diff, against the text, and put the budget check in its own lock block above the predicate, leaving the comment naming S7 in place. Spec line 125 and the brief's Budget order put the predicate first. So every event in scope is charged: at a budget of one wake per 10 s, four changes the predicate rejects mute the neuron with 0 wakes, and the next real change gets nothing, where a tree built from S7's text wakes once (`scratchpad/s7_proof/budget_order_probe.py`). The global budget is charged the same way. T3 misses it because every change in T3 qualifies. Claude's recommendation: leave the keep unmerged on the loop branch, add a frozen function that a rejected change spends no budget, and fix it as a step the metric can score. Discarding the keep and re-running S7 would pin nothing. Reverting is not Claude's call.

**The failure router landed (Nov 4).** `50a6cbb` and `6be4a17` on the mission, the cherry-pick of `c2d6d37` and the wider form. Harness suite 370 passed, guards 9, ruff clean, `check` ready; both reviewers said land with notes. Rehearsals show first prompts byte-identical, so the prefix is safe.

**The Jev decision gate, measured (Nov 4).** Plain rules beat it. On Joe's last 26 approvals it removes none, with 0 false acts because nothing acted; across all 66 the same repaired code gives the same verdict with or without Jev. It stays unmerged at `0cf9120` on `harness/jev-decisions`. 120 requests went to TypeSafe, more than Joe was first told: they carried the hard rules, the decided list and, on 70 of them, his own messages. Report: `scratchpad/jev_approvals/REPORT.md`.

**Both S7 reviews say do not merge (Nov 4).** The reviewer: one hard failure, the budget gate before predicate eval, against spec lines 124 to 130, brief line 393 and S7's text. The adversary, working from the same brief and told nothing of it either, found the same one first: with every default and the real clock, a 4 s drag on an attribute the predicate does not name spends the global 60 per minute, and the next real change gives no wake, no flag and no state change. It adds two more. One burst is a permanent mute at a low budget, which is the queued window step, reproduced now on the real Rust budget. And a mute write that cannot be saved raises out of `_on_event` and stops every neuron registered after the muted one, because the `for record` loop has no guard per record. Both say the T3 flip is honest and `budget.rs` is right: 50,000 random calls against a reference written from the text, 0 differences. Moving the block costs the metric nothing, so at 0 failing a corrected reply cannot score a gain; a frozen test has to go in first.

The draft is `scratchpad/frozen_order/test_budget_order.py`, two functions on the CONTRACT surface. On the keep both fail, 5 of 5, and under `--assert=plain` too; with the block moved both pass, 5 of 5, and phase 1 reads 13 of 13. The step that follows should carry the isolation per record in its text, and `scratchpad/s7_proof/budget_order_probe.py` and the adversary's `save_failure` probe join the standing S7 checks.

Parked from these reviews, not S7's to fix: a global refusal leaves no trace, and which neuron starves is decided by registration order; the default neuron budget of 100 per 10 s can never fill before the global 60 per minute, so a default neuron cannot reach a mute; an operator cannot see a neuron two trips from a mute; `Budget::new` validates nothing, so a window of 0 or NaN switches the budget off; spec line 138's session-layer un-mute composes as dormant while the handle stays muted, and Joe's release text says restart, which S8 makes true.

**S7b, the order fix (Nov 4).** Joe placed `tests/acceptance/phase1/test_budget_order.py`, so the loop branch reads 2 failing and a corrected `neuron.py` can score. S7b moves the budget check to replace the S7 comment after eval, with no second lock, and wraps each record's body in a try, so a Save that raises on one mute leaves the neurons after it running. The text was proved on a scratch copy before the worker saw it. S7 stays unmerged until S7b keeps and passes review.

**Both reviews of S7 and S7b say do not merge (Nov 4).** S7b kept (row 85, `95e02cc`, 2 -> 0) with half its step: the budget now runs after the predicate in one lock, and 14 of the earlier adversary's probes flipped to right with none going back, but the isolation per record is absent and the comment naming S7 is still there. Hard, from both: a mute that cannot be saved costs every neuron after it its events, because the loop has no guard per record. It is rarer than a read-only file makes it sound: a reader in another process holding the file for 400 ms is enough, 3 of 3. The mute also reads muted with no flag on the stage, because the first Save raises before the flag is authored. Hard, from the reviewer only, and not S7b's to fix: one burst is still a permanent mute through the 10 ms window. Moving nothing back is needed; the combined change is better than or equal to S7 on every probe.

Joe's word was to merge once both cleared, so nothing merged. As with the order, a clause nothing scores did not land, so the fix needs a frozen target first. The draft is `scratchpad/frozen_order/test_mute_isolation.py`, two functions, proved on the keep (2 failed), a copy with the try (1 failed) and a copy with the try and one ChangeBlock with one Save (15 of 15). Parked from these reviews, beyond those already listed: a stronger opinion on `plexus:budgetWakes` composes and is ignored; the spec's risk gate, stage 4, has no home in any plan row, and its classifier cannot be imported under the Nov 1 rule; a refused Save holds the dispatcher about 340 ms and leaves a temp file each time. The standing `save_failure` probe reads WRONG even on a correct tree, because it sleeps 150 ms against that 340 ms; use `save_failure_settled` in `scratchpad/s7b_review_reviewer/probes/adv_plus.py`.

**Counting Joe's next 20 decisions (Nov 4, on his word).** They start after his yes to the three plain rules. A decision is anything Claude brings him, or anything he answers that changes the work. The last column says whether a plain rule already covered it. Nothing else gets built for fewer approvals until this reads 20 of 20.

| # | When | What he decided | Took Claude's recommendation | A plain rule covered it |
|---|---|---|---|---|
| 1 | Nov 4 | Placed the order test; merge the mission into the loop branch, add S7b, start the run | Yes | No: frozen tests are his |
| 2 | Nov 4 | Merge S7 and S7b and push both branches once the reviewer and adversary clear them; they did not | Came before the recommendation | No: merges are his |
| 3 | Nov 4 | Placed the isolation test, which starts S7c | Yes | No: frozen tests are his |
| 4 | Nov 4 | Once the reviewer and adversary clear S7c, merge S7, S7b and S7c without waiting for the burst finding, and push both branches | Yes | No: merges are his |
