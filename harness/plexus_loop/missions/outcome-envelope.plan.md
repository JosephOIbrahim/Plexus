# Plan: mission `outcome-envelope` (M2b, Phase 3's first)

**What it is for.** Blueprint v5.4 §4: every Plexus call returns one envelope, `Outcome`, with a status (`Ok`, `Unavailable` or `Blocked`), a payload, and a reason that is required whenever the status is not `Ok`. It is defined once in Rust and exposed to Python through PyO3, so the Rust core and the Python layers share one type. Joe decided its shape on Nov 1 (`NEXTGEN_SCAFFOLD_PLAN.md`, `rust.outcome-and-errors`) and that it lands in its own mission, M2b, before identity (M3's `cache_key` is the first call that returns one). Phase 3 is the contracts; this mission is its first frozen file.

**Slug.** `Phase` is not a slug that names a mission, so the slug comes from the scope: `outcome-envelope`.

## 1. Decisions, with the recommended option

These are the mission's assumptions until Joe says otherwise.

| # | Decision | Recommended | Why | What a different answer costs |
|---|---|---|---|---|
| D1 | Where Python finds it | **`plexus._core.Outcome`**, and no Python wrapper module | It is how `Budget` and `compile_predicate` are reached today; a wrapper under `plexus/` would be a second definition and a new focus path | A re-export in `plexus/core/` adds a file, a layers rank and a second place the name lives |
| D2 | How Python builds one | **One validating constructor**, `Outcome(status, payload=None, *, reason_code=None, reason=None, missing=())`, and no classmethods | Nov 1 gives Python a bool `.ok`; a class attribute cannot be that getter and an `Outcome.ok(...)` builder at once. One door also means one place the rules are read from | Builders under other names (`Outcome.success(...)`) are possible later and change no rule |
| D3 | Names | **Nov 1's attributes**: `.status`, `.payload`, `.reason_code`, `.reason`, `.missing`, `.ok`. The constructor's keywords match them, and the three reason keywords are keyword-only | A field is read and written under one name; keyword-only keeps `Outcome("blocked", "x")` from reading a sentence as a payload | Other names change the frozen bytes and the CONTRACT lines |
| D4 | The rules, each a `ValueError` at construction | **Status spelled exactly** (`"ok"`, `"unavailable"`, `"blocked"`: no other case, no surrounding space). **Not ok needs a reason**: a snake_case `reason_code` (a lowercase ASCII letter, then lowercase ASCII letters, digits, `_`) and a `reason` that is not blank. **Ok takes no reason**. **Only ok carries a payload**, `None` included. **Only unavailable names `missing`**, and `missing` alone is no reason. A wrong type is a `TypeError` | "Reason required when not Ok" is Joe's scope; snake_case codes, the payload rule and `missing` for Unavailable alone are Nov 1's constructors (`ok(T)`, `unavailable(code, detail, missing)`, `blocked(code, detail)`) read as rules. A mistake a caller's own arguments show raises, as Nov 1 says | Looser codes (any non-empty text) or a payload beside a reason are one line each in `Outcome::new` and a case each in the frozen file |
| D5 | Mutability and shapes | **Frozen** (`#[pyclass(frozen)]`: setting or adding an attribute raises `AttributeError`); `.missing` a **tuple**, in the order given; `.payload` **the very object given** | An answer that can be edited after it is returned is not an answer; a tuple says the same as frozen | A list or a copy changes a case each |
| D6 | What it does not do yet | **`repr()` names the status and the reason code (or the payload)**; no `__eq__`, `__hash__`, `__bool__`, pickling or `__traverse__` | Each waits for a caller that needs it; `__bool__` especially, because `if outcome:` reading as "ok" is the footgun §4 warns against (branch on `.status`) | Adding one later is additive; a payload that holds its own Outcome is a reference cycle the GC cannot see until `__traverse__` lands |
| D7 | The Rust shape | **Departs from Nov 1 in one place:** `Reason.code` is a `String`, not `&'static str`, because an Outcome Python builds carries a code typed at run time. Otherwise as Nov 1: `enum Status`, `struct Reason { code, detail, missing }`, `struct Outcome<T>` with private fields. `Outcome::ok(T)` cannot fail; `unavailable` and `blocked` return `Result<Self, String>`, because they check the rules; **every rule lives in `Outcome::new`**, which `py.rs` calls for every Python-built Outcome. `map` is there for the Rust-to-Python bridge M3 needs | The rule set is written once, in Rust, as §4 asks, and no Rust caller can build an Outcome around it | Keeping `&'static str` means a second, Python-only Reason type, and the rules written twice |
| D8 | Visibility | **`pub mod outcome;`**, the other modules staying private | A second workspace crate (`plexus-usd`, Blueprint §13: `Outcome<StageId>`) has to name `plexus_core::outcome::Outcome`; the layers guard allows `pub mod` | Private now means a one-word change in the first mission that needs it |
| D9 | No panic across PyO3 | **`#![deny(clippy::unwrap_used, clippy::expect_used)]` at the top of `outcome.rs`**, not crate-wide | The layers guard lets `lib.rs` declare modules and nothing else. Measured: `cargo clippy` on the reference finds nothing in `outcome.rs` or `py.rs` (the 14 findings are `predicate.rs`'s, as on the base). There is no clippy gate: CI's minimal toolchain has no clippy | A crate-wide deny needs a guard change (Joe's, `harness/**`) and a clippy gate |
| D10 | Where the test lives | **`tests/acceptance/phase3/test_outcome.py`** with an empty `phase3/__init__.py`, as `phase1/` has; CONTRACT gains one sentence in its opening paragraph and a `plexus._core` section; Plexus CI gains a "Frozen phase 3" step (C3) | Phase 3 is the contracts, and later contract tests join this folder | Under `phase2/` it would sit with the organ files and run in CI's 8-minute step |
| D11 | Gates | **layers, core, predicate_smoke, phase1 (new), cargo, posix, unit.** `neuron_unchanged` is dropped (`neuron.py` is outside focus). **`phase1` is new**: `py.rs` is sent whole, no target case reads `Budget`, and `neuron.py` imports it, so all 30 phase 1 tests run after `core` (35 s). **`posix` stays** because it is the only gate that builds the core for Linux | A whole-file `py.rs` that lost `Budget` would otherwise be kept | Without `phase1`, the reviewer alone guards `Budget` and the predicate's Python surface |
| D12 | Branch | **`mission/outcome-envelope`, cut from `mission/organ-spawn` at `d57056d`** by Joe's placement script | `mission/organ-spawn` is the default branch and holds alpha.13 and decisions 02, 09 and 10 | Another base changes the pinned CONTRACT blob |
| D13 | Steps | **One step, E1, three whole files, longest first**: `outcome.rs`, `py.rs`, `lib.rs` | `lib.rs`'s `pub mod outcome;` cannot be scaffolding (it breaks the build without `outcome.rs`), and the worker stops after a trivial first file (memory), so the one-line file goes last | Two steps cannot work: nothing in the target passes until `py.rs` registers the class |

## 2. The frozen file

`tests/acceptance/phase3/test_outcome.py`, 50 cases, sha256 `02877880…`. Each case imports `Outcome` itself, so a missing class fails each case alone and the metric collects 50.

- **Positive cases** (so an implementation that refuses everything fails): ok with a payload, ok with none, ok with `0`; unavailable with and without `missing`; blocked; four snake_case codes accepted.
- **A reason is required**: not ok with nothing, a code alone or a sentence alone (3 × 2 statuses); `missing` alone; an empty or blank sentence and an empty code.
- **Ok takes no reason** (4); **only ok carries a payload** (2 statuses, a dict and `0`); **only unavailable names `missing`**.
- **Codes**: eight spellings refused (`NonFinite`, `Non_finite`, `non-finite`, `non finite`, `2fast`, `_hidden`, `café_closed`, `non_finite `).
- **Status**: ten spellings, each given the arguments its nearest real status would accept, so only the spelling can refuse it (`OK`, `Ok`, ` ok`, `ok `, `Blocked`, `UNAVAILABLE`, ` blocked`, `failed`, `unknown`, ``).
- **Types**: six wrong-type arguments raise `TypeError` (an int or `None` status, an int code, a bytes sentence, a bare-string `missing`, a `missing` holding an int).
- **Frozen**: seven attribute names, on an ok and an unavailable Outcome; **surface**: `__module__`, not an exception, `repr()`.

**CONTRACT.md** is `d57056d`'s (blob `d0cffbec…`) plus the sentence and the section, sha256 `fbcc948d…`.

## 3. The reference

On top of `d57056d`, in `crates/plexus-core/src/`: `outcome.rs` (new, 217 lines with six Rust tests), `py.rs` (the `Outcome` class added, everything else unchanged) and `lib.rs` (`pub mod outcome;`). E1's text carries all three verbatim, 15,552 characters; the toml parses back to the reference byte for byte.

## 4. What no frozen case can read, and what covers it

| Clause | Why no case reads it | What covers it |
|---|---|---|
| The rules live in `Outcome::new` in Rust, and `py.rs` builds every Outcome through it, not with checks of its own | Python sees the same `ValueError` either way | The step text and brief say so; the reviewer compares the kept files with the reference byte for byte |
| `Outcome`'s fields are private; the three constructors and `new` are the only doors | Rust privacy is invisible from Python | The reviewer; `cargo test` compiles the six Rust tests against the public API |
| The six Rust tests stay in `outcome.rs` | Nothing fails if they vanish | The reviewer (byte for byte) |
| `#![deny(clippy::unwrap_used, clippy::expect_used)]` | No clippy gate | The reviewer; measured clean on the reference |
| The core builds and phase 3 passes on Linux | The harness runs on Windows | The `posix` gate builds it for Linux; Plexus CI's Linux leg runs phase 3 once C3 lands; measured in WSL below |

## 5. Proof (Nov 15, `m2b/` in session 08db8b6d's scratchpad)

- **Base, `d57056d`:** **50 failed**, every one `ImportError: cannot import name 'Outcome' from 'plexus._core'`. For a new type the reason is the same for each case; the mutant run is what shows each case reads its own clause.
- **Reference:** **50 passed**, three runs in a row (0.2 s each) on Windows, Python 3.12.10; **50 passed** under WSL Ubuntu, Python 3.14.2, against the Linux build the `posix` gate made.
- **Phase 1 and 2 whole on the reference:** **301 passed, 3 skipped** (the POSIX-only cases), 4 min 46 s, as on `b900b3b`. Phase 1 alone: 30 passed, 35 s.
- **Gates on the reference:** layers 9 passed; `core` builds clean (no warnings); `predicate_smoke` passes; `cargo test` 6 passed; `posix` 41 passed and 1 Windows-only skip, 39 s; `unit` 465 passed with the three mission files in place (3 min 56 s, as CI's Windows leg on `b900b3b`); `check` reads `ready`.
- **Mutants: 19 of 19 caught**, one clause each: ok takes a reason (4 cases fail), not-ok without a reason (2), a payload beside a reason (2), no snake_case check (8), digits refused (1), a blank sentence passes (1), blocked names `missing` (1), the status lowercased (4), the status trimmed (3), `missing` a list (3), attributes can be added (1), ok needs a payload (1), a bare string is one missing name (1), no `repr` (1), no module name (1), `.ok` true for unavailable (1), code and sentence swapped (7), `missing` sorted (1), the payload copied (1). The status-trimmed mutant at first survived, because every status case carried a reason and `" ok"` with a reason is refused anyway; the case now gives each spelling the arguments its nearest real status accepts.
- **Adversary pass** (its own worktree, without the reference): still running when C1 was made; its findings go into this plan when it reports, and any test change they call for is Joe's, as a second frozen commit.

**The mission file** (`outcome-envelope.toml`): E1 gives the whole reference; metric `pytest_failures` on `test_outcome.py` alone; four known-fix anchors, each once in the brief.

**The placement script** (`.plexus_loop/place_outcome_envelope.sh`) pins `02877880…` for the test, `e3b0c442…` (empty) for `phase3/__init__.py`, `fbcc948d…` for CONTRACT, and the CONTRACT blob `d0cffbec…` it was built on. Its dry run in a scratch clone of `mission/organ-spawn` cut `mission/outcome-envelope`, committed the three files with matching hashes and printed its dry-run marker; the clone is removed.

**Placed** by Joe on Nov 15 as `5250952` on `mission/outcome-envelope`, cut from `d57056d`. Checked on disk before anything else: the committed `test_outcome.py` is `02877880…`, `phase3/__init__.py` is `e3b0c442…` and `CONTRACT.md` is `fbcc948d…`, the three pinned hashes; the branch's diff from `mission/organ-spawn` is those three files.

## 6. Scaffolding, Claude's, after Joe's placement and before `run`

1. **C1:** `outcome-envelope.toml`, `.worker.md` and this plan into `harness/plexus_loop/missions/`.
2. **C2:** `program.md` rule 2 names `mission/outcome-envelope` and `plexus-loop/outcome-envelope`.
3. **C3:** Plexus CI's "Frozen phase 3" step, and its header says phases 1, 2 and 3. The mission branch's CI then reads red on phase 3 until E1 is kept, which is its honest state; the loop branch inherits the step, so the keep's CI run shows phase 3 on Windows and Linux.

Then `check`, its output pasted here, the push of `mission/outcome-envelope` by name, and `run`.

**Made on Nov 15:** C1 `ce2f04f`, C2 `8c8a8dc`, C3 `6266288`, on top of Joe's `5250952`. `check` on `mission/outcome-envelope` after C3:

```
mission outcome-envelope: worker ollama (qwen3-coder:30b), 7 gate(s), metric pytest_failures
Houdini: absent; next attempt runs on the gpu
worker: check does not load qwen3-coder:30b; run loads it first and refuses if it cannot
ready
```
