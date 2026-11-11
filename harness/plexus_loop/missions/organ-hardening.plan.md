# Plan: mission `organ-hardening` (M3.2)

**What it is for.** alpha.10 released `CozyLifecycle` with an instance folder and a Windows Job Object, and its notes left seven gaps open. This mission closes them in one file, so no host has to know about them: on Windows the root starts suspended and is resumed only once the job holds it, so nothing it starts escapes the tree; a hold that fails kills the root before it runs; on POSIX the group is signalled only while the root is unreaped, and a refused kill becomes `OrganError`; beside an instance the constructor refuses abbreviated folder flags and an instance inside the workspace's temp folder, judging the folder on disk; and `start()` holds the instance with an OS lock. It also closes a hole in alpha.10's own check, where `\\?\` plus the workspace path was accepted as an instance.

**Shape.** One worker step, H1, one file, `plexus/organs/cozy.py`. One frozen file, `tests/acceptance/phase2/test_organ_hardening.py`, 14 functions, 21 Windows cases and 3 POSIX cases, plus eight CONTRACT bullets. Base `mission/organ-isolation` at `a7f4fc5`; the code base is alpha.10's `28f2a47`.

## 1. Decisions, taken on Joe's word of Nov 11

Each was drafted with a recommendation by a six-expert design panel (WIN_SYS, POSIX_SYS, COMFY_LEAD, TEST_ARCH, RED_TEAM and a CI engineer), arbitrated by an ARCHITECT, and Joe took all six recommendations.

| # | Decision | Taken | Why | Flip cost |
|---|---|---|---|---|
| D1 | How the root starts suspended and resumes | `Popen` with `CREATE_SUSPENDED`, then the job, then `NtResumeProcess` with its NTSTATUS checked | 200 of 200 roots were in the job at their first line; the resume costs 7 µs against 197 ms for the documented thread walk | The thread walk adds 0.2 to 0.8 s to every start and needs a one-thread check |
| D2 | The ~80 µs between `Popen` returning and the resume | Accepted, and stated in the plan and the alpha.11 notes | A host that dies there leaves an inert suspended root, which never runs; alpha.10's version of that instant lets the root run outside any job | `CreateProcessW` with a job list: 80 to 120 lines of ctypes, and all 39 existing cases proved again |
| D3 | What a failed hold does | Kill the suspended root, close the job, drop the lock, report `unavailable`, raise `OrganError`; an interrupt is raised again as itself after the same steps | A suspended root that never ran is the whole tree (200 of 200); today a raise there leaks the tree and leaves `starting` last | Raw errors pass through, and a host catching only `OrganError` crashes |
| D4 | What lets a frozen case see S1 and S2 | A child host whose audit hook pauses at the first `ctypes` call after the spawn, or raises there | Fails alpha.10 100 of 100, catches both broken orders 30 of 30, and costs nothing on a correct start | Holding `CreateProcess` for 3 s: misses "resume before the job holds it", and costs 3 s a case |
| D5 | How POSIX knows the group is still its own | Never reap the root before the kill; `waitid` with `WNOWAIT`; reap only after | In a pid namespace with forced reuse, alpha.10 killed an unrelated process 3 of 3; this design 0 of 3 | No other measured design closes it; a `kill(0)` check cannot tell a newcomer apart |
| D6 | Which POSIX cases are frozen | Two portable recorder cases that skip on Windows, with the real-kernel proofs run under WSL | The only portable case that fails both alpha.10 and a check-then-kill design | Freezing nothing leaves S3 and S4 to a log and the reviewer |
| D7 | Which kill errors become `OrganError` | Every `OSError` but `ProcessLookupError`, before the wait and the release | I5 already says "OrganError and nothing else"; measured: a refused first `stop()`, then a successful second | Converting only `PermissionError` still leaks other OS errors |
| D8 | How broad the flag refusal is | Any `--x…` that is a start of one of the four flags, including `--u`, `--t`, `--o`, `--d` | ComfyUI accepts any unambiguous start and its last value wins; `--temp=` falls back to the workspace's temp | A per-flag minimum tied to today's option table |
| D9 | How the temp folder and the workspace itself are recognised | Compare folders on disk: strip `\\?\`, resolve, then `samefile` over the existing parents | Right for 23 Windows and 17 POSIX spellings, and it closes alpha.10's `\\?\` hole | A resolve-only check leaves the prefix, the trailing space and the hole |
| D10 | What marks an instance in use | An OS lock the lifecycle holds on `<instance>/.plexus-instance.lock`, taken in `start()`, passed to comfy-cli on POSIX | Refused in-process and across processes, freed when its holder dies, never inherited on Windows | A constructor refusal races the start; a host-only lock on POSIX lets a second engine start beside an orphan |

Parked at Joe's word: refusing `--port` and `--listen` overrides, and comfy-cli's Windows argument expansion (`%VAR%`, `~`, wildcards).

## 2. The frozen file

`tests/acceptance/phase2/test_organ_hardening.py`, 14 functions, CRLF like its neighbours. It imports its helpers from `test_organ_isolation.py` (`FAKE_CLI`, `FAKE_MAIN`, `Rig`, `alive`, the 8188 guard) and from `test_organ_lifecycle.py` (`within`, `free_port`, `Reports`, `cli_runs`), and an `Engine` from `test_organ_malformed.py` so constructor cases cost milliseconds.

| Function (cases) | CONTRACT line | Reads | On alpha.10 |
|---|---|---|---|
| `test_a_process_the_root_starts_at_once_ends_with_its_host` | H1 | A child host paused by an audit hook until `main.py` exists; the host exits without `stop()` | fails: 100 of 100 |
| `test_a_tree_no_job_can_hold_is_killed_before_it_runs` | H2 | The same host at Windows' job-nesting ceiling | fails: 50 of 50 |
| `test_an_error_between_the_spawn_and_the_hold_kills_the_root` | H2 | The hook raises at the first low-level call after the spawn | fails: a raw `OSError`, `starting` last, the tree left outside any job |
| `test_a_kill_never_reaches_the_roots_number_after_the_root_is_reaped` | H3 | Recorder on `os.killpg`/`os.kill`; after the reap no signal reaches that number | POSIX; measured with forced reuse |
| `test_a_kill_the_system_refuses_is_an_organ_error_and_stop_can_try_again` | H4 | Recorder refuses the first kill with `PermissionError` | POSIX; measured with a seccomp filter |
| `test_an_abbreviated_folder_flag_beside_an_instance_is_refused` (6) | H5 | Every start of the four flags, `--u`, `--t`, `--o`, `--d`, and the empty forms | fails: every form constructs |
| `test_other_flags_pass_beside_an_instance_and_any_without_one` | H5 | Guard: ComfyUI's 101 other flags pass, and so does everything without an instance | passes (guard) |
| `test_an_instance_in_the_workspaces_temp_folder_is_refused` (10) | H6 | `temp`, `temp/inst`, a path not made yet, `x/../temp`, a junction, the workspace through a link, `TEMP`, `\\?\`, a trailing space | fails: only the workspace itself is refused |
| `test_folders_that_only_look_like_the_workspaces_temp_are_accepted` | H6 | Guard: `temp2`, `temporary`, `temp_inst`, `temp/../instances/a`, another folder's `temp`, `instances/a` | passes (guard) |
| `test_the_workspace_itself_with_the_long_path_prefix_is_refused` | H6 | `\\?\` plus the workspace | fails: accepted, and ComfyUI would use the workspace's own database |
| `test_an_instance_another_lifecycle_runs_is_refused_until_it_stops` | H7 | A second lifecycle on one instance, then each start after a stop | fails: a second engine starts |
| `test_a_start_that_fails_lets_its_instance_go` | H7 | Guard: after a failed start the instance is free | passes (guard) |
| `test_an_instance_another_host_runs_is_refused_until_that_host_ends` | H7 | Another host's engine, killed with `TerminateProcess` | fails: a second engine starts beside it |
| `test_an_instance_stays_in_use_while_its_engine_outlives_its_host` | H7 | POSIX: a dead host's engine keeps the instance | no lock (and a host-only lock fails too) |

Inconclusive premises fail rather than pass: a hook that never armed, no root found, a suspend count that cannot be read, a pause that ended without `main_pid`, a nesting refusal that never came.

## 3. Ordered change

**H1, `plexus/organs/cozy.py`, target `test_organ_hardening.py`.** The step text gives the whole file verbatim, because the change touches seven places: the module constants (`CREATE_SUSPENDED`, `INSTANCE_LOCK`, `_NOWAIT`), the Windows block (`msvcrt`, `ntdll`, `_resumed`) and an `else:` branch for `fcntl`, four new module helpers (`_exited`, `_names_folder_flag`, `_real`, `_same`, `_inside`, `_locked`, `_unlocked`), the constructor, `_alive`, `_spawn` (the lock, the suspended spawn, one guard enclosing it, kill-before-close), `_kill` (the POSIX branch), and `_release`/`_drop_lock`. Everything above `LISTEN` stays byte for byte.

The reference is `m32/reference/plexus/organs/cozy.py`, 669 lines, sha256 `1f5344c3…`.

## 4. Prompts (harness `build_prompt`, `m32/verify/build_toml.py`)

The first prompt is about 58,394 characters of 95,000: the step text (the whole reference) plus the brief and `CONTRACT.md`. That is 36,606 characters of room. The file is larger than M3.1's, so `timeout_s` rises to 7200 in the worker block.

## 5. Proof (Nov 11, `m32/`)

- **Base, alpha.10's code:** 21 Windows cases fail, each for its own reason, 3 guard cases pass, 3 POSIX cases skip, in 58.3 s.
- **Reference:** 24 pass, 3 skip, 0 fail, in 58.4 s. The 39 existing lifecycle and isolation cases pass in 133.8 s. **Phase 1 and phase 2 whole, in `m32/wt` with the reference: 286 passed, 3 failed, 3 skipped in 240.5 s.** Phase 1 is 30 of 30. Phase 2 is 253 passed, 3 skipped (the POSIX cases) and 3 failed: H1a, H2a and H2b, the three cases that read the moment between `Popen` and the hold. They fail as inconclusive, by design, because the lever they use, the `ctypes.call_function` audit event, exists only on Python 3.14; this machine's 3.12.10 and 3.13.14 raise `ctypes.dlopen` and `dlsym` but not `call_function`. All three passed 24 of 24 against the same reference on 3.14.2, and 21 of 21 non-guard cases still fail on alpha.10 there.
- **Prototype:** H1a, H2a and H2b pass against the S1/S2 prototype in 13.9 s, so the cases read the mechanism and not only the reference.
- **Mutants: 8 of 9 caught.** M1 no `CREATE_SUSPENDED` (H1a), M2 resume before the job holds it (H1a), M3 the root is not killed when the job fails (H2a), M4 exact flag names only (H5a), M5 every `-directory` flag refused (H5b), M7 the temp check as a string prefix (H6b), M8 no lock (H7a), M9 the lock never let go (H7b). M6, dropping the `\?\` strip, survives and is equivalent: `samefile` alone refuses every spelling the frozen cases use. The strip still covers a `\?\` path that does not exist yet, which no case reads.
- **POSIX under WSL Ubuntu:** H3, H4 and H7d pass against the reference in 2.8 s; H7c skips as Windows-only.

## 6. Scaffolding and order

- **C0, Joe:** the placement line, which cuts `mission/organ-hardening` from `mission/organ-isolation` and puts the two pinned files in one commit. Nothing is pushed.
- **C1, Claude:** `organ-hardening.toml`, `.worker.md` and `.plan.md` into `harness/plexus_loop/missions/`.
- **C2, Claude:** program rule 2 names `mission/organ-hardening` and `plexus-loop/organ-hardening` (`m32/mission/C2_program_rule2.diff`).
- Then `check`, push `mission/organ-hardening` on Joe's go, `run`, reviewer on the keep, `/report`.

## 7. `check`

Pasted after the mission files are laid in a scratch copy.

## 8. Comfy-Cozy

Nothing is mapped: this mission changes `plexus/organs/cozy.py`, Plexus's own organ. The ComfyUI facts it relies on were read from `G:/COMFY/ComfyUI` (0.34.0) and are named in the decisions.

## 9. Left open

- The ~80 µs host-death window (D2), for the alpha.11 notes.
- A temp folder that does not exist yet, spelled through a UNC alias (needs the folder to exist for `samefile`).
- A workspace whose own ComfyUI moved its temp folder with `--temp-directory`.
- On POSIX, a comfy-cli that dies alone frees the lock while `main.py` runs on.
- A ComfyUI started outside Plexus is invisible to the lock.
- macOS is untested.
- The frozen `test_organ_lifecycle.py` still hints `taskkill /T /F` in its failure text; only Joe can change that file.
- Parked: `--port`/`--listen` overrides, and comfy-cli's argument expansion.
