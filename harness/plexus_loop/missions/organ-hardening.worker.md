# Worker brief: mission `organ-hardening`

You make one change per attempt. The harness keeps it only if every gate passes and at least one more test in `tests/acceptance/phase2` passes. This mission has one step, H1, and it changes one file, `plexus/organs/cozy.py`. The prompt names the step.

**Every attempt starts from the last kept commit.** A dropped attempt's file is gone. When the prompt says why the last attempt was dropped, fix that cause and send the file again, whole.

## How to reply

- Exactly one fenced block holding `cozy.py` whole, from its first line to its last: `file:plexus/organs/cozy.py`. Never a diff.
- No commentary, no placeholder and no `...` standing for lines you kept. The file must compile.
- The step's text gives the whole file. Copy it as written, at its indent.
- Write no test of your own. The frozen tests are the judge.

## What exists already

- `cozy.py` holds `CozyOrgan` and, at its end, `CozyLifecycle` with its constants and helpers above it. `OrganError` comes from `plexus.organs.protocol`.
- The file under Files is alpha.10's, at `28f2a47`: `CozyLifecycle` already takes `instance`, passes the four folder flags, and on Windows holds comfy-cli's process in a Job Object with kill-on-close.
- The target is `tests/acceptance/phase2/test_organ_hardening.py` (14 functions, 21 cases that run on Windows, 3 POSIX cases). Its cases fail today, and three are guards that pass today.
- `tests/acceptance/CONTRACT.md` is under Files. The `CozyLifecycle` lines under `plexus.organs` are the contract; the eight bullets that start with "On Windows `start()` creates" are this mission's.

## Rules the gates enforce

- Change only `plexus/organs/cozy.py`. Any other path drops the attempt before anything runs.
- `neuron.py` does not change, and the `neuron_unchanged` gate checks it.
- Never import `agent`, `cognitive` or anything from them, at any scope, or the `layers` gate fails with "Comfy-Cozy is a reference only".
- `cozy.py` never imports `pxr`, or the `layers` gate fails with "these modules must stay free of pxr". The standard library is all this needs: `ctypes`, `msvcrt` and `fcntl` come with Python.

## Rules the frozen tests read

- Everything above `LISTEN` stays byte for byte, `CozyOrgan` and the unused `e` in its history read included.
- On Windows `start()` creates comfy-cli's process with `CREATE_SUSPENDED`, puts it in the kill-on-close job, and only then resumes it, checking the result. A suspended root that never ran is the whole tree.
- When the job cannot be made, the resume fails, or anything raises between the spawn and the resume, `start()` kills that process before it runs, closes the job, drops the instance lock, reports `"unavailable"` and raises `OrganError`. An interrupt such as `KeyboardInterrupt` is raised again as itself after the same steps, and `self._proc` and `self._job` are set only after a successful resume.
- On POSIX the lifecycle learns that the root has exited without reaping it (`os.waitid` with `WNOWAIT`), signals the group only while the root is unreaped, and reaps it only after the kill. Every `OSError` from that kill except `ProcessLookupError` becomes `OrganError`, before the wait and the release, so `stop()` can try again.
- Beside an instance the constructor refuses, with `ValueError` and before any report, any `extra` item whose name is a start of one of the four folder flags (`--user`, `--da`, `--te`, `--ou` and up), any instance inside `<workspace>/temp`, and the workspace itself however either is spelled. Compare folders on disk, not strings: a `..`, a junction or symlink, the `\\?\` prefix and another Windows case all name the same folder.
- `start()` holds its instance with an operating-system lock taken without waiting, before it makes a folder or spawns anything, and lets it go when the tree ends. A second lifecycle on the same instance reports `"unavailable"` and raises `OrganError` naming the folder.
- The child gets `stdin=subprocess.DEVNULL`, the log opened with `'ab'` and `stderr=subprocess.STDOUT`: never an unread `subprocess.PIPE`.
- `stop()` kills only the tree its own `start()` spawned and never by a pid read anywhere else. It never runs `comfy stop` or a `--background` launch.
- `report` runs on the caller's thread. Never catch its exception.

## When the metric ran past its limit

The metric stops at 600 s. Phase 2 with the new file takes about 220 s when the machine is quiet, so a wrong file that leaves child processes behind can still finish. Keep `PORT_S`, `STATS_S`, `ready_s`, `stop_s` and `poll_s` as they are, and sleep `poll_s` between measurements.
