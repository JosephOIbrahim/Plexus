# Worker brief: mission `organ-live`

You make one change per attempt. The harness keeps it only if every gate passes and at least one more test in `tests/acceptance/phase2` passes. This mission has one step, L1, and it changes one file: `plexus/organs/cozy.py`.

**Every attempt starts from the last kept commit.** A dropped attempt's file is gone. When the prompt says why the last attempt was dropped, fix that cause and send `cozy.py` again, whole.

## How to reply

- Exactly one fenced block, whose info string is `file:plexus/organs/cozy.py`, holding the whole file from its first line to its last:

```file:plexus/organs/cozy.py
"""The Cozy organ, ..."""
...the complete file...
```

- Never a diff. A diff in this mission has never applied, and a reply that is a diff is dropped before anything runs.
- No commentary, no placeholder and no `...` standing for lines you kept. The file must compile.
- Write no test of your own. The frozen tests are the judge.

## What exists already

- Phases 1 and 2 are done. `plexus/organs/cozy.py` is under Files: the Cozy organ, which already passes T7, T8, `test_organ_surface.py` and a run against a real ComfyUI. Start from that copy. Every line the step does not name stays as it is.
- `tests/acceptance/phase2/test_organ_malformed.py` is under Files. It is the step's target: thirteen cases where the engine replies with something the organ cannot read, or does not reply at all. Today each one escapes as `KeyError`, `TypeError`, `JSONDecodeError`, a returned value, or a call that waits past the deadline.
- `tests/acceptance/CONTRACT.md` is under Files. `OrganError` is the one error core sees from an organ.
- `tests/acceptance/live/test_organ_live.py` runs the organ against a real ComfyUI. The harness does not score it; it is run by hand on every keep, and it already passes. Nothing in this step may break it.

## Rules the gates enforce

- Change only `plexus/organs/cozy.py`. Any other path drops the attempt before anything runs.
- Never import `agent`, `cognitive` or anything from them, at any scope, or the `layers` gate fails with "Comfy-Cozy is a reference only".
- `cozy.py` never imports `pxr`, or the `layers` gate fails with "these modules must stay free of pxr".
- Python's standard library is all `cozy.py` needs: no `requests`, no `httpx`, no install.

## Rules the frozen tests and the review read

- Every `raise OrganError(...)` that comes from another exception says `from e`, so the cause stays readable.
- No error core can see holds the engine's job id. The id lives in `metadata["engineJobId"]` and nowhere else; `test_no_error_core_sees_holds_the_engine_id` reads every error's text for it.
- A failure that is not the engine's fault, such as a bad seed or a node without `inputs`, is refused before anything reaches the engine.

## When the metric ran past its limit

The metric stops at 300 s. A reply whose history read waits on a socket for the whole `HTTP_TIMEOUT_S` can run every test past it and leave no failure text. The step's `_call_timeout` is the cure: no HTTP call waits past the job's deadline.
