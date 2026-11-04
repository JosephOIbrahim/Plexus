# Worker brief — mission `acceptance`

You make one change per attempt. The harness keeps it only if every gate passes and at least one more test in `tests/acceptance/phase1` passes. The prompt names the one step this attempt is for; do that step only, and touch only the files that step names.

**Every attempt starts from the last kept commit.** A dropped attempt's files are gone. When the prompt says why the last attempt was dropped, fix that cause and resubmit the whole step: every file the step needs, as whole-file blocks. Never send a diff against a file only a dropped attempt created.

## How to reply

- **A new file, or a file you rewrite completely:** one fenced block per file, whose info string is `file:` plus the path, holding the whole file:

  ````
  ```file:plexus/core/axon.py
  """The axon: turns USD change notices into coalesced events."""
  ...the complete file...
  ```
  ````

- **An edit to an existing file:** one unified diff in a ```` ```diff ```` block, with `a/` and `b/` path prefixes, `--- a/<path>`, `+++ b/<path>`, and hunks whose context lines start with a space.
- Nothing else inside either kind of block: no commentary, no `?` lines, no placeholders.
- **Every `.rs` file, `lib.rs` included, goes in a whole-file block, never a diff.** They are short, and a diff against them breaks more easily than the file.

## What exists already

- `plexus/__init__.py` (empty package) and `crates/plexus-core` (a Cargo crate whose `py.rs` holds an empty PyO3 module `plexus._core` with `__version__`). The `core` gate builds it and copies the library to `plexus/_core.pyd`; you never build anything yourself.
- `tests/acceptance/CONTRACT.md` is the exact Python surface the tests call. Match its names and signatures.

## The split (decided: Option A)

- **Python** owns everything that touches `pxr`: the `Tf.Notice` callback, the event queue, one dispatcher thread with a 50 ms debounce, action worker threads, `wait_idle`, reading composed values, authoring, saving, and the path allowlist gate.
- **Rust** (`plexus._core`) owns the pure logic: `compile_predicate(source, scope) -> Predicate` (raises `PredicateError`), `Predicate.paths()`, `Predicate.seed(values)`, `Predicate.eval(changed, values) -> bool`, `Predicate.commit_wake(values)`, and `Budget(wakes, window_s)` with `peek(now)` and `admit(now)` returning `"wake" | "trip" | "mute"`. Only `str`, `int`, `float`, `bool`, `None`, `list`, `tuple`, `dict` cross. Rust never owns a clock: Python passes `now` from the runtime's injected clock.
- `plexus/core/predicate.py` re-exports `PredicateError` from `plexus._core`, so `pytest.raises` matches.
- Rust module layout: `lib.rs` holds only comment lines, `mod name;` lines, and `#[cfg(feature = "python")]` on the line before `mod py;`. No `use`, `pub use` or `#![...]`. Declare a module in the same reply that creates its file: `mod predicate;` in S3, `mod budget;` in S7.
- `py.rs` is the only file that names pyo3, comments included (the guard greps the raw text for `pyo3`). Every `#[pyclass]` and the `#[pymodule]` live there.
- The only `.rs` file names the layers gate accepts in `crates/plexus-core/src` are `lib`, `py`, `predicate` and `budget` (later `error`, `outcome`, `canon`, `graph`, `composer`). Any other name, such as `parser.rs`, `scope.rs` or `cache.rs`, fails the gate.
- A module may write `crate::X` only for a strictly lower rank: error 0, outcome 1, predicate/budget/canon/graph 2, composer 3, py 4. So `predicate.rs` and `budget.rs` never name each other.
- Leave `crates/plexus-core/Cargo.toml` alone. `default = []` stays empty, because the `cargo` gate runs `cargo test` without the `python` feature.

## Rules the gates enforce

- Change only `plexus/**`, `crates/**`, `Cargo.toml`, `Cargo.lock`.
- Never import `agent`, `cognitive` or anything from them, at any scope. Never copy code from them.
- No engine vocabulary anywhere under `plexus/` or `crates/` (the T8 test scans `.py .rs .toml .json .usda`): not `cfg`, `KSampler`, `prompt_id`, `class_type`, `SaveImage`, `LoadImage` or other ComfyUI node names. In Rust, `#[cfg(...)]` attributes are fine; the word `cfg` anywhere else is not. No `[target.'cfg(...)']` table in any Cargo.toml and no `build.rs`.
- Modules that must not import `pxr`: `plexus/__init__.py`, `plexus/schema`, `plexus/core/__init__.py`, `plexus/core/predicate.py`, `plexus/membrane/__init__.py`, `plexus/organs/__init__.py`. No import cycles.
- **Package `__init__.py` files hold a docstring only.** `plexus/core/__init__.py` and `plexus/membrane/__init__.py` are created with nothing but a docstring, and `plexus/__init__.py` is never edited. Import submodules directly (`from plexus.core.axon import PlexusAxon`), never through the package.
- `plexus/core/axon.py` and `plexus/core/stagekit.py` never import each other: the axon watches any stage it is given, and stagekit only writes layers.
- **Placeholders are wording, never code.** In this brief and the step text, `<id>`, `<participant>`, `<name>` and `<exchange.usda path>` stand for a value. In code they become a variable inside an f-string, such as `f"from_{participant_id}.usda"`, never part of a name: `from_<id> = ...` is a syntax error, and the whole attempt is dropped for it. Every `.py` file you send must compile.

## Facts you would otherwise learn by failing

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
- Compare `f64` values directly (`a < b`, `a >= b`); never cast with `as` to compare. `*a as i32 < *b as i32` does not even parse: rustc reads `i32 <` as the start of generic arguments ("`<` is interpreted as a start of generic arguments for `i32`, not a comparison"), and an `i32` cast would also throw away the 0.15 steps T2 measures.
- `values.get(path)` gives an `Option<&Value>`: match it in one step, `if let Some(Value::Num(n)) = values.get(path)`. Binding the `&Value` first and then matching `Some(..)` on it fails with E0308, "expected `Value`, found `Option<_>`".
- `parse_clause` reads the keyword first (`changed(`, `delta(`, `attr(`, `exists(`), then hands the remainder, which starts at `(`, to `parse_path`; an unknown keyword is an `Err`. A `parse_clause` that hands the raw clause to `parse_path` rejects every grammar-v0 predicate, the valid ones included, and the `predicate_smoke` gate then fails with "a predicate the frozen tests register does not compile". The rejection-only target test passes on such code; the gate is what catches it.
- The clause kind comes from the keyword, never from the literal's type: a `delta` clause takes only a number, an `attr` clause a literal (a number, a quoted string or a bare token).
- `in_scope` splits the path at the first `.` and tests only the prim part: `/Exchange/LookState.temperature` is inside `/Exchange/LookState`; `/Exchange/LookStateX` is not.
- Call `trim_start()` on the rest before `parse_cmp`, and again before `parse_number` or `parse_literal`: every frozen predicate is written with spaces (`delta(P) > 0.2`), so the rest after `)` starts with one. `compile` trims `source` first.
- Propagate `parse_path`'s `Err` with `?`, never replace it with a catch-all message: the scope error must reach Python as the `PredicateError` text.
- Empty source, a trailing `AND`, and `AND` not followed by whitespace are each an `Err`; a predicate with no clauses never compiles.
- A path with no cache entry makes a `delta` clause false; never compare against 0.0. `seed` fills the cache from the composed values of `paths()` at registration: after `seed`, every path with a numeric composed value has an entry; a path without one (missing attribute, non-numeric value, `None`) stays absent and its `delta` clause is false until a wake commits a value.
- In `neuron.py`, `register()` keeps the compiled predicate, the scope, the action and the budget numbers on a per-neuron record the runtime reads later (S4 adds the dispatcher that reads it). `prim_path` on the handle is `Sdf.Path(f"/Plexus/Neurons/{name}")`, never a `str`. `/Plexus`, `/Plexus/Neurons` and the neuron prim are all `def`: `Sdf.CreatePrimInLayer` leaves the ancestors as `over`, so set `specifier = Sdf.SpecifierDef` on each. The default clock is `time.monotonic`. `compile_predicate` is imported at the top of the file (`predicate.py` is `pxr`-free, so there is no cycle). `__init__` creates the axon; `start()` starts it and attaches the dispatcher (S4), idempotently; `wait_idle` may return `True` until S4.

**In S3, `predicate.rs` starts from this skeleton** (checked: `cargo check` passes on it as written, with unused warnings only). Keep every type, derive and signature exactly as written, lifetimes included; replace each `todo!()` with its body; add no `use` beyond `std`, no `crate::`, no `#[cfg(test)]` and no error type. Nothing in it does anything yet: `compile`'s grammar, the scope rule, `paths()` order, the delta cache rule and every comparison are yours to write inside these signatures.

```rust
//! Predicate grammar v0 (PLEXUS_SPEC.md §4), in plain Rust.
//!
//! predicate := clause { "AND" clause }
//! clause    := "changed(" path ")" | "delta(" path ")" cmp number
//!            | "attr(" path ")" cmp literal | "exists(" path ")"
//! cmp       := ">" | ">=" | "<" | "<=" | "==" | "!="
//!
//! No OR. Every path is absolute and inside the neuron's scope. This file names nothing
//! outside std: no other module of this crate and no Python types; py.rs wraps it.

use std::collections::HashMap;

/// A composed attribute value as Python hands it over. It holds a `String`, so it is
/// never `Copy`.
#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Num(f64),
    Str(String),
    Bool(bool),
}

/// One comparison operator of the grammar.
#[derive(Debug, Clone, PartialEq)]
pub enum Cmp {
    Gt,
    Ge,
    Lt,
    Le,
    Eq,
    Ne,
}

impl Cmp {
    /// `a <op> b` for two numbers.
    fn holds(&self, a: f64, b: f64) -> bool {
        todo!()
    }

    /// `actual <op> wanted` for an `attr` clause: numbers compare as numbers; strings and
    /// bools only with `==` and `!=`; two different kinds are never equal.
    fn holds_values(&self, actual: &Value, wanted: &Value) -> bool {
        todo!()
    }
}

/// One clause. A `delta` threshold is an `f64`, never a `Value`.
#[derive(Debug, Clone, PartialEq)]
pub enum Clause {
    Changed { path: String },
    Delta { path: String, cmp: Cmp, value: f64 },
    Attr { path: String, cmp: Cmp, value: Value },
    Exists { path: String },
}

/// A compiled predicate. `paths` holds every path the clauses name, once each, in the
/// order they first appear. `cache` is the delta cache: written only by `seed` and
/// `commit_wake`, never by `eval`.
#[derive(Debug, Clone)]
pub struct Predicate {
    clauses: Vec<Clause>,
    paths: Vec<String>,
    cache: HashMap<String, f64>,
}

/// Compile `source` for a neuron whose scope is `scope`. Clauses are joined by `AND` only;
/// `OR`, trailing text or an unknown clause is an `Err`. A path outside the scope is an
/// `Err` here, at registration, never at fire time.
pub fn compile(source: &str, scope: &str) -> Result<Predicate, String> {
    todo!()
}

impl Predicate {
    /// Every path the clauses name, once each, in order.
    pub fn paths(&self) -> Vec<String> {
        todo!()
    }

    /// Fill the delta cache from the composed values at registration.
    pub fn seed(&mut self, values: &HashMap<String, Value>) {
        todo!()
    }

    /// True when every clause holds against `changed` (the event's paths) and `values`
    /// (the composed values of `paths()`; a missing key means no value). Reads the cache,
    /// never writes it.
    pub fn eval(&self, changed: &[String], values: &HashMap<String, Value>) -> bool {
        todo!()
    }

    /// Move the delta cache to the values the wake saw.
    pub fn commit_wake(&mut self, values: &HashMap<String, Value>) {
        todo!()
    }
}

/// True when `path` is inside `scope`: the prim part (before the first `.`) equals `scope`
/// or starts with `scope` followed by `/`. A plain `starts_with(scope)` would accept
/// `/Exchange/LookStateX` for the scope `/Exchange/LookState`.
fn in_scope(path: &str, scope: &str) -> bool {
    todo!()
}

// Each parser returns what it parsed and the input it did not consume, and the AND loop in
// `compile` continues from that rest. A parser that takes two `&str` names the lifetime of
// the one it returns a slice of.

/// One clause from the start of `s`, with the rest of `s` after it.
fn parse_clause<'a>(s: &'a str, scope: &str) -> Result<(Clause, &'a str), String> {
    todo!()
}

/// A path up to the closing `)`, checked with `in_scope`, with the rest after the `)`.
fn parse_path<'a>(s: &'a str, scope: &str) -> Result<(String, &'a str), String> {
    todo!()
}

/// A comparison operator, the two-character forms tried before `>` and `<`, with the rest
/// after it.
fn parse_cmp<'a>(s: &'a str) -> Result<(Cmp, &'a str), String> {
    todo!()
}

/// A number parsed with `str::parse::<f64>`, also when it ends the input, with the rest
/// after it.
fn parse_number<'a>(s: &'a str) -> Result<(f64, &'a str), String> {
    todo!()
}

/// A literal: a number, a quoted string, or a bare token, with the rest after it.
fn parse_literal<'a>(s: &'a str) -> Result<(Value, &'a str), String> {
    todo!()
}
```

**Codeless schema plugin (T0), checked on usd-core 26.5.** `plexus/schema/__init__.py` defines `plugin_dir()` returning `Path(__file__).parent`. Next to it, `plugInfo.json` and `generatedSchema.usda`. The `Types` key must differ from the schema's identifier; the identifier is the alias. Shape, for one schema and one attribute:

```json
{"Plugins": [{"Info": {"Types": {
    "PlexusSchemaPlexusProjectAPI": {"alias": {"UsdSchemaBase": "PlexusProjectAPI"},
        "autoGenerated": true, "bases": ["UsdAPISchemaBase"], "schemaKind": "singleApplyAPI"}}},
  "LibraryPath": "", "Name": "plexusSchema", "ResourcePath": ".", "Root": ".", "Type": "resource"}]}
```

```
#usda 1.0

class "PlexusProjectAPI" (
    customData = {
        token apiSchemaType = "singleApply"
    }
)
{
    token plexus:status (
        allowedTokens = ["active", "paused", "archived"]
    )
}
```

Write every schema and attribute T0 lists, with its exact type and token order.

**In-process registration.** T7 checks `GetAppliedSchemas()` in the pytest process, so one module every runtime entry point imports first (for example `plexus/membrane/exchange.py`) calls `Plug.Registry().RegisterPlugins(str(plugin_dir()))` once at import, with `from pxr import Plug` (`Plug` is its own `pxr` module; `Usd.Plug` does not exist, and run 4 attempt 5 failed every test on it). Checked on 26.5: registering after a stage is open still works, but registering after the process's first schema lookup (`GetAppliedSchemas`, `HasAPI`, `ApplyAPI`) does not, and every later lookup then reports no Plexus schemas.

**Membrane and stage.**
- `register_participant` appends `from_<id>.usda` at the end of `exchange.usda`'s subLayers (weakest), idempotently, and saves both files. `layer.subLayerPaths` is a live list proxy: change it in place with `if p not in layer.subLayerPaths: layer.subLayerPaths.append(p)`. Never assign the proxy back (`layer.subLayerPaths = sublayers` raises `Boost.Python.ArgumentError` on 26.5, which failed run 6 attempt 4); to assign, pass a plain `list`. Open every layer with `Sdf.Layer.FindOrOpen(p)`, and call `Sdf.Layer.CreateNew(p)` only when the file does not exist. `FindOrOpen` returns `None` for a missing file (it does not create it), so write `layer = Sdf.Layer.FindOrOpen(p) or Sdf.Layer.CreateNew(p)` in `create_exchange`, `create_project` and `register_participant` (run 7 attempt 1 failed every test on `CreatePrimInLayer` with a `None` layer in `create_project`). On 26.5, `CreateNew` on an existing path raises if the layer is open in this process, and silently empties the file if it is not.
- The new `from_<id>.usda` must exist on disk, because the tests `FindOrOpen` it. It holds `def "Exchange" { def "<id>" {} }`, so the participant's first real write resyncs only its own prim, not `/Exchange`, which is an ancestor of every neuron scope.
- Register before opening the exchange stage. Appending a sublayer to an open stage sends a notice on `/`.
- `create_project` writes the project layer with plain `Sdf`, never through a `Usd.Stage`: `spec = Sdf.CreatePrimInLayer(layer, "/Exchange")`, `spec.specifier = Sdf.SpecifierDef`, `spec.referenceList.Prepend(Sdf.Reference(str(exchange_path), "/Exchange"))`, then `layer.Save()`. `Usd.Prim` has no `AddReference` (run 4 attempt 2 failed every test on that `AttributeError`); the `Usd` form is `prim.GetReferences().AddReference(ref)`. Checked on 26.5: the `Sdf` form composes with no errors.
- Apply `PlexusProjectAPI` to `/Project` the same way as the neuron prim, at `Sdf` level: `spec.SetInfo("apiSchemas", Sdf.TokenListOp.Create(prependedItems=["PlexusProjectAPI"]))`, then `Sdf.AttributeSpec(spec, "plexus:projectId", Sdf.ValueTypeNames.String).default = project_id`. Never call `Usd.Prim.ApplyAPI` with these codeless schemas: on 26.5 it raises even after the plugin is registered (run 4 attempt 3 failed every test on it).
- `conftest.py` imports `plexus.core.stagekit` before `plexus.membrane.exchange`, so `stagekit.py` imports `plexus.membrane.exchange` at the top, which registers the plugin (see "In-process registration"). That import is allowed: `exchange.py` never imports `stagekit` or `axon`.
- Every `ctx.author` call checks the path allowlist first, with `Sdf.Path.HasPrefix`. That check is path-aware: `/Exchange/lookNeuronX` does not match `/Exchange/lookNeuron`. On deny, author an attribute whose name starts with `plexus:flag` on the neuron prim, save, and return.
- On allow, author with plain `Sdf` on `edit_layer` itself, never through `stage`, whose default edit target is `exchange.usda`. `edit_layer = Sdf.Layer.FindOrOpen(str(path))` is the same layer object the stage composes.
- `Sdf.CreatePrimInLayer` creates every missing ancestor as `over`. Set `spec.specifier = Sdf.SpecifierDef` on each one, or `Usd.PrimRange` skips the subtree and T6's dump comes back empty.
- Author the specs and both attributes inside one `with Sdf.ChangeBlock():`, with no `Usd` reads inside it. Then call `edit_layer.Save()` at once: T6 reloads the layer, and `Reload()` throws away anything unsaved.
- `plexus:sourceLayer` is `Sdf.ValueTypeNames.String` holding `edit_layer.identifier` verbatim. On Windows that identifier uses forward slashes (`C:/Users/.../from_lookNeuron.usda`). `str(path)` and `.realPath` use backslashes and fail T4.
- The neuron prim is `/Plexus/Neurons/<name>` in the edit layer, with all three prims `def`. Apply the schema at Sdf level: `spec.SetInfo("apiSchemas", Sdf.TokenListOp.Create(prependedItems=["PlexusNeuronAPI"]))`.
- Author with the schema's types: `plexus:state` is Token, `plexus:lastWake` is String (not a float), and `plexus:flag…` is String.
- The budget's mute writes `plexus:state = "muted"` and a `plexus:flag…` attribute there, saved.

**Paths.**
- `Sdf.Layer.CreateNew`, `Sdf.Layer.FindOrOpen`, `Usd.Stage.Open` and `Sdf.Reference` take a `str`, never a `pathlib.Path`: pass `str(path)`. A `Path` fails with `Boost.Python.ArgumentError: ... Layer.CreateNew(WindowsPath)` (checked on 26.5; run 8 attempt 1).

**Imports.**
- Import every `pxr` module a file names, at the top of that file: `from pxr import Sdf, Tf, Usd` (and `Plug` where it registers). A name used but not imported fails with `NameError: name 'Usd' is not defined` at the first call (run 6 attempt 1).

**Notices.**
- `Tf.Notice.Register(Usd.Notice.ObjectsChanged, self._on_notice, stage)` returns a listener. The notice type is `Usd.Notice.ObjectsChanged`, from `from pxr import Tf, Usd`; `Tf.Notice.ObjectsChanged` does not exist (run 5 attempt 4 failed T1 on it). Keep it on `self`, or it is collected and the callback never fires (checked on 26.5). `cool()` and `stop()` call `.Revoke()` on it.
- The callback receives two arguments, the notice and the sender: a method is `def _on_notice(self, notice, sender):`. With `def _on_notice(self, notice):` every authoring call fails with `TypeError: ..._on_notice() takes 2 positional arguments but 3 were given` (checked on 26.5; run 8 attempt 4).
- The callback runs synchronously on whichever thread authored: the test's main thread, or your own action thread mid-write. So it takes no lock. All it does is copy `n.GetChangedInfoOnlyPaths()` and `n.GetResyncedPaths()` into `frozenset`s of `Sdf.Path` (which is hashable), bump a pending counter, and enqueue. The notice is only valid during the callback.
- Count pending at enqueue, not at dispatch. `settle()` and T6 call `wait_idle` right after an authoring call returns, before the dispatcher has woken.
- Threads, events, locks and queues come from Python's `threading` and `queue` modules (`threading.Event()`, `threading.RLock()`, `queue.Queue()`), never from `pxr`: `Tf` has no `Event` and no `Token`. A stop flag is `self._stop_event = threading.Event()`. `Tf.Event()` and `Tf.Token()` fail with `AttributeError: module 'pxr.Tf' has no attribute ...` (checked on 26.5; run 8 attempts 2 and 3).
- The dispatcher blocks on `queue.get(timeout=...)` and closes the window 50 ms after the first event. That design measured T1 p95 = 52 ms against the 250 ms budget. Don't poll with long sleeps.

**What the kept S3 code still owes S4** (review of run 15 attempt 1, `9d7bb5f`, Nov 3). S3's target passes on it and the `predicate_smoke` gate holds; S4 sends `plexus/core/neuron.py` again, whole, with these fixed. Run 16 attempts 1 and 2 applied the S2 list above and nothing from this one: both left `_on_event` as `pass`, so no action ever ran, and T5's `Hints` prim never existed. Each item here is as binding as the S2 list:
- `NeuronHandle` is a plain `@dataclass` (not frozen) that the runtime mutates in place under its lock (`record.handle.wakes += 1`, `record.handle.state = ...`), or a class whose `wakes` and `state` are properties over the per-neuron record. The tests hold the object `register()` returned and read `h.wakes` and `h.state` from it later. `9d7bb5f` has `@dataclass(frozen=True)` with `wakes=0` baked in at `register()`, so `handle.wakes += 1` raises `FrozenInstanceError` and no wake can ever show.
- `register()` stores `self._neurons[name] = record` holding `compiled`, `scope`, `action`, the three budget numbers and `handle`, where `NeuronHandle` is a plain `@dataclass` (no `frozen=True`), so `handle.wakes += 1` works; the dispatcher reads that record. `_run_action(record, values)` builds `ctx = _Ctx(self, record)`, calls `record.action(ctx)` inside `try` / `except Exception: traceback.print_exc()`, and in `finally`, under the lock, sets `record.handle.state = "dormant"` and `self._running -= 1`. `wait_idle(timeout)` polls every 5 ms until `time.monotonic()` passes its deadline and returns `True` the first time `(self._axon is None or self._axon.idle()) and self._running == 0`, else `False`. `stop()` joins the live action threads, then calls `axon.cool()`. `9d7bb5f` computes `compiled` and drops it, never writes `self._neurons`, and keeps `action` and `scope` nowhere.
- `/Plexus` and `/Plexus/Neurons` are `def` too: after `Sdf.CreatePrimInLayer`, set `specifier = Sdf.SpecifierDef` on `edit_layer.GetPrimAtPath("/Plexus")` and on `.../Neurons`, as on the neuron prim. `Usd.PrimRange("/Plexus")` prunes an `over` subtree, so T6's record would be empty.
- `Predicate.eval`'s `changed` is an exact string match against `paths()`, so Python expands the event first: `changed = [p for p in pred.paths() if Sdf.Path(p) in ev.paths or any(Sdf.Path(p).HasPrefix(r) for r in ev.resynced)]` (the rule two paragraphs below). A resync at an ancestor never reaches Rust by itself.
- `seed` and `commit_wake` both take exactly the composed values of `Predicate.paths()`, read as `stage.GetAttributeAtPath(p).Get()` with `None` left out, and both get the same dict: `commit_wake` writes every numeric key it is given and a stale entry survives a commit whose values lack the key. Delta is measured from the last commit, not the last eval (commit at 1.3, then 1.45 is false, 1.0 is true, 1.55 is true); `eval` never writes the cache.
- The dispatcher lives in `_on_event` (`9d7bb5f`: `pass`; a reply that keeps the `pass`, or never calls the stored `action`, fails T5 with `GetPrimAtPath('/Exchange/lookNeuron/Hints')` null, because nothing is ever authored). In order, for each `record` in `self._neurons.values()`: skip it unless some path in `event.paths` or `event.resynced` has `HasPrefix(Sdf.Path(record.scope))`, or some `r` in `event.resynced` has `Sdf.Path(record.scope).HasPrefix(r)`; `changed = [p for p in record.compiled.paths() if Sdf.Path(p) in event.paths or any(Sdf.Path(p).HasPrefix(r) for r in event.resynced)]`; under the runtime lock, `values` holds `a.Get()` for each `p` in `record.compiled.paths()` where `a = self.stage.GetAttributeAtPath(p)` is valid and `a.Get()` is not `None`; if `record.compiled.eval(changed, values)` is `False`, continue; otherwise, still under the lock, `self._running += 1`, `record.handle.wakes += 1`, `record.handle.state = "awake"`, then `threading.Thread(target=self._run_action, args=(record, values), daemon=True).start()`. One runtime-wide `threading.RLock` guards every pxr read and write; `Sdf.ChangeBlock` wraps each authoring burst; `ctx.author` goes through `gate.py`.
- The allowlist is a list of `Sdf.Path` prim paths, never globs: `[Sdf.Path(f"/Exchange/{participant_id}")] + [Sdf.Path(g) for g in grants]`, and `ctx.author` allows `prim_path` when `Sdf.Path(prim_path).HasPrefix(allowed)` holds for one of them. The `/**` in CONTRACT.md and in this brief is wording for "and everything under it", which `HasPrefix` already means. Checked on 26.5: `Sdf.Path("/Exchange/lookNeuron/**")` is ill-formed, becomes `Sdf.Path.emptyPath` with a warning, `HasPrefix` of it is `False`, and every write is denied, T5's `Hints` write included (run 16's `gate.py` did exactly this).
- `ctx.author(prim_path, attr_name, value, type_name)`, in order: the allowlist check above (on deny: a `plexus:flag...` `String` on the neuron prim in `edit_layer`, `Save()`, return); then under the runtime lock, inside one `with Sdf.ChangeBlock():`, `spec = Sdf.CreatePrimInLayer(edit_layer, prim_path)`; for each `a` in `Sdf.Path(prim_path).GetPrefixes()`, `edit_layer.GetPrimAtPath(a).specifier = Sdf.SpecifierDef`; `attr = spec.attributes.get(attr_name) or Sdf.AttributeSpec(spec, attr_name, type_name)` and `attr.default = value`; the same `.get(...) or` idiom for `plexus:sourceLayer` (`Sdf.ValueTypeNames.String`, value `edit_layer.identifier`); after the block, still under the lock, `edit_layer.Save()`. Checked on 26.5: `Sdf.AttributeSpec` on a name that already exists raises `Tf.ErrorException` ("Cannot create spec ... because it already exists"), so the `.get or` idiom, the one `_support.py` uses for `temperature`, is what lets a second wake author.
- The axon's pending counter subtracts the number of notices drained into each window, not 1 per window: two notices in one window otherwise leave `idle()` false forever and `settle` asserts "runtime did not go idle". A `ctx.author` outside a `ChangeBlock` sends up to six notices in microseconds.
- The axon may be created in `__init__` or in `start()` (`9d7bb5f` creates it in `start()`); `start()` is idempotent either way, and `register()` before `start()` must not wake anything.
- Known gaps left for later, not S4's: `in_scope` rejects descendants (`/Exchange/LookState/Child.x`; S5 may fix it); `changed(P)AND delta(P)` with no space compiles; bare tokens and `true`/`false` do not parse as `attr` literals; `!=` across kinds is false.

**What a notice carries, measured on 26.5** (resynced | info-only):
- A changes `temperature` (an existing attribute): `| /Exchange/LookState.temperature`. The same value again sends no notice. `Save()` sends none.
- First write of a new prim into a layer: a resync at the highest prim that is new to that layer (`/Exchange` if the layer had no `/Exchange` spec).
- New attribute on an existing prim: a resync at the attribute path.
- Sublayer appended to an open stage: `| /`.
- `Layer.Reload()` that picked up another process's edit (T6): `| /, /Exchange/LookState.temperature`. T6's only wake comes from this notice.
- `Reload()` returns False and sends nothing when the file's mtime is unchanged. Ar's timestamp on Windows is whole seconds.

So an event is in a neuron's scope when one of its paths `HasPrefix(scope)`, or a resynced path is an ancestor of scope. An info-only `/` never puts an event in scope by itself. `changed(P)` is true when `P` is in the info-only set, or `P` or one of its ancestors is resynced.

**What the kept S2 code still owes S4** (review of run 9 attempt 4, Nov 2). T1 passes on it, but S4's `wait_idle` cannot be built on it as it stands. S4 sends `plexus/core/axon.py`, `plexus/membrane/exchange.py` and `plexus/core/stagekit.py` again, whole, with these fixed:
- `axon.py`: the queue is a plain list popped by a loop that sleeps `debounce_s` when it is empty, so there is no real 50 ms window and nothing to wait on. Replace it with `queue.Queue()`; the dispatcher blocks on `get(timeout=0.1)`, then drains with `get(timeout=remaining)` until 50 ms after that first event.
- `axon.py`: there is no pending counter. Add one: `+1` per notice in the callback at enqueue; after every subscriber has returned for the coalesced event, subtract the number of notices drained into that window, so two notices in one window bring it back to 0. The runtime's subscriber marks an action as running before it starts the action thread and returns. Expose `idle() -> bool` (pending is 0 and no window is open) for the runtime's `wait_idle` to poll alongside its running actions.
- `axon.py`: `_on_notice` still does `with self._queue_lock:`. Drop that lock and the `_queue_lock` attribute; `queue.Queue.put` is thread-safe on its own.
- `axon.py`: a subscriber exception is swallowed with `pass`. Print it with `traceback.print_exc()` to stderr and keep dispatching, so a failing action shows in the test output.
- `axon.py`: `cool()` sets the stop flag and joins, dropping whatever is queued. Revoke the listener first, then let the dispatcher deliver what is already queued before it exits.
- `exchange.py`: the new `from_<id>.usda` holds only `def "Exchange"`. Add the `def "<id>"` child under it (see "Membrane and stage"), with a variable such as `f"/Exchange/{participant_id}"`.
- `exchange.py`: the plugin is registered from a hand-built path. Use `from plexus.schema import plugin_dir` and `Plug.Registry().RegisterPlugins(str(plugin_dir()))`.
- `exchange.py` and `stagekit.py` import `Path` a second time inside a function; delete those inner imports.

**Dataclasses.** A dict or set default must be `field(default_factory=dict)` (or `frozenset()` for frozensets); a literal `{}` default raises when the class is defined.

**Budget order.** Evaluate the predicate first. On a match, `v = budget.peek(now)`:
- `v != "wake"`: call `budget.admit(now)` anyway. That records the trip, and the third consecutive trip returns `"mute"`; on `"mute"` author `plexus:state = "muted"` and a `plexus:flag…` attribute on the neuron prim, saved. No action runs.
- `v == "wake"`: if the runtime's global budget `peek(now)` is not `"wake"`, drop the wake and charge nothing. Otherwise `admit(now)` on both budgets, `predicate.commit_wake(values)`, then run the action.

A wake resets the trip count; once muted, `admit` keeps returning `"mute"`. Checked: `Budget(1, 10.0)` admitted at t = 1000, 1002, 1004, 1006 returns wake, trip, trip, mute, which is T3's sequence.

**One lock for pxr writes.**
- On 26.5, two threads authoring and saving different layers at once killed the interpreter: exit code 3, no traceback, nothing on stderr. One `threading.RLock` around every Sdf author and Save fixed it.
- The dispatcher (which writes mute and state) and every action thread take that one runtime-wide lock for each author-plus-Save and for each composed-value read.
- The notice callback never takes it.
