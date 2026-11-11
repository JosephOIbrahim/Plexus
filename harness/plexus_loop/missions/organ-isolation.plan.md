# Plan: mission `organ-isolation` (M3.1)

**What it is for.** D4 (Nov 11) ran `CozyLifecycle` against the real comfy-cli and found that `--user-directory` alone lets ComfyUI move the workspace's own `user/comfyui.db` into the new folder (G:/COMFY/ComfyUI/app/database/db.py:86-108), and that `main.py` wipes its temp folder at start (main.py:488-491). The M3 review left S1, S2, S3 and N1 open. M3.1 closes all of them in `CozyLifecycle` itself, so no host has to remember the right flags, and nothing the lifecycle starts outlives a stop or its host.

**Shape.** One worker step, I1, one file, `plexus/organs/cozy.py`. One frozen file, `tests/acceptance/phase2/test_organ_isolation.py`, 20 cases, plus six CONTRACT lines. Base `mission/organ-lifecycle` at `4d69762` (alpha.9's code, `9022f40`, plus docs).

## 1. Decisions, drafted with the recommended option

Each is the mission's assumption until Joe says otherwise. A different answer changes the frozen bytes, and Claude re-proves them and regenerates the pins before anything is placed.

| # | Decision | Recommended | Why | Flip cost |
|---|---|---|---|---|
| D1 | `instance` required or optional | **Optional, `instance: Path | None = None`** | Required breaks M3's 19 frozen lifecycle cases, which build `CozyLifecycle` without it and pin sentence 7's exact argv (LB2). With `None` the argv stays sentence 7's. | Required: Joe revises `test_organ_lifecycle.py` too. |
| D2 | Guard rails on `instance` | **`ValueError` in the constructor when it resolves to the workspace itself, or when `extra` names one of the four flags, alone or as `flag=value`** | Both would put ComfyUI back on the workspace's own folders. Raising before measuring means nothing is reported and nothing runs. Without an instance, `extra` may name them as before (IS2b). | Drop IS2 (9 cases) and two lines. |
| D3 | How the tree is held (S3) | **A Windows Job Object; POSIX keeps the process group** | `taskkill /T` walks children from the root, so once comfy-cli has exited, `main.py` is out of reach. A job holds every process the root starts. Stdlib `ctypes`, no new dependency. | Record descendants by polling: needs psutil or Toolhelp ctypes, and misses a child started between polls. |
| D4 | Kill-on-close (D3 b, parked since M3) | **Yes: on Windows the engine ends with the host that started it** | An engine a dead host leaves holds the port; the next host's constructor reads it `ready` but can never stop it (sentence 61). Kill-on-close makes that impossible on Windows. | Drop IS8 and the flag `0x2000`; an engine then survives its host, as today. |
| D5 | What a start that cannot begin does (S1) | **Report `unavailable` and raise `OrganError` naming the path** | Keeps M3's order (starting first, Joe's Nov 10 change) and never leaves a stale `starting`. | — |
| D6 | A start while its own engine answers but is not yet ComfyUI (S2) | **Wait, report nothing until `ready`, for a first and a second start alike** | Sentence 62 already says a further start "waits on that process the same way". | — |

Left as they are: `--input-directory` (the input folder stays shared with the workspace); a start lock between hosts (sentence 78).

## 2. The frozen file

`tests/acceptance/phase2/test_organ_isolation.py`, 620 lines, CRLF like its neighbours, imports its timing helpers from `test_organ_lifecycle.py`. FAKE_CLI adds two modes to M3's: `orphan` (the cli starts `main.py`, waits until it answers, waits 2 s and exits) and `orphan_early` (the cli starts `main.py` and exits at once). FAKE_MAIN models ComfyUI's folder handling, from the installed G:/COMFY/ComfyUI: `--user-directory` must exist (cli_args.py:256); without `--database-url` a foreign user folder takes the workspace's database and renames it `.bak` (db.py:86-108); temp is wiped at start (main.py:488-491). Every workspace starts with "the 8188 instance's" `user/comfyui.db`, `temp/keep.txt` and `output/keep.png`. Same safety as M3: USERPROFILE and HOME point into tmp_path, any connect to 8188 fails the test, every call runs on a joined daemon thread, teardown writes `die` and stops every lifecycle. `alive()` never signals a pid (os.kill on Windows would end it) and reads an unreaped child's `Z` state as dead on POSIX.

| Case | CONTRACT line | Reads | On the base |
|---|---|---|---|
| IS1 | I1 | `instance` given as `instances/x/../is1` relative to the host's folder, which moves before `start()`; an earlier session's database and output already in it: the exact argv, the folders existing before `main.py` starts, the earlier files kept, and the workspace's database, temp and output untouched after start and stop | fails |
| IS2 ×9 | I2 | `ValueError` before any report for the workspace written `ws/user/..`, and for `extra` naming each of the four flags, alone and as `flag=value` | fail |
| IS2b | I2 | Without an instance, `extra` may name the flags | passes (guard) |
| IS3 ×3 | I3 (S1) | A log under `main.py` (a file), an instance that is a file, a command that does not exist: `OrganError` naming the path, last report `unavailable`, nothing run | 2 fail, the command case passes (guard) |
| IS4 | I4 (S2) | `/system_stats` answering 404 while its own engine runs: a second `start()` still waits after 1.5 s, reports only `ready`, runs nothing more | fails |
| IS4b | I4 | The same before the first `start()`: it waits, and reports `stopped, starting, ready` | passes (guard) |
| IS5 | I5 (S3) | The root exits after `main.py` answers: `stop()` returns `stopped`, the port closes, `main.py` is gone | fails |
| IS6 | I5 (S3) | The root exits before `main.py` binds: `start()` raises, and 5 s later nothing holds the port | fails |
| IS7 | I5 (N1) | `stop_s=0.01`: `stop()` returns `stopped` or raises `OrganError`, never another type, and the tree still ends | fails |
| IS8 | I6 (D4) | Windows only: a child host starts the engine and exits without `stop()`; within 15 s the port closes and `main.py` is gone | fails |

The six CONTRACT lines go right after "A host bridges the two" (sentence 66), and nothing else in CONTRACT.md changes. Their text is in `m31/frozen/contract_lines.md`. I5 says `stop_s` bounds the waits after the kill, not the kill itself, and leaves the order of the kill and the report open, as M3 did.

## 3. Ordered change

**I1, `plexus/organs/cozy.py`, target `test_organ_isolation.py`.** Two places, both in the lifecycle part: (1) `CHILD_ENV_SET`/`_DIRECT` gain `INSTANCE_FLAGS`, the Windows-only `ctypes` block and `_job_holding`; (2) the class `CozyLifecycle` is replaced whole. Everything above `CHILD_ENV_SET` stays byte for byte, the import lines included. The step text gives both blocks verbatim (the measured cure); the reference diff has 121 added lines, every non-blank one a whole line of the text, and base plus the two changes is the reference byte for byte (`m31/verify/build_toml.py`).

## 4. Prompts (harness `build_prompt`, `m31/verify/budget.py`)

| State | Characters | Room of 95,000 | Left out |
|---|---|---|---|
| S0 first prompt | 62,262 | 32,738 | nothing |
| S1 after a gate-passing drop, cozy.py handed on, the three longest failures | 76,296 | 18,704 | nothing |
| S2 after a drop at a gate | 67,049 | 27,951 | nothing |

`neuron.py` is out of focus, so each prompt is 8,800 to 10,600 characters shorter than M3's L2.

## 5. Proof (Nov 11, `m31/wt`, a worktree at `4d69762`)

- **Base:** 17 of the 20 fail, each for its own reason (`m31/verify/base_failures.txt`): `unexpected keyword argument 'instance'` (IS1, IS2 ×9, IS3 instance); a raw `FileNotFoundError` on the log (IS3 log); `OrganError: port … answers, but not as ComfyUI` on the second start (IS4); `port … still answers 5 s after the tree … was killed` (IS5); `main.py … holds port …` (IS6); `TimeoutExpired` from taskkill (IS7); `main.py … still runs` after the host exited (IS8). IS2b, IS3's command case and IS4b pass: they guard what already holds. Phase 2 whole: 218 passed, 17 failed.
- **Reference:** 20 of 20, three repeats green (about 62 s each); phase 2 whole 235 of 235 (157 s); phase 1 30 of 30; M3's 34 lifecycle and state cases unchanged. Under WSL Ubuntu: 19 passed, IS8 skipped. Guards 9, `neuron_unchanged` without `--may-add` rc 0, `core` and `predicate_smoke` rc 0, the narrowed `unit` gate 459 passed (233 s), `check` ready. No fake left running on Windows or WSL.
- **Mutants:** 23, 21 caught. Survivors: X13, closing the job instead of `TerminateJobObject`, which ends the same tree (equivalent); X15, an unconverted `proc.wait` `TimeoutExpired`, which IS7 cannot force because the job ends the root inside 10 ms.
- **Adversary (a subagent, its own worktree, 17 mutants and a WSL run):** three HARD findings, all closed. H1: on POSIX, `alive()` read an unreaped root as alive, so IS5 failed the reference on Linux; now it reads the `Z` state. H2: folders made without `exist_ok`, or the instance emptied on every start, passed; IS1 now starts with an earlier session's files in the instance and checks they survive, and I1 says "makes whichever is missing, keeping what they hold". H3: a log in a missing folder failed an implementation that made the folder, which CONTRACT allows; the log now sits under a file. Six SOFT gaps, all closed: all four flags in both forms (IS2), the workspace through `..` (IS2), resolution in the constructor and after a move of the host's folder (IS1), the command that does not exist (IS3), a first start's 404 (IS4b), and I5 no longer fixes the kill-before-report order. Notes taken: the orphan cli now waits 2 s before it exits (a race near 0 ms in the worst alignment); IS7's reading of `stop_s` is now in I5.

## 6. Scaffolding and order

- **C0, Joe:** `! bash "C:/Users/User/AppData/Local/Temp/claude/a1cf58fc35533771/0e857ac5-42ca-45b8-a5d9-b5ef72ac971b/scratchpad/m31/mission/place_organ_isolation_tests.sh"` from the Claude Code prompt. It needs `mission/organ-lifecycle`, clean; cuts `mission/organ-isolation`; copies the two pinned files (test `7160a149…`, CONTRACT `0aa63bcb…`); commits; pushes nothing. A dry run in a scratch clone placed exactly these two files, 626 lines, and a second run refused.
- **C1, Claude:** `organ-isolation.toml`, `.worker.md`, `.plan.md` into `harness/plexus_loop/missions/`.
- **C2, Claude:** program.md rule 2 names `mission/organ-isolation` and `plexus-loop/organ-isolation` (`m31/mission/C2_program_rule2.diff`).
- Then `check`, push `mission/organ-isolation` on Joe's go, `run`, reviewer on the keep, D4's script rerun with `instance=` in place of the four flags, `/report`.

## 7. `check` (in `m31/wt` with everything laid)

```
mission organ-isolation: worker ollama (qwen3-coder:30b), 6 gate(s), metric pytest_failures
Houdini: running; next attempt runs on the cpu
worker: check does not load qwen3-coder:30b; run loads it first and refuses if it cannot
ready
```

Doctor, Nov 11: `qwen3-coder:30b` present in Ollama, rustc 1.99.1, usd-core 0.26.5, Houdini running (CPU).

## 8. Comfy-Cozy

The brief names no Comfy-Cozy module, so there is nothing to map. The ComfyUI facts above come from the installed ComfyUI at G:/COMFY/ComfyUI, read, not run.

## 9. Left open, and two things for Joe

- Left open on purpose: the words of every message past the path or port it names; the folder names' case; how the tree is held (a Job Object is the reference, not the contract); POSIX kill-on-close (`PR_SET_PDEATHSIG` is Linux-only; IS8 is skipped off Windows); a start lock between hosts; an input folder per instance; whether "a process this lifecycle started" means the root alone or the whole tree once the root has exited.
- **For Joe:** the frozen `test_organ_lifecycle.py` still says, inside SENTENCE_9, "On Windows run taskkill /T /F /PID <root>". After I1 that hint is wrong. No M3 case reads it, so nothing fails, but a worker reading an M3 failure would be pointed at taskkill. Only Joe can change that file.
- **For Joe:** decisions D1 to D6 above.
