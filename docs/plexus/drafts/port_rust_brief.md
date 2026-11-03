# Port mission draft: the Rust predicate and budget, behind the phase-1 surface

Moved out of `harness/plexus_loop/missions/acceptance.worker.md` on Nov 3 when Option B (all-Python phase 1) was staged on `prep/option-b`. Nothing here is current while phase 1 runs under B; it is the brief material the Rust port mission starts from, behind the same `plexus.core.predicate` and `plexus.core.budget` surface. The port's frozen target is Joe's to write: `plexus.core.predicate.PredicateError is plexus._core.PredicateError`, the same identity for `compile_predicate` and `Budget`, a table of cases checking Python against Rust, and phase 1 as the no-regression gate. The Rust error record is ledger rows 43 and 46–56 (`.plexus_loop/acceptance/attempts.jsonl`): E0255, E0433, E0277 (`&f64`, and a custom error type across pyo3), E0599, E0308 (three shapes), E0106, E0204, E0282, E0382, a cast parsed as generics, and the `crate::py` rank violation.

## The split under Option A (as it stood)

- **Python** owns everything that touches `pxr`: the `Tf.Notice` callback, the event queue, one dispatcher thread with a 50 ms debounce, action worker threads, `wait_idle`, reading composed values, authoring, saving, and the path allowlist gate.
- **Rust** (`plexus._core`) owns the pure logic: `compile_predicate(source, scope) -> Predicate` (raises `PredicateError`), `Predicate.paths()`, `Predicate.seed(values)`, `Predicate.eval(changed, values) -> bool`, `Predicate.commit_wake(values)`, and `Budget(wakes, window_s)` with `peek(now)` and `admit(now)` returning `"wake" | "trip" | "mute"`. Only `str`, `int`, `float`, `bool`, `None`, `list`, `tuple`, `dict` cross. Rust never owns a clock: Python passes `now` from the runtime's injected clock.
- `plexus/core/predicate.py` re-exports `PredicateError` from `plexus._core`, so `pytest.raises` matches.
- Rust module layout: `lib.rs` holds only comment lines, `mod name;` lines, and `#[cfg(feature = "python")]` on the line before `mod py;`. No `use`, `pub use` or `#![...]`. Declare a module in the same reply that creates its file: `mod predicate;` in S3, `mod budget;` in S7.
- `py.rs` is the only file that names pyo3, comments included (the guard greps the raw text for `pyo3`). Every `#[pyclass]` and the `#[pymodule]` live there.
- The only `.rs` file names the layers gate accepts in `crates/plexus-core/src` are `lib`, `py`, `predicate` and `budget` (later `error`, `outcome`, `canon`, `graph`, `composer`). Any other name, such as `parser.rs`, `scope.rs` or `cache.rs`, fails the gate.
- A module may write `crate::X` only for a strictly lower rank: error 0, outcome 1, predicate/budget/canon/graph 2, composer 3, py 4. So `predicate.rs` and `budget.rs` never name each other.
- Leave `crates/plexus-core/Cargo.toml` alone. `default = []` stays empty, because the `cargo` gate runs `cargo test` without the `python` feature.

## Facts the worker would otherwise learn by failing (Rust)

**pyo3 0.30 (checked: pyo3 0.30.1, abi3-py311, Python 3.14.2, cargo 1.99.1).** Older pyo3 idioms do not compile. `PyObject` no longer exists (use `Py<PyAny>` or `&Bound<'_, PyDict>`). `fn _core(py: Python, m: &PyModule)` fails. `py.get_type_bound::<T>()` fails. In S3, write `py.rs` whole, exactly as this block: it has no `PyBudget` and no `crate::budget`, because `budget.rs` does not exist until S7. Copy its `use` lines as they are. `PredicateError` is the name `create_exception!` defines, so never import anything as `PredicateError`: `use crate::predicate::{Value, Error as PredicateError};` fails with E0255, "the name `PredicateError` is defined multiple times".

```rust
//! The Python extension module `plexus._core`. The only file that names pyo3.

use std::collections::HashMap;

use pyo3::create_exception;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::predicate::Value;

create_exception!(plexus._core, PredicateError, PyValueError);

/// dict[str, float | int | bool | str | None] -> Rust values. None and other types are left out.
fn to_values(d: &Bound<'_, PyDict>) -> PyResult<HashMap<String, Value>> {
    let mut out = HashMap::new();
    for (k, v) in d.iter() {
        let key: String = k.extract()?;
        let val = if let Ok(b) = v.extract::<bool>() {
            Value::Bool(b) // bool first: True also extracts as 1.0
        } else if let Ok(x) = v.extract::<f64>() {
            Value::Num(x)
        } else if let Ok(s) = v.extract::<String>() {
            Value::Str(s)
        } else {
            continue;
        };
        out.insert(key, val);
    }
    Ok(out)
}

#[pyclass(name = "Predicate")]
struct PyPredicate {
    inner: crate::predicate::Predicate,
}

#[pymethods]
impl PyPredicate {
    fn paths(&self) -> Vec<String> {
        self.inner.paths()
    }
    fn seed(&mut self, values: &Bound<'_, PyDict>) -> PyResult<()> {
        self.inner.seed(&to_values(values)?);
        Ok(())
    }
    fn eval(&self, changed: Vec<String>, values: &Bound<'_, PyDict>) -> PyResult<bool> {
        Ok(self.inner.eval(&changed, &to_values(values)?))
    }
    fn commit_wake(&mut self, values: &Bound<'_, PyDict>) -> PyResult<()> {
        self.inner.commit_wake(&to_values(values)?);
        Ok(())
    }
}

#[pyfunction]
fn compile_predicate(source: &str, scope: &str) -> PyResult<PyPredicate> {
    crate::predicate::compile(source, scope)
        .map(|inner| PyPredicate { inner })
        .map_err(PredicateError::new_err)
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("PredicateError", m.py().get_type::<PredicateError>())?;
    m.add_class::<PyPredicate>()?;
    m.add_function(wrap_pyfunction!(compile_predicate, m)?)?;
    Ok(())
}
```

**In S7 only, `py.rs` gains three pieces,** in the same reply that adds `mod budget;`: this block after `compile_predicate`, and `m.add_class::<PyBudget>()?;` on the line after `m.add_class::<PyPredicate>()?;`.

```rust
#[pyclass(name = "Budget")]
struct PyBudget {
    inner: crate::budget::Budget,
}

#[pymethods]
impl PyBudget {
    #[new]
    fn new(wakes: u32, window_s: f64) -> Self {
        PyBudget { inner: crate::budget::Budget::new(wakes, window_s) }
    }
    fn peek(&self, now: f64) -> &'static str {
        self.inner.peek(now)
    }
    fn admit(&mut self, now: f64) -> &'static str {
        self.inner.admit(now)
    }
}
```

What this fixes for the other files:
- `predicate.rs` must provide `pub enum Value { Num(f64), Str(String), Bool(bool) }`, `pub fn compile(source: &str, scope: &str) -> Result<Predicate, String>`, and `Predicate` methods `paths(&self) -> Vec<String>`, `seed(&mut self, &HashMap<String, Value>)`, `eval(&self, &[String], &HashMap<String, Value>) -> bool` and `commit_wake(&mut self, &HashMap<String, Value>)`.
- The `#[pyclass(name = ...)]` wrappers keep the Rust struct names free. Pyclass fields must be thread-safe: no `Rc`, `RefCell` or `Cell`; mutate through `&mut self`.
- A key missing from `values` means the attribute has no value. Python passes `changed` as a list of `str(path)`.
- In `predicate.rs`, compare numbers by value. A `HashMap` lookup or a `match` on a reference gives `&f64`; dereference it before comparing (`*current > value`, or bind by value with `Some(&Value::Num(current))`). Comparing `&f64` with `f64` fails with E0277, "can't compare `&f64` with `f64`".
- Each parse function in `predicate.rs` returns what it parsed and the input it did not consume: `fn parse_clause<'a>(s: &'a str, scope: &str) -> Result<(Clause, &'a str), String>`, and the AND loop continues from that rest. A function that takes two `&str` and returns a borrow must name the lifetime, exactly as that signature does: the same function written without `<'a>` fails with E0106, "missing lifetime specifier". A `Clause` does not know its own length: `rest[clause.len()..]` fails with E0599, "no method named `len` found for enum `Clause`".
- A `delta` clause holds an `f64`, never a `Value`: parse its number with `s.parse::<f64>()` and return an `Err` for anything else. Only an `attr` clause holds a `Value`. `Clause::Delta { path, cmp, value }` with a `Value` fails with E0308, "mismatched types: expected `f64`, found `Value`".
- `Value` derives `Debug, Clone, PartialEq` and nothing else. It holds a `String`, so `#[derive(Copy)]` on it fails with E0204, "the trait `Copy` cannot be implemented for this type". Where a copy is needed, `.clone()` it.
- `compile` and every parse function return a `Result`, never an `Option`: take their value with `if let Ok(x) = ...` or `match ... { Ok(x) => ..., Err(e) => ... }`, and pass an `Err` up with `?`. `if let Some(x) = parse_clause(...)` fails with E0308, "mismatched types: expected `Result<...>`, found `Option<_>`".
- `predicate.rs` defines no error type: `compile` returns `Result<Predicate, String>`, and `py.rs` turns that `String` into Python's `PredicateError` with `.map_err(PredicateError::new_err)`, as its block shows. A `struct PredicateError` or `enum PredicateError` of your own in `predicate.rs` cannot cross into Python: pyo3 fails with E0277, "`PredicateError` cannot be converted to a Python object" and "the trait bound `PredicateError: PyErrArguments` is not satisfied".

## Known fixes for the Rust errors (toml, for the port mission file)

```toml
[[known_fixes]]
match = '''the name `PredicateError` is defined multiple times'''
file = "harness/plexus_loop/missions/acceptance.worker.md"
anchor = "never import anything as `PredicateError`"
[[known_fixes]]
match = '''can't compare `&f64` with `f64`|can't compare `f64` with `&f64`'''
file = "harness/plexus_loop/missions/acceptance.worker.md"
anchor = "In `predicate.rs`, compare numbers by value"
[[known_fixes]]
match = '''no method named `len` found for (enum|struct) `Clause`'''
file = "harness/plexus_loop/missions/acceptance.worker.md"
anchor = "Each parse function in `predicate.rs` returns what it parsed"
[[known_fixes]]
match = '''expected `f64`, found `Value`|expected `Value`, found `f64`'''
file = "harness/plexus_loop/missions/acceptance.worker.md"
anchor = "A `delta` clause holds an `f64`, never a `Value`"
[[known_fixes]]
match = '''\.rs \(rank \d\) uses crate::\w+ \(rank \d\)'''
file = "harness/plexus_loop/missions/acceptance.worker.md"
anchor = "A module may write `crate::X` only for a strictly lower rank"
[[known_fixes]]
match = '''missing lifetime specifier'''
file = "harness/plexus_loop/missions/acceptance.worker.md"
anchor = "must name the lifetime"
[[known_fixes]]
match = '''the trait `Copy` cannot be implemented for this type'''
file = "harness/plexus_loop/missions/acceptance.worker.md"
anchor = "`Value` derives `Debug, Clone, PartialEq` and nothing else"
[[known_fixes]]
match = '''expected `Result<[^`]*>`, found `Option<[^`]*>`|expected `Option<[^`]*>`, found `Result<[^`]*>`'''
file = "harness/plexus_loop/missions/acceptance.worker.md"
anchor = "return a `Result`, never an `Option`"
[[known_fixes]]
match = '''PredicateError` cannot be converted to a Python object|PredicateError: PyErrArguments` is not satisfied'''
file = "harness/plexus_loop/missions/acceptance.worker.md"
anchor = "`predicate.rs` defines no error type"
```
