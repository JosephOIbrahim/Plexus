"""The `posix` gate: the lifecycle's POSIX cases, run in WSL2 Ubuntu on the worktree the gate runs in.

The harness measures on Windows, where test_organ_hardening_posix.py and the POSIX halves of the lifecycle and isolation files
skip, so without this gate no attempt answers for them (organ-closeout plan, D5). This gate runs those three files under
Linux, where their Windows-only cases skip instead, after building plexus._core for Linux into the worktree.

What it needs inside WSL2 Ubuntu, all at user level (set up Nov 15):
  - ~/.venvs/plexus: Python 3.14.2 (uv), the project's dependencies, usd-core 26.5 and the pinned test tools;
  - ~/.cargo/bin: Rust 1.99.1 (rustup), and a C linker (`cc`) for cargo to link with.
The Linux build goes to its own target directory in the WSL home, never the Windows one the harness shares, and
plexus/_core.so is ignored by git as plexus/_core.pyd is.

A missing distro, venv or toolchain fails the gate with a line that names it; the gate never skips.

Run from the repo or worktree root: python harness/plexus_loop/posix_gate.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

DISTRO = "Ubuntu"
VENV = "$HOME/.venvs/plexus"
TARGET = "$HOME/.cache/plexus-cargo"
FILES = [
    "tests/" + "acceptance/phase2/test_organ_hardening_posix.py",
    "tests/" + "acceptance/phase2/test_organ_lifecycle.py",
    "tests/" + "acceptance/phase2/test_organ_isolation.py",
]


def script(jobs: str | None = None) -> str:
    """The bash the gate runs in WSL: check the venv and the toolchain, build plexus/_core.so, then pytest the three files."""
    lines = [
        "set -e",
        f'PY="{VENV}/bin/python"',
        f'test -x "$PY" || {{ echo "posix gate: no Python at {VENV}; see harness/plexus_loop/posix_gate.py"; exit 2; }}',
        'export PATH="$HOME/.cargo/bin:$PATH"',
        'command -v cargo >/dev/null || { echo "posix gate: no cargo in ~/.cargo/bin; see harness/plexus_loop/posix_gate.py"; exit 2; }',
        'command -v cc >/dev/null || { echo "posix gate: no C linker (cc) in WSL; cargo cannot link plexus._core"; exit 2; }',
        f'export CARGO_TARGET_DIR="{TARGET}" PYO3_PYTHON="$PY" PYTHONDONTWRITEBYTECODE=1',
    ]
    if jobs:
        lines.append(f"export CARGO_BUILD_JOBS={int(jobs)}")  # the CPU profile's cap, carried into WSL
    lines += [
        '"$PY" harness/plexus_loop/build_core.py',
        'exec "$PY" -m pytest -q -p no:cacheprovider -ra -m "not integration" ' + " ".join(FILES),
    ]
    return "\n".join(lines)


def argv(root: Path, jobs: str | None = None) -> list[str]:
    """wsl.exe runs bash in the worktree itself: --cd translates the Windows path, and --exec starts bash with no shell
    before it, so nothing in the script is expanded on the way in. bash is not a login shell: under `set -e` a login shell's
    ~/.bash_logout turned an `exit 2` into 1 (measured Nov 15), and the script sets PATH itself."""
    return ["wsl.exe", "-d", DISTRO, "--cd", str(root), "--exec", "bash", "-c", script(jobs)]


def main(root: Path | None = None) -> int:
    root = (root or Path.cwd()).resolve()
    wsl = shutil.which("wsl.exe")
    if wsl is None:
        print("posix gate: wsl.exe is not on PATH, so the POSIX cases cannot run here", file=sys.stderr)
        return 2
    try:
        r = subprocess.run(argv(root, os.environ.get("CARGO_BUILD_JOBS")), check=False)
    except OSError as e:
        print(f"posix gate: could not start wsl.exe: {e}", file=sys.stderr)
        return 2
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
