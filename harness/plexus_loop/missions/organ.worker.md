# Worker brief: mission `organ`

You make one change per attempt. The harness keeps it only if every gate passes and at least one more test in `tests/acceptance/phase2` passes. The prompt names the one step this attempt is for. Do that step only, and send every file that step names.

**Every attempt starts from the last kept commit.** A dropped attempt's files are gone. When the prompt says why the last attempt was dropped, fix that cause and resend the whole step: every file the step names, each as a whole-file block.

## How to reply

- One fenced block per file, whose info string is `file:` plus the path, holding the whole file:

```file:plexus/organs/protocol.py
"""The organ contract."""
...the complete file...
```

- Send whole files in this mission, never a diff. Every line you keep is in the file you send: no commentary, no placeholder and no `...` standing for lines you kept.
- Write no new Rust test and no test of your own in any language. The frozen tests are the judge, and a test of yours has only ever cost attempts.
- **Placeholders are wording, never code.** In this brief and the step text, `<id>` and `<prompt_id>` stand for a value. In code they become a variable inside an f-string. Every `.py` file you send must compile.

## What exists already

- Phase 1 is done and every one of its tests passes. `plexus/core/neuron.py` is under Files: `NeuronRuntime`, `_Ctx.author`, the helper `_set_attr`, `_author_on_neuron`, and `_save_refused`, which flags a refused Save on the neuron instead of printing. The `core` gate builds `plexus/_core.pyd`; you never build anything yourself.
- `tests/acceptance/CONTRACT.md` is the exact Python surface the tests call. Match its names and signatures.
- `tests/acceptance/phase2/test_t7_round_trip.py` is under Files. Its `FakeComfy` is the engine for this mission, so nothing here needs a real ComfyUI.
- `tests/acceptance/phase2/test_organ_surface.py` is frozen too, and it is not under Files. It reads nearly every clause of each step that T7 and T8 do not, and the few it leaves unread are required all the same. It runs the organ with a small `poll_s` and `deadline_s` against a fake engine of its own, which also refuses a graph, fails a job, drops a connection and shows a preview. Each test's name says the clause it reads, and a test's failure text says what to change.

## Rules the gates enforce

- Change only `plexus/organs/**` and `plexus/core/neuron.py`. Any other path drops the attempt before anything runs, `crates/**` and `Cargo.toml` included: this mission changes no Rust.
- Never import `agent`, `cognitive` or anything from them, at any scope, or the `layers` gate fails with "Comfy-Cozy is a reference only".
- T8 reads every line of every `.py`, `.pyi`, `.rs`, `.usda`, `.json` and `.toml` file under `plexus/` and `crates/` except `plexus/organs/cozy.py`, comments and strings included. `plexus/organs/protocol.py`, `plexus/organs/__init__.py` and `plexus/core/neuron.py` must never name `prompt_id`, `class_type`, `cfg`, `KSampler`, `CheckpointLoaderSimple`, `CLIPTextEncode`, `VAEDecode`, `VAEEncode`, `EmptyLatentImage`, `SaveImage`, `LoadImage`, `LoraLoader` or `ControlNetApply`. A hit fails with "engine vocabulary leaked into the core" and names the file and the line. Those words are free inside `cozy.py` and nowhere else.
- `plexus/organs/protocol.py`, `plexus/organs/__init__.py` and `plexus/organs/cozy.py` never import `pxr`, or the `layers` gate fails with "these modules must stay free of pxr". The caller authors, never the organ.
- `plexus/organs/__init__.py` holds one docstring and nothing else, or the `layers` gate fails with "package __init__.py files hold a docstring only".
- `plexus/core/neuron.py` never imports `plexus.organs.cozy`, at any scope, or the `layers` gate fails with "plexus.core.neuron imports plexus.organs.cozy".
- The `neuron_unchanged` gate compares the code of `plexus/core/neuron.py` with the last kept commit. It passes only when every class, function and statement stands and the one thing gained is `_Ctx.author_asset`. Comments, blank lines, docstrings and the order of the imports do not count. A new import or a new helper drops the attempt, so start again from the copy of `neuron.py` in this prompt and add that one method.

## Rules the frozen tests and the review read

No gate holds these. Frozen `test_organ_surface.py` reads the first two, the review reads the last two on every keep, and a keep that breaks one stops for Joe.

- Python's standard library is all `cozy.py` needs: no `requests`, no `httpx`, no `websocket`, no install.
- `author_asset` reads `record.path`, `record.sha256` and `record.metadata` and imports nothing from `plexus.organs`, not even for a type hint.
- Never copy code from `agent` or `cognitive`.
- A reply sends only its step's files. O2 sends `neuron.py` and nothing under `plexus/organs`.

## The organ

The organ knows the engine, and core knows only the contract. `cozy.py` talks HTTP with `urllib.request` and returns an `AssetRecord`. Core authors that record through `ctx.author_asset`.

**`plexus/organs/protocol.py`, whole, copied exactly.** A dict default must be `field(default_factory=dict)`: a literal `{}` default fails with "mutable default <class 'dict'> for field inputs is not allowed".

```python
"""The organ contract (PLEXUS_SPEC.md section 8): all that core may know about an engine."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class OrganError(RuntimeError):
    """An engine refused a job, failed it, or ran past the organ's deadline."""


@dataclass(frozen=True)
class Job:
    graph: dict
    seed: int
    colorspace: str
    correlation_id: str
    inputs: dict = field(default_factory=dict)


@dataclass(frozen=True)
class JobHandle:
    """The Plexus correlation id and nothing else. The engine's own job id stays inside the organ."""

    correlation_id: str


@dataclass(frozen=True)
class Progress:
    correlation_id: str
    state: str  # "queued", "done" or "failed"


@dataclass(frozen=True)
class OrganProfile:
    """The fields of PlexusOrganAPI."""

    organ_id: str
    kind: str
    endpoint: str
    capabilities: list[str]
    cost_hint: str


@dataclass(frozen=True)
class AssetRecord:
    path: Path
    sha256: str
    metadata: dict


class Organ(Protocol):
    @abstractmethod
    def profile(self) -> OrganProfile: ...

    @abstractmethod
    def capabilities(self) -> list[str]: ...

    @abstractmethod
    def submit(self, job: Job) -> JobHandle: ...

    @abstractmethod
    def stream(self, handle: JobHandle) -> Iterator[Progress]: ...

    @abstractmethod
    def result(self, handle: JobHandle) -> AssetRecord: ...
```

**`plexus/organs/cozy.py` starts from this skeleton.** Keep every import, constant and signature as written and replace each `raise NotImplementedError` with its body. `CozyOrgan` stays a subclass of `Organ`, so a missing method fails every T7 test with "Can't instantiate abstract class CozyOrgan".

```python
"""The Cozy organ, written new against ComfyUI's own HTTP API. The only file under plexus/ that may name engine words."""

from __future__ import annotations

import copy
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from plexus.organs.protocol import AssetRecord, Job, JobHandle, Organ, OrganError, OrganProfile, Progress

ORGAN_ID = "cozy"
ORGAN_VERSION = "0.1.0"
SEED_INPUTS = ("seed", "noise_seed")
COLORSPACES = ("acescg", "srgb", "linear", "raw")
INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1
HTTP_TIMEOUT_S = 60.0


@dataclass(frozen=True)
class _Submitted:
    """What the organ remembers of one job. It stays in here: core never sees the engine's id."""

    prompt_id: str
    seed: int | None
    colorspace: str


class CozyOrgan(Organ):
    def __init__(self, endpoint: str, output_dir: Path, *, poll_s: float = 0.2, deadline_s: float = 3600.0):
        raise NotImplementedError

    def profile(self) -> OrganProfile:
        raise NotImplementedError

    def capabilities(self) -> list[str]:
        raise NotImplementedError

    def submit(self, job: Job) -> JobHandle:
        raise NotImplementedError

    def stream(self, handle: JobHandle) -> Iterator[Progress]:
        raise NotImplementedError

    def result(self, handle: JobHandle) -> AssetRecord:
        raise NotImplementedError

    def _get_json(self, route: str) -> dict:
        """GET the endpoint plus route, as JSON. A URL or HTTP failure is an OrganError."""
        raise NotImplementedError

    def _history_entry(self, prompt_id: str) -> dict | None:
        """This job's entry in /history/<prompt_id>, or None while the engine's history does not have it or the engine cannot answer."""
        raise NotImplementedError

    def _fetch_file(self, image: dict) -> Path:
        """GET /view for one output and write it under output_dir. Returns the path of the file on disk."""
        raise NotImplementedError

    def _env_fingerprint(self) -> str:
        """SHA-256 hex over the engine's environment, from /system_stats and /object_info."""
        raise NotImplementedError
```

**The engine's HTTP surface, as `FakeComfy` answers it.**
- `POST /prompt` with the JSON body `{"prompt": graph}` answers `{"prompt_id": "...", "number": 0, "node_errors": {}}`.
- `GET /history/<prompt_id>` answers `{}` until the job is done, then `{"<prompt_id>": {"outputs": {"9": {"images": [{"filename": "...", "subfolder": "", "type": "output"}]}}, "status": {"status_str": "success", "completed": true, "messages": []}}}`.
- `GET /view?filename=...&subfolder=...&type=...` answers the file's bytes. Build the query with `urllib.parse.urlencode`.
- `GET /object_info` answers one key per node class the engine can run.
- `GET /system_stats` answers `{"system": {"os", "comfyui_version", "python_version", "pytorch_version"}, "devices": [{"name", "type", "vram_total"}]}`. A real engine adds free-memory fields such as `ram_free` and `vram_free` to the same reply.

**Facts about the organ's lines.**
- `/history/<prompt_id>` is the truth: `result` returns only once the job's entry is there and the file is on disk. Anything else that says done, the reply to the POST included, trips "result() returned before /history had the job". A read that fails with a 5xx or finds no connection means not yet, because one blip must not void a running job: keep polling until `deadline_s`. A 4xx means a wrong route and raises `OrganError` at once.
- If the prompt says the metric run timed out, `result` or `stream` never saw the entry. Check that `_history_entry` reads `.get(prompt_id)` with the variable and not the quoted word, and that the loop reads again each turn.
- `FakeComfy` never refuses or fails a job, so an `OrganError` in a T7 failure came from your own organ: most often an empty first history read treated as an error, where it means not yet.
- Copy the graph with `copy.deepcopy`, write the seed only into an input that holds an `int`, and change nothing else: a link is a two-item list such as `["4", 1]`, and T7 compares every link and every `class_type` with the graph it gave you. No renumbering, no sorting and no rebuilding of nodes.
- Post once per `submit`: T7 asserts `len(comfy.prompts) == 1`, so no retry and no second POST inside `submit` or `result`.
- `self._jobs` maps the correlation id to a `_Submitted`, inside the organ. `JobHandle` carries the correlation id only, so `result` finds the engine's id in `self._jobs` and nothing outside `cozy.py` ever holds it, except `AssetRecord.metadata["engineJobId"]`: not the handle, not the file's name and not an error's text. That is Patch 01-C.
- The fingerprint hashes `system.os`, `system.comfyui_version`, `system.python_version`, `system.pytorch_version`, each device's `name` and `type`, and the sorted class names of a fresh `/object_info` read, as `json.dumps(..., sort_keys=True)` through SHA-256. A node pack update is drift, so the cached `self._nodes` will not do. Nothing else from those replies: free memory moves between two reads, so hashing the whole reply passes T7's fake and gives a real engine a new fingerprint on every job, which is no use as a drift key. A constant fails with "envFingerprint is the drift key".
- `metadata["modelHashes"]` is an empty list in this mission. ComfyUI's HTTP surface gives no model hash, and an honest empty list beats an invented one.

**Authoring an asset.**
- `author_asset` is a method of `_Ctx` in `neuron.py`. An exception inside an action stays on the action's thread: `_run_action` prints it, and the frozen test usually sees only the prim that never landed, `AssertionError: projectA.usda`. The real error is under "Captured stderr call" in the output, and today it is `AttributeError: '_Ctx' object has no attribute 'author_asset'`.
- Author with plain `Sdf` on `rt.edit_layer` itself, never through a `Usd.Stage`, whose default edit target is `exchange.usda`. Apply the schema at `Sdf` level: `spec.SetInfo("apiSchemas", Sdf.TokenListOp.Create(prependedItems=["PlexusAssetAPI"]))`.
- `Sdf.CreatePrimInLayer` creates every missing ancestor as `over`. Set `layer.GetPrimAtPath(prefix).specifier = Sdf.SpecifierDef` for each prefix in `path.GetPrefixes()`, as `author` does, or the prim does not show up in ordinary traversal.
- The asset path is `Sdf.AssetPath(str(record.path))`. `Sdf.AssetPath(record.path)` with a `Path` fails with "Use keyword arguments 'authoredPath', 'evaluatedPath', and/or 'resolvedPath'", under "Captured stderr call", and when the prim landed without its path T7 reads `AttributeError: 'NoneType' object has no attribute 'resolvedPath'`. Checked on 26.5.
- Build every value before taking the lock. A value that fails inside the `Sdf.ChangeBlock()` leaves part of the record in the layer, and the quiesce's own Save writes that part to disk, where it composes as if whole.
- Every attribute goes through `_set_attr(spec, name, value, type_name)`: a bare `Sdf.AttributeSpec` on a name that already exists raises `Tf.ErrorException`.
- `plexus:sourceLayer` is `rt.edit_layer.identifier` verbatim. On Windows that identifier uses forward slashes; `str(path)` and `.realPath` use backslashes and fail T7's last assert.
- Hold `rt._lock` around the `Sdf.ChangeBlock()` and the `layer.Save()`, as `author` does: two threads authoring and saving at once killed the interpreter on 26.5, exit code 0x80000003, no traceback, and two neurons woken by one project write are enough.
