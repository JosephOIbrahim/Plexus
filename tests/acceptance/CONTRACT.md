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
  - `publish_organ(profile) -> Sdf.Path` — defines `/Plexus/Organs/<organId>` with `PlexusOrganAPI` in the edit layer and saves it as it lands, so a neuron reading the composed exchange, in any participant's runtime, sees the engine. It reads `profile.organ_id`, `.kind`, `.endpoint`, `.capabilities` and `.cost_hint`, imports nothing from `plexus.organs` and names no engine. It authors the five `PlexusOrganAPI` attributes of §3 and nothing else, each value as given, with `plexus:capabilities` sorted by code point as Python's `sorted()` orders it, defines (`def`, not `over`) every missing ancestor, and returns the prim's `Sdf.Path`. A second publish of one organ id replaces all five values in the edit layer. When two participants publish one organ id, the stronger sublayer's opinion is the one that composes. It may be called before or after `start()`. A field of the wrong type raises `TypeError` (`organ_id`, `kind`, `endpoint` and `cost_hint` are each a `str`, and `capabilities` a `list` or `tuple` of `str`); a kind or cost hint outside the allowed tokens that `Usd.SchemaRegistry` holds for `PlexusOrganAPI`, or an organ id that is not a valid prim name, raises `ValueError`; a schema registry without `PlexusOrganAPI` raises `RuntimeError`; any other value Sdf cannot hold raises. Each raises with nothing authored.
  - `publish_organ_state(organ_id: str, state: str) -> Sdf.Path` — authors one token attribute, `plexus:lifecycle`, holding `state`, on `/Plexus/Organs/<organId>` in the edit layer and saves it as it lands, so a neuron in this process scoped on the organ wakes on it; `state` is one of `"stopped"`, `"starting"`, `"ready"` or `"unavailable"`. It writes only for an organ whose prim this runtime's own edit layer holds with `PlexusOrganAPI`, so `publish_organ` comes first; it authors nothing else (no API schema, none of the five `PlexusOrganAPI` attributes, no `plexus:sourceLayer`), a later `publish_organ` of that organ leaves `plexus:lifecycle` as it is, and it imports nothing from `plexus.organs`, names no engine and returns the prim's `Sdf.Path`. A non-`str` organ id or state raises `TypeError`; a state outside those four, an organ id that is not a valid prim name, or an organ this runtime's edit layer has not published raises `ValueError`; each raises with nothing authored.
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
- `submit()` also raises `OrganError`, before anything is posted, when the job's graph holds a value JSON cannot write (an object, a set, a cycle).
- `plexus.organs.cozy.CozyOrgan` also takes the keyword arguments `poll_s: float = 0.2` and `deadline_s: float = 3600.0`. `stream()` and `result()` read the engine's history every `poll_s`, and past `deadline_s` they raise `OrganError`, because a timeout voids a job rather than hanging it.
- `plexus.organs.protocol.JobHandle(correlation_id: str)`. A test builds one by hand to ask about a job the organ never saw.
- `plexus.organs.protocol.Progress` with `.correlation_id` and `.state`, one of `"queued"`, `"done"` or `"failed"`. `stream(handle)` yields `"queued"` on each poll while history lacks the job, then `"done"` or `"failed"` once.
- `plexus.organs.protocol.OrganProfile` with `.organ_id`, `.kind`, `.endpoint`, `.capabilities` and `.cost_hint`, the `PlexusOrganAPI` fields of §3. `capabilities()` names each class in the engine's `/object_info`.
- `plexus.organs.protocol.AssetRecord(path: Path, sha256: str, metadata: dict)` is also how a test builds a record by hand. From the organ, `metadata["engine"]` is the organ id, `metadata["modelHashes"]` holds no hash without a source, and `metadata` also holds `colorspace`, `createdAt`, an ISO-8601 time, and `seed` only when the organ wrote a seed into the graph.
- `result()` returns only once the engine's history has the job and the file is on disk. `AssetRecord.path` is a local file whose SHA-256 is `.sha256`. `metadata["envFingerprint"]` is non-empty and changes when the engine's environment does.
- `plexus.organs.cozy.CozyLifecycle(workspace: Path, port: int, *, command: Sequence[str], report: Callable[[str], object], extra: Sequence[str] = (), log: Path | None = None, ready_s: float = 300.0, stop_s: float = 30.0, poll_s: float = 0.5)` starts, stops and measures one ComfyUI on `127.0.0.1:<port>` through comfy-cli; it sits beside the organ contract, not in it (`Organ` gains nothing), so a host calls it and a neuron never does; `.endpoint` is `http://127.0.0.1:<port>`.
- A measurement reads `"ready"` when the port answers `GET /system_stats` with a JSON object holding a `system` object, `"unavailable"` when anything else answers there, and, when nothing accepts a connection, `"starting"` while a process this lifecycle started is alive and `"stopped"` otherwise; `probe()` measures, calls `report(state)` and returns the state, and the constructor probes once, so a state an earlier process left in the saved edit layer is replaced by a measurement before the constructor returns.
- `start()` reports and returns `"ready"` when the port already answers as ComfyUI, spawning nothing; when something else answers on the port, or `<workspace>/main.py` is not a file, it reports `"unavailable"` and raises `OrganError` naming the port or the path, spawning nothing.
- Otherwise it reports `"starting"`, runs `[*command, "--skip-prompt", f"--workspace={workspace}", "launch", "--", "--listen", "127.0.0.1", "--port", str(port), *extra]` in the foreground with stdin at end of file and stdout and stderr appended to `log` (discarded when `log` is None), and returns `"ready"` once a measurement reads it; when that process exits first, or `ready_s` passes, after which it kills the tree, it reports `"unavailable"` and raises `OrganError`; while a process this lifecycle started is still alive, a further `start()` spawns nothing more and waits on that process the same way.
- The child's environment sets `COMFY_NO_TELEMETRY` and `DO_NOT_TRACK` to `1` and leaves out `COMFY_CLI_BACKGROUND`, `COMFY_OUTPUT`, `VIRTUAL_ENV`, `CONDA_PREFIX`, `PYTHONPATH`, `PYTHONHOME` and `PXR_PLUGINPATH_NAME`, and the lifecycle runs `command` once per start and never for comfy-cli's `--background` launch or `comfy stop`, which act on whatever process comfy-cli's user-wide config names.
- `stop()` kills the process tree its own `start()` spawned, root and descendants together and nothing else, returns once the port no longer accepts a connection, and reports and returns `"stopped"`; with no such tree (it never spawned one, the engine was already answering, or it already stopped it) it raises `OrganError` and touches nothing.
- `report` runs on the thread that called the constructor, `probe()`, `start()` or `stop()`, and no thread of the lifecycle's own writes anything; an exception from `report` reaches that caller, and a tree already spawned stays this lifecycle's, so `stop()` still ends it.
- A host bridges the two with `report=lambda state: runtime.publish_organ_state(organ_id, state)` after `runtime.publish_organ(profile)`; the frozen tests run `command` as `[sys.executable, <fake script>]` on ports the operating system hands out, never the real comfy-cli and never port 8188.

## Proof that the tests are passable

On Nov 1 a throwaway Python prototype (about 350 lines, not committed) passed all 18 tests here on usd-core 26.5, three runs in a row. Deliberately broken versions failed as they should: an engine term in `plexus/core`, an organ that trusts the first `/history` read, and a constant `envFingerprint`.

## What the tests deliberately leave open

How events cross processes, how the predicate is compiled, where the scheduler runs, and whether any of it is Rust. Spec v2.1 and Blueprint v5.2 decide those, not the tests.

`test_organ_surface.py` leaves open which asset wins when a second lands on one prim, and what a second job under one correlation id gets, past the first handle keeping its own job. Both wait for the retry mission under Patch 01-D.

- Cross-process wakes on `plexus:lifecycle` wait for T1b. A watcher between calls, a start lock shared between hosts, adopting an engine a dead host left, cancel, and engine pools wait for later missions.
