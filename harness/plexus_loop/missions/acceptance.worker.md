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

## What exists already

- `plexus/__init__.py` (empty package) and `crates/plexus-core` (a Cargo crate whose `py.rs` holds an empty PyO3 module `plexus._core` with `__version__`). The `core` gate builds it and copies the library to `plexus/_core.pyd`; you never build anything yourself.
- `tests/acceptance/CONTRACT.md` is the exact Python surface the tests call. Match its names and signatures.

## The split (Option B for phase 1, staged)

- **Python owns everything in phase 1.** The `Tf.Notice` callback, the event queue, one dispatcher thread with a 50 ms debounce, action worker threads, `wait_idle`, reading composed values, authoring, saving, the path allowlist gate, and the pure logic too: the predicate and the budget.
- `plexus/core/predicate.py` (no `pxr` import) holds `class PredicateError(ValueError)`, `compile_predicate(source: str, scope: str) -> Predicate`, and `class Predicate` with `paths() -> list[str]`, `seed(values: dict) -> None`, `eval(changed: list[str], values: dict) -> bool` and `commit_wake(values: dict) -> None`. `values` maps a path to `float | int | bool | str`; a missing key means no value.
- `plexus/core/budget.py` (no `pxr` import, no clock) holds `class Budget(wakes: int, window_s: float)` with `peek(now: float) -> str` (pure) and `admit(now: float) -> str`, each `"wake"`, `"trip"` or `"mute"`. The runtime passes `now` from its injected clock.
- Nothing under `crates/` changes in phase 1: `crates/**`, `Cargo.toml` and `Cargo.lock` are frozen. The scaffold crate still builds in the `core` and `cargo` gates, and `plexus/_core.pyd` keeps its `__version__` only. The Rust port is its own mission later, behind this same surface; `docs/plexus/drafts/port_rust_brief.md` keeps its facts.

## Rules the gates enforce

- Change only `plexus/**`. `crates/**`, `Cargo.toml` and `Cargo.lock` are frozen for phase 1.
- Never import `agent`, `cognitive` or anything from them, at any scope. Never copy code from them.
- No engine vocabulary anywhere under `plexus/` or `crates/` (the T8 test scans `.py .rs .toml .json .usda`): not `cfg`, `KSampler`, `prompt_id`, `class_type`, `SaveImage`, `LoadImage` or other ComfyUI node names. In Rust, `#[cfg(...)]` attributes are fine; the word `cfg` anywhere else is not. No `[target.'cfg(...)']` table in any Cargo.toml and no `build.rs`.
- Modules that must not import `pxr`: `plexus/__init__.py`, `plexus/schema`, `plexus/core/__init__.py`, `plexus/core/predicate.py`, `plexus/membrane/__init__.py`, `plexus/organs/__init__.py`. No import cycles.
- **Package `__init__.py` files hold a docstring only.** `plexus/core/__init__.py` and `plexus/membrane/__init__.py` are created with nothing but a docstring, and `plexus/__init__.py` is never edited. Import submodules directly (`from plexus.core.axon import PlexusAxon`), never through the package.
- `plexus/core/axon.py` and `plexus/core/stagekit.py` never import each other: the axon watches any stage it is given, and stagekit only writes layers.
- **Placeholders are wording, never code.** In this brief and the step text, `<id>`, `<participant>`, `<name>` and `<exchange.usda path>` stand for a value. In code they become a variable inside an f-string, such as `f"from_{participant_id}.usda"`, never part of a name: `from_<id> = ...` is a syntax error, and the whole attempt is dropped for it. Every `.py` file you send must compile.

## Facts you would otherwise learn by failing

**The Python predicate (S3) and budget (S7), as rules.** `compile_predicate` parses `clause { "AND" clause }`, where a clause is `changed(path)`, `delta(path) cmp number`, `attr(path) cmp literal` or `exists(path)` and `cmp` is one of `> >= < <= == !=`; `OR`, trailing text or an unknown clause raises `PredicateError`. A path is inside the scope when the part before its first `.` equals the scope or starts with the scope followed by `/` (a plain `startswith(scope)` would accept `/Exchange/LookStateX` for `/Exchange/LookState`); an outside path raises `PredicateError` at compile time, never at fire time. `paths()` lists every path the clauses name, once each, in first-appearance order. The delta cache maps a path to the number last committed; only `seed` and `commit_wake` write it and `eval` only reads it, so sub-threshold changes accumulate until a wake commits them. `eval` holds when every clause holds: `changed` when the path is in the event's list; `delta` when the path has a numeric value, the cache has one, and `abs(value - cached) cmp number` holds; `attr` when the composed value compares as asked (numbers as numbers; strings and bools only with `==` and `!=`; different kinds are never equal); `exists` when the path has a value. Compare numbers as floats and never truncate them. Parse a number with `float(text)` and raise `PredicateError` on `ValueError`. The budget: a wake at `t` counts while `now < t + window_s`; `admit(now)` returns `"wake"` when fewer than `wakes` wakes are live and records this one, `"trip"` otherwise and counts it, and `"mute"` on the third consecutive trip and forever after; a wake resets the trip count; `peek(now)` returns what `admit(now)` would return without recording anything.

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
