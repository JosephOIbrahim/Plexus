# Worker brief: mission `organ-lifecycle`

You make one change per attempt. The harness keeps it only if every gate passes and at least one more test in `tests/acceptance/phase2` passes. This mission has two steps, and each changes one file. L1 adds `NeuronRuntime.publish_organ_state` to `plexus/core/neuron.py`. L2, once L1 is kept, appends `CozyLifecycle` to `plexus/organs/cozy.py`. The prompt names the step.

**Every attempt starts from the last kept commit.** A dropped attempt's file is gone. When the prompt says why the last attempt was dropped, fix that cause and send the step's file again, whole.

## How to reply

- Exactly one fenced block holding the step's file whole, from its first line to its last: `file:plexus/core/neuron.py` for L1, `file:plexus/organs/cozy.py` for L2. Never a diff.
- Send the step's file only. No commentary, no placeholder and no `...` standing for lines you kept. The file must compile.
- The step's text gives every new line. Copy them as written, at their indent.
- Write no test of your own. The frozen tests are the judge.

## What exists already

- `neuron.py` holds `NeuronRuntime.publish_organ`, which defines `/Plexus/Organs/<organId>` with `PlexusOrganAPI` in the runtime's edit layer. `Sdf` and `_set_attr` are already there. `cozy.py` holds `CozyOrgan`; `OrganError` comes from `plexus.organs.protocol`.
- `publish_organ_state` is a method of `NeuronRuntime`, right after `publish_organ` and before `start`. It writes only for an organ this runtime published.
- `CozyLifecycle` is a new class at the end of `cozy.py`, after `CozyOrgan`, with its constants and `_port_open` above it. It is not part of `Organ`, and `cozy.py` never imports `plexus.core`.
- The targets are `tests/acceptance/phase2/test_organ_state.py` (L1, 15 cases) and `test_organ_lifecycle.py` (L2, 19 cases). Neither is under Files: each failure's text quotes CONTRACT and reaches the next prompt.
- `tests/acceptance/CONTRACT.md` is under Files. `publish_organ_state` under `plexus.core.neuron` is L1's contract; `CozyLifecycle` under `plexus.organs` is L2's.

## Rules the gates enforce

- Change only the step's file. Any other path drops the attempt before anything runs.
- The `neuron_unchanged` gate compares the code of your `neuron.py` with the last kept commit, statement by statement, and lets in one new name, `NeuronRuntime.publish_organ_state`. Any other change drops the attempt with "this step adds NeuronRuntime.publish_organ_state and changes nothing else": a new import, a module-level constant, a new helper, or one changed line in another method. Start again from the copy under Files and add the method alone.
- Never import `agent`, `cognitive` or anything from them, at any scope, or the `layers` gate fails with "Comfy-Cozy is a reference only".
- `cozy.py` never imports `pxr`, or the `layers` gate fails with "these modules must stay free of pxr". The standard library is all L2 needs: no psutil, no requests, no install.

## Rules the frozen tests read

- The core is blind to the engine: `neuron.py` never imports `plexus.organs`, not even through `__import__` or `importlib`, and its text never names the engine or comfy-cli, in code, comments or strings.
- Every check in `publish_organ_state` runs before anything is authored. Under `self._lock` it reads the prim spec with `layer.GetPrimAtPath` and raises `ValueError` unless it prepends `PlexusOrganAPI`; it never creates the prim. One `_set_attr` in an `Sdf.ChangeBlock`, then `layer.Save()` inside the lock.
- In L2 only the two import lines and the appended block change. `CozyOrgan` and every helper above the block stay byte for byte, the unused `e` in its history read included.
- The child gets `stdin=subprocess.DEVNULL`, the log opened with `'ab'` (or `subprocess.DEVNULL`) and `stderr=subprocess.STDOUT`: never an unread `subprocess.PIPE`, which fills while the engine loads and stops it before it binds the port.
- `stop()` kills only the tree its own `start()` spawned, root and descendants together (`taskkill /T /F /PID` on Windows), and never by a pid read anywhere else. It never runs `comfy stop` or a `--background` launch. With no tree of its own it raises `OrganError` and reports nothing.
- `report` runs on the caller's thread. Never catch its exception: it reaches the caller of the constructor, `probe()`, `start()` or `stop()`.

## When the metric ran past its limit

The metric stops at 600 s. Each test bounds its own calls, but a `start()` or `stop()` that waits out every limit costs about 20 s a case. Keep `PORT_S`, `STATS_S`, `ready_s`, `stop_s` and `poll_s` as the step gives them, and sleep `poll_s` between measurements.
