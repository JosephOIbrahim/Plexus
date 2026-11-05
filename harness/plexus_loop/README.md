# plexus-loop

Plexus's own build harness, from Blueprint v5.2 §12. It was written fresh for Plexus and shares no code with any other harness.

Claude plans and reviews. A local model makes the attempts. You decide what gets promoted.

## Run it

```
python -m harness.plexus_loop check harness/plexus_loop/missions/acceptance.toml
python -m harness.plexus_loop run   harness/plexus_loop/missions/acceptance.toml
python -m harness.plexus_loop stop
```

`check` validates the mission and says whether the next attempt would run on the CPU or the GPU. It does not load the model, so `ready` says nothing about the worker. `run` works until a budget or a stop condition ends it. `stop` drops a stop file, and the run halts after its current attempt.

## What one attempt does

1. It starts a fresh git worktree at the best commit so far.
2. It looks for Houdini. If Houdini is running, or the check can't tell, the attempt runs on the CPU: the worker asks Ollama for `num_gpu 0` and a thread cap, the gates run with `CUDA_VISIBLE_DEVICES` empty, and `CARGO_BUILD_JOBS` is capped.
3. The worker changes files.
4. The change is dropped if it touches a frozen path or anything outside the focus, writes a path git ignores, or leaves out a file its step lists.
5. Every gate must pass.
6. The metric must improve by at least `min_delta`. For `pytest_failures`, failures, errors and skips all count, and a run that collects fewer tests than before is dropped.
7. A kept change is committed onto `plexus-loop/<mission>` and becomes the new starting point. Everything else is thrown away with its worktree.

## When it stops

It stops when the attempt or hour budget is used, after too many attempts in a row that weren't kept, after two attempts in a row that reached no server able to run the model, when a stop file appears, or when every target test passes.

It refuses to start if a path the mission requires is missing, if a stop file is already there, if the mission names no gates, if another mission holds the lock, if the worker cannot load its model, or if the gates or the metric fail before any change.

## What it leaves

- `.plexus_loop/<mission>/REVIEW.md` says what happened and gives the two git commands to look at the work.
- `.plexus_loop/<mission>/attempts.jsonl` has one line per attempt.
- The `plexus-loop/<mission>` branch holds the kept commits. Nothing merges by itself.

## Workers

The default is Ollama with `qwen3-coder:30b`, which replies with whole-file blocks for new or rewritten files and a unified diff for edits, and the harness applies both. To use another command-line model, set `kind = "command"` and give its command. `{prompt_file}` and `{worktree}` are filled in, and the command runs inside the worktree and edits files there.

## Costs to know

The `unit` gate in the first mission runs the harness's own tests and two seeded test files on every attempt, which takes over two minutes. Joe narrowed it on Nov 1: Plexus imports nothing from the seeded Comfy-Cozy code, so its suite can only catch repo-wide effects. The full suite (5,158 tests, 9 min 29 s) runs once at mission end.
