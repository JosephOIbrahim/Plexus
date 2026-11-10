# Worker brief: mission `organ-registry`

You make one change per attempt. The harness keeps it only if every gate passes and at least one more test in `tests/acceptance/phase2` passes. This mission has three steps, and each changes one file. R1 adds `NeuronRuntime.publish_organ` to `plexus/core/neuron.py`, so every participant's runtime sees which engines exist. R2 makes `plexus/organs/cozy.py` end every reply it still cannot read in an `OrganError`. R2b makes, in `cozy.py`, the changes R2 asked for that the kept R2 left out. The prompt names the step. R1 and R2 are kept, so R2b is the step left.

**Every attempt starts from the last kept commit.** A dropped attempt's file is gone. When the prompt says why the last attempt was dropped, fix that cause and send the step's file again, whole.

## How to reply

- Exactly one fenced block holding the step's file whole, from its first line to its last. For R1 its info string is `file:plexus/core/neuron.py`; for R2 and R2b it is `file:plexus/organs/cozy.py`:

```file:plexus/core/neuron.py
"""Neuron runtime and neuron prim management."""
...the complete file...
```

- Never a diff. In mission organ a diff of `neuron.py` was sent twice and neither applied. Send the whole file.
- Send the step's file only. The other file stays as it is in the repo.
- No commentary, no placeholder and no `...` standing for lines you kept. The file must compile.
- Write no test of your own. The frozen tests are the judge.

## What exists already

- Phases 1 and 2 are done, and so is mission organ-live. R1 and R2 are kept: `neuron.py` already holds `publish_organ`, and `cozy.py` already ends the 51 reply shapes in `OrganError`. `plexus/core/neuron.py` and `plexus/organs/cozy.py` are both under Files. Start from the copy of the step's file there, and keep every line the step does not name.
- `neuron.py` holds `NeuronRuntime`, whose `register` already writes `/Plexus/Neurons/<name>` into the runtime's edit layer with no publication gate. It also holds `_Ctx.author` and `_Ctx.author_asset`, which author and save inside `with rt._lock:`. The module-level helper `_set_attr(spec, name, value, type_name)` already exists, and `Sdf` and `Usd` are already imported from `pxr`.
- `publish_organ` is a method of `NeuronRuntime`, placed right after `register` and before `start`. It is not a method of `_Ctx`: the publication gate would drop a neuron's write under `/Plexus`, and no neuron installs an organ. R1's text gives every line of it.
- `tests/acceptance/phase2/test_organ_registry.py` is R1's target, 40 tests. It is not under Files, because R1's text spells out the method; each failure's own text reaches the next prompt.
- `tests/acceptance/phase2/test_organ_reply_shapes.py` is R2's target, 51 cases, and it is under Files. It imports its fake engine and helpers from `test_organ_malformed.py`, which is under Files too, and `GRAPH`, `OBJECT_INFO` and `PNG` from `test_t7_round_trip.py`.
- `tests/acceptance/phase2/test_organ_history_reads.py` is R2b's target, 8 cases, and it is under Files. It imports its fake engines and helpers from `test_organ_malformed.py` and `test_organ_reply_shapes.py`.
- `tests/acceptance/CONTRACT.md` is under Files. Its `publish_organ` line under `plexus.core.neuron` is R1's contract. Its `OrganError` lines under `plexus.organs` are R2's: `OrganError` is the one error core sees from an organ.
- `tests/acceptance/live/test_organ_live.py` runs the organ against a real ComfyUI. The harness does not score it; it is run by hand on every keep, and it already passes. Nothing in R2 may break it.

## Rules the gates enforce

- Change only the step's file. Any path outside `plexus/core/neuron.py` and `plexus/organs/cozy.py` drops the attempt before anything runs.
- The `neuron_unchanged` gate compares the code of your `neuron.py` with the last kept commit, statement by statement, and lets in one new name, `NeuronRuntime.publish_organ`. Any other change drops the attempt with "this step adds NeuronRuntime.publish_organ and changes nothing else": a new import, a module-level constant, a new helper, or one changed line in another method, `_Ctx.author_asset` included. Start again from the copy of `neuron.py` under Files and add the method alone.
- Never import `agent`, `cognitive` or anything from them, at any scope, or the `layers` gate fails with "Comfy-Cozy is a reference only".
- `cozy.py` never imports `pxr`, or the `layers` gate fails with "these modules must stay free of pxr". Python's standard library is all it needs, and `http.client` is part of it: no `requests`, no `httpx`, no install.

## Rules the frozen tests and the review read

- The core is blind to the engine: `neuron.py` never imports `plexus.organs`, even for a type hint, and never names an organ kind or an engine, in code, comments or strings, because frozen T8 and the registry test's guard read it line by line. `publish_organ` reads the allowed tokens from `Usd.SchemaRegistry().FindAppliedAPIPrimDefinition("PlexusOrganAPI")` and never writes a token list.
- Every check of `publish_organ` finishes before anything is authored. Then it sets every value on a probe prim in a scratch `Sdf.Layer.CreateAnonymous()`, and only then takes `self._lock`, so a profile that cannot land raises with nothing authored in the edit layer and nothing saved.
- In `publish_organ`, `layer.Save()` runs inside `with self._lock:`, after the `Sdf.ChangeBlock`, as in `_Ctx.author_asset`: a test reads the file at the moment the lock is let go.
- `http.client.HTTPException`, which covers `BadStatusLine`, `IncompleteRead`, `InvalidURL` and `RemoteDisconnected`, is not an `OSError`, so no `except OSError` catches it. In `submit`, `_get_json` and `_fetch_file` the except tuple names it beside `OSError`, because each of those branches raises `OrganError`. `_history_entry` is the one place it stays out of the tuple: there `except (urllib.error.URLError, OSError) as e:` means not yet and returns `None`, and its own branch, `except http.client.HTTPException as e:`, comes after that one and raises `OrganError` at once, because a reply the engine sent that http.client cannot read, or a URL it will not send, is an answer and not a missing connection. `RemoteDisconnected` is both, so the `OSError` branch, which comes first, still reads it as not yet.
- A null history status means no status, and the job is done: ComfyUI's `task_done` writes `"status": null` when it has none. `stream` and `result` each read the status as `(entry.get('status') or {}).get('status_str')`, never with `.get` on what `entry.get('status', {})` hands back, which is `None` for a null.
- Every `raise OrganError(...)` that a step adds and that comes from another exception says `from e`, so the cause stays readable. A raise the step says stays keeps its text.
- No error core can see holds the engine's job id or the URL of the history read. The id lives in `metadata["engineJobId"]` and nowhere else.

## When the metric ran past its limit

The metric stops at 600 s. A reply whose history read waits on a socket for the whole `HTTP_TIMEOUT_S` can run every test past it and leave no failure text. `_call_timeout` already caps each history read at the job's deadline; keep it.
