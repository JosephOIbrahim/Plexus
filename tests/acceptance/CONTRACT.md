# Plexus acceptance tests: the Python surface they pin

These tests turn Engineering Spec v2.1 §3, §9 and §10 (T1 to T8) into code. They are **frozen**: the build harness may never change anything under `tests/acceptance/`. Joe may.

The spec names modules (§2) but not functions. To test behaviour, the tests need a small Python surface, and this file is that surface. Everything below it is free: Python, Rust through `plexus._core`, or both. The tests only ever call what is listed here, read composed values back through plain `pxr`, and author "project A" opinions with plain `Sdf`, so any USD writer counts as a participant.

`phase1/` is the slice (the §3 schema gate and T1 to T6). It is the first harness mission. `phase2/` is T7 and T8, for the mission after it.

## `plexus.schema`

- `plugin_dir() -> pathlib.Path` — the directory holding `plugInfo.json` and `generatedSchema.usda` for the four codeless API schemas (§3). Pointing `PXR_PLUGINPATH_NAME` at it before `pxr` loads must register them.

## `plexus.membrane.exchange` (§7)

- `create_exchange(directory: Path) -> Path` — writes `directory/exchange.usda` with an `/Exchange` prim and an empty sublayer list. Returns the path. Idempotent.
- `register_participant(exchange: Path, participant_id: str, grants: Sequence[str] = ()) -> Path` — appends `from_<participantId>.usda` as the **weakest** sublayer and returns its path. Idempotent. The participant's publication allowlist is `/Exchange/<participantId>/**` plus each granted prim path and its subtree.
- `participants(exchange: Path) -> list[str]` — participant ids, strongest first, read from `exchange.usda` itself.

## `plexus.core.stagekit`

- `create_project(path: Path, exchange: Path, project_id: str) -> Path` — writes a project root layer whose `/Exchange` prim references the composed exchange root (§7.2), weaker than local opinions, and whose `/Project` prim has `PlexusProjectAPI` applied with `plexus:projectId` set.

## `plexus.core.axon` (§5)

- `StageEvent` — a dataclass with `paths: frozenset[Sdf.Path]`, `resynced: frozenset[Sdf.Path]` and `t: float`.
- `PlexusAxon(stage, debounce_s: float = 0.05)` with `subscribe(callback)`, `start()` and `cool()`. Callbacks receive coalesced `StageEvent`s on the dispatcher thread, never inside the notice callback.

## `plexus.core.neuron` (§6)

- `NeuronRuntime(exchange: Path, participant_id: str, *, clock=time.monotonic, global_wakes_per_min: int = 60)` — opens the composed exchange as its stage, registers itself as a participant, and runs an axon on that stage.
  - `.stage` — the runtime's `Usd.Stage`.
  - `.edit_layer` — the participant's `Sdf.Layer`; every opinion the runtime or its neurons author lands here and nowhere else (A6), and is saved to disk as it lands (T6).
  - `register(name, *, scope, predicate, action, budget_wakes, budget_window, budget_tokens=0, tools=()) -> NeuronHandle` — defines `/Plexus/Neurons/<name>` with `PlexusNeuronAPI` in the edit layer and compiles the predicate. A malformed predicate, or a path outside `scope`, raises `plexus.core.predicate.PredicateError` here, not at fire time.
  - `start()`, `stop()`, and `wait_idle(timeout: float) -> bool` (true once no event is pending, no debounce window is open and no action is running).
- `NeuronHandle` — `.name`, `.prim_path` (an `Sdf.Path`), `.wakes` (an int count), `.state` (`"dormant"`, `"awake"` or `"muted"`).
- An action is `action(ctx) -> None`. `ctx.author(prim_path, attr_name, value, type_name)` authors one attribute through the publication gate (§7.3) into the edit layer and stamps `plexus:sourceLayer` on that prim with the edit layer's identifier. `type_name` is an `Sdf.ValueTypeNames` member. A write outside the allowlist is dropped, and the neuron prim gets an attribute whose name starts with `plexus:flag`. `ctx.author_asset(prim_path, record)` authors an `AssetRecord` as a `PlexusAssetAPI` prim the same way. Both define (`def`, not `over`) any missing ancestor of the target prim in the edit layer, so the opinion shows up in ordinary stage traversal (T6 dumps with `Usd.PrimRange`).

## `plexus.core.predicate` (§4)

- `PredicateError` — raised for bad syntax or an out-of-scope path.

## `plexus.organs` (§8, phase 2)

- `plexus.organs.protocol.Job(graph: dict, seed: int, colorspace: str, correlation_id: str, inputs: dict = {})`.
- `plexus.organs.protocol.AssetRecord` with `.path` (Path), `.sha256` (str) and `.metadata` (dict holding at least `engine`, `engineJobId`, `envFingerprint`, `organVersion`, `modelHashes`).
- `plexus.organs.cozy.CozyOrgan(endpoint: str, output_dir: Path)` implementing `profile()`, `capabilities()`, `submit(job) -> JobHandle`, `stream(handle)` and `result(handle) -> AssetRecord`.
- `JobHandle.correlation_id` is the job's own `correlation_id`. The handle carries nothing engine-side that core reads (Patch 01-C): no engine job id leaves the organ except as `AssetRecord.metadata["engineJobId"]`.
- `result()` returns only once the engine's history has the job and the file is on disk. `AssetRecord.path` is a local file whose SHA-256 is `.sha256`. `metadata["envFingerprint"]` is non-empty and changes when the engine's environment does.

## Proof that the tests are passable

On Nov 1 a throwaway Python prototype (about 350 lines, not committed) passed all 18 tests here on usd-core 26.5, three runs in a row. Deliberately broken versions failed as they should: an engine term in `plexus/core`, an organ that trusts the first `/history` read, and a constant `envFingerprint`.

## What the tests deliberately leave open

How events cross processes, how the predicate is compiled, where the scheduler runs, and whether any of it is Rust. Spec v2.1 and Blueprint v5.2 decide those, not the tests.
