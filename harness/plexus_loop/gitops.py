"""The few git operations the harness needs, each one a plain git command."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

IDENTITY = {
    "GIT_AUTHOR_NAME": "plexus-loop",
    "GIT_AUTHOR_EMAIL": "plexus-loop@localhost",
    "GIT_COMMITTER_NAME": "plexus-loop",
    "GIT_COMMITTER_EMAIL": "plexus-loop@localhost",
}


class GitError(RuntimeError):
    pass


def git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    full_env = None
    if env:
        full_env = dict(os.environ)
        full_env.update(env)
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, env=full_env, check=False)
    if r.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def repo_root(start: Path) -> Path:
    return Path(git(start, "rev-parse", "--show-toplevel").strip())


def rev(repo: Path, ref: str) -> str:
    return git(repo, "rev-parse", "--verify", ref + "^{commit}").strip()


def ensure_branch(repo: Path, branch: str) -> str:
    """Create the harness branch at HEAD if it doesn't exist. Return its tip."""
    try:
        return rev(repo, "refs/heads/" + branch)
    except GitError:
        git(repo, "branch", branch, "HEAD")
        return rev(repo, "refs/heads/" + branch)


def add_worktree(repo: Path, path: Path, sha: str) -> None:
    if path.exists():
        remove_worktree(repo, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    git(repo, "worktree", "add", "--detach", str(path), sha)


def remove_worktree(repo: Path, path: Path) -> None:
    try:
        git(repo, "worktree", "remove", "--force", str(path))
    except GitError:
        shutil.rmtree(path, ignore_errors=True)
        git(repo, "worktree", "prune")


def changed_paths(worktree: Path) -> list[str]:
    """Every path the attempt touched, tracked or new, both sides of a rename."""
    out = git(worktree, "status", "--porcelain", "-z", "--untracked-files=all")
    parts = out.split("\0")
    paths: list[str] = []
    i = 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        paths.append(path)
        if "R" in status or "C" in status:
            if i < len(parts) and parts[i]:
                paths.append(parts[i])
            i += 1
    return sorted(set(paths))


def commit_all(worktree: Path, message: str) -> str:
    git(worktree, "add", "-A")
    git(worktree, "-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", message, env=IDENTITY)
    return rev(worktree, "HEAD")


def advance_branch(repo: Path, branch: str, new: str, old: str) -> None:
    """Move the harness branch forward, only if nobody else moved it."""
    git(repo, "update-ref", "refs/heads/" + branch, new, old)
