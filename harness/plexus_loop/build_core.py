"""The `core` gate: build plexus._core for the worktree it runs in.

cargo builds crates/plexus-core with the `python` feature, and the library is copied
to plexus/_core.pyd (Windows) or plexus/_core.so, so `import plexus._core` works from
the worktree. The harness sets CARGO_TARGET_DIR to one shared directory, so builds stay
warm across attempts, and the CPU profile beside Houdini sets CARGO_BUILD_JOBS, which
cargo honours. With no crate yet there is nothing to build, and the gate passes.

Run from the repo or worktree root: python harness/plexus_loop/build_core.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def artifact(target: Path) -> tuple[Path, str]:
    """The library cargo writes, and the file name Python imports it as."""
    release = target / "release"
    if sys.platform.startswith("win"):
        return release / "plexus_core.dll", "_core.pyd"
    if sys.platform == "darwin":
        return release / "libplexus_core.dylib", "_core.so"
    return release / "libplexus_core.so", "_core.so"


def main(root: Path | None = None) -> int:
    root = (root or Path.cwd()).resolve()
    if not (root / "crates" / "plexus-core" / "Cargo.toml").is_file():
        print("build_core: no crates/plexus-core yet; nothing to build")
        return 0
    cmd = ["cargo", "build", "--release", "--features", "python", "-p", "plexus-core"]
    try:
        r = subprocess.run(cmd, cwd=root, check=False)
    except OSError as e:
        print(f"build_core: could not start cargo: {e}", file=sys.stderr)
        return 2
    if r.returncode != 0:
        return r.returncode
    target = Path(os.environ.get("CARGO_TARGET_DIR") or (root / "target"))
    if not target.is_absolute():
        target = root / target
    built, name = artifact(target)
    if not built.is_file():
        print(f"build_core: cargo succeeded but {built} is missing", file=sys.stderr)
        return 2
    dest = root / "plexus" / name
    dest.parent.mkdir(exist_ok=True)
    shutil.copy2(built, dest)
    print(f"build_core: {built} -> {dest.relative_to(root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
