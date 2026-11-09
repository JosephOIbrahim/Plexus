# Mission `organ-live`: plan

**One step, L1, makes every reply an engine can send end in an `OrganError`, and keeps the Cozy organ working against a real ComfyUI.** Joe chose, Nov 9: `G:\COMFY\ComfyUI`, run on the CPU with `--cpu`, and the real-engine test frozen as `integration`, with a skip counted as a failure on every keep.

## 1. What the frozen files read

| File | Items | Scored by the harness | On the merged organ (`1813ebe`) | With the reference `cozy.py` |
|---|---|---|---|---|
| `phase2/test_organ_malformed.py` | 13 | yes, under `phase2` | **13 failing** | 0 failing |
| `live/test_organ_live.py` | 5 | no: `integration`, outside `phase2` | 5 passing | 5 passing |
| The rest of `phase2` | 69 | yes | 0 failing | 0 failing |
| `phase1` | 30 | no, read on each keep | 30 passing | 30 passing |

**The thirteen malformed cases**, each of which fails today for the reason it names (checked line by line): a `/prompt` reply that is not JSON; one without `prompt_id`; a node without `inputs`, refused before posting; a seed that is a string, a float or a bool, refused before posting; a history entry without `outputs`; a `/history` reply that is not JSON; a `/system_stats` reply that is not JSON; an `/object_info` reply that is not JSON; a 4xx and a 5xx refusal whose body is not JSON, which must keep the engine's words; and a `/history` call that hangs, which must not run past a 1 s deadline by more than 5 s (today it runs 30 s, to the fake's own limit).

**The live file** runs the organ against the ComfyUI at `PLEXUS_COMFYUI_URL`, default `http://127.0.0.1:8188`, with a graph that needs no model: `EmptyImage` into `SaveImage`, a 64 by 64 square. It reads: the engine lists both classes; a real job comes back as a PNG under `output_dir` with its hash and the five metadata keys, the engine's id nowhere in the path; two jobs never share a file; a real refusal is an `OrganError` naming the bad input; and a neuron's real round trip composes the asset into both projects. No ComfyUI answering: every test skips and says how to start one.

**Why no model.** `G:\COMFY\ComfyUI`'s checkpoint folder holds SDXL and LTX, no SD 1.5, so the plan's SD 1.5 job would have needed a download or the other install. A model-free graph still crosses every route the organ reads, runs in about 13 s on the CPU, and tests the organ, not a model. A job with a real checkpoint is a later hand probe if Joe wants one.

**What the real engine showed** (read-only, Nov 9, ComfyUI 0.34.0 on the CPU, Python 3.14.2, torch 2.9.1): the merged organ already completes a real job end to end. `/object_info` lists 2,760 classes and takes about 6 s, so `capabilities()` costs 6 s once and the fingerprint 6 s per result, because it reads a fresh `/object_info` each time (Patch 01-B's drift key). A refused graph comes back 400 with a JSON body whose `node_errors` names the bad input; the organ keeps it in the error.

## 2. The step

L1 changes `plexus/organs/cozy.py` only, and spells out seven changes as exact code, in file order: `_json` and `_call_timeout` at module level; a seed that is not an `int` refused; a node without `inputs` or `class_type` refused before posting; the POST's body read through `_json`, every `HTTPError` raised with the body's text, and a missing `prompt_id` refused; the history read given the deadline; a history entry without `outputs` refused; `_get_json` and `_history_entry` reading through `_json`, the history call's timeout capped by the deadline. The reference `cozy.py` in the scratch folder is those seven changes and nothing else, and it is what the proof ran.

## 3. The mission file

- `focus` is `plexus/organs/cozy.py` alone. `neuron.py` is out, so no `neuron_unchanged` gate is needed.
- The metric is `phase2`, all of it, 82 items once the file is placed; a keep needs a strict gain there. The live file sits in `tests/acceptance/live/`, outside the metric, because the harness counts a skip as a failure and the loop must not depend on a running ComfyUI.
- Gates: `layers`, `core`, `predicate_smoke`, `cargo`, `unit`, as mission `organ` less `neuron_unchanged`.
- The first prompt measures 37,029 characters, about 9,300 tokens, with the harness's own `build_prompt`: the brief, `CONTRACT.md`, the malformed test and `cozy.py`. Nothing is left out under `context_chars` 95000.
- Budget 8 attempts, 6 hours. The fix router is off. No known fixes: none of the brief's lines answers a failure text yet.

## 4. Decisions logged

- **A skip is a failure on a keep.** `keep_check.sh` refuses to run without a ComfyUI answering, fails on any skip in `live/`, and reads phase 1 and phase 2 whole.
- **CONTRACT.md gains two sentences,** in Joe's placement commit: what `live/` holds, and the replies that must end in `OrganError`, with the rule that no call waits past the deadline.
- **The hang test's bound is 5 s over a 1 s deadline,** with a 0.5 s floor per call, so a slow box does not fail it while a 30 s wait does.
- **Some H5 cases are not here:** a `/system_stats` reply missing a field the fingerprint reads, and a `/view` that returns no image bytes. Both still escape as `KeyError` or write an empty file; they are small and can join a later step.
- **The real-refusal test checks only that the engine's words reach the error.** Those words name node inputs, not node classes, but a `node_errors` body can carry class names into an error core sees. T8 reads source, not errors, so nothing here forbids it; it is a question for the voice of errors, Joe's call.

## 5. How it starts

1. Joe runs `! bash .plexus_loop/place_organ_live_tests.sh`: it checks the four drafts' hashes and a clean tree, cuts `mission/organ-live` from `mission/organ`, and commits the four frozen files alone. Nothing is pushed.
2. Claude commits the scaffolding on `mission/organ-live`, each its own commit: **C1** `organ-live.toml`, `organ-live.worker.md` and this plan into `harness/plexus_loop/missions/`; **C2** program rule 2 names `mission/organ-live` and `plexus-loop/organ-live`.
3. `check`, then ComfyUI on the CPU: `python -m comfy_cli --workspace="G:\COMFY\ComfyUI" launch -- --cpu`.
4. On Joe's go, the first push of `mission/organ-live` (it holds the frozen files, so rule 2 stops Claude) and `run`.
5. On each keep: `keep_check.sh` on the kept tree (live with a skip as a failure, phase 1, phase 2, `git show --stat`), then the reviewer and the adversary.

## 6. Where it lives

Everything is under `C:\Users\User\AppData\Local\Temp\claude\a1cf58fc35533771\0e857ac5-42ca-45b8-a5d9-b5ef72ac971b\scratchpad\organ_live`: `frozen/` (the four files Joe places), `organ-live.toml`, `organ-live.worker.md`, this plan, `reference_cozy.py`, `proof.py`, `keep_check.sh`, `probe_real.py`, and `wt/`, the scratch worktree the proof ran in.
