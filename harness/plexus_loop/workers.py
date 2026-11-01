"""Workers: the local model that makes each attempt.

A worker gets a worktree, a prompt and a profile, and changes files in the
worktree. The harness then decides whether to keep the change. Two kinds ship:

- ``OllamaWorker`` asks a local Ollama model for a unified diff and applies it.
- ``CommandWorker`` runs any command-line model or tool in the worktree and
  lets it edit files directly. ``{prompt_file}`` and ``{worktree}`` in its
  command are filled in.

Any object with an ``attempt`` method of the same shape can stand in, which is
how the tests run without a model.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .mission import WorkerSpec
from .profile import Profile


@dataclass
class WorkerResult:
    ok: bool
    note: str = ""


class Worker(Protocol):
    def attempt(self, worktree: Path, prompt: str, profile: Profile) -> WorkerResult: ...


_FENCE = re.compile(r"```(?:diff|patch)?\s*\n(.*?)```", re.DOTALL)


def extract_diff(text: str) -> str | None:
    """Pull a unified diff out of a model reply, or None if there isn't one."""
    for block in _FENCE.findall(text):
        if "--- " in block and "+++ " in block:
            return block if block.endswith("\n") else block + "\n"
    for marker in ("diff --git ", "--- "):
        i = text.find(marker)
        if i != -1 and "+++ " in text[i:]:
            body = text[i:]
            return body if body.endswith("\n") else body + "\n"
    return None


def apply_diff(worktree: Path, diff: str) -> WorkerResult:
    with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False, encoding="utf-8") as f:
        f.write(diff)
        patch = f.name
    try:
        r = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", "--recount", patch],
            cwd=worktree, capture_output=True, text=True, check=False)
    finally:
        Path(patch).unlink(missing_ok=True)
    if r.returncode != 0:
        return WorkerResult(False, "patch did not apply: " + (r.stderr.strip().splitlines() or ["?"])[0])
    return WorkerResult(True, "patch applied")


class OllamaWorker:
    def __init__(self, spec: WorkerSpec):
        self.spec = spec

    def payload(self, prompt: str, profile: Profile) -> dict:
        body: dict = {"model": self.spec.model, "prompt": prompt, "stream": False}
        if profile.ollama_options:
            body["options"] = dict(profile.ollama_options)
        return body

    def attempt(self, worktree: Path, prompt: str, profile: Profile) -> WorkerResult:
        req = urllib.request.Request(
            self.spec.host.rstrip("/") + "/api/generate",
            data=json.dumps(self.payload(prompt, profile)).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.spec.timeout_s) as resp:
                reply = json.loads(resp.read().decode("utf-8")).get("response", "")
        except Exception as e:  # noqa: BLE001 - network, timeout, bad JSON all mean no attempt
            return WorkerResult(False, f"ollama call failed: {type(e).__name__}: {e}")
        diff = extract_diff(reply)
        if diff is None:
            return WorkerResult(False, "model reply held no unified diff")
        return apply_diff(worktree, diff)


class CommandWorker:
    def __init__(self, spec: WorkerSpec):
        self.spec = spec

    def attempt(self, worktree: Path, prompt: str, profile: Profile) -> WorkerResult:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(prompt)
            prompt_file = f.name
        cmd = [c.replace("{prompt_file}", prompt_file).replace("{worktree}", str(worktree)) for c in self.spec.cmd]
        try:
            r = subprocess.run(
                cmd, cwd=worktree, env=profile.environ(), capture_output=True, text=True,
                timeout=self.spec.timeout_s, check=False)
        except subprocess.TimeoutExpired:
            return WorkerResult(False, "worker command timed out")
        except OSError as e:
            return WorkerResult(False, f"worker command could not start: {e}")
        finally:
            Path(prompt_file).unlink(missing_ok=True)
        if r.returncode != 0:
            return WorkerResult(False, f"worker command exited {r.returncode}")
        return WorkerResult(True, "command finished")


def make_worker(spec: WorkerSpec) -> Worker:
    if spec.kind == "ollama":
        return OllamaWorker(spec)
    return CommandWorker(spec)
