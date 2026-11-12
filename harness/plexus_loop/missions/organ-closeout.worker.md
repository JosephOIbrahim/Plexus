# Worker brief: mission `organ-closeout`

You make one change per attempt. The harness keeps it only if every gate passes and at least one more test in the target passes. One step, K1, one file, `plexus/organs/cozy.py`.

## How to reply

- Exactly one fenced block holding `cozy.py` whole: `file:plexus/organs/cozy.py`. Never a diff, no commentary, no `...`.
- The step gives the whole file. Copy it as written.
- Write no test of your own.

## What exists already

- `cozy.py` at `8de1b67` holds `CozyLifecycle` with a suspended start, a held tree, an instance lock and four folder flags.
- The target is `tests/acceptance/phase2/test_organ_closeout.py`; three of its cases pass today and are guards.
- `CONTRACT.md` carries J1 to J8, the eight lines this mission adds.

## Rules the gates enforce

- Change only `plexus/organs/cozy.py`. `neuron.py` does not change.
- Never import `agent`, `cognitive` or `pxr`.
- Everything above `LISTEN` stays byte for byte.

## Rules the frozen tests read

- A local admin share is the drive it names: `\\localhost\C$\…`, `\\127.0.0.1\C$\…` and this machine's own name, with or without `\\?\UNC\`, all mean `C:\…`, whether or not the folder exists. Only this host's shares count. A sibling such as `…\temp2\…` or `declared_temp2_sibling` is not inside.
- `workspace_temp=` declares where the host's own ComfyUI keeps its temp files; an instance inside it is refused with `ValueError`, before any report, as `<workspace>/temp` is.
- The probe of ComfyUI's own `comfyui.db.lock` decides "in use": a held lock refuses with `OrganError` naming the instance and `unavailable` last; a lock file nobody holds, or none at all, is free; the probe lets the lock go at once, so a later lifecycle on the same instance starts.
