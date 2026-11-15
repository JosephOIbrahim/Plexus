# Worker brief: mission `outcome-envelope`

You make one change per attempt. The harness keeps it only if every gate passes and at least one more test in the target passes. One step, E1, three files under `crates/plexus-core/src/`: `outcome.rs` (new), `py.rs` and `lib.rs`.

## How to reply

- Exactly three fenced blocks, in this order: `file:crates/plexus-core/src/outcome.rs`, then `file:crates/plexus-core/src/py.rs`, then `file:crates/plexus-core/src/lib.rs`. Each holds its file whole. Never a diff, no commentary, no `...`.
- The step gives all three files. Copy each as written, byte for byte, the tests at the end of `outcome.rs` included.
- Write no test of your own, in Rust or in Python.

## What exists already

- `plexus._core` is built from `crates/plexus-core` by the `core` gate. Today it holds `PredicateError`, `Predicate`, `Budget` and `compile_predicate`, and `neuron.py` imports `Budget` from it.
- The target is `tests/acceptance/phase3/test_outcome.py`: 50 cases, and all 50 fail today because `plexus._core.Outcome` is not registered yet.
- `CONTRACT.md` carries the `plexus._core` section this mission adds.

## Rules the gates enforce

- Change only the three files. Every other path, `Cargo.toml` included, stays as it is.
- `lib.rs` may only declare modules. `outcome` is declared `pub mod outcome;`, and nothing else in `lib.rs` changes.
- Only `py.rs` may name pyo3. `outcome.rs` is rank 1 and uses no other module of the crate; `py.rs` uses `crate::outcome`.
- `py.rs` keeps `PredicateError`, `Predicate`, `Budget` and `compile_predicate` exactly as they are; the `phase1` gate runs every phase 1 test against them.
- `cargo test` runs the six tests at the end of `outcome.rs`.

## Rules the frozen tests read

- `plexus._core.Outcome is registered` by `m.add_class::<PyOutcome>()` in `_core`, as a frozen class whose module is `plexus._core`.
- The status is one of `"ok"`, `"unavailable"` and `"blocked"`, spelled exactly: `Status::from_name` reads the text as given, with no lowercasing and no trimming.
- A status that is not ok needs a snake_case `reason_code` and a `reason` that is not blank; only ok carries a payload, and only unavailable names what is `missing`. Every one of these rules lives in `Outcome::new` in `outcome.rs`, and `py.rs` builds every Outcome through it.
- `missing` comes back as a tuple, in the order given; `payload` comes back as the very object given.
