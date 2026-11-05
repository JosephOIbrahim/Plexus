"""Does the mission branch differ from the loop branch on anything an attempt's worktree reads?

build_prompt reads the brief and the other context files from the attempt's worktree, which is cut from the tip of
plexus-loop/<mission>. Only the toml comes from the main tree. A restart with the two branches apart runs on files nobody
is looking at, which cost rows 64 to 73, about 4.6 hours. So run this before any restart, and expect none.

    python harness/plexus_loop/tools/worktree_reads_diff.py [mission]

Exits 1 when they differ. Read-only.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def differing(repo: Path, mission: str) -> tuple[int, list[str]]:
    """How many context files the mission names, and which of them differ between its two branches."""
    cfg = tomllib.loads((repo / "harness" / "plexus_loop" / "missions" / f"{mission}.toml").read_text(encoding="utf-8"))
    context = cfg["mission"]["context"]
    out = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only", f"plexus-loop/{mission}", f"mission/{mission}", "--", *context],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    )
    return len(context), [n for n in out.stdout.splitlines() if n.strip()]


def main(argv: list[str]) -> int:
    mission = argv[0] if argv else "acceptance"
    count, names = differing(REPO, mission)
    print(f"plexus-loop/{mission} vs mission/{mission}, {count} context files:", names or "none")
    return 1 if names else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
