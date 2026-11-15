"""Shared helpers for Plexus Claude Code hooks.

Hooks read a JSON event on stdin. Exit 0 = allow. Exit 2 = block; stderr is shown to Claude.
Everything here is deterministic and dependency-free so it runs on Windows (Git Bash or PowerShell)
and on Linux without a venv.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()).resolve()


def read_event() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def block(reason: str) -> None:
    sys.stderr.write(reason.rstrip() + "\n")
    sys.exit(2)


def frozen_paths() -> list[str]:
    f = PROJECT / ".claude" / "frozen_paths.txt"
    out: list[str] = []
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                out.append(s.replace("\\", "/"))
    return out


def rel(path_str: str) -> str:
    """Repo-relative, forward-slash form of a path (or the input if outside the repo)."""
    try:
        p = Path(path_str)
        if not p.is_absolute():
            p = PROJECT / p
        return p.resolve().relative_to(PROJECT).as_posix()
    except Exception:
        return path_str.replace("\\", "/")


def is_frozen(path_str: str) -> bool:
    r = rel(path_str)
    for fp in frozen_paths():
        if fp.endswith("/"):
            if r.startswith(fp) or r == fp.rstrip("/"):
                return True
        elif r == fp:
            return True
    return False


# Synapse must never enter the codebase. Prose that names it as a reference is fine; code and deps are not.
SYNAPSE_CODE = re.compile(
    r"(^|\n)\s*(from\s+synapse[\w.]*\s+import|import\s+synapse\b)"  # python imports
    r"|[\"']synapse[\w\-]*[\"']\s*[=:]"  # toml/json dependency keys
    r"|synapse\s*=\s*[\"'{]"  # cargo/pyproject dep lines
    r"|^\s*synapse[\w\-]*\s*(>=|==|~=|<|>|$)",  # requirements.txt lines
    re.IGNORECASE | re.MULTILINE,
)
MONETA_OLD = re.compile(r"agent[./]integrations[./]moneta", re.IGNORECASE)

# Comfy-Cozy is an architecture reference only (Joe, Nov 1; Blueprint v5.4, §0 item 9): nothing under plexus/ or crates/
# imports the seeded agent.* or cognitive.*, at module or function scope, or loads them by name. The worker's code is held
# to the same rule by the `layers` gate (harness/plexus_loop/guards/test_layers.py); this catches Claude's own edits.
COZY_IMPORT = re.compile(
    r"^[ \t]*from[ \t]+(?:agent|cognitive)(?:\.[\w.]+)?[ \t]+import\b"  # from agent.x import y
    r"|^[ \t]*import[ \t]+(?:[\w.]+(?:[ \t]+as[ \t]+\w+)?[ \t]*,[ \t]*)*(?:agent|cognitive)(?:\.[\w.]+)?(?![\w.])"  # import a, agent.x
    r"|(?:import_module|__import__|\bimport)\(\s*[\"'](?:agent|cognitive)[.\"']",  # importlib, __import__, PyO3 py.import("agent")
    re.MULTILINE,
)


def is_plexus_code(path_str: str) -> bool:
    """plexus/ or crates/, where Plexus's own code lives; prose there (.md) is not code."""
    r = rel(path_str)
    return r.startswith(("plexus/", "crates/")) and not r.endswith(".md")

PROSE_DIRS = ("docs/", "harness/", ".claude/", "README", "CHANGELOG", "CLAUDE.md")


def is_prose(path_str: str) -> bool:
    r = rel(path_str)
    return r.endswith(".md") or any(r.startswith(d) for d in PROSE_DIRS)


def houdini_running() -> bool | None:
    """True if a Houdini process is visible, False if none, None if we cannot tell.
    None is treated as 'running' by callers: unknown means CPU."""
    try:
        if sys.platform.startswith("win"):
            out = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=10
            ).stdout.lower()
            return any(k in out for k in ("houdini", "hindie", "houdinifx", "husk", "hython"))
        out = subprocess.run(["ps", "-A", "-o", "comm="], capture_output=True, text=True, timeout=10).stdout.lower()
        return any(k in out for k in ("houdini", "hindie", "houdinifx", "husk", "hython"))
    except Exception:
        return None


def git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=PROJECT, capture_output=True, text=True, timeout=20
        ).stdout.strip()
    except Exception:
        return ""
