---
description: Check the Plexus build environment (Ollama + model, Rust, maturin, usd-core 0.26.5, Houdini state, harness check) and fix only what is inside the repo's own venv or Cargo workspace
argument-hint: [mission name, default acceptance]
allowed-tools: Bash(python -m harness.plexus_loop check *), Bash(ollama *), Bash(cargo *), Bash(rustc *), Bash(maturin *), Bash(python -c *), Bash(pip *), Bash(uv *), Read
---

## Pre-computed context

- Harness check: !`m=${ARGUMENTS:-acceptance}; python -m harness.plexus_loop check harness/plexus_loop/missions/$m.toml 2>&1 | head -10`
- Ollama server: !`ollama ps 2>&1 | head -3`
- Ollama models: !`ollama list 2>&1 | head -10`
- Rust: !`rustc --version 2>&1; cargo --version 2>&1`
- maturin: !`maturin --version 2>&1`
- usd-core: !`python -c "from pxr import Usd; print('usd-core', Usd.GetVersion())" 2>&1`
- Python: !`python --version 2>&1`
- Houdini processes: !`tasklist /FI "IMAGENAME eq houdini*" 2>/dev/null | tail -n +4 || ps -A -o comm= 2>/dev/null | grep -i houdini || echo "(none visible / check failed → CPU)"`

## Task

Report what the checks found in plain sentences. Required: usd-core (0, 26, 5) to match Houdini 22; `qwen3-coder:30b` present in `ollama list` and the server answering `ollama ps`; maturin and a stable Rust toolchain; the harness `check` printing `ready`.

Fix only environment problems, and only inside the repo's venv or Cargo workspace. For anything system-wide — pulling the model, installing a toolchain, a driver — state the exact command and ask Joe before running it. If `check` says `not ready: missing ...`, that is a repo-state problem for the mission plan, not something to patch here.
