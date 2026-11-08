# Capsule — Plexus

**Where we are:** Mile 5.9 of ~6. Phase 1 is done and released (`plexus-0.1.0-alpha.5` on `831d09f`, 30 of 30). **Mission `organ` (phase 2) reached its target on Nov 8: `tests/acceptance/phase2` reads 0 failing of 65 on `plexus-loop/organ` at `6b7f657`**, from 62 at baseline, and phase 1 reads 30 of 30 on that tree. Three runs, 18 attempts, 5 keeps, all on the CPU beside Houdini. Nothing is merged: `plexus-loop/organ` holds the five worker commits, `mission/organ` (`66309b5`, pushed) holds Joe's frozen placement `204fbbc`, the scaffolding and three O1 text revisions. <!-- src:0e857ac5 date:2026-11-08 -->

**Next action (Nov 8):** no run is live. Joe's decision is open: merge `plexus-loop/organ` into `mission/organ` now with the adversary's hard finding carried to a follow-up step, or answer the finding first. The finding: `_Ctx.author_asset` (`plexus/core/neuron.py:68-111` at `6b7f657`) checks no value's type before the lock, so a value of the wrong type (`engineJobId=123`, `modelHashes=[1,2]`, `colorspace=5`, `createdAt=5`) raises inside the `ChangeBlock` after some attributes are set, and `_run_action`'s flag Save writes half an asset to disk. CONTRACT.md:37 and O2's text both say a value that cannot land leaves nothing authored; the frozen test's two cases fail before the lock, so it never reaches this. Claude's recommendation: the S8b shape, one frozen test Joe places for a wrong-type value, and a step O2b that authors into an anonymous layer first and copies the spec under the lock with `Sdf.CopySpec`, so a failed value leaves the real layer untouched. Merging is his word either way. <!-- src:0e857ac5 date:2026-11-08 -->

**Read this before touching a mission between runs: the worker reads the brief from the loop branch, not the mission branch.** Only the toml (step text, known-fix regexes, budget) comes from the main tree; the brief, context files and known-fix anchors come from the attempt's worktree, cut from the loop branch tip. Never restart a run with the mission branch ahead of the loop branch on anything the worktree reads. A toml-only text change keeps the worker's cached prompt prefix. <!-- src:b30a0d29 date:2026-11-05 -->

**What the organ runs taught** <!-- src:0e857ac5 date:2026-11-08 -->
- Run 1 (8 attempts, 0 kept): seven replies stopped after `plexus/organs/__init__.py` alone, attempts 4 to 8 byte-identical, because O1's text named that one-line file first under the header's "smallest change". Cured by committing the file as scaffolding (`40f358f`) and opening O1 with the three blocks in order (`9db3f06`).
- Run 2 (8 attempts, 3 kept, 62 to 14): the first full organ kept at 16; attempt 3 resent the kept `cozy.py` byte-identical, because after a keep the prompt shows test names and no failure text. Two later keeps fixed one clause each, one of them after a 404 branch the worker had added and then reversed.
- Run 3 (2 attempts, 2 kept, 14 to 0): `66309b5` spelled out the four remaining `cozy.py` changes as exact code; the worker applied them line for line and O1 closed on the first attempt, then O2 passed every gate, `neuron_unchanged` included, on the second.
- Exact code in the step text is again the measured cure. A byte-identical resend after a keep is the signal to spell out what is left.

**Open findings on the organ, none blocking a merge except as Joe decides** <!-- src:0e857ac5 date:2026-11-08 -->
- Hard, above: a wrong-type value leaves half an asset on disk.
- `cozy.py` H5: a non-JSON reply, a `/prompt` reply without `prompt_id`, a node without `inputs`, an entry without `outputs`, or a string seed escape as plain Python errors, not `OrganError`. O1 never asked for it.
- `cozy.py`: a 4xx refusal with a non-JSON body says only "Bad Request", and a 5xx drops its body; a kept JSON body may carry engine node names into an error core sees, worth checking against T8's intent; the deadline is checked after the blocking call, so a hung call overruns by up to 60 s; `capabilities()` hands out its cached list.
- `neuron.py`: a bool or float seed lands as an int; `modelHashes="abc"` lands as three hashes; a colorspace outside Spec 3's four lands; a relative `record.path` lands unresolved; a second `author_asset` at one prim leaves the first call's optional attributes behind; an existing `class` ancestor becomes `def` and other applied schemas are replaced (both inherited from `author`'s pattern, which O2 asked for); a comment at :78 says "with proper type checking" and nothing checks types.
- Clean, by the adversary: the deny flag matches `ctx.author`'s exactly, 8 and 12 neurons on one write ran three times in a child process with no crash, a missing key raises before the lock, a failed Save does not stall the runtime.

**Standing**
- Watch: whenever a run is live, one line per ledger row, unasked (`.plexus_loop/organ/watch/row.py <row>`). On a keep: the hand probe `organ_prep/proof/surface_probe.py` from the kept tree, `git show --stat`, the whole of phase 1, the reviewer and an adversary. `scratchpad/keep_checks.sh <worktree>` runs the first and third (session 0e857ac5's scratchpad).
- Release checklist (item 6 of the Nov 7 capsule): any keep reviewed and merged only on Joe's word; the full suite, harness suite, guards, ruff and `check` on the exact commit; the diff since the last tag scanned; notes checked claim by claim; an annotated `plexus-*` tag on the mission branch (never `v*`, never main, never moved once pushed). The bash guard reads `-F` beside a push as a force push, so messages go in with `--file=`.
- The guard hook blocks any command whose stages name the frozen folder beside a writer such as `cp` or `rev-parse` chains; run such reads through a script file.

**Blockers:** none. Ollama shows three `ollama.exe serve` processes (started 05:52, 14:42 and an older 20:24) and three `ollama app.exe`; runs worked, but this is the shape behind the Nov 5 engine-folder deletion, so an Ollama update must wait for Joe to close the extra instances. Two stale `tail -f` processes on `run31.log` are still alive and harmless.

**Energy required:** low. Joe's calls: the merge and the hard finding above; the first release with phase 2; whether to tidy the organ findings in a later mission; closing Houdini whenever the GPU should run (no attempt has ever run on the GPU).

**Ideas parked**
- The harness could show failure text after a keep too, not only after a drop; run 2's attempt 3 resent the kept file because it saw only test names.
- The prompt header's "Make the smallest change that moves the number" fought O1 twice; a step with several files could drop that line.
- Rule 3 (auto-restart after a run that kept nothing) never fired in the organ mission; its reach is still Joe's to settle.
