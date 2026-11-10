# Mission `organ-registry`: plan

**M2 puts organs on the stage.** Step R1 adds one method, `NeuronRuntime.publish_organ(profile) -> Sdf.Path`, to `plexus/core/neuron.py`. The host calls it at startup with the organ's profile, the way it calls `register`. The method defines one `PlexusOrganAPI` prim in the runtime's edit layer, so every participant's runtime sees which engines exist. Step R2 closes nine escapes, 53 cases, where the Cozy organ still lets a reply end as something other than `OrganError`. Each step changes one file. Both are proved against references, apart and together, at `0428f77`.

## 1. Decisions for Joe before placement

### Decision 1: where organ prims live

**Answered, Joe, Nov 9: "Go with the architect's prim-location recommendation": A.** The method's owner is the runtime under either option.

| | **A · `/Plexus/Organs/<organId>`** (recommended) | **B · `/Exchange/<participant>/Organs/<organId>`** |
|---|---|---|
| The publisher's runtime stage | sees it | sees it |
| Every other participant's runtime stage | sees it (measured) | sees it (measured) |
| A fresh process opening `exchange.usda` | sees it, `PlexusOrganAPI` applied (measured) | sees it |
| A project made by `stagekit.create_project`, which references only `/Exchange` | **does not** | **sees it**, `PlexusOrganAPI` applied (measured) |
| Two participants publish one organ id | **one shows**: the stronger sublayer wins on every stage, and the weaker's republish is invisible even to its own stage (`probe_collision.py`) | **both show**, each with its own endpoint |
| Where a neuron finds all organs | one root | every participant's `Organs` |
| Spec §3 | matches | departs; needs a v5.4/Patch note and Joe's word |

**Why A.**
- Spec §3 is normative for schemas (Blueprint §14), and it names this path.
- Joe's goal is every agent aware of all the networks. Agents are neurons, and every participant's runtime composes `/Plexus/Organs`.
- Runtime records already live under `/Plexus`: `register` writes `/Plexus/Neurons/<name>` there.
- M4 gets one root to scan.

**The real cost of A is one organ id per exchange.** When two participants publish one id, the stronger participant's profile wins. `CozyOrgan.ORGAN_ID` is the constant `"cozy"` (`cozy.py:20`), so a per-endpoint organ id is a follow-up for the organ in M3 or M4, under either option.

**A conflict to see.** `harness/CAPSULE.md`'s M2 line says "every neuron *and project* sees which engines exist". Under A, projects do not. Under B they do.

**Why the owner is a runtime method and not a `_Ctx` method:**
- `check_allowlist` would drop a `_Ctx` write to `/Plexus/Organs`.
- Blueprint §5 rule 7 says no neuron may install or swap an organ.
- Spec §3 says capabilities are "interrogated at registration".
- `register()` already writes `/Plexus/Neurons` ungated.

Under B a `_Ctx` method would become gate-legal, but rule 7 and "interrogated at registration" still hold.

**What a flip to B costs:** two code lines and the contract sentence's path.
- The method's `root = "/Plexus/Organs"` becomes `root = f"/Exchange/{self._participant_id}/Organs"`, in the reference and in R1's text.
- The frozen test's `ORGAN_ROOT = "/Plexus/Organs"` becomes `ORGAN_ROOT = f"/Exchange/{NEURON_PARTICIPANT}/Organs"`. The test's project-B assertion follows `ORGAN_ROOT`, so it needs no edit.
- It was rehearsed. With `ORGAN_ROOT` flipped alone, run on the reference with only its root line flipped (mutant M02b), 40 tests passed. Today's root on M02b failed 38, and the flipped root on the unflipped reference failed 38. Both files were restored byte for byte.
- A flip changes the registry test's and CONTRACT.md's bytes, so Claude re-proves them and regenerates the placement script's pins before Joe places anything.
- It also touches words, not code: R1's sentence "there is no publication gate, because /Plexus/Organs is the runtime's own record", the brief's lines on `_Ctx` and on `/Plexus`, the toml's header comment, and this plan.

### Decision 2: `"status": null` as an error

**Answered, Joe, Nov 9: drop the two null cases; a null status means done.** Evidence: ComfyUI's `PromptQueue.task_done` takes `status: Optional[...]` and writes `'status': None` when given none (`G:\COMFY\ComfyUI\execution.py`, `task_done`). The draft holds 51 cases; R2's change Eight reads `isinstance(entry.get('status') or {}, dict)`, and the two reads `entry.get('status', {}).get('status_str')` in `stream` and `result` become `(entry.get('status') or {}).get('status_str')`, without which a null status would escape as `AttributeError` there. A scratch probe, not frozen, shows a null-status entry giving a record from `result` and `['done']` from `stream` on the reference, and `AttributeError` from both at `0428f77`.

R2's test freezes a history entry whose `status` is `null` as an `OrganError`: 2 of its 53 cases, via `stream` and via `result`. The L2 lane believes, unverified, that ComfyUI may treat `status` as optional or nullable. The stock worker always sets it, and the live run passed.

- **If `null` is possible for a finished job:** drop the `null` id from the test (51 cases), and change line Eight of R2 to `isinstance(entry.get('status') or {}, dict)`. Claude then re-proves and re-pins.
- **If not:** place it as it is.

### Decision 3: CONTRACT.md's `publish_organ` sentence

**Answered, Joe, Nov 9: the pass-2 wording is applied** to the placed CONTRACT.md.

The final CONTRACT.md carries the first-pass sentence, unchanged. The R1 lane's second pass proposes three more wordings, which the frozen test's messages already lean on:
- capabilities sorted by code point, as Python's `sorted()` orders them;
- capabilities a `list` or `tuple` of `str`;
- any other value Sdf cannot hold raises.

The proposal is `m2/frozen/CONTRACT_proposal_pass2.txt`, and it is not applied.

### Also for Joe to weigh, none of which blocks placing

- **Spec-only pins that are now frozen.** These are pinned by the test, not by the CONTRACT:
  - capabilities as a tuple, empty, or padded with spaces;
  - an empty endpoint, or one with a trailing slash;
  - a kind given as a `str` subclass;
  - an untyped prim (`typeName ''`);
  - `Sdf.Path` as the return type;
  - the organ id `über`;
  - lone-surrogate values raising with nothing authored, in any class.
- **One test reaches past the CONTRACT's surface.** `test_the_file_holds_the_organ_before_the_lock_is_let_go` replaces the private `rt._lock` with a recording `RLock`. A rename of `_lock` breaks the test, not the behaviour.
- **Two mutants survive on purpose, and the test's docstring says so.**
  - M33: no `Sdf.ChangeBlock`. The axon gets more notices and coalesces them, and nothing a caller reads changes.
  - M43: the five attributes authored in another order. USD reads by name, so pinning the order would pin the code's shape.
- **The widened-registry test finds the `allowedTokens` lines by their exact text.** If the schema generator's formatting changes, the test fails saying it cannot widen the file. It never passes falsely.

## 2. What the frozen files read

| File | Items | Scored | At `0428f77` | With its reference |
|---|---|---|---|---|
| `phase2/test_organ_registry.py` (R1) | 40 | yes, under `phase2` | **39 failing**, all the missing method; 1 passes, the guard | 0 failing |
| `phase2/test_organ_reply_shapes.py` (R2) | 53 | yes, under `phase2` | **53 failing**, each with the escape it names | 0 failing |
| The rest of `phase2` | 82 | yes | 0 failing | 0 failing |
| `phase1` | 30 | no, read on each keep | 30 passing | 30 passing |
| `live/test_organ_live.py` | 5 | no: `integration`, a skip counts as a failure | 5 passing | 5 passing in each lane, 0 skipped |

**The baseline the harness starts from: 92 failing of 175** in `phase2` (39 + 53). It was measured with both drafts and the final CONTRACT.md laid in at `0428f77`, in 22.6 s.

**R1's ladder** (verify lane, second pass). Draft sha `03b859f8…`.
- **Base:** 39 failed and 1 passed.
  - 38 failures read `AttributeError 'NeuronRuntime' object has no attribute 'publish_organ'`.
  - The widened-registry failure reads "publishing each gave AttributeError AttributeError".
  - No failure has another cause.
  - The one pass is the guard, `test_neuron_names_no_organ_kind_and_imports_no_organ`, which passes before and after, as T8 does.
- **Reference:**
  - The draft passes 40 of 40.
  - Phase 2 passes 122 of 122, and phase 1 passes 30 of 30, with no lone failure to rerun.
  - T8 passes 2, and `harness/plexus_loop/guards` passes 9.
  - The gate's own new test passes 13.
  - Live passes 5 with 0 skipped, in 62 s.
- **Gate:** with `--may-add NeuronRuntime.publish_organ` it returns rc 0. Without the option it returns rc 1, `new: NeuronRuntime.publish_organ`.
- **Mutants:** 63 mutants and 2 controls. 61 are caught, and M33 and M43 survive, as section 1 says. The first pass's gate mutants: G0 rc 0, and G1 to G7 rc 1, all 8 as expected.

**After Joe's Nov 9 decisions (re-proved, `m2/final/logs/reprove_*.txt`):** R1's draft unchanged, 39 failing of 40 at `0428f77` and 40 of 40 on the reference; R2's draft 51 failing of 51 at `0428f77` (AttributeError 20, TypeError 12, KeyError 5, BadStatusLine 5, IncompleteRead 6, ValueError 1, InvalidURL 2) and 51 of 51 on the reference; phase 2 90 failing of 173 at `0428f77` and 173 of 173 with both references; phase 1 30 of 30; T8 2 of 2; guards and the gate's test 22 of 22; the gate with `--may-add` rc 0, without it rc 1. First prompts, measured with `build_prompt` and a 4,000-character baseline tail: R1 75,522 characters, R2 after R1 keeps 79,446, nothing left out, 15,554 to spare. The numbers below are the lanes' first proof, before the decisions.

**R2's ladder** (L2 lane). Draft sha `739c6baf…`, before Decision 2.
- **Base:** 53 failed of 53. Every case fails with the escape it names:
  - AttributeError 22, TypeError 12, KeyError 5, BadStatusLine 5, IncompleteRead 6, ValueError 1, InvalidURL 2: 53 in all, no overlap (corrected from the lane's summary by the critic, from `l2/logs/base_draft_table.txt`).
  - Every HTTP-fault case reached its intended route, and none ended as an OSError reset.
- **Reference:** `reference_cozy.py` is +46 -22, and its one new import is `http.client`.
  - The draft passes 53 of 53.
  - Phase 2 passes 135 of 135, and phase 1 passes 30 of 30.
  - The guards pass 9 of 9.
  - Live passes 5 of 5 with 0 skipped, in 55.6 s.
  - Ruff finds nothing new.
- **The lane's own findings:**
  - A ninth escape: a refusal whose body stops short raises `IncompleteRead` from `e.read()` in `submit`'s `HTTPError` branch.
  - The brief's premise for case 8 was wrong. `InvalidURL` is an `HTTPException`, not a `ValueError`.

**Both references in one tree** (this package, Nov 9):
- Phase 2: 175 of 175 in 22.9 s.
- Phase 1: 30 of 30.
- The guards and the gate's test together: 22 of 22.
- The gate with `--may-add`: rc 0. With no option: rc 1.
- **Live was not run in the combined tree.** ComfyUI at `:8188` did not answer `/system_stats` in 2 minutes of polling, and it is shared, so it was not started. Each lane ran live 5 of 5 on its own reference, and R1 changes no organ code.

## 3. The steps and the mission file

**R1, `plexus/core/neuron.py` only.**
- Its text is O2b's form: one whole-file block and never a diff.
- It says where the method goes: inside `NeuronRuntime`, after `register`'s `return handle` and before `def start`.
- It gives all 53 lines of the reference method at their indent. A check confirms that each of the 51 non-blank added lines of `reference/neuron.diff` is a line of the step text.
- It says why each part is there, and that nothing else changes, because the gate drops it.
- None of the lines it hands over names an organ kind.

**R2, `plexus/organs/cozy.py` only.** Its text is the L2 lane's `STEP_R2.md` block, byte for byte (checked). It gives eleven changes as exact code, in file order.

**Order.** The router is `first`, and R2 names no `after`, because the two files are independent. R1 therefore has every attempt until its 40 targets pass, and R2 starts then. If R1 stalls for the whole budget, R2 never runs in this mission.

**The mission file:**
- `focus` is the two files, and each step's `files` names only its own.
- The metric is `phase2` whole, 175 items, with `timeout_s` 600: a `publish_organ` that hangs costs about 10 s in each of some 39 tests, past 300 s (critic). R2's draft only checks that bad replies are refused, and T7, `test_organ_surface.py` and `test_organ_malformed.py` check that good ones still come through.
- **The harness keeps on the net count only** (`loop.py`, "no strict gain"). A `cozy.py` that fixes the 53 and breaks a few of those tests still keeps. The whole-folder metric makes such a keep visible, and the read of phase 2 whole on every keep (section 5) is what catches it. No gate refuses it.
- The gates are `layers`; `neuron_unchanged` with `--may-add NeuronRuntime.publish_organ`; `core`; `predicate_smoke`; `cargo`; and the same narrowed `unit` set. After C3, `unit` also runs the gate's own test.
- `--may-add` replaces the default `_Ctx.author_asset`, so a change to `author_asset` now drops too.
- The worker block is mission organ-live's. Budget: 8 attempts and 6 hours. The fix router is off.

**Context, decided by measurement.** The list is: the brief, CONTRACT.md, `test_organ_malformed.py`, and `test_organ_reply_shapes.py`, which imports it. `test_organ_registry.py` (33,767 characters) is out, as `test_organ_surface.py` was in mission organ.

These are first prompts, measured with the harness's own `build_prompt` at `context_chars` 95000:

| State | R1 | R2 | Left out |
|---|---|---|---|
| Baseline, as the task names it (best 92), with the baseline metric's tail as the harness passes it | 74,968 chars, about 18,700 tokens | 75,204 | nothing |
| After R1 keeps, R2's real first state (reference `neuron.py`, best 53), with that tail | 78,270 | 78,506 | nothing |
| Baseline with the registry test in context | 94,228 | 94,464 | **`cozy.py`** |
| After R1 with the registry test in context | 80,195 | 80,431 | **`neuron.py` and `cozy.py`** |

These include the baseline metric's tail (up to 4,000 characters), which `build_prompt` counts before any file; the packager first measured without it (70,927 and 74,465), and the critic remeasured. With the registry test out, R2's real first prompt is 16,494 characters under the budget. The worst drops the critic measured: R1 after a failed gate 79,773, R2 after a failed gate 83,291, nothing left out.

**Drop prompts were not measured.** A drop's prompt adds:
- the failure text of at most 3 target tests;
- a gate's output, clipped to 4,500 characters;
- the step file it handed on, which then takes the place of its tip copy under Files.

When that runs past the budget, `build_prompt` leaves files out from the end of the list. A step's file is handed on only after a drop that passed every gate, or a left-out drop; after a gate-failed R2 drop, `cozy.py` sits last in Files and would be the first file cut. At 83,291 that drop does not trip the budget today.

**Known fixes: eight, each with an anchor that occurs once in the brief.** Each match was tried with `re.search` on real failure text in `corpus.txt`. That text comes from:
- the pass-2 mutants' failure reasons;
- both base runs;
- and, run here on one-line mutations of the worktree's files, restored at once: the gate on an extra import, the guards on `import pxr` and `import agent` in `cozy.py`, and T8 on an engine class named in `neuron.py`.

The eight fixes:
1. The missing method.
2. The gate's "this step adds NeuronRuntime.publish_organ and changes nothing else".
3. An organ kind, a `plexus.organs` import or engine vocabulary in `neuron.py`.
4. Authoring before a refusal.
5. A save outside the lock.
6. An `http.client` exception escaping.
7. Comfy-Cozy imports.
8. `pxr` in `cozy.py`.

**The run cannot start before C3:** `requires` names C3's `tests/harness_plexus_loop/test_neuron_unchanged.py` (critic's medium finding).

**The gate's `--may-add` name is exempt from changed and gone too.** Once R1 keeps, a later attempt could rewrite or delete `publish_organ` and pass the gate; the 40 frozen registry tests in the metric and the read of phase 2 on each keep catch that, not the gate.

## 4. Scaffolding, each its own commit on `mission/organ-registry`

- **C0, Joe's:** the placement script commits the two frozen tests and CONTRACT.md alone.
- **C1:** `organ-registry.toml`, `organ-registry.worker.md` and this plan, into `harness/plexus_loop/missions/`.
- **C2:** program rule 2 also names `mission/organ-registry` and `plexus-loop/organ-registry`. The one-line diff is `C2_program_rule2.diff`.
- **C3:** the gate's `--may-add`.
  - `harness/plexus_loop/neuron_unchanged.py`, from `m2/reference/neuron_unchanged.py`, sha `ac82eb91…`.
  - Its first test, `tests/harness_plexus_loop/test_neuron_unchanged.py`, from `m2/reference/test_neuron_unchanged.py`, sha `99352c9f…`, 13 tests.
  - With no option the gate behaves as before, word for word, so mission organ's known fix still matches.
  - The gate at `0428f77` reads no options. Without C3 it ignores `--may-add` and drops every R1 reply with `new: NeuronRuntime.publish_organ`.

## 5. How it starts

1. Joe answers decisions 1 to 3. Any change to a frozen file means Claude re-proves it and regenerates the pins first.
2. Joe runs `! bash "C:/Users/User/AppData/Local/Temp/claude/a1cf58fc35533771/0e857ac5-42ca-45b8-a5d9-b5ef72ac971b/scratchpad/m2/mission/place_organ_registry_tests.sh"`.
   - It checks the three files' hashes, a clean tree, and that neither test exists yet.
   - It cuts `mission/organ-registry` from `mission/organ-live`, or runs on it.
   - It commits the three files alone. Nothing is pushed.
3. Claude commits C1, C2 and C3, then runs `python -m harness.plexus_loop check harness/plexus_loop/missions/organ-registry.toml`.
4. On Joe's go, Claude pushes `mission/organ-registry`, which holds the frozen files, so rule 2 stops Claude without that go. Then `run`.
5. On each keep:
   - phase 2 and phase 1 whole, and the gate with `--may-add`;
   - for an R2 keep, live too, with ComfyUI answering and a skip counted as a failure;
   - `git show --stat`;
   - then the reviewer and the adversary.

## 6. Where it lives

All of it is under `C:\Users\User\AppData\Local\Temp\claude\a1cf58fc35533771\0e857ac5-42ca-45b8-a5d9-b5ef72ac971b\scratchpad\m2\mission`.

**What Joe places:** `frozen/`, the three files that `place_organ_registry_tests.sh` checks and commits.

**What Claude commits after that (C1 to C3):**
- `organ-registry.toml`, `organ-registry.worker.md` and this plan.
- `C2_program_rule2.diff`.
- The gate and its test from `m2/reference/`.

**The scripts and their record:**
- `build_frozen.py` builds `frozen/` and the final CONTRACT.md.
- `lay_in.py` lays everything into `wt/` only.
- `check_mission.py` holds the parse, text, known-fix and prompt checks.
- `build_corpus.py` writes `corpus.txt`.
- `run.py` writes `logs/`.
- `wt/` is the detached worktree at `0428f77` the checks ran in.

**Inputs:**
- `m2/design/DESIGN.md` (the architect's design; its draft test and `reference_method.py` are superseded by `m2/frozen/` and `m2/reference/neuron.py`, which R1 carries)
- `m2/reference/` (R1's method and the gate)
- `m2/frozen/` (R1's draft and its ladder driver `pass2.py`)
- `m2/verify/logs/`
- `m2/l2/` (R2's draft, its reference, `STEP_R2.md` and `PROOF.md`)

## 7. After run 1: step R2b, and what the reviews found (Nov 9)

**Run 1, on the CPU (`hserver.exe` counts as Houdini):** baseline 90 failing of 173 on `db2884c`.
- Attempt 1, R1: kept as `baf0c01`, 90 to 51, 25.8 min, prompt read 433 s. Its method is R1's 52 lines exactly.
- Attempt 2, R2: kept as `8654893`, 51 to 0, all 51 reply-shape cases flipped, nothing newly failing, 18.3 min, prompt read 258.9 s.
- The run stopped: every target test passes. On the keep's tree, phase 2 reads 173 of 173 and phase 1 30 of 30.

**The reviewer:** R1 keep, nothing hard or soft. R2 keep with a note, fix first:
- Eight's last sentence was not made: `stream` and `result` still read `entry.get('status', {}).get('status_str')`, so a null status raises AttributeError. The parent raised it too, so it is no regression, but it is Joe's Nov 9 decision left undone.
- Nine is defeated: `_history_entry`'s not-yet tuple gained `http.client.HTTPException`, against "Nothing else in the file changes", so the branch Nine added is never reached. A /history reply that breaks HTTP is read again until the deadline and reported as "Job timed out", the wrong cause: 600 s in the session, an hour by default. The frozen cases give a 1 s deadline, so they passed on the timeout.
- A blank line after Two's first try, cosmetic.
- The likely cause is the brief's line "`http.client.HTTPException`, which covers": "each HTTP call's except tuple names it" reads as that tuple too.

**The adversary** confirmed both and widened them: an empty list, an empty string, 0 and false as the status escape the same way as null, and a prompt_id holding a space takes the timeout path too, through `InvalidURL`.

**Step R2b.** Four lines, which make `cozy.py` the proved reference line for line:
- In `submit`, the stray blank line goes.
- In `stream` and `result`, the status reads become `(entry.get('status') or {}).get('status_str')`.
- In `_history_entry`, `http.client.HTTPException` leaves the not-yet tuple.

Its target is Joe's follow-up, `test_organ_history_reads.py`, 8 cases, sha256 `e1a49689…`, placed with `.plexus_loop/place_organ_history_test.sh`. The proof on `8654893`:
- 8 of 8 fail on the keep.
- With only the status reads, 2 pass; with only the tuple, the other 6. Each case reads its own line.
- With the four lines, 8 of 8 pass and phase 2 reads 181 of 181, ten runs in a row.
- Its first line credits Joe with the null ruling only; "at once" is R2's own text, Nine, so placing the file is Joe's yes to it.

Mission-file changes, commit C4:
- R2b is the third step, and its target is required and in context.
- The brief says three steps and rewords the HTTPException line. It gains a null-status line, and its stale "300 s" metric limit now reads 600.
- Two known fixes: `history status is null` hits the 2 null cases on the keep, and `again until the deadline` hits the other 6.
- R2b's prompt, built by the harness's own `build_prompt` against the 95,000-character budget, leaves nothing out:
  - first: 84,426 characters, about 21,100 tokens;
  - after a drop that passed every gate, with `cozy.py` handed on: 92,390;
  - after a drop at a gate: 89,214.
  When `cozy.py` is handed on it is not in Files, so `neuron.py`, which R2b never touches, would be the first file left out.

**Calls Claude made, by CLAUDE.md's "make the call, write the assumption":**
1. An empty list, an empty string, 0 or false as the status reads as done, as null does. R2's Eight, `isinstance(entry.get('status') or {}, dict)`, which Joe chose, already lets them past the check, and the reads now agree with it. ComfyUI writes only null or an object. No case pins them. Null-only would change Eight's line, and that is Joe's call.
2. R2b stays inside R2's own text. The adversary's new findings below are a candidate L3 lane with its own frozen test, Joe's pick when.
3. The draft's waiting cases poll every 0.5 s, so about a dozen sockets open where a hundred did. While proving, two whole-phase-2 runs failed one test each with Windows' `WinError 10055`, socket buffers exhausted. The adversary's socket-heavy probes were running then, so the cause is not isolated. The ten whole-phase-2 runs since were clean.
4. The adversary's new findings are in lines R2 did not change, and none is a regression, so Claude read them as nothing new for the merge Joe made conditional (Nov 9: "When the reviews land with nothing new, merge 8654893"). They do not change R2b. They are listed below for a later lane.

**Candidate L3, from the adversary on `8654893`:** none is a regression from R2, and three were spot-checked (3, 4 and 8).
1. A str prompt_id that is not ASCII raises `UnicodeEncodeError` at the history read; one holding `#` or `?` reads another URL and waits out the deadline.
2. A JSON reply nested 100,000 deep raises `RecursionError` on every route: `_json` catches only `ValueError`.
3. A redirect whose Location is `http://[::1` raises `ValueError` on every route.
4. In `_fetch_file` the urlencode and the file write sit outside the try. A lone surrogate or a NUL in the name escapes, and on Windows so does a name Linux allows, such as `render_12:30:00_00001_.png`, with `OSError` 22.
5. `/view`, `/system_stats` and `/object_info` reads use a fixed 60 s timeout, so a hung one holds `result()` past `deadline_s`. A /history reply that drips holds it past too, because the timeout is per read.
6. A graph holding a lock or a generator raises `TypeError` from `copy.deepcopy` before the JSON check.
7. Soft: a graph nested 3,000 deep, or a graph that is not a dict; the engine's job id on the exception chain (`__context__.url` after a 404, `__cause__.doc` after a non-JSON reply), which the brief's "say from e" invites and CONTRACT's no-id line forbids; a bad node beside a good image refuses the job while `stream()` says done; a /history reply that is JSON but not an object waits out the deadline.

The adversary's probes are in `scratchpad\adv_8654893\`, and the reviewer's are in `scratchpad\review_or\`.
