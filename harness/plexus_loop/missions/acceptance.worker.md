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

**pyo3 0.30 (checked: pyo3 0.30.1, abi3-py311, Python 3.14.2, cargo 1.99.1).** Older pyo3 idioms do not compile. `PyObject` no longer exists (use `Py<PyAny>` or `&Bound<'_, PyDict>`). `fn _core(py: Python, m: &PyModule)` fails. `py.get_type_bound::<T>()` fails. Write `py.rs` whole, from this file (in S3, leave out the three `PyBudget` pieces; S7 adds them):

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

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("PredicateError", m.py().get_type::<PredicateError>())?;
    m.add_class::<PyPredicate>()?;
    m.add_class::<PyBudget>()?;
    m.add_function(wrap_pyfunction!(compile_predicate, m)?)?;
    Ok(())
}
```

What this fixes for the other files:
- `predicate.rs` must provide `pub enum Value { Num(f64), Str(String), Bool(bool) }`, `pub fn compile(source: &str, scope: &str) -> Result<Predicate, String>`, and `Predicate` methods `paths(&self) -> Vec<String>`, `seed(&mut self, &HashMap<String, Value>)`, `eval(&self, &[String], &HashMap<String, Value>) -> bool` and `commit_wake(&mut self, &HashMap<String, Value>)`.
- The `#[pyclass(name = ...)]` wrappers keep the Rust struct names free. Pyclass fields must be thread-safe: no `Rc`, `RefCell` or `Cell`; mutate through `&mut self`.
- A key missing from `values` means the attribute has no value. Python passes `changed` as a list of `str(path)`.

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
- The callback runs synchronously on whichever thread authored: the test's main thread, or your own action thread mid-write. So it takes no lock. All it does is copy `n.GetChangedInfoOnlyPaths()` and `n.GetResyncedPaths()` into `frozenset`s of `Sdf.Path` (which is hashable), bump a pending counter, and enqueue. The notice is only valid during the callback.
- Count pending at enqueue, not at dispatch. `settle()` and T6 call `wait_idle` right after an authoring call returns, before the dispatcher has woken.
- The dispatcher blocks on `queue.get(timeout=...)` and closes the window 50 ms after the first event. That design measured T1 p95 = 52 ms against the 250 ms budget. Don't poll with long sleeps.

**What a notice carries, measured on 26.5** (resynced | info-only):
- A changes `temperature` (an existing attribute): `| /Exchange/LookState.temperature`. The same value again sends no notice. `Save()` sends none.
- First write of a new prim into a layer: a resync at the highest prim that is new to that layer (`/Exchange` if the layer had no `/Exchange` spec).
- New attribute on an existing prim: a resync at the attribute path.
- Sublayer appended to an open stage: `| /`.
- `Layer.Reload()` that picked up another process's edit (T6): `| /, /Exchange/LookState.temperature`. T6's only wake comes from this notice.
- `Reload()` returns False and sends nothing when the file's mtime is unchanged. Ar's timestamp on Windows is whole seconds.

So an event is in a neuron's scope when one of its paths `HasPrefix(scope)`, or a resynced path is an ancestor of scope. An info-only `/` never puts an event in scope by itself. `changed(P)` is true when `P` is in the info-only set, or `P` or one of its ancestors is resynced.

**Dataclasses.** A dict or set default must be `field(default_factory=dict)` (or `frozenset()` for frozensets); a literal `{}` default raises when the class is defined.

**Budget order.** Evaluate the predicate first. On a match, `v = budget.peek(now)`:
- `v != "wake"`: call `budget.admit(now)` anyway. That records the trip, and the third consecutive trip returns `"mute"`; on `"mute"` author `plexus:state = "muted"` and a `plexus:flag…` attribute on the neuron prim, saved. No action runs.
- `v == "wake"`: if the runtime's global budget `peek(now)` is not `"wake"`, drop the wake and charge nothing. Otherwise `admit(now)` on both budgets, `predicate.commit_wake(values)`, then run the action.

A wake resets the trip count; once muted, `admit` keeps returning `"mute"`. Checked: `Budget(1, 10.0)` admitted at t = 1000, 1002, 1004, 1006 returns wake, trip, trip, mute, which is T3's sequence.

**One lock for pxr writes.**
- On 26.5, two threads authoring and saving different layers at once killed the interpreter: exit code 3, no traceback, nothing on stderr. One `threading.RLock` around every Sdf author and Save fixed it.
- The dispatcher (which writes mute and state) and every action thread take that one runtime-wide lock for each author-plus-Save and for each composed-value read.
- The notice callback never takes it.
