# Plan: mission `organ-closeout` (M3.3)

**What it is for.** alpha.11 shipped `CozyLifecycle` with a suspended start, a held tree and a guarded instance, and its notes list what it left open. This mission closes the part of that list that can be closed in the same file, and refuses the part that cannot be closed honestly.

**Slug.** `organ-hardening-2:` is not a valid slug (a colon), and it names no mission file. The slug is `organ-closeout`, from the scope: closing organ-hardening's open list.

## 1. The scope, item by item, and what each one can actually carry

| Item | Joe's words | Can it be closed? | What reads it |
|---|---|---|---|
| A | the ~80 µs suspended-root window | **No, not without a rewrite Joe has twice declined.** Closing it means creating the root already inside the job: `CreateProcessW` with `STARTUPEXW` and `PROC_THREAD_ATTRIBUTE_JOB_LIST`, which replaces `Popen`'s whole Windows half — working directory, environment block, handle inheritance — and takes away the audit-hook lever H1a, H2a and H2b rest on | Nothing new: the window stays a stated limit in the plan and the release notes, and the reviewer walks the order |
| B | a temp folder that does not exist yet spelled through a UNC alias | **Yes.** `resolve()` leaves `\\localhost\C$\…` and `\\?\UNC\…` untouched when the path does not exist (measured), so the comparison needs a lexical normalisation before it | A frozen case: an instance written through the admin share of a not-yet-existing temp folder is refused |
| C | a workspace whose own ComfyUI moved its temp directory | **Only if the host says where it moved it.** Plexus cannot read another process's argv, and the only channel that carries it, `/system_stats` on 8188, is forbidden. A new optional constructor argument lets the host declare it | A frozen case: `workspace_temp=` refuses an instance inside the declared folder |
| D | on POSIX a comfy-cli that dies alone frees the lock while main.py runs | **Yes.** ComfyUI takes `filelock.FileLock(<db>.lock)` itself (app/database/db.py:122-135), and on POSIX that is `fcntl.flock`; a non-blocking attempt on the same file detects a live engine whose comfy-cli is gone | A frozen case on both systems: a bystander holding `<instance>/user/comfyui.db.lock` makes `start()` refuse |
| E | coverage for the three POSIX cases | **Yes, as a gate.** The harness runs on Windows, so the three cases can only be scored by a gate that runs them where they apply: a WSL gate in the mission file | The gate itself, plus the existing cases |

## 2. Decisions, drafted with the recommended option

| # | Decision | Recommended | Why | Flip cost |
|---|---|---|---|---|
| D1 | Is item A in this mission? | **No. A stays a stated limit**, in the plan and in the alpha.12 notes | The alternatives are a `CreateProcessW` rewrite that costs the three cases that read the window today, or a window narrowed by microseconds and still there. The window leaves an inert suspended root, never a running one outside the job; alpha.10's version did that, and this one cannot | Joe says rewrite: a mission of its own, H1a/H2a/H2b reworked, all 27 cases re-proved |
| D2 | How B judges an admin-share spelling | **Normalise the spelling, then compare.** Strip `\\?\` and `\\?\UNC\`; turn `\\localhost\X$\…` (also `127.0.0.1`, the machine name) into `X:\…`; then `_real` as today | Measured: `resolve()` keeps the prefix on a path that does not exist, so no disk comparison can see it. The mapping is lexical and testable without creating the folder | Only the existing-path case is caught, and the not-yet-made spelling stays a residual |
| D3 | C's shape | **An optional `workspace_temp: Path | None = None`** beside `instance`; when given, an instance inside it is refused exactly as an instance inside `<workspace>/temp` is | The host is the only party that knows where its workspace's ComfyUI keeps its temp; the default stays today's behaviour, so no existing host changes | Nothing gets closed; the gap stays documented |
| D4 | D's shape | **Probe ComfyUI's own lock.** With an instance, after taking Plexus's `.plexus-instance.lock`, try `<instance>/user/comfyui.db.lock` non-blocking; if another holder has it, report `unavailable` and raise naming the instance. A missing file, or one nobody holds (a killed engine leaves it), is free | ComfyUI's own `FileLock` is `msvcrt.locking` on Windows and `fcntl.flock` on POSIX, so the probe sees a live `main.py` even when comfy-cli is gone — the POSIX hole alpha.11 left | A ComfyUI started outside Plexus stays invisible |
| D5 | E's shape | **A WSL gate in the mission file** that runs `test_organ_hardening_posix.py` and the POSIX-eligible cases of the two older lifecycle files under `wsl.exe -d Ubuntu` | It is the only way the harness scores the three cases at all, and it makes the worker answer for S3, S4 and H7d | They stay unscored, as in M3.2 |
| D6 | How the new optional argument is spelled | **`workspace_temp`, keyword-only, after `instance`**, so `CozyLifecycle(..., instance=X, workspace_temp=Y)` reads plainly and no positional caller breaks | alpha.10 and alpha.11 both added keyword-only arguments after `poll_s`; the frozen tests build with keywords | A different name changes the frozen bytes and the CONTRACT lines |

## 3. The frozen file

`tests/acceptance/phase2/test_organ_closeout.py`, with cases for B, C and D, plus the WSL gate's coverage of E. Written and proved before placement; the details go here once they are measured.

## 4. The reference

`plexus/organs/cozy.py`, on top of `8de1b67`: the lexical normalisation, the `workspace_temp` argument, and the ComfyUI lock probe. Everything above `LISTEN` stays byte for byte.


## 5. Proof (Nov 12, `m33/`)

- **Base, alpha.11 at `8de1b67`:** 5 failed, 4 passed. J1 (both spellings) accepted the admin-share instance; J3 and J4 raised `TypeError` on `workspace_temp`; J6 started a second engine beside a held database lock. The four that pass are the guards: J2, J5, and J7's two premises.
- **Reference:** **9 passed**, three repeats, 25 s the last and 9 s the first two before J7 grew its second half.
- **Neighbours on the reference:** lifecycle 19 + isolation 20 + hardening 24 = **63 passed**, 3 min 12 s.
- **POSIX cases under WSL Ubuntu:** **3 passed**, 5.6 s.
- **Mutants: 6 of 6 caught.** M1 no local-share mapping (J1), M2 `workspace_temp` ignored (J3), M3 the declared folder compared as a string prefix (J4), M4 no database-lock probe (J6), M5 any lock file means in use (J7's `no-file` premise), M6 the probe never lets the lock go (J7's second lifecycle). M3 and M5 at first survived, and the cases were tightened rather than the mutants retired.

**The mission file** (`organ-closeout.toml`): K1 gives the whole reference, 34,924 characters; the first prompt is about 62,677 of 95,000; the metric targets `test_organ_closeout.py` alone; three known-fix anchors, each once in the brief.

**The placement script** pins `094df397…` for the test and `2a2ef65a…` for the CONTRACT draft, and the CONTRACT blob `83631171…` it was built on.
