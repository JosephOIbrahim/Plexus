# Worker brief: mission `organ-isolation`

You make one change per attempt. The harness keeps it only if every gate passes and at least one more test in `tests/acceptance/phase2` passes. This mission has one step, I1, and it changes one file, `plexus/organs/cozy.py`. The prompt names the step.

**Every attempt starts from the last kept commit.** A dropped attempt's file is gone. When the prompt says why the last attempt was dropped, fix that cause and send the file again, whole.

## How to reply

- Exactly one fenced block holding `cozy.py` whole, from its first line to its last: `file:plexus/organs/cozy.py`. Never a diff.
- No commentary, no placeholder and no `...` standing for lines you kept. The file must compile.
- The step's text gives every new line. Copy them as written, at their indent.
- Write no test of your own. The frozen tests are the judge.

## What exists already

- `cozy.py` holds `CozyOrgan` and, at its end, `CozyLifecycle` with its constants and `_port_open` above it. `OrganError` comes from `plexus.organs.protocol`. The imports already hold `os`, `signal`, `socket`, `subprocess`, `Path`, `Callable` and `Sequence`.
- `CozyLifecycle` takes one more keyword argument, `instance`, after `poll_s`. Given a folder, ComfyUI gets its own user folder, database, temp folder and output inside it.
- The Windows block (`ctypes`, `wintypes`, `_K32`, `_JobLimits`) sits under `if os.name == 'nt':` right after `_DIRECT`, and `_job_holding` follows it at module level.
- The target is `tests/acceptance/phase2/test_organ_isolation.py` (20 cases; 17 fail today, and three guard what already holds). It is not under Files: each failure's text quotes CONTRACT and reaches the next prompt.
- `tests/acceptance/CONTRACT.md` is under Files. The `CozyLifecycle` lines under `plexus.organs` are the contract, the six after "A host bridges the two" included.

## Rules the gates enforce

- Change only `plexus/organs/cozy.py`. Any other path drops the attempt before anything runs.
- `neuron.py` does not change, and the `neuron_unchanged` gate checks it.
- Never import `agent`, `cognitive` or anything from them, at any scope, or the `layers` gate fails with "Comfy-Cozy is a reference only".
- `cozy.py` never imports `pxr`, or the `layers` gate fails with "these modules must stay free of pxr". The standard library is all I1 needs: `ctypes` comes with Python. No psutil, no install.

## Rules the frozen tests read

- Everything above `CHILD_ENV_SET` stays byte for byte, `CozyOrgan` and the unused `e` in its history read included.
- The child gets `stdin=subprocess.DEVNULL`, the log opened with `'ab'` (or `subprocess.DEVNULL`) and `stderr=subprocess.STDOUT`: never an unread `subprocess.PIPE`, which fills while the engine loads and stops it before it binds the port.
- On Windows the tree is held in a Job Object: `_job_holding(proc.pid)` right after `Popen`, `TerminateJobObject` in `_kill`, `CloseHandle` in `_release`. `taskkill` is gone, because it walks children from a root that may already have exited. The job is made with kill-on-close, so the engine ends with the host.
- `stop()` kills only the tree its own `start()` spawned and never by a pid read anywhere else. It never runs `comfy stop` or a `--background` launch. With no tree of its own it raises `OrganError` and reports nothing.
- A failure while making a folder, opening the log or running the command reports `'unavailable'` and raises `OrganError` naming the path. A kill or a wait that fails raises `OrganError`, never `TimeoutExpired`.
- `report` runs on the caller's thread. Never catch its exception: it reaches the caller of the constructor, `probe()`, `start()` or `stop()`.

## When the metric ran past its limit

The metric stops at 600 s. Each test bounds its own calls, but a `start()` or `stop()` that waits out every limit costs about 20 s a case. Keep `PORT_S`, `STATS_S`, `ready_s`, `stop_s` and `poll_s` as they are, and sleep `poll_s` between measurements.
