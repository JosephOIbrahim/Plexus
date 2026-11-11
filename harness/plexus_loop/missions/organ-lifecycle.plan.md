# Mission `organ-lifecycle`: plan

**M3 puts ComfyUI's lifecycle on the stage.** Step L1 adds one engine-blind method, `NeuronRuntime.publish_organ_state(organ_id, state) -> Sdf.Path`, to `plexus/core/neuron.py`. It authors one token, `plexus:lifecycle`, on `/Plexus/Organs/<organId>` in the runtime's own edit layer, and only for an organ that runtime published. Step L2 appends one class, `CozyLifecycle`, to `plexus/organs/cozy.py`. It runs comfy-cli in the foreground, owns only the process tree its own `start()` spawned, and hands each measurement, `stopped`, `starting`, `ready` or `unavailable`, to a `report(state)` callback that the host points at `publish_organ_state`. So a neuron in the host's process wakes when the engine is `ready` and reaches it through the organ. Each step changes one file. Both are proved against references at `a7806e5` (alpha.8's code is `bfd4fb8`). The design is `m3/design/DESIGN.md`, the judged minimal design with six grafts.

## 1. Decisions for Joe before placement

**Answered, Joe, Nov 10: "Go with the recommendations on D1 to D5."** Each is drafted as recommended below, and the frozen drafts, the reference and the step texts follow it. The table stays as the record of the options and what a later flip costs.

| # | Question | Recommended (drafted) | Other options | Flip cost |
|---|---|---|---|---|
| D1 | The state's shape and place | **(a)** one plain `plexus:lifecycle` token on the organ prim, four tokens, no schema change. Nothing in M3 needs typed metadata; the predicate grammar is AND-only (predicate.rs:3), so `ready` is the one token a neuron needs. | (b) typed attributes on `PlexusOrganAPI` (a Patch 02; collides with test_organ_registry.py:58, :68, :205, which assert five attributes); (c) a state plus a reason token; (d) a state, a free-text reason and an ISO time | To (b): one attribute in generatedSchema.usda (a worker step on plexus/schema/), a spec note, about 6 lines in the method, and Joe edits T0's table or FIVE. To (c): a second `_set_attr` and parameter, one CONTRACT sentence, two cases. Either changes LS1's "exactly one more attribute" and the four-state parameters. |
| D2 | Where the lifecycle code lives | **(a)** `CozyLifecycle` in plexus/organs/cozy.py, the one file T8 lets know ComfyUI (test_t8_blindness.py:3-5) | (b) an engine-blind plexus/organs/lifecycle.py plus Cozy glue; (c) start, stop and probe on `Organ` | To (b): one more step and file, `NO_PXR` gains the module (test_layers.py:31-34), LB2 to LB10 keep their reads. To (c): a spec 8.1 change, and any neuron holding an organ could start an engine (rule 7). |
| D3 | An engine whose host died | **(a)** never adopt: the next host reads it as `ready`, spawns nothing and its `stop()` refuses; Joe stops it by hand | (b) the engine dies with its host (Job Object kill-on-close, PR_SET_PDEATHSIG); (c) adopt through a saved pid (rejected: two hosts can both adopt) | (b): about 45 lines of ctypes in L2, one child-host case, one CONTRACT sentence; worth measuring before M4. (c): about 40 lines, two cases, a pid file. |
| D4 | The first live run | **(a) then (b)**: by hand after the keep, with Joe present, port 8190, G:/COMFY/ComfyUI, `extra=["--user-directory", <a Plexus folder>]`, accepting comfy-cli's `recent_workspace` write; then a later non-frozen step | (c) no live run in M3 | (b) now: one more step and a non-frozen target. Isolating USERPROFILE: about 6 lines and one env assertion, and it moves the torch and Hugging Face caches. |
| D5 | Spurious re-wakes on another participant's first write (neuron.py:291-297) | **(a)** document it; frozen wake windows register every participant and publish every organ before `start()`; the core fix lands before M4 sends jobs from organ-state wakes | (b) fix `_on_event` in M3 | (b): a third step on neuron.py (`--may-add NeuronRuntime._on_event`, about 15 lines), one frozen case, every phase-1 wake case kept green. |

**Also for Joe to weigh, none of which blocks placing** (from the proof, `m3/proof/pass2/PROOF.md` "Problems"):
- **Answered, Joe, Nov 10: `start()` while its own process is still starting.** CONTRACT sentence 7 gains a half-sentence: "while a process this lifecycle started is still alive, a further `start()` spawns nothing more and waits on that process the same way." LB9 reads it: while the reboot loop has main.py paused, a second `start()` runs on its own thread, returns `ready` once main.py comes back, and `cli_seen.jsonl` still holds one run. Mutant X8 (spawn on `starting` too), which survived pass 2, now fails LB9 with "ran the command again: 2 runs" (Claude's rerun, `m3/verify/x8.py`).
- **Two clauses only the exact code holds**: stdin at end of file (C4: under pytest's fd capture an inherited stdin is the null device too) and the wait for the port after the kill (C14: the fake's port closes with its process). Both are in the step text and named in the test's docstring; D4's live run is their only real read.
- **X9 is equivalent under CONTRACT**: without the identifier check the published check still raises `ValueError` with nothing authored, with a message naming an empty path.
- **Answered, Joe, Nov 10: the log opens after `report('starting')`.** In the reference `_spawn`, `self._tell('starting')` now comes before `out = open(self._log, 'ab') ...`, so a `report` that raises there leaves no file open; `starting` still comes before `Popen`. The swap is in the reference, L2_block.txt, L2's step text, STEPS.md and the toml, and L2's why-paragraph says "starting is reported first, before the log is opened and before Popen". No case reads it (LB12 uses `log=None`); the exact code carries it.

**Calls made without asking** (each follows a rule or ruling; Joe can overturn any):
- Foreground only; never `--background`, `comfy stop`, `comfy env` or `comfy which`. The host alone starts and stops engines (blueprint 5.2 rule 7).
- A `report` callback, not a runtime argument, so cozy.py never imports `plexus.core`.
- The constructor measures, so a state a dead process saved is replaced before the constructor returns.
- Standard library only, no psutil: declaring it edits frozen `pyproject.toml`.
- **No frozen test file in the worker's context** (section 4). Each step's text gives every new line, and each failure text quotes its CONTRACT sentence.
- L2 names `after = ["L1"]`: its bridge cases LB1 and LB11 call `publish_organ_state`.
- The gate's `--may-add NeuronRuntime.publish_organ_state` replaces M2's name, so a change to `publish_organ` now drops too.
- Seven known fixes, each tried on real failure text (section 3), each anchored once in the brief.
- No C3: the gate has read `--may-add` since M2's C3.

## 2. What the frozen files read

| File | Items | Scored | At `a7806e5` | With its reference |
|---|---|---|---|---|
| `phase2/test_organ_state.py` (L1) | 15 | yes, under `phase2` | **15 failing**, each "NeuronRuntime has no method publish_organ_state" plus sentence 1 | 0 failing |
| `phase2/test_organ_lifecycle.py` (L2) | 19 | yes, under `phase2` | **19 failing**: 17 "plexus.organs.cozy has no CozyLifecycle" plus sentence 4, 2 (LB1, LB11) "NeuronRuntime has no method publish_organ_state, which the host bridge calls" plus sentence 11 | 0 failing |
| The rest of `phase2` | 181 | yes | 0 failing | 0 failing |
| `phase1` | 30 | no, read on each keep | 30 passing | 30 passing |
| `CONTRACT.md` | DESIGN section 2's eleven sentences and the left-open line, three insertions | | | |

Drafts (sha256): `test_organ_state.py` `18db1de39a7f…`, `test_organ_lifecycle.py` `cb019bf4ac24…`, `CONTRACT.md` `c57b7a56572e…`. **The baseline the harness starts from: 34 failing of 215** in `phase2`.

**Base** (a7806e5 with the drafts laid in; proof pass 2):

| Run | Result | Time |
|---|---|---|
| the two new files | 34 failed of 34, each its own AssertionError, no collection or import error | 3.2 s (wall 7.1 s) |
| phase 2 whole | 181 passed, 34 failed | 24.0 s |
| phase 1 | 30 passed of 30 | 32.8 s |

**Reference** (a7806e5 plus reference neuron.py `a378b0afad35…` and cozy.py `edd835448d43…`, uncommitted):

| Run | Result | Time |
|---|---|---|
| the two new files | 34 passed of 34 | 77.2 s |
| phase 2 whole | 215 passed | 98.3 s |
| phase 1 | 30 passed of 30 | 32.5 s |
| `harness/plexus_loop/guards` | 9 passed | 0.3 s |
| T8 | 2 passed | 0.5 s |
| `tests/harness_plexus_loop/test_neuron_unchanged.py` | 13 passed | 4.7 s |
| gate with `--may-add NeuronRuntime.publish_organ_state` | rc 0, "every statement of the last kept commit stands" | |
| gate with no option | rc 1, "new: NeuronRuntime.publish_organ_state" | |
| ruff on the two files | one F841 at cozy.py:227, already at a7806e5 (CozyOrgan's history read); nothing new | |

**Mutants** (59, each one edit of the reference, run with `-x` on the two new files, restored byte for byte, psutil scan after each): **55 caught, 4 survived.**

| Step | Mutants | Caught | Survived |
|---|---|---|---|
| L1 (N1 to N13, P9, X1, X9) | 16 | 15 | X9 |
| L2 (C1 to C27, P1, P2, P4 to P8, X2 to X8, X10, X11) | 43 | 40 | C4, C14, X8 |

| Survivor | Clause | Why it survives | Judged |
|---|---|---|---|
| X9 | sentence 3, organ id not a prim name | equivalent: the published check raises the same `ValueError` with nothing authored | not important |
| C4 | sentence 7, stdin at end of file (stdin=None) | structural: under fd capture an inherited stdin is the null device; an unread PIPE (C27, P1) is caught | not important |
| C14 | sentence 9, returns once the port refuses | structural: the fake's port closes with its process | not important; D4's live run |
| X8 | sentences 5 and 8, once per start | a gap in CONTRACT: `start()` during its own `starting` spawns again; reachable only by two threads | minor; section 1 |

**Flake** (reference, serial):

| Run | Repeats | Result | Times |
|---|---|---|---|
| the two new files | 10 | 340 of 340 case runs green | 76.87 to 79.50 s (wall 80.5 to 83.9 s) |
| phase 2 whole | 3 | 215 passed each | 100.67, 99.74, 109.18 s |
| counting the reference rung | 11 and 4 | no failure, no WinError 10055 | |

No process was left over after any rung, mutant or flake run.

## 3. The steps and the mission file

**L1, `plexus/core/neuron.py` only.** 4,744 characters, O2b's whole-file form. It says where the method goes (after `publish_organ`'s `return path`, before `def start`), gives its 26 lines at their indent, says why each part is there, and that nothing else changes. All 25 non-blank added lines of the reference diff are whole lines of the step text (checked by `build_and_lay.py`).

**L2, `plexus/organs/cozy.py` only, `after = ["L1"]`.** 14,076 characters. Three changes in file order: four imports, the widened `collections.abc` line (shown as the whole import block), and the appended block of six constants, `_port_open` and `CozyLifecycle`, exactly. All 138 non-blank added lines of the reference diff are whole lines of the step text. It tells the worker to leave CozyOrgan's unused `e` (ruff F841) alone.

Both texts are `m3/reference/STEPS.md`'s, byte for byte, hold no `'''` and no backslash, and round-trip through `tomllib` unchanged.

**The mission file:**
- `requires`: both new frozen files, `test_t7_round_trip.py`, `tests/acceptance/phase1`, `tests/harness_plexus_loop/test_neuron_unchanged.py`.
- `focus`: `neuron.py` and `cozy.py`; `frozen` as M2.
- `context`: the brief and CONTRACT.md only.
- Metric `pytest_failures` on `tests/acceptance/phase2`, `timeout_s = 600`: every new call is bounded (10 s a publish or construct, 20 s a start or stop), so a hanging reply costs about 20 s a case over 34 cases.
- Gates as M2: `layers`; `neuron_unchanged --may-add NeuronRuntime.publish_organ_state`; `core`; `predicate_smoke`; `cargo`; the narrowed `unit` set.
- Worker block as M2 (`qwen3-coder:30b`, `timeout_s` 4800, `context_chars` 95000, `num_ctx` 49152). Router `first`. Budget 8 attempts, 6 hours, 8 consecutive failures. Fix router `none`.
- **The harness keeps on the net count only.** A `cozy.py` that passes the 19 and breaks a CozyOrgan test still keeps; the whole-folder metric makes it visible and the read of phase 2 on each keep catches it.

**Known fixes: seven, each anchor once in the brief** (`check_fixes.py`, `check_fixes.out`):

| Match | Anchor | Real text it hit |
|---|---|---|
| `NeuronRuntime has no method publish_organ_state` | `` `publish_organ_state` is a method of `NeuronRuntime` `` | proof base_new.log and base_phase2.log (17 cases each) |
| `plexus\.organs\.cozy has no CozyLifecycle` | `` `CozyLifecycle` is a new class at the end of `cozy.py` `` | proof base_new.log and base_phase2.log (17 cases each) |
| `adds NeuronRuntime\.publish_organ_state and changes nothing else` | ``The `neuron_unchanged` gate compares`` | the gate in `wt/` on L1 plus `import os.path` |
| `plexus/core/neuron\.py holds \[` | `The core is blind to the engine` | LS1 in `wt/` on L1 plus a comment naming ComfyUI |
| `never an unread subprocess\.PIPE` | ``never an unread `subprocess.PIPE` `` | LB3 in `wt/` on the reference cozy.py with mutant P1 |
| `Comfy-Cozy is a reference only` | ``Never import `agent`, `cognitive` `` | the guards in `wt/` on cozy.py plus `import agent` |
| `these modules must stay free of pxr` | ```cozy.py` never imports `pxr` `` | the guards in `wt/` on cozy.py plus `from pxr import Sdf` |

## 4. Context and prompt measures

Measured with the harness's own `build_prompt` (`budget_m3.py`, `budget_m3.out`) in the scratch clone with everything laid in, `context_chars` 95,000, the metric tail at its 4,000-character cap, a gate's output at `FEEDBACK_CHARS` 4,500, and real target failures. The handed-on file is the reference file, a whole reply's size. L2 runs with the reference neuron.py laid in (L1 kept); its first prompt's Files holds that neuron.py whole, `publish_organ_state` included (checked).

| Prompt | Characters | About tokens | Room | Left out | Files, in order |
|---|---|---|---|---|---|
| L1 first | 59,846 | 14,961 | 35,154 | nothing | brief, CONTRACT, neuron.py, cozy.py |
| L1 after a gate-passing drop, neuron.py handed on | 68,685 | 17,171 | 26,315 | nothing | brief, CONTRACT, cozy.py, neuron.py (handed on) |
| the same with the three longest failures | 68,816 | 17,204 | 26,184 | nothing | |
| L1 after a gate drop | 64,498 | 16,124 | 30,502 | nothing | brief, CONTRACT, neuron.py, cozy.py |
| L2 first (L1 kept) | 71,078 | 17,769 | 23,922 | nothing | brief, CONTRACT, neuron.py, cozy.py |
| L2 after a gate-passing drop, cozy.py handed on | 86,855 | 21,713 | 8,145 | nothing | brief, CONTRACT, neuron.py, cozy.py (handed on) |
| the same with the three longest failures | 86,915 | 21,728 | 8,085 | nothing | |
| L2 after a gate drop | 75,654 | 18,913 | 19,346 | nothing | brief, CONTRACT, neuron.py, cozy.py |

The brief is 4,663 characters. L1 has 15 target failures (longest 587 characters), L2 19 (longest 1,473). **L2's handed-on prompt is the tight one: 8,085 to spare.** A reply about 8,000 characters longer than the reference cozy.py (19,291) would push `neuron.py`, the only Files entry, out first. If that happens, the lever is L2's why-paragraph (4,672 characters), not the context list. With a frozen test in context these prompts would grow by about 22,000 to 42,000 characters, past the budget on L2.

## 5. Scaffolding, each its own commit

- **C0, Joe's:** `place_organ_lifecycle_tests.sh` cuts `mission/organ-lifecycle` from `mission/organ-registry` and commits the two frozen tests and CONTRACT.md alone.
- **C1, Claude's:** `organ-lifecycle.toml`, `organ-lifecycle.worker.md` and this plan, into `harness/plexus_loop/missions/`.
- **C2, Claude's:** program rule 2 also names `mission/organ-lifecycle` and `plexus-loop/organ-lifecycle` (`C2_program_rule2.diff`, one line).

## 6. How it starts

1. Joe answers D1 to D5. Any answer other than the recommended one changes frozen bytes: Claude re-proves and regenerates the pins first.
2. Joe runs `! bash "C:/Users/User/AppData/Local/Temp/claude/a1cf58fc35533771/0e857ac5-42ca-45b8-a5d9-b5ef72ac971b/scratchpad/m3/mission/place_organ_lifecycle_tests.sh"`. It checks the three hashes, that it runs on `mission/organ-registry` with a clean tree, that `mission/organ-lifecycle` does not exist, that CONTRACT.md is still a7806e5's blob and that neither test exists; it cuts the branch and commits the three files alone. Nothing is pushed.
3. Claude commits C1 and C2, then runs `python -m harness.plexus_loop check harness/plexus_loop/missions/organ-lifecycle.toml`.
4. On Joe's go, Claude pushes `mission/organ-lifecycle` (rule 2, after C2), then `run`.
5. On each keep: phase 2 and phase 1 whole, the gate with `--may-add`, `git show --stat`, a psutil scan for leftover fakes, then the reviewer and the adversary. After an L2 keep, D4's live run on port 8190 with Joe present, never 8188, and never `tests/acceptance/live/test_organ_live.py` during the mission.

## 7. Where it lives

All of it is under `C:\Users\User\AppData\Local\Temp\claude\a1cf58fc35533771\0e857ac5-42ca-45b8-a5d9-b5ef72ac971b\scratchpad\m3`.
- **What Joe places:** `C:\Users\User\AppData\Local\Temp\claude\a1cf58fc35533771\0e857ac5-42ca-45b8-a5d9-b5ef72ac971b\scratchpad\m3\frozen\` (`test_organ_state.py`, `test_organ_lifecycle.py`, `CONTRACT.md`), through `C:\Users\User\AppData\Local\Temp\claude\a1cf58fc35533771\0e857ac5-42ca-45b8-a5d9-b5ef72ac971b\scratchpad\m3\mission\place_organ_lifecycle_tests.sh`.
- **C1 and C2:** `C:\Users\User\AppData\Local\Temp\claude\a1cf58fc35533771\0e857ac5-42ca-45b8-a5d9-b5ef72ac971b\scratchpad\m3\mission\` `organ-lifecycle.toml`, `organ-lifecycle.worker.md`, `organ-lifecycle.plan.md`, `C2_program_rule2.diff`.
- **Scripts and record (same folder):** `build_and_lay.py` (builds the toml from `toml_template.txt` and STEPS.md, lays everything into `wt\`), `check_fixes.py` and `corpus.txt`, `budget_m3.py` and `budget_m3.out`, `check_output.txt`, `dry\` (the two placement clones, `dry_run.out`, `dry_compare.out`), `wt\` (the scratch clone at a7806e5).
- **Inputs:** `m3\design\DESIGN.md` and `judge_probe\`, `m3\reference\` (STEPS.md, the reference files and diffs), `m3\proof\pass2\PROOF.md` and `logs\`, `m3\frozen\NOTES.md` and `CHANGES.md`.

## 8. The adversary's findings and how each was answered

`m3/adversary/FINDINGS.md` does not exist. Its findings are quoted item by item in `m3/frozen/CHANGES.md`, and the proof worked from those, as this plan does.

| # | Finding | Answer |
|---|---|---|
| 1 | HARD: sentence 7's output routing had no reading case (P1, P2, P11) | Fixed. FAKE_MAIN writes about 250 KB to stdout and 260 KB to stderr before it binds; LB2 reads "appended" and "stderr"; P1 is caught by LB3 and its text carries the SPAWN line, which known fix 5 matches. |
| 2 | HARD: sentence 10 read only for `start()`; sentence 9's "touches nothing" unread (P4, P5, P6, P8) | Fixed. LB12 `[constructor, starting, stop]`; LB3 and LB4 assert a refused `stop()` reports nothing. |
| 3 | HARD: no containment if an attempt ignores `command` or `port` | Fixed. An autouse fixture points USERPROFILE and HOME at tmp_path and fails any connect to 8188 from the test process. |
| 4 | SOFT: LB6 accepted a bare `main.py` (P7) | Fixed: LB6 asserts the full path is in the message. |
| 5 | SOFT: the registry guard missed `__import__`, importlib and comfy-cli (P9) | Fixed: LS1 ends with a text guard (no `plexus.organs`, no `comfy` in neuron.py); known fix 4 matches it. |
| 6 | SOFT: two misleading texts | Fixed: SENTENCE_7 is CONTRACT word for word; the PIPE advice is its own SPAWN line; `port_race` speaks only when the fake never ran. |
| 7 | SOFT (reference): "its output is in None" | Fixed in the reference and so in L2's text: "its output was discarded". |
| 8 | SOFT (design): D4's live run and a start lock | Not in the tests; D4 is Joe's (section 1). |
| 9 | SOFT: timing margins under load | No change; START_S stays 20; flake 340 of 340 and 4 of 4. |
| proof C7 | "appended to log" unread | Fixed: LB2 writes an earlier line first and reads both. |
| proof C4, C14 | structural survivors | No change; named in the docstring; section 2. |
| proof X8 | start during its own `starting` | Surfaced for Joe (section 1). |
| proof, reference | log opened before `starting` | Surfaced for Joe (section 1); L2 carries the proved reference. |

## 9. Check

Run in the scratch clone `wt\` at a7806e5 with the three frozen drafts, the three mission files and C2 laid in (`check_output.txt`):

```
mission organ-lifecycle: worker ollama (qwen3-coder:30b), 6 gate(s), metric pytest_failures
Houdini: running; next attempt runs on the cpu
worker: check does not load qwen3-coder:30b; run loads it first and refuses if it cannot
ready
rc=0
```

Known fixes (`check_fixes.out`): all seven match real failure text and every anchor occurs exactly once in the brief; the clone's files were restored byte for byte and a psutil scan found nothing left over.

Placement dry run (`dry\dry_run.out`, `dry\dry_compare.out`): in two `git clone --shared` clones of E:/Plexus on `mission/organ-registry` at a7806e5, each with a copy of the script whose only change is its `cd` line, both runs committed the three files alone on a new `mission/organ-lifecycle` with parent a7806e5 and the same tree; after Joe's Nov 10 answers the re-run in fresh clones (`dry2\`) gives tree `7fbaab4f1f2a99afe60741503a3f2ee57113b0ee` in both, 1,183 insertions; the message ends with the Co-Authored-By line; no remote ref changed. A second run refused ("this runs on mission/organ-registry ..., and you are on mission/organ-lifecycle"), and a third, back on `mission/organ-registry`, refused ("mission/organ-lifecycle already exists"). E:/Plexus was untouched: still `mission/organ-registry`, clean, no `organ-lifecycle` ref.


## 10. Re-proof after Joe's Nov 10 answers (Claude's own rerun)

Changes: CONTRACT sentence 7's half-sentence and LB9's reading case (drafts `frozen\prev2\` before); the log open moved below `report('starting')` in the reference and everywhere its code is quoted (`reference\prev2\`). `test_organ_state.py` is unchanged. Run serially by Claude in a fresh `git clone --shared` at a7806e5 (`m3\verify\`, `ladder.py`, `x8.py`):

| Run | Result |
|---|---|
| base: the two new files | 15 of 15 and 19 of 19 fail, each its own AssertionError |
| base: phase 2 whole, phase 1 | 181 passed, 34 failed; 30 of 30 |
| reference: the two new files | 15 of 15; 19 of 19 in 78 s |
| reference: phase 2 whole, phase 1 | 215 passed in 102 s; 30 of 30 |
| guards, the gate's own test | 9 and 13 passed |
| gate with and without `--may-add NeuronRuntime.publish_organ_state` | rc 0; rc 1, "new: NeuronRuntime.publish_organ_state" |
| X8 (spawn while starting) | caught by LB9: "ran the command again" |
| the lifecycle file, three repeats | 19 of 19 each, 78 s each |
| leftover processes | none |

Package: the toml rebuilt from STEPS.md (only the swap and the why-sentence differ); `check` ready, rc 0 (`check_output2.txt`); seven known fixes still hit (`check_fixes2.out`); prompts re-measured (`budget_m3_2.out`), nothing left out; placement pins regenerated (`place_organ_lifecycle_tests.sh`, previous in `.prev2`).
