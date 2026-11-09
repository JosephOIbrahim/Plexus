# Plexus acceptance tests: the Python surface they pin

These tests turn Engineering Spec v2.1 §3, §9 and §10 (T1 to T8) into code. They are **frozen**: the build harness may never change anything under `tests/acceptance/`. Joe may.

The spec names modules (§2) but not functions. To test behaviour, the tests need a small Python surface, and this file is that surface. Everything below it is free: Python, Rust through `plexus._core`, or both. The tests only ever call what is listed here, read composed values back through plain `pxr`, and author "project A" opinions with plain `Sdf`, so any USD writer counts as a participant.

`phase1/` is the slice (the §3 schema gate and T1 to T6). It is the first harness mission. `phase2/` is T7, T8 and `test_organ_surface.py`, which reads what the organ contract promises and those two leave unread, for the mission after it. `live/` holds what needs a real engine: `test_organ_live.py` runs the Cozy organ against a running ComfyUI. Its tests are marked `integration`, skip and say why when no ComfyUI answers, and stay out of CI and out of the harness's score. `pending/` holds T1b, the two-process version of T1. It stays skipped and uncounted until the event transport is decided.

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
- `ctx.author_asset` reads `record.path`, `record.sha256` and `record.metadata`, and imports nothing from `plexus.organs`. It authors the thirteen `PlexusAssetAPI` attributes of §3 with the record's values, `plexus:retryOf` empty and `plexus:retryReason` `none`, and authors `plexus:seed`, `plexus:colorspace` and `plexus:createdAt` only when their keys are in `metadata`. A value that cannot land raises on the action's thread with nothing authored.

## `plexus.core.predicate` (§4)

- `PredicateError` — raised for bad syntax or an out-of-scope path.

## `plexus.organs` (§8, phase 2)

- `plexus.organs.protocol.Job(graph: dict, seed: int, colorspace: str, correlation_id: str, inputs: dict = {})`.
- `plexus.organs.protocol.AssetRecord` with `.path` (Path), `.sha256` (str) and `.metadata` (dict holding at least `engine`, `engineJobId`, `envFingerprint`, `organVersion`, `modelHashes`).
- `plexus.organs.cozy.CozyOrgan(endpoint: str, output_dir: Path)` implementing `profile()`, `capabilities()`, `submit(job) -> JobHandle`, `stream(handle)` and `result(handle) -> AssetRecord`.
- `JobHandle.correlation_id` is the job's own `correlation_id`. The handle carries nothing engine-side that core reads (Patch 01-C): no engine job id leaves the organ except as `AssetRecord.metadata["engineJobId"]`.
- `plexus.organs.protocol.OrganError` is the one error core sees from an organ. `capabilities()`, `submit()`, `stream()` and `result()` raise it when the engine refuses a job, fails it, cannot be reached or runs past the deadline, when `submit()` meets a class the engine lacks, a seed `plexus:seed` cannot hold or a colorspace §3 does not allow, when a handle names a job the organ does not hold, and when the engine's reply cannot be read: a body that is not JSON, a reply without the field the organ reads, a graph node without `inputs`, or a seed that is not an `int`. A call never waits past the job's deadline for one HTTP reply.
- `plexus.organs.cozy.CozyOrgan` also takes the keyword arguments `poll_s: float = 0.2` and `deadline_s: float = 3600.0`. `stream()` and `result()` read the engine's history every `poll_s`, and past `deadline_s` they raise `OrganError`, because a timeout voids a job rather than hanging it.
- `plexus.organs.protocol.JobHandle(correlation_id: str)`. A test builds one by hand to ask about a job the organ never saw.
- `plexus.organs.protocol.Progress` with `.correlation_id` and `.state`, one of `"queued"`, `"done"` or `"failed"`. `stream(handle)` yields `"queued"` on each poll while history lacks the job, then `"done"` or `"failed"` once.
- `plexus.organs.protocol.OrganProfile` with `.organ_id`, `.kind`, `.endpoint`, `.capabilities` and `.cost_hint`, the `PlexusOrganAPI` fields of §3. `capabilities()` names each class in the engine's `/object_info`.
- `plexus.organs.protocol.AssetRecord(path: Path, sha256: str, metadata: dict)` is also how a test builds a record by hand. From the organ, `metadata["engine"]` is the organ id, `metadata["modelHashes"]` holds no hash without a source, and `metadata` also holds `colorspace`, `createdAt`, an ISO-8601 time, and `seed` only when the organ wrote a seed into the graph.
- `result()` returns only once the engine's history has the job and the file is on disk. `AssetRecord.path` is a local file whose SHA-256 is `.sha256`. `metadata["envFingerprint"]` is non-empty and changes when the engine's environment does.

## Proof that the tests are passable

On Nov 1 a throwaway Python prototype (about 350 lines, not committed) passed all 18 tests here on usd-core 26.5, three runs in a row. Deliberately broken versions failed as they should: an engine term in `plexus/core`, an organ that trusts the first `/history` read, and a constant `envFingerprint`.

## What the tests deliberately leave open

How events cross processes, how the predicate is compiled, where the scheduler runs, and whether any of it is Rust. Spec v2.1 and Blueprint v5.2 decide those, not the tests.

`test_organ_surface.py` leaves open which asset wins when a second lands on one prim, and what a second job under one correlation id gets, past the first handle keeping its own job. Both wait for the retry mission under Patch 01-D.
