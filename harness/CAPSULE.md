# Capsule — Plexus

**Where we are:** Mile 2 of ~4. Mission `acceptance` ran its first 5 Jev-routed attempts on the CPU (Nov 1, 20:24–21:18). Phase1 is at 10 failing of 11 (baseline 11): T0, the schema gate, passes. One kept commit, `4e494b3` on `plexus-loop/acceptance` (S1, the schema plugin; reviewer verdict: keep, no hard or soft failures). Attempts 2–5 all aimed at S2 and all failed at `git apply`, before any gate ran. Scaffolding C1–C6 is on `mission/acceptance` (tip `abc6ba0`, pushed); pyo3 0.30.1 builds and imports on Python 3.14.2. Nothing is merged.

**Next action:** Joe approves the patch-handling fix (three parts, below). Claude makes it as its own harness commit, shows it, then runs the next batch of attempts from `4e494b3`.

**Blockers:**
- The worker's diffs for new files don't apply: "diff header lacks filename", a stray `?` line (twice), and "new file … depends on old contents". The harness doesn't save the raw reply, so the cause can't be seen yet.
- Proposed fix, needs Joe's OK: (1) save each attempt's raw reply under `.plexus_loop/<mission>/replies/`; (2) clean the diff before applying (drop non-diff lines, retry with relaxed path handling); (3) let the worker return a new file as a whole-file block, or put an exact new-file diff example in the worker brief.
- The `layers` guard lives at `harness/plexus_loop/guards/test_layers.py` (interim). Joe may move it to `tests/acceptance/guards/`.

**Energy required:** low. One yes/no on the fix, then the harness runs unattended (about 10.6 min per attempt on the CPU).

**Ideas parked:**
- Show the failing gate's output (compiler errors, test tails) of the last dropped attempt in the next prompt; today the worker only sees the reason line. Matters from S3, the first Rust step.
- Attempt 5 wrote `plexus/core/neuron.py`, which belongs to S3, while routed to S2: the step section may need a firmer "these files only" line.
- Spec Patch 02 is approved; its document and T0-style frozen test still need writing before M4.
- `release.yml` is Comfy-Cozy's pipeline. Retarget or retire it before any Plexus release.
- `harness/plexus-loop` lacks the Comfy-Cozy-reference and scaffold work; merge `mission/acceptance` back when Joe promotes.
- Open decisions elsewhere: the Blueprint v5.4 draft's four (no-import hook, `comfyui-agent` MCP server, D6 licence reading, a fifth contract).
- The seed (`agent/`, `cognitive/`): Joe decides whether it stays. SALUS / Moneta / Hanish: Joe is leaning toward removing them. `CLAUDE.cozy.md`: delete with the seed, or keep as history.
