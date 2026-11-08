# Mission `organ`: plan

Status: **draft for Joe. His five answers of Nov 5 are in, and section 8 marks each with his words. Nothing below has run on the real repo and nothing has landed.** Every number comes from scratch trees in `C:/Users/User/AppData/Local/Temp/claude/E--Plexus/b30a0d29-4d4a-473f-9338-d6f7d60e541b/scratchpad/organ_prep/proof`, and every table here is filled by `proof/fill_docs.py` from `proof/results`. The ladder, the frozen file's proof, the loop, the mutants, the known fixes and the prompts come from this stage's runs, `proof/results/first_proof.log` and `proof/results/after_first.txt`. Written Nov 4, 2026, and revised Nov 5 from `mission/acceptance` at `0cee44f`. Run 30 ended while this was written: its ledger reads S9 kept at a score of 4, then S8 kept at a score of 1, then S8 kept at a score of 0, on `plexus-loop/acceptance`. Their merge is on Joe's word, and nothing here acted on it. Two attacks read the first draft, and `README.md` beside this plan says what each finding changed.

Done means every test under `tests/acceptance/phase2` passes, `test_organ_surface.py` included, and every test under `tests/acceptance/phase1` still passes. The harness metric is `pytest_failures` on `tests/acceptance/phase2`, direction lower, `min_delta = 1`. Phase 1 is held by a read of the whole phase by hand on each keep.

---

## 1. Setup facts

### Frozen tests in the target

Once Joe has placed the new file there are 58 `def test_` functions in 3 files, and 65 collected items, because some are parametrized. They cover spec IDs T7 and T8 and what those two leave unread.

| Spec ID | File | Items | What it needs from `plexus/` |
|---|---|---|---|
| T7 round trip | `test_t7_round_trip.py` | 5 | `plexus.organs.protocol.Job`, `plexus.organs.cozy.CozyOrgan` with `submit` and `result`, `ctx.author_asset` in `neuron.py` |
| T8 blindness | `test_t8_blindness.py` | 2 | no engine word anywhere under `plexus/` or `crates/` outside `plexus/organs/cozy.py` |
| Surface, draft for Joe to place | `test_organ_surface.py` | 58 | every clause of O1 and O2 that T7 and T8 leave unread, section 7 |

**Baseline on the stand-in with the file placed:** 62 failing of 65. All five T7 items and all but one item of the new file fail with `No module named 'plexus.organs'`. Both T8 items and `test_neuron_imports_nothing_from_organs` pass. Phase 1 reads 0 failing of 25 on the same tree.

**Count note.** CONTRACT.md's "18" dates from Nov 1. Today the frozen folder holds 25 phase 1 items, 7 phase 2 items and T1b in `pending/`, and the new file adds 58.

**No frozen test looks wrong.** I read T7 and T8 against CONTRACT.md, Spec sections 3, 8 and 10, and Patch 01. T7 passes on code written to the contract, and section 5 shows it failing on an organ that trusts the first history read, one that never reads history, a constant fingerprint, renumbered links and a double POST. What T7 cannot see is what the new file reads.

### Environment

`/doctor` has not run for this mission and is still owed at setup. The organ needs no install: `cozy.py` uses Python's standard library only.

### Gate timings

Measured in the scripted harness run in section 5, on the CPU profile, except `unit`, which ran once on a full scratch tree.

| Gate | Seconds | Result on the top rung |
|---|---|---|
| `layers` | 6.0 | 9 passed |
| `neuron_unchanged` | 0.2 | every statement of the last kept commit stands |
| `core` | 1.2 | builds and copies `_core.pyd` |
| `predicate_smoke` | 0.8 | passes |
| `cargo` | 1.2 | passes |
| `unit` | 401 | 365 passed, 1 warning |
| metric | 21.3 | 0 failing of 65 |

### `check` output

From the top rung, a scratch git repo that holds these files. It is pasted again from the real repo at setup.

```
mission organ: worker ollama (qwen3-coder:30b), 6 gate(s), metric pytest_failures
Houdini: running; next attempt runs on the cpu
ready
```

---

## 2. Comfy-Cozy as a reference

The seeded `agent/` code in this repo was read. `G:\Comfy-Cozy` was not touched, and the `cozy-mapper` agent has not run; it runs at setup if Joe wants verdicts beyond these. Nothing is copied or imported, and the layers gate fails any `agent.*` import.

| Module | Verdict | What the organ takes as an idea, in its own terms |
|---|---|---|
| `agent/engine/comfyui_adapter.py`, `agent/engine/_base.py` | reference, rebuild in Python | One object owns every call to the engine. The organ is new, uses `urllib`, and has no WebSocket, because T7's fake has none and the contract treats it as a hint. |
| `agent/diagnosis/diagnosis.py`, `collect_env` | reference, rebuild in Python | The environment key comes from the engine's own report and leaves out what moves between reads. |
| `agent/tools/workflow_lock.py` | reference, later | Real model hashes need more than the HTTP surface gives. `modelHashes` is an empty list in this mission. |

---

## 3. Ordered changes

The metric rewards any test that flips, and with the new file placed nearly every clause is a test. A protocol file alone moves little, because almost every test imports `cozy.py`, so the first step carries all three new files. A partial answer keeps: the smallest organ that moves the number takes the score from 62 to 47, and O1 stays the ready step until its targets pass. Its next prompt says so, and section 5 has that run.

| Step | Aimed at | Gain | Paths |
|---|---|---|---|
| O1 | T7 link test twice, `test_result_waits_for_history_and_a_real_file`, `test_env_fingerprint_tracks_the_engine_environment`, T8, and 41 functions of the new file | 62 to 12 | `plexus/organs/__init__.py`, `plexus/organs/protocol.py`, `plexus/organs/cozy.py` |
| O2 | `test_neuron_round_trip_composes_into_both_projects`, T8, and 11 functions of the new file | 12 to 0 | `plexus/core/neuron.py` |

`proof/target_split.py` reads which step makes each function pass from the ladder's own reports and writes the two lists, and it says so when the toml and the ladder differ. A function that fails on rung 0 and passes on rung 1 is O1's, and one that fails on rung 1 is O2's. `test_neuron_imports_nothing_from_organs` passes on every rung and reads `neuron.py`, so it is O2's guard.

O2 names O1 in `after`. T8 is a target of both, so an engine word that O1 lets through keeps O1 ready until it is gone, and one in `neuron.py` leads O2's next prompt. Any step's reply can still keep with an engine word in it, because the metric counts tests.

---

## 4. The mission file

`organ.toml` is a new file, so the whole file is the proposal. These are the places it differs from `acceptance.toml`.

| Field | Acceptance | Organ | Why |
|---|---|---|---|
| `metric.target` | phase1 | phase2 | The mission. |
| `metric.timeout_s` | 1800 by default | 300 | One quoted word in `_history_entry` otherwise adds 30 minutes to an attempt, and the next prompt holds nothing about why. Section 5 has the phase's time against this limit. |
| `requires` | phase 1, spec | T7, the new file, phase 1, spec | The run refuses to start until Joe has placed the new file, because the targets name it. |
| `focus` | `plexus/**` | `plexus/organs/**`, `plexus/core/neuron.py` | Only what the organ needs. A reply that touches anything else drops before anything runs, the axon and the Rust included. |
| `context` | brief, contract, support, conftest, 8 phase 1 test files | brief, contract, support, conftest, T7, T8 | The brief carries the rows of the spec this mission reads. Reading is the worker's largest cost after writing. The new file stays out, section 10. |
| `gates` | five | the same five plus `neuron_unchanged` | Section 6. The `phase1` gate is out, on Joe's word. |
| `worker.context_chars` | 150000 | 95000 | Section 5. |
| `worker.timeout_s` | 4800 | 4800 | Section 8, decision 5. |
| `router.kind` | jev | first | One step is ready at a time, so Jev would never be asked. |
| `fix_router.kind` | jev | none | Section 8, decision 8. |
| `budget` | 120, 11, 30 for the night | 8, 6, 8 for a day | Section 8, decision 6. |
| `known_fixes` | 14 | 14, all new | Each is checked against a real failure text, the new file's among them. Each anchor resolves to one brief line. |

---

## 5. The proof

This stage's run is `chain.py --first`, one chain in about 103 minutes of steps, and `proof/results/first_proof.log` holds it. It hashes what lands at the start and at the end, and the two match. The whole chain is not for this stage. It leaves out T1's margin on the top rung, facts about usd-core, the new gate's sweep, because neither the gate's script nor the code they read has changed. Those read from `proof/results/chain.log`, the last full chain, which ran before Joe's answers, on the same scratch code. They all run again on `mission/organ`, section 9. After that run one sentence of O1's text, one line of the brief, and in the frozen file one docstring sentence and the length of the waits past the allowance changed, so the hashes on disk differ from the log's in those three files. The ladder, the hand probe, the target split, the second right reply, the frozen file's own proof and the prompts read again on these final bytes, `proof/results/after_first.txt`. The mutants, the scenarios, the known fixes, the unit gate and the real tip did not, because a right reply never reaches those waits and the most waits any mutant ran out is 3, 15 s against the allowance of 30 s.

Scratch code was written from each step's text and the brief. Wherever it needed something the text did not say, the text gained that line and the code was checked against it again. `protocol.py` is pulled from the brief's own block by the script, and the script refuses a `cozy.py` that loses a line of the brief's skeleton. It also refuses a rung 0 whose `neuron.py` does not hold every line O2 and the brief name. Rung 0 is a copy of `real_full`, the nearest stand-in for S8 and S9 applied, with the frozen tests and the harness laid over it from the repo, with the scaffolding of decision 12 laid on top, and with `test_organ_surface.py` and CONTRACT's lines placed. `real_full` itself was only read.

### The ladder

| Rung | Phase 2 | The failure | Phase 1 | The hand probe |
|---|---|---|---|---|
| The stand-in as it stands, with the file placed | 62 failing of 65 | `No module named 'plexus.organs'`, what O1 names | 0 of 25 | 1 failing of 2 |
| With O1 written from its text | 12 failing of 65 | `'_Ctx' object has no attribute 'author_asset'` and `AssertionError: projectA.usda`, what O2 names | 0 of 25 | 0 failing of 2 |
| With O2 written from its text | 0 failing of 65 | none | 0 of 25 | 0 failing of 2 |

`harness/plexus_loop/guards` passes on rung 2, 9 of 9. `organ.toml` loads through `load_mission`. The real loop tip read 62, 12 and 0 of 65 on phase 2, and 0 of 25 on phase 1 at the top. The unit gate ran once on a full tree, the whole of HEAD with the top rung's `plexus/`, the mission files and the frozen file laid over it: 365 passed, 1 warning, in 401 s.

### The frozen file's own proof

**Three runs on the top rung.** Three runs of the file alone read 0 failing of 58 each, with no flicker, in 15.4, 14.4, 15.4 s.

**Order.** It reads the same in reverse order, 0 failing on the top rung, and the smallest organ fails the same 36 items in both orders. Each of the 52 functions passes alone, in its own process. On a reply where result never returns, forward fails 31 and reverse fails 31, and they are the same tests. On a reply where author_asset never returns, forward fails 11 and reverse fails 11, and they are the same tests.

**The repo's scans.** `tests/test_portability_guards.py` passes with the file placed on a full scratch tree, 3 passed, 1 warning. Its three scans read `agent/` and `cognitive/` and skip any `tests/` folder, so they never read this file, and nothing else in the repo scans it.

**On its worst wrong replies, on a busy machine.** Every wait in the file has a limit. A call into the organ waits 5 s, a wake 10 s, and a child process 60 s. The calls and the wakes draw on one allowance of 30 s, past which a wait lasts 2 s, or 5 s where it meets a closed port, so a reply that hangs on every call does not pay every limit, and a right reply never draws on it. Busy here means pytest pinned to two logical CPUs with 3 busy loops beside it, at low priority. A right reply takes the whole of phase 2 29.8 s.

| Reply | The file alone | The whole of phase 2 |
|---|---|---|
| the constructor never returns | 46 failing of 58 in 137.5 s | T7 itself hangs, so the metric's limit ends it whatever this file does |
| submit never returns | 42 failing of 58 in 129.6 s | T7 itself hangs, so the metric's limit ends it whatever this file does |
| result never returns | 31 failing of 58 in 113.8 s | T7 itself hangs, so the metric's limit ends it whatever this file does |
| the quoted word: result never sees the entry | 25 failing of 58 in 90.1 s | T7 itself hangs, so the metric's limit ends it whatever this file does |
| stream never returns | 3 failing of 58 in 40.2 s | 3 failing of 65 in 44.7 s |
| author_asset never returns | 11 failing of 58 in 68.1 s | 12 failing of 65 in 107.2 s |
| result and author_asset never return | 41 failing of 58 in 131.3 s | T7 itself hangs, so the metric's limit ends it whatever this file does |
| the smallest organ that moves the number | not read alone | 36 failing of 65 in 34.8 s |
| `result` polls with no deadline | not read alone | 3 failing of 65 in 52.4 s |
| `stream` polls with no deadline | not read alone | 1 failing of 65 in 33.7 s |
| `submit` waits for the job to finish | not read alone | 4 failing of 65 in 46.0 s |
| `author_asset` takes no lock | not read alone | 1 failing of 65 in 30.8 s |

The worst the file alone took on any of these is 138 s, and the worst the whole of phase 2 took where T7 does not hang is 107 s, against the metric's 300 s. That fits well inside, so `metric.timeout_s` stays 300.

### A second right reply

`proof/second_reply.py` holds a right reply written from the texts in another shape: other attribute names, other loops, attributes built in another order, a direct read of `/system_stats`, `createdAt` with a Z: on O1 it fails the same tests the ladder's rung 1 fails, 12, it passes `neuron_unchanged`, and it reads layers 0 of 9, frozen phase 2 0 of 65, frozen phase 1 0 of 25, the hand probe 0 of 2. So the file holds what the texts ask for and not the scratch code's spelling.

### The harness's own loop

The real `MissionRun` ran on a scratch git repo, with a scripted worker in place of the model, so the real gates, metric, keep rule and next prompts all ran. One change from `organ.toml`, only in that script: `unit` is left out, because it reads none of these files and it has its own run above.

| Attempt | Step | What the reply did | Result |
|---|---|---|---|
| 1 | O1 | `protocol.py` imports `pxr` | dropped at `layers` |
| 2 | O1 | the smallest organ that moves the number | kept, strict gain; score 47 |
| 3 | O1 | every GET through `_get_json` goes to a route the engine does not have | no strict gain (56 vs best 47); its files are handed on |
| 4 | O1 | the step's files | kept, strict gain; score 12 |
| 5 | O2 | `_run_action`'s mute guard is gone | dropped at `neuron_unchanged` |
| 6 | O2 | `author_asset` raises on its first line | no strict gain (12 vs best 12); its files are handed on |
| 7 | O2 | the step's file | kept, strict gain; score 0 |

### The states the placed file makes common, and the ones the attacks found

`proof/scenarios.py` runs the same loop through each state and checks what the next prompt says. It patches `core` and `cargo` in its own process, because no reply there touches Rust. All 40 of its checks hold.

- The count is long, so a reply that clears part of O1 keeps. The brief's skeleton alone, the smallest organ that moves the number, the right O1 and the right O2 read 62 to 61 to 47 to 12 to 0, and each one kept, 4 keeps in 4 attempts where the ladder's right replies need 2. O1 stayed the ready step until its targets passed.
- After a partial keep the prompt has no drop section. It holds the kept `cozy.py` under Files and a metric tail that names the failing tests, 33 of the 47 still failing. It holds no assert's message until a later attempt drops, because the harness shows a target's failure text only after a drop. So a test's name has to say its clause, and each does.
- A quoted `.get('prompt_id')` stops at the metric's own 300 s limit, read at 300.1 s, and the next prompt holds the brief's line for it and the three files.
- A partial keep's next prompt opens with what was true before the step landed, says to start from the kept copy under Files, and its metric output lists the fingerprint test as FAILED.
- A `neuron.py` that loses `plexus:tools` drops at `neuron_unchanged`, hands nothing on, and the one copy in the next prompt still holds the line.
- After a full drop on O2 the one copy is under Your last attempt's files, the text points there, and the fix keeps with no line lost.
- An O2 that loses one attribute keeps as a partial gain, O2 stays ready, and the next attempt's own `author_asset` passes `neuron_unchanged` against the kept one, because that gate lets that one method change.
- An O2 reply that also rewrites `cozy.py`, and an organ that writes its file in the working directory, both still keep, because the count falls. `git show --stat` shows each, so it is a review item, section 9.
- A diff that does not apply drops the attempt and hands nothing on, and a clean diff applies, passes `neuron_unchanged` and keeps, so the prompt's own line about diffs costs an attempt at most.

### The new gate on its own

Of 138 one-statement breaks of `neuron.py` outside `author_asset`, 138 drop. 5 right trees pass, among them a reworded docstring, two imports in another order and the second right reply. A new import, a new helper, a new method and a lost `@dataclass` all drop.

### Breaking one clause at a time

Each row is the top rung with one thing broken, run once. It reads the first thing that sees the break, in the order the gates run. I broke 78 clauses and replies one at a time. 11 fail T7 or T8, 53 fail the frozen file and nothing else in the metric, 11 are dropped by a gate before the metric, 1 show only on the hand probe: `protocol.py` names engine words outside T8's list, and 2 show on nothing and are read by eye: `layer.Save()` inside the `ChangeBlock` and no `Sdf.ChangeBlock` in `author_asset`. 8 right replies in other shapes read clean.

| Broken | What sees it |
|---|---|
| `result` never reads history | 9 failing of 65, T7 or T8 among them: `AssertionError: result() returned before /history had the job` |
| `result` trusts the first history read | 6 failing of 65, T7 or T8 among them: `plexus.organs.protocol.OrganError: not done` |
| a constant fingerprint | 7 failing of 65, T7 or T8 among them: `AssertionError: envFingerprint is the drift key; it must change with the engine` |
| the fingerprint hashes the whole `/system_stats` reply | the frozen file sees it, 2 of 65: `test_the_fingerprint_stands_still_when_only_free_memory_moves` |
| node ids and links renumbered | 5 failing of 65, T7 or T8 among them: `assert '{"103.latent...s":["108",0]}' == '{"3.latent_i...ges":["8",0]}'` |
| two POSTs per `submit` | 6 failing of 65, T7 or T8 among them: `AssertionError: assert 2 == 1` |
| the seed is never written | the frozen file sees it, 4 of 65: `test_seed_lands_in_the_seed_input_and_nowhere_else` |
| the engine id rides on the handle | the frozen file sees it, 1 of 65: `test_the_handle_carries_no_engine_id` |
| `CozyOrgan` has no `stream` | 51 failing of 65, T7 or T8 among them: `TypeError: Can't instantiate abstract class CozyOrgan without an implementation for abstra` |
| no file on disk | 28 failing of 65, T7 or T8 among them: `FileNotFoundError: [Errno 2] No such file or directory: '...` |
| a later job overwrites the file | the frozen file sees it, 1 of 65: `test_two_jobs_with_one_engine_filename_keep_two_files` |
| an engine word in a `protocol.py` docstring | 1 failing of 65, T7 or T8 among them: `AssertionError: engine vocabulary leaked into the core:` |
| `submit` writes into the job's own graph | the frozen file sees it, 1 of 65: `test_submit_leaves_the_jobs_own_graph_alone` |
| no check of the node classes | the frozen file sees it, 1 of 65: `test_a_class_the_engine_lacks_stops_before_the_post` |
| `SEED_INPUTS` holds `seed` alone | the frozen file sees it, 1 of 65: `test_noise_seed_is_written` |
| the seed overwrites an input that holds a link | the frozen file sees it, 2 of 65: `test_a_seed_wired_from_a_link_survives` |
| `images[0]` with no `OrganError` | the frozen file sees it, 2 of 65: `test_an_entry_without_images_raises` |
| an engine error entry reads as done | the frozen file sees it, 1 of 65: `test_an_error_entry_raises` |
| `/view` asked by filename alone | the frozen file sees it, 2 of 65: `test_the_saved_output_wins_over_a_preview` |
| the first output's images key, read literally | the frozen file sees it, 4 of 65: `test_an_entry_without_images_raises` |
| a refused graph loses the engine's words | the frozen file sees it, 1 of 65: `test_a_refused_graph_carries_the_engines_words` |
| the fingerprint hashes `comfyui_version` alone | the frozen file sees it, 6 of 65: `test_the_fingerprint_moves_with_every_field_of_the_environment[os]` |
| an unknown handle raises `KeyError` | the frozen file sees it, 1 of 65: `test_an_unknown_handle_is_an_organ_error` |
| a dead engine raises `URLError` | the frozen file sees it, 1 of 65: `test_a_dead_engine_is_an_organ_error` |
| metadata `engine` says comfyui | the frozen file sees it, 1 of 65: `test_model_hashes_are_empty_and_engine_is_the_organ_id` |
| `modelHashes` holds an invented hash | the frozen file sees it, 1 of 65: `test_model_hashes_are_empty_and_engine_is_the_organ_id` |
| `output_dir` kept as given | the frozen file sees it, 1 of 65: `test_a_relative_output_dir_gives_an_absolute_path` |
| `_get_json` through `requests` | the frozen file sees it, 1 of 65: `test_the_organ_imports_the_standard_library_and_the_contract_only` |
| the smallest organ that moves the number | the frozen file sees it, 36 of 65: `test_a_relative_output_dir_gives_an_absolute_path` |
| the Protocol loses an abstractmethod and `cozy.py` loses `stream` | the frozen file sees it, 3 of 65: `test_stream_says_queued_then_done` |
| the file lands in the working directory | the frozen file sees it, 1 of 65: `test_the_file_lands_under_output_dir` |
| `result` polls with no deadline | the frozen file sees it, 3 of 65: `test_no_error_core_sees_holds_the_engine_id` |
| `stream` polls with no deadline | the frozen file sees it, 1 of 65: `test_stream_stops_at_the_deadline` |
| `stream` says done on an error entry | the frozen file sees it, 1 of 65: `test_stream_says_failed_on_an_error_entry` |
| the organ keeps only the last job and ignores the handle | the frozen file sees it, 2 of 65: `test_a_second_job_under_one_id_never_takes_the_first_handle` |
| the organ never GETs `/view` and writes a placeholder | the frozen file sees it, 3 of 65: `test_the_saved_output_wins_over_a_preview` |
| `cozy.py` imports `pxr` and authors a USD layer itself | the `layers` gate drops it: `test_pxr_only_from_rank_two_up` |
| `CozyOrgan` drops the `Organ` base, `stream` and `profile` | the frozen file sees it, 5 of 65: `test_model_hashes_are_empty_and_engine_is_the_organ_id` |
| `submit` waits for the job to finish | the frozen file sees it, 4 of 65: `test_submit_returns_before_the_job_is_done` |
| `protocol.py` names engine words outside T8's list | hand only: the hand probe sees it, 2 of 2: `test_protocol_is_the_briefs_block` |
| a history error names the engine's id | the frozen file sees it, 1 of 65: `test_no_error_core_sees_holds_the_engine_id` |
| the file's name holds the engine's id | the frozen file sees it, 1 of 65: `test_the_engine_id_leaves_only_as_metadata` |
| one failed history read voids the job | the frozen file sees it, 3 of 65: `test_no_error_core_sees_holds_the_engine_id` |
| the first image wins, preview or not | the frozen file sees it, 2 of 65: `test_an_entry_with_only_a_preview_raises` |
| the fingerprint leaves out the node classes | the frozen file sees it, 1 of 65: `test_the_fingerprint_moves_with_every_field_of_the_environment[a node class]` |
| a 4xx on history polls on until the deadline | the frozen file sees it, 2 of 65: `test_no_error_core_sees_holds_the_engine_id` |
| the record holds a seed the engine never got | the frozen file sees it, 1 of 65: `test_a_seed_that_never_reached_the_engine_is_not_recorded` |
| the fingerprint reads the cached node classes | the frozen file sees it, 1 of 65: `test_the_fingerprint_moves_with_every_field_of_the_environment[a node class]` |
| a colorspace outside the schema goes through | the frozen file sees it, 1 of 65: `test_a_colorspace_outside_the_schema_is_refused_before_the_post` |
| a held correlation id silently takes the handle | the frozen file sees it, 1 of 65: `test_a_second_job_under_one_id_never_takes_the_first_handle` |
| a seed past int64 goes to the engine | the frozen file sees it, 1 of 65: `test_a_seed_past_int64_is_refused_before_the_post` |
| a right reply: a fingerprint that opens `/system_stats` itself | reads clean |
| a right reply: `createdAt` in ISO 8601 with a Z | reads clean |
| a right reply: `createdAt` in local time with its offset | reads clean |
| a right reply: the file in a folder under `output_dir` | reads clean |
| a right reply: `capabilities` in the engine's own order | reads clean |
| a right reply: a shorter fingerprint | reads clean |
| a right reply: a second job under one id runs, and the first handle keeps its own | reads clean |
| an engine word in a `neuron.py` comment | 1 failing of 65, T7 or T8 among them: `AssertionError: engine vocabulary leaked into the core:` |
| `author_asset` applies no schema | 2 failing of 65, T7 or T8 among them: `AssertionError: projectA.usda` |
| `plexus:sourceLayer` from `realPath` | 1 failing of 65, T7 or T8 among them: `AssertionError: assert '...` |
| `author_asset` never saves | the frozen file sees it, 1 of 65: `test_every_asset_attribute_lands_with_the_schemas_type_and_on_disk` |
| `author_asset` leaves `over` ancestors | the frozen file sees it, 2 of 65: `test_every_asset_attribute_lands_with_the_schemas_type_and_on_disk` |
| `author_asset` has no allowlist check | the frozen file sees it, 2 of 65: `test_an_asset_outside_the_allowlist_is_dropped_and_flagged` |
| `author_asset` needs more than CONTRACT's five keys | the frozen file sees it, 6 of 65: `test_a_record_with_only_the_contracts_five_keys_still_lands` |
| `plexus:organVersion` never authored | the frozen file sees it, 2 of 65: `test_every_asset_attribute_lands_with_the_schemas_type_and_on_disk` |
| `_run_action`'s mute guard is gone | `neuron_unchanged` drops it; phase 1 alone reads 1 of 25 |
| the neuron budget check is gone | `neuron_unchanged` drops it; phase 1 alone reads 9 of 25 |
| `ctx.author`'s allowlist check is gone | `neuron_unchanged` drops it; phase 1 alone reads 3 of 25 |
| `author_asset` takes no lock | the frozen file sees it, 1 of 65: `test_two_neurons_on_one_write_both_publish` |
| `Sdf.AttributeSpec` instead of `_set_attr` | the frozen file sees it, 1 of 65: `test_a_second_asset_on_one_prim_does_not_raise` |
| `layer.Save()` inside the `ChangeBlock` | nothing sees it, the review reads it by eye, and no harm was shown |
| no `Sdf.ChangeBlock` in `author_asset` | nothing sees it, the review reads it by eye, and no harm was shown |
| `neuron.py` imports `AssetRecord` for a type hint | `neuron_unchanged` drops it; phase 1 alone reads 0 of 25 |
| `author_asset` imports `AssetRecord` inside the method | the frozen file sees it, 1 of 65: `test_neuron_imports_nothing_from_organs` |
| the deny flag says something else | the frozen file sees it, 1 of 65: `test_the_deny_flag_says_what_ctx_author_says` |
| `plexus:organVersion` holds `meta['engine']` | the frozen file sees it, 1 of 65: `test_each_asset_attribute_holds_the_records_value` |
| `plexus:retryOf` holds the sha | the frozen file sees it, 1 of 65: `test_each_asset_attribute_holds_the_records_value` |
| the global wake budget check is gone | `neuron_unchanged` drops it; phase 1 alone reads 0 of 25 |
| `plexus:tools` never authored | `neuron_unchanged` drops it; phase 1 alone reads 0 of 25 |
| an action's exception is no longer printed | `neuron_unchanged` drops it; phase 1 alone reads 0 of 25 |
| the scope filter of Spec 6 step 1 is gone | `neuron_unchanged` drops it; phase 1 alone reads 0 of 25 |
| `ctx.author` authors without the lock | `neuron_unchanged` drops it; phase 1 alone reads 0 of 25 |
| `ctx.author` no longer saves | `neuron_unchanged` drops it; phase 1 alone reads 0 of 25 |
| `author_asset` leaves half a record on a seed past Int64 | the frozen file sees it, 1 of 65: `test_a_value_that_cannot_land_leaves_nothing_in_the_file[a seed past Int64]` |
| a right reply: `author_asset` authors one attribute past the thirteen | reads clean |

### What the worker reads

Measured with the harness's own `build_prompt`, in the worst case each state allows: a metric tail at its limit, a gate output at its limit, three target failures at their limit, and every known fix firing at once. Tokens are characters over 3.75. `num_ctx` is 49152. This is the mission as it stands, with the new file out of the context list. Section 10 has the other way.

| Step and state | Characters | Tokens | Room after its reply | Room after 6,500 tokens | Smallest `context_chars` that leaves nothing out |
|---|---|---|---|---|---|
| O1 first attempt | 67,222 | 17,926 | 28,663 | 24,726 | 67,175 |
| O1 after a gate failure | 76,692 | 20,451 | 26,138 | 22,201 | 76,615 |
| O1 after a full drop | 90,907 | 24,242 | 22,347 | 18,410 | 90,820 |
| O1 after a left-out drop | 87,041 | 23,211 | 23,378 | 19,441 | 86,956 |
| O2 first attempt | 71,816 | 19,151 | 26,488 | 23,501 | 71,767 |
| O2 after a gate failure | 81,033 | 21,609 | 24,030 | 21,043 | 80,958 |
| O2 after a full drop | 88,033 | 23,475 | 22,163 | 19,177 | 87,951 |
| O2 after a left-out drop | 84,147 | 22,439 | 23,199 | 20,213 | 84,067 |

Every context file and `neuron.py` stay in the prompt in every state. O1's own files are not in the prompt on a first attempt or after a gate failure, because they exist nowhere then: the prompt names them as missing, and the brief holds the protocol block and the skeleton to start from. After a full drop or a left-out drop they are handed on whole. O2's own file is in every state.

`context_chars` 95000 leaves about 4,180 characters of room over the worst case, for a `neuron.py` that S8 wrote longer. The budget caps the files only, so it does not make a prompt longer. Even at 3.75 characters per token, the reply has more than 24,000 tokens of room, against the 6,500 used as the yardstick in phase 1 and the 3,513 that `neuron.py` needs.

### What this proof does not cover

No model has seen these prompts. The same hand wrote the step texts, both right replies and the frozen file, so the ladder shows the text is enough for a reader who already knows T7, not yet for the worker, and the sentence O1 adds about the smallest change is unmeasured on a model. The stand-in is not the worker's real S8, so O2's named lines get checked again on the real tip at setup. T7's engine and the new file's are fakes, and no real ComfyUI was started, so what a real engine adds to these replies comes from the repo's reference code and from memory of ComfyUI's source: `vram_free` is at `agent/health.py:102`, `ram_free` was not checked live, nor were a preview's `temp` type, the seed input's range, or `node_errors` in a 200.

---

## 6. The gates that hold `neuron.py`

**`neuron_unchanged`, new.** O2 sends `neuron.py` whole, and many of its lines are read by no frozen test. The first attack broke 138 statements one at a time and 35 passed phase 1 and phase 2 both, which I reran on the first draft, ctx.author's lock among them, and losing that lock kills the interpreter on two neurons. This gate reads the parsed code against the last kept commit: every class, function and statement stands, and the file gains `_Ctx.author_asset` alone. Comments, blank lines, docstrings and the order of the imports do not count. A new import or a helper beyond `author_asset` drops, which is what O2's text asks. It takes 0.2 s and has no wall clock. A lossy file never passes the gates, so it is never handed on as the copy the next attempt starts from.

The two attacks proposed two forms. The second asked for `git diff --numstat -w` failing on any deleted line, which is the simpler script. It is not this gate, because a line-based read cannot see the case that matters. When ctx.author loses its Save and `author_asset` is added, `git diff --numstat -w` counts 0 deleted lines, because `author_asset` ends with the same line, so that read passes the reply; the parsed compare drops it. A right reply that rewords one docstring counts 1 deleted line, so that read drops it; the parsed compare passes it.

The gate is scaffolding under `harness/`, so it lands in Claude's own commit, decision 12.

**`phase1`, out on Joe's word.** Before the new gate it was the only thing holding `neuron.py`, and it held only what phase 1 asserts. Its reach is now none: focus bars every file but `plexus/organs/**` and `neuron.py`, phase 1 reads 0 of 25 with `plexus/organs` broken at import, no phase 1 test names `author_asset`, and `neuron_unchanged` lets `neuron.py` gain that one method alone. So no attempt that passes the new gate can change what phase 1 reads, and in that gate phase 1 could only fail falsely.

**The cost it no longer has is the wall clock.** `test_a_to_b_visibility_p95_under_250ms` holds a p95 of 250 ms and counts each write's Save inside it, so a busy box could fail a good attempt, and a false failure would have thrown away 30 to 40 minutes and one attempt of the budget. The evidence for taking it out:

- The first draft's proof ran phase 1 42 times, one process at a time. On two runs, while the box was slow, correct code failed: once T1 alone, with a p95 of 427.7 ms, and once T1 at 518.8 ms together with the burst test's 95 ms span and `settle`'s 5 s, with the phase taking 93 s. `C:/Users/User/AppData/Local/Temp/claude/E--Plexus/b30a0d29-4d4a-473f-9338-d6f7d60e541b/scratchpad/organ_repair/before/results/chain.log` holds the second.
- The burst and disk proof saw T1 fail 14 of 264 runs with three pytest runs at once, on any tree, and 0 of 27 alone.
- T1's own loop on the top rung reads median 52.7 ms, p95 54.2 ms, worst 64.6 ms, against a limit of 250 ms.

Phase 1 is now read by hand on each keep, section 9. The two brief lines and two known fixes that served the gate are gone with it. The toml loads with 6 gates and `check` says ready.

---

## 7. What the new frozen file scores

These gaps were in what T7 leaves unasserted, not in what it asserts. The `seed-mutated` case does test that writing a seed leaves the link arrays alone, and that holds; it does not check that the seed landed. `frozen/test_organ_surface.py` holds them, 52 functions and 58 items, 0 failing on the top rung. It goes to `tests/acceptance/phase2/test_organ_surface.py` when Joe places it. It carries its own fake engine and reads the organ only through what CONTRACT names, so the second right reply passes it whole. Its tests run in the order O1's text gives the bodies, so the three failures a dropped attempt's prompt leads with are the earliest clauses it missed.

| Clause | Asked by | The frozen file's test | Step |
|---|---|---|---|
| A relative `output_dir` still gives an absolute path, and a dead engine is an `OrganError` | the step text | `test_a_relative_output_dir_gives_an_absolute_path`, `test_a_dead_engine_is_an_organ_error` | O1 |
| The seed lands in the seed input and nowhere else, even in the case T7 names `seed-mutated`, and `submit` posts once | CONTRACT, `Job.seed` | `test_seed_lands_in_the_seed_input_and_nowhere_else` | O1 |
| `submit` leaves the job's own graph alone | the step text | `test_submit_leaves_the_jobs_own_graph_alone` | O1 |
| A seed wired from a link stays a link and is not recorded as the job's seed | Spec 8.2, Spec 3 | `test_a_seed_wired_from_a_link_survives`, `test_a_seed_that_never_reached_the_engine_is_not_recorded` | O1 |
| `noise_seed` is written | the skeleton | `test_noise_seed_is_written` | O1 |
| A class the engine lacks, a seed past int64 and a colorspace outside Spec 3 all stop before the POST | Spec 8.2, Spec 3 | `test_a_class_the_engine_lacks_stops_before_the_post`, `test_a_seed_past_int64_is_refused_before_the_post`, `test_a_colorspace_outside_the_schema_is_refused_before_the_post` | O1 |
| A second job under a held correlation id never takes the first handle. It does not pin the refusal the text asks for, because Patch 01-D leaves a retry's handle to the retry mission | Patch 01-C | `test_a_second_job_under_one_id_never_takes_the_first_handle` | O1 |
| A refused graph carries the engine's words | the step text | `test_a_refused_graph_carries_the_engines_words` | O1 |
| `submit` does not wait for the job | Spec 8.1 | `test_submit_returns_before_the_job_is_done` | O1 |
| The engine's id leaves only as metadata: not the handle, not the file's name, not an error | CONTRACT, Patch 01-C | `test_the_handle_carries_no_engine_id`, `test_the_engine_id_leaves_only_as_metadata`, `test_no_error_core_sees_holds_the_engine_id` | O1 |
| A job whose history never comes is voided at the deadline, and one failed read is not that | Blueprint section 8 | `test_result_stops_at_the_deadline`, `test_one_refused_history_read_leaves_the_job_running`, `test_a_dead_engine_during_a_poll_waits_out_the_deadline_and_voids_the_job` | O1 |
| A 4xx on history fails at once, and an unknown handle is an `OrganError` | the step text | `test_a_wrong_history_route_fails_at_once`, `test_an_unknown_handle_is_an_organ_error` | O1 |
| Two open jobs collect out of order | Patch 01-C | `test_two_open_jobs_collect_out_of_order` | O1 |
| An engine error, no image, or only a preview raises; the saved output wins over a preview | the step text | `test_an_error_entry_raises`, `test_an_entry_without_images_raises`, `test_an_entry_with_only_a_preview_raises`, `test_the_first_output_image_is_found_past_a_node_without_images`, `test_the_saved_output_wins_over_a_preview` | O1 |
| `/view` carries subfolder and type, and the file holds the engine's bytes, under `output_dir`, never over an earlier file | the step text | `test_the_view_query_carries_subfolder_and_type`, `test_the_file_on_disk_holds_the_engines_bytes`, `test_the_file_lands_under_output_dir`, `test_two_jobs_with_one_engine_filename_keep_two_files` | O1 |
| `modelHashes` holds no hash this engine never gave, and `engine` is the organ id | Patch 01-E, Spec 3 | `test_model_hashes_are_empty_and_engine_is_the_organ_id` | O1 |
| The record holds the seed that ran, the colorspace and a creation time. An O2 target must never fail for O1's fault, so this reads the record itself | Spec 3, the step text | `test_the_record_holds_the_seed_the_colorspace_and_when` | O1 |
| The fingerprint stands still when only free memory moves, and moves with torch, device, OS, Python and a node class | Patch 01-B | `test_the_fingerprint_stands_still_when_only_free_memory_moves`, `test_the_fingerprint_moves_with_every_field_of_the_environment` | O1 |
| `capabilities`, `profile` and `stream` answer with the right shapes, and `stream` says failed and stops at the deadline | CONTRACT, Spec 3 | `test_capabilities_name_the_engines_node_classes`, `test_profile_holds_the_organ_api_fields`, `test_stream_says_queued_then_done`, `test_stream_stops_at_the_deadline`, `test_stream_says_failed_on_an_error_entry` | O1 |
| The organ imports the standard library and the contract only, and `neuron.py` nothing from `plexus.organs` | the brief | `test_the_organ_imports_the_standard_library_and_the_contract_only`, `test_neuron_imports_nothing_from_organs` | O1, O2 |
| Thirteen attributes land with the schema's types and the record's values, on disk as they land, with `def` ancestors | Spec 3, CONTRACT | `test_every_asset_attribute_lands_with_the_schemas_type_and_on_disk`, `test_each_asset_attribute_holds_the_records_value` | O2 |
| `author_asset` refuses a path outside the allowlist, and its flag says what `ctx.author`'s says. The flag's words are not pinned | CONTRACT | `test_an_asset_outside_the_allowlist_is_dropped_and_flagged`, `test_the_deny_flag_says_what_ctx_author_says` | O2 |
| A record with only CONTRACT's five keys lands, and a value that cannot land leaves nothing in the file, with a whole record landing first so a reply that lands nothing fails | CONTRACT, Blueprint section 6 | `test_a_record_with_only_the_contracts_five_keys_still_lands`, `test_a_value_that_cannot_land_leaves_nothing_in_the_file` | O2 |
| Two neurons on one write both publish, which dies without the lock, and a second asset on one prim does not raise | the step text | `test_two_neurons_on_one_write_both_publish`, `test_a_second_asset_on_one_prim_does_not_raise` | O2 |
| Guard: a changed predicate does not wake on its own asset | Spec 6 | `test_a_changed_predicate_does_not_rewake_on_its_own_asset` | O2 |
| Guard: a second process reads the asset from the file alone | Spec section 9, T6's point | `test_a_second_process_reads_the_asset_from_the_file` | O2 |

**What stays by hand.** `proof/surface_probe.py` now holds two tests and only them, because one reads a harness file and the other widens T8, which is Joe's alone: `test_protocol_is_the_briefs_block` and `test_no_wider_engine_word_outside_the_organ`. It runs on each keep, and a failure stops for Joe.

**What the review reads by eye.** `layer.Save()` inside the `ChangeBlock` and no `ChangeBlock` at all pass every test, because neither attack nor I could show harm from either. `git show --stat` reads an O2 that also rewrites `cozy.py` and a stray file in a keep.

**What the file calls that CONTRACT did not list.** `poll_s` and `deadline_s` on `CozyOrgan`, `OrganError`, the `JobHandle` constructor, `Progress` and `OrganProfile`'s fields, the `AssetRecord` constructor and the three metadata keys past the five. `frozen/CONTRACT.md` is the whole file with those lines added, and `frozen/CONTRACT_additions.md` shows them alone with why each is there. They wait for `mission/organ`, because `CONTRACT.md` sits in the cached head of every phase 1 prompt.

---

## 8. Decisions for Joe

Joe's words, Nov 5: "yes to all five organ decisions in organ_prep/README.md: add the neuron_unchanged gate, take the phase1 gate out, finish surface_probe.py as a draft for me to place, budget 8 attempts, and end the mission when T7 and T8 pass". Decisions 3, 4, 6, 11 and 12 carry his words. The other seven stand as recommended and count as answered, as the README told him they would.

1. **Branch names and base.** **Stands as recommended.** `mission/organ` for Claude's commits and `plexus-loop/organ` for kept attempts, which is what the harness derives from the name. `program.md` and `/mission` say to branch off `harness/plexus-loop`, but that branch has no `plexus/` code, so `mission/organ` branches from `mission/acceptance` once S8 and S9 are merged there. The harness cuts `plexus-loop/organ` from HEAD at the first `run`.
2. **Pushes and fast-forwards.** **Stands as recommended.** "What Claude does without asking", item 2, gets these two branches, with the same check that nothing under `tests/acceptance/` is in the diff. The first push of `mission/organ` holds the placed file, so that check stops it, and that one push is Joe's word.
3. **The `phase1` gate**, section 6. **Answered, Joe, Nov 5: "take the phase1 gate out".** That is option c. The block is out of `organ.toml`, the two brief lines and the two known fixes went with it, and the whole of phase 1 is read by hand on each keep, section 9. The toml loads with 6 gates and `check` says ready.
4. **A frozen test for section 7.** **Answered, Joe, Nov 5: "finish surface_probe.py as a draft for me to place".** That is the second option. `frozen/test_organ_surface.py` is the draft, and `frozen/CONTRACT.md` is that file's lines. Placing the file moves the baseline from 5 to 62 of 65, O1 takes it to 12 and O2 to 0, and its functions joined O1's and O2's targets, split on the ladder. Two tests stayed out, because one reads a harness file and the other widens T8, which is his call alone. The sentence each step text carried about the probe is gone. The reason stands: T7 and T8 pass an organ that leaves `profile`, `capabilities` and `stream` unwritten, writes no seed and has no deadline, and the loop keeps it. The new file reads 36 of 65 failing on that organ with O2's method in place, inside the loop.
5. **`timeout_s`.** **Stands as recommended.** 4800, the value phase 1 runs with since Nov 4. The worst case for this mission at the worst rates on record is about 3,326 s, so 3600 would hold too, and a false timeout costs an hour while a long one costs nothing unless the model hangs.
6. **Budget.** **Answered, Joe, Nov 5: "budget 8 attempts".** 8 attempts, 6 hours, 8 failures, which is what the toml says. At 30 to 40 minutes an attempt that is at most about 5.3 hours, and the run stops as soon as every target test passes. At the acceptance ledger's keep rates, 0.262 over every real attempt and 0.583 over the last 12, five attempts give 39 to 90 percent odds of two keeps, and eight give 66 to 99 percent. With the file placed the mission needs at least 2 keeps, as before, plus one for each reply that clears only part of a step: the scripted path that clears part of O1 twice took 4, and the scripted loop with one partial keep took 3. At those same rates, eight attempts give 35 to 94 percent odds of 3 keeps, 13 to 80 of 4, and 3 to 56 of 5. So eight attempts hold a path of 3 or 4 keeps at the recent rate and are thin for it at the whole ledger's. Those rates price a keep at what it cost on a short count, and on this count any one more test keeps, so a partial keep comes cheaper than they say, and the last keeps cost what they cost. Run 30 showed that shape on a short count: S8 took 2 keeps, 4 to 1, then 1 to 0. This is ledger arithmetic with each attempt taken alike, and the ledger's drops were mostly Rust while O1 and O2 are Python, so it is a caution and not a forecast. A stop at the budget loses no keep, because each keep is on the loop branch, and it drops only the handed-on files. A keep stops for Joe before any next run, under `program.md`, so more attempts after a stop at 8 are his word.
7. **`context_chars`.** **Stands as recommended.** 95000, section 5. `num_ctx` stays 49152.
8. **The failure router.** **Stands as recommended: off.** So nothing leaves the machine. Turned on, every full drop sends TypeSafe the failure output, the step's id and text, and the brief's prose lines, and the floor of 0.7 was judged on run 19's brief, not this one.
9. **The `unit` gate.** **Stands as recommended: kept for this mission.** Joe narrowed it on Nov 1 for mission acceptance, and it stays as written. It cannot see `plexus/organs` or `neuron.py`, and it costs 150 to 240 s an attempt. The full comfy-cozy suite still runs once at mission end.
10. **The block and the skeleton in the brief.** **Stands as recommended.** `protocol.py` is copied whole from the brief, as `py.rs` was in S3. It holds dataclasses and a Protocol, no logic. `cozy.py` starts from a skeleton of signatures, and the step texts spell out every body: the seed loop as code, the rest in prose, and every attribute of `author_asset` with its value and type. So the worker's part is writing them correctly, and little of the logic is left for it to find. The hard rule allows this, since Claude revises the mission and lands no code, and S8's text has the same shape.
11. **What phase 2 means.** **Answered, Joe, Nov 5: "end the mission when T7 and T8 pass".** The mission adds nothing from the blueprint's longer list. The harness stops when every test under its metric target passes, so with the new file placed that means T7, T8 and the new file. The new file reads clauses O1's and O2's step texts and the brief already ask for, plus two guards that read phase 1's behaviour through the new asset and ask for no new code, so it adds no scope to what he decided. Blueprint section 11 lists more under Phase 2: projection through L3, idempotency, cancel, progress, failover across workers, and the shadow composer. Spec promises that have no step and no test here either: no prim under `/Plexus/Organs/` is authored, though Spec 3 applies `PlexusOrganAPI` there; Spec 8.2's result row promises timings and no attribute holds them; its submit row asks for validate before execute and the text checks only that the classes exist; Spec 6 says both runs carry the neuron's correlation id and the schema has no attribute for it; and a second asset at one prim overwrites the first with no flag, which Patch 01-D forbids, while nothing in this mission retries. Those are later missions with their own tests.
12. **The new gate and the guard's one word.** **Answered, Joe, Nov 5: "add the neuron_unchanged gate".** Scaffolding Claude commits before `run`, no longer conditional: `harness/plexus_loop/neuron_unchanged.py`, section 6, and `plexus.organs.cozy` added to `NO_PXR` in `harness/plexus_loop/guards/test_layers.py`, so an organ that imports `pxr` drops at `layers`. Spec 8.1 says the caller authors, never the organ. Both are read on scratch with the guards and the unit gate passing.

The go itself is also his, after these.

---

## 9. The hour phase 1 ends

1. S8 and S9 keep, pass their reviews, and merge into `mission/acceptance` on Joe's word.
2. The worker is up. `/doctor organ`.
3. Claude cuts `mission/organ` from `mission/acceptance` and checks it out. Nothing is placed before this, because `CONTRACT.md` is in `acceptance.toml`'s context list and landing it earlier would change phase 1's cached prompt.
4. **Joe places the file and CONTRACT's lines**, on `mission/organ`. The hook stops Claude at that folder, so these commands are his:

   ```bash
   F="C:/Users/User/AppData/Local/Temp/claude/E--Plexus/b30a0d29-4d4a-473f-9338-d6f7d60e541b/scratchpad/organ_prep/frozen"
   cd /e/Plexus
   test "$(git branch --show-current)" = "mission/organ"
   cp "$F/test_organ_surface.py" tests/acceptance/phase2/
   cp "$F/CONTRACT.md" tests/acceptance/
   git add tests/acceptance/phase2/test_organ_surface.py tests/acceptance/CONTRACT.md
   git commit -m "frozen: what the organ contract promises and T7 and T8 leave unread"
   ```

5. From `C:/Users/User/AppData/Local/Temp/claude/E--Plexus/b30a0d29-4d4a-473f-9338-d6f7d60e541b/scratchpad/organ_prep/proof`: `python -B chain.py --ref mission/organ`. That reads the merged code, the frozen tests with the placed file and CONTRACT's lines, the harness and the spec from that one commit, rebuilds the ladder and repeats every check in section 5 in about 104 minutes. `make_rung0.py` refuses a ref that lacks the placed file or holds other bytes than the draft. `proof/ref_check.py` proved that on a scratch clone, with E:/Plexus only read. `make_rung0.py --ref` refused a ref without the placed file. On a commit of the real loop tip, run 30's S8 and S9 in it, with both drafts placed, it built rung 0 from that one commit, and the ladder read 62, 12 and 0 of 65 on phase 2 and 0 of 25 on phase 1 at the top. `make_ladder.py` refuses, by name, a rung 0 that lacks a line O2 or the brief names, and the chain stops there. If it refuses after S8 lands, the step text gets revised before anything else, and that revision is shown to Joe.
6. Joe's go.
7. Scaffolding, each its own commit on `mission/organ`, shown to Joe:
   - **C1** `mission: organ, its brief and its plan`: `harness/plexus_loop/missions/organ.toml`, `organ.worker.md`, `organ.plan.md`.
   - **C2** `program: rule 2 names the organ branches`.
   - **C3** `harness: test that each organ known fix resolves to one brief line`, one test beside the one acceptance has.
   - **C4** `harness: neuron_unchanged gate, and the cozy organ in the guard's NO_PXR`.
8. Push `mission/organ` on Joe's word, because the placement commit is under `tests/acceptance/`. Then `python -m harness.plexus_loop check harness/plexus_loop/missions/organ.toml`, paste its output here, and `run` with `mission/organ` checked out. The lock allows one mission at a time, so phase 1's run must have exited.
9. Per attempt: one line to Joe with the step, the tests that flipped and `prompt_eval_s`. On each keep, in this order: `proof/surface_probe.py` from the kept tree, the two hand tests, where any failure stops for Joe; `git show --stat`, which must list only the step's own files, so an O2 keep lists `neuron.py` alone and neither keep lists a stray file; a read of the whole of phase 1, because no gate reads it now; then the `reviewer` agent and the adversary. A partial keep gets the same read, so the first keeps of a run are read as whatever they are.

Remember: the worker reads the brief from the loop branch. After `run` has cut `plexus-loop/organ`, a brief commit reaches the worker only once the loop branch contains it.

---

## 10. Calls Claude made, logged

- **The new file stays out of the context list.** Without it, the largest floor is 90,820 characters and the worst prompt 24,242 tokens, and O1's first attempt reads 17,926 tokens, a cold read of 773 s at the worst rate on record. With it, the largest floor is 141,144 characters, so `context_chars` 95000 leaves the new file itself out of 8 of 8 states and `neuron.py` out of 6, and with room for all of it O1's first attempt reads 31,346 tokens, a cold read of 1,351 s, and the worst prompt 37,662 tokens. The step texts spell out every body, a failure's text reaches the next prompt, and the worker's cold read grows faster than a prompt's length. The brief says the file is there and is not under Files.
- `metric.timeout_s` stays 300. The worst the whole of phase 2 took on the wrong replies where T7 does not hang is 107 s on a busy machine, section 5, so no raise is needed. A reply that hangs T7 costs 300 s of an attempt, as it did.
- The new file pins less than the texts in six places, where a frozen test would otherwise freeze a choice the brief or a later mission may want open. A held correlation id only has to leave the first handle its own job. The file only has to land under `output_dir`. `capabilities` only has to name the classes, in any order. `createdAt` only has to parse and fall inside this job's time, in any zone. The fingerprint only has to be non-empty. The attribute list is read as at least the thirteen.
- The deny flag is compared with what `ctx.author` wrote, so its words stay unpinned, as the disk test left them.
- All the file's waits on hangs draw on one allowance of 30 s, kept in one module-level list, which no other frozen file does. Without it a reply that hangs on every call would pay about 300 s in this file alone. With it the worst is 138 s. The cost: a reply that has already hung that long and is also slow can fail a later test it would pass with the full wait, so on such a reply the order of the tests can change which ones fail. A right reply never draws on it. Independent waits are the other way to write it, with the longer worst case, and that is Joe's to choose in a file he places.
- `test_a_value_that_cannot_land_leaves_nothing_in_the_file` lands a whole record first, because a reply that lands nothing would otherwise pass it, and it would never route to O2.
- `author_asset`'s tests build their records by hand, so an O2 target never fails for a fault in O1's organ. The one exception is the second-process guard, which runs after O1's targets pass.
- Four known fixes each gained an alternative for the new file's text: `'_Ctx' object has no attribute 'author_asset'`, `link-array invariant`, `submit() posted N times` and `Use keyword arguments`.
- `requires` names the new file, so a run cannot start with its targets unplaced.
- O2's text no longer names an `allowed =` line. Run 30's real S8 wrote the deny flag's value inline in `author`, so the text says to copy that branch whole, and `make_ladder.py` no longer asks for that line. Section 5's read of the real tip is on that wording.
- `PLEXUS_SPEC.md` is out of context, and the brief carries what this mission reads from it.
- The organ id is `cozy` and its version `0.1.0`. `metadata["engine"]` holds the organ id, as Spec section 3 says.
- `stream` polls `/history`. There is no WebSocket in this mission: Patch 01-C makes it a hint, the fake has none, and the standard library has no client.
- `modelHashes` is an empty list. ComfyUI's HTTP surface gives no hash, and Patch 01-E's rule is that unknown beats invented.
- `job.inputs` is unused, because nothing says yet what it holds.
- A job with several outputs records the first image of type `output`. `AssetRecord` holds one path.
- The asset path is absolute, which T7 allows. A relative path would suit a stage in git better, and that is a later call. The new file's second-process test allows it too.
- The file's name is a uuid and the engine's filename, because CONTRACT lets the engine's id leave only as metadata, and identical bytes rule out a name from the sha.
- `deadline_s` defaults to 3600 and `poll_s` to 0.2, both keyword arguments.
- A failed history read with a 5xx or no connection means not yet, and a 4xx raises at once. One blip must not void a running job, and a wrong route must not hide behind a one-hour deadline. So `_history_entry` does not go through `_get_json`, and the job's id never reaches an error's text.
- The fingerprint takes `os`, `comfyui_version`, `python_version`, `pytorch_version`, each device's `name` and `type`, and the sorted class names of a fresh `/object_info` read, because Patch 01-B names node pack updates first among the drift it is for. That is one more GET per result, and its cost on a large real install is unmeasured. The driver is not in those replies, and the CUDA tag is inside `pytorch_version`.
- A correlation id the organ already holds is refused at `submit`, because the first handle otherwise answers with the second job and no error.
- A seed that arrives through a link stays a link, and the record then holds no seed, because the engine never got the job's seed. A seed past int64 is refused at `submit`, because `plexus:seed` cannot hold it, and a colorspace outside Spec 3's four tokens is refused there too.
- `author_asset` builds its values before it takes the lock, so a value that cannot land raises with nothing authored.

---

## 11. Open points

**New with the frozen file.**

- After a keep the next prompt shows a failing test's name and no failure text, because the harness fills `target_failures` only on a drop and pytest crops a summary line at 80 columns, so a worker on a partial keep reads names until an attempt drops. A harness change could show messages after a keep too, and that is Joe's to ask for.
- T7 builds its organ with the 3600 s default, so a reply that never sees the history entry still hangs T7 until the metric's 300 s limit and leaves no failure text, whatever this file does. The brief's line covers that state.
- A reply that hangs at import of `plexus/organs/protocol.py` holds Python's import lock, and the file's bounded calls fail one by one on it, so only the metric's own limit ends T7 there.
- The allowance in the file makes a wait 2 s long once 30 s have gone on hangs. A right reply never spends it. A box stalled past that much in one run would read more tests failing than it should, and on a reply that hangs and is also slow the order of the tests can change which ones fail.
- O1's text asks for a held-id refusal and a sorted `capabilities`, and the frozen file scores neither, because a right reply may do otherwise. The review reads them on each keep.

**Findings left, each with its reason.**

- The prompt's own head and footer still say to send edits as a diff while the brief says never, because a diff that applies now costs nothing under `neuron_unchanged`, a diff that does not apply costs one attempt, and the real answer is the harness flag already parked in the capsule.
- A 200 reply with non-empty `node_errors` still passes through `submit`, because that shape comes from memory of ComfyUI's source and no real engine may run here, so it is checked when a real ComfyUI first runs.
- A project A writer in the same process racing an action that adds a new prim kills the interpreter with the lock in place, 3 of 3 through `author_asset` and 3 of 3 through phase 1's own `ctx.author`, and it stays for the mission that runs a live session, because it is phase 1's runtime and T7 writes once and waits.

**Parts of findings left, each with its reason.**

- The line "Make the smallest change that moves the number" stays at `loop.py:441`, because O1's own sentence answers it inside the prompt and the reword also edits a pinned harness test, so it waits for a keep that shows clauses dropped.
- A keep can still commit a stray file outside focus, because the focus check runs before the gates and closing that is a harness change, while the frozen file and the review see it.
- Patch 01-D says a retry carries the same correlation id and `submit` now refuses a held id, because the retry mission has to decide what a retry's handle is and a silent wrong answer is worse until then. The frozen file pins only the first handle keeping its job, so that mission will not have to change it.
- `layer.Save()` inside the `ChangeBlock` and no `ChangeBlock` at all still pass every test, because neither attack nor I could show harm from either, so the text still asks for them and the review reads them.
- T8's word list stays narrower than Spec 10's sentence, because T8 is frozen and widening it is Joe's call.

**Carried over from the first draft.**

- After T7 and T8 pass, nothing has yet run against a real ComfyUI, and the launcher's session wiring lives in `examples/`, outside this mission's focus, so both wait for Joe's word.
- The reference code's `workflow.lock` holds real model hashes, and filling `plexus:modelHashes` is later work.
- `/report`'s kept-commit list reads `harness/plexus-loop..plexus-loop/organ`, which would also list all of phase 1 on this base, and `REVIEW.md` holds the right range.
