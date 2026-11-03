"""Workers: the local model that makes each attempt.

A worker gets a worktree, a prompt and a profile, and changes files in the
worktree. The harness then decides whether to keep the change. Two kinds ship:

- ``OllamaWorker`` asks a local Ollama model for its change and applies it: whole-file
  blocks (```file:<path>) for new or fully rewritten files, and a unified diff for edits.
  The diff is cleaned of stray non-diff lines before ``git apply``.
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .mission import WorkerSpec
from .profile import Profile


@dataclass
class WorkerResult:
    ok: bool
    note: str = ""
    reply: str = ""  # the model's raw reply, saved by the loop so failed attempts can be read
    wrote: list[str] = field(default_factory=list)  # paths written by whole-file blocks
    # The model server's own account of the call, when it gives one (ollama_stats).
    stats: dict = field(default_factory=dict)


class Worker(Protocol):
    def attempt(self, worktree: Path, prompt: str, profile: Profile) -> WorkerResult: ...


_FENCE_LINE = re.compile(r"^\s*(`{3,})(.*?)\s*$")


@dataclass
class Block:
    info: str
    body: str
    closed: bool = True


def fenced_blocks(text: str) -> list[Block]:
    """Every fenced block in a reply, read line by line, CommonMark-style.

    A block closes only on a bare fence at least as long as its opener. An inner fence
    with an info string (a docstring's ```python example) nests until its own bare close.
    A block still open at the end of the reply is returned with closed=False.
    """
    blocks: list[Block] = []
    opener = 0
    depth = 0
    info = ""
    body: list[str] = []
    for line in text.splitlines(keepends=True):
        m = _FENCE_LINE.match(line)
        if not opener:
            if m:
                opener, info, body, depth = len(m.group(1)), m.group(2).strip(), [], 0
            continue
        if m and len(m.group(1)) >= opener:
            if m.group(2).strip():
                depth += 1
            elif depth:
                depth -= 1
            else:
                blocks.append(Block(info, "".join(body)))
                opener = 0
                continue
        body.append(line)
    if opener:
        blocks.append(Block(info, "".join(body), closed=False))
    return blocks


_FILE_INFO = re.compile(r"(?:^|\s)file:\s*(\S+)", re.IGNORECASE)


def extract_files(text: str) -> list[Block]:
    """Whole-file blocks: a fence whose info string holds ``file:<path>`` carries the file's full content."""
    out = []
    for b in fenced_blocks(text):
        m = _FILE_INFO.search(b.info)
        if m:
            out.append(Block(m.group(1).strip("`'\""), b.body, b.closed))
    return out


def extract_diff(text: str) -> str | None:
    """Pull a unified diff out of a model reply, or None if there isn't one.

    The unfenced fallback is used only when the reply has no fenced blocks at all, so text
    inside a whole-file block is never mistaken for a diff.
    """
    blocks = fenced_blocks(text)
    for b in blocks:
        if b.info.lower() in ("", "diff", "patch") and "--- " in b.body and "+++ " in b.body:
            return b.body if b.body.endswith("\n") else b.body + "\n"
    if blocks:
        return None
    for marker in ("diff --git ", "--- "):
        i = text.find(marker)
        if i != -1 and "+++ " in text[i:]:
            body = text[i:]
            return body if body.endswith("\n") else body + "\n"
    return None


def _strip_prefix(path: str) -> str:
    path = path.split("\t")[0].strip()
    for pre in ("a/", "b/"):
        if path.startswith(pre):
            return path[2:]
    return path


def clean_diff(diff: str) -> str:
    """Rebuild a model's diff into one git apply accepts.

    Each file's ``---``/``+++`` pair (a ``---`` line counts as a header only when ``+++``
    follows it) gets a fresh ``diff --git a/P b/P`` header, ``new file mode`` when the old
    side is /dev/null, and a/ b/ prefixes. The model's own git, index and mode lines are
    dropped. Inside a hunk only context, +, - and backslash lines are kept: stray prose and
    marks go, a lost blank context line comes back as a space, and in a new file a lone
    ``?`` (a blank line the model mangled) becomes an empty added line.
    """
    lines = [x.rstrip("\r") for x in diff.splitlines()]
    out: list[str] = []
    in_hunk = False
    new_file = False
    i = 0
    while i < len(lines):
        line = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if line.startswith("--- ") and nxt.startswith("+++ "):
            old, new = _strip_prefix(line[4:]), _strip_prefix(nxt[4:])
            new_file, gone = old == "/dev/null", new == "/dev/null"
            path = old if gone else new
            out.append(f"diff --git a/{path} b/{path}")
            if new_file:
                out.append("new file mode 100644")
            elif gone:
                out.append("deleted file mode 100644")
            out.append("--- /dev/null" if new_file else f"--- a/{old}")
            out.append("+++ /dev/null" if gone else f"+++ b/{new}")
            in_hunk = False
            i += 2
            continue
        if line.startswith("@@"):
            in_hunk = True
            out.append(line)
        elif line.startswith(("diff --git ", "index ", "new file mode", "deleted file mode",
                              "old mode", "new mode")):
            in_hunk = False
        elif in_hunk:
            if line[:1] in (" ", "+", "-", "\\"):
                out.append(line)
            elif line == "":
                out.append("+" if new_file else " ")
            elif new_file and line.strip() == "?":
                out.append("+")
        i += 1
    return "\n".join(out) + "\n" if any(x.startswith("@@") for x in out) else ""


def _first_error(stderr: str) -> str:
    lines = [x for x in stderr.strip().splitlines() if x.strip()]
    errors = [x for x in lines if x.startswith("error:")]
    msg = (errors or lines or ["no output from git apply"])[0]
    return re.sub(r"\S*\.patch(:\d+)?", r"<patch>\1", msg)


def _git_apply(worktree: Path, diff: str) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False, encoding="utf-8",
                                     errors="replace", newline="\n") as f:
        f.write(diff)
        patch = f.name
    try:
        return subprocess.run(["git", "apply", "--whitespace=nowarn", "--recount", patch],
                              cwd=worktree, capture_output=True, text=True, check=False)
    finally:
        Path(patch).unlink(missing_ok=True)


def apply_diff(worktree: Path, diff: str) -> WorkerResult:
    """Apply a diff: the rebuilt one first, then the model's own. A failed git apply changes nothing."""
    cleaned = clean_diff(diff)
    candidates = [(cleaned, "patch applied (rebuilt)")] if cleaned else []
    if cleaned != diff:
        candidates.append((diff, "patch applied"))
    first_error = None
    for candidate, how in candidates:
        r = _git_apply(worktree, candidate)
        if r.returncode == 0:
            return WorkerResult(True, how)
        first_error = first_error or _first_error(r.stderr)
    return WorkerResult(False, "patch did not apply: " + (first_error or "the diff holds no hunk"))


_WIN_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10))}
_BAD_CHARS = set('<>"|?*') | {chr(c) for c in range(32)}


def _unsafe(rel: str) -> str:
    """Why a whole-file path is refused, or "" when it is safe."""
    if not rel or rel.startswith("/") or ":" in rel:
        return "absolute or drive path"
    for part in rel.split("/"):
        bare = part.rstrip(". ").lower()
        if part in ("", ".", ".."):
            return "empty, . or .. component"
        if bare == ".git" or re.search(r"~\d", part):
            return ".git or a short-name alias"
        if bare.split(".")[0] in _WIN_RESERVED:
            return "reserved device name"
        if set(part) & _BAD_CHARS:
            return "character not allowed in a file name"
    return ""


def write_files(worktree: Path, files: list[Block]) -> WorkerResult:
    """Write whole-file blocks into the worktree. Paths must stay inside it, outside .git.

    The loop still checks every written path against focus and frozen afterwards, and
    drops the attempt if anything git ignores was written.
    """
    root = worktree.resolve()
    wrote: list[str] = []
    for f in files:
        rel = f.info.replace("\\", "/")
        while rel.startswith("./"):
            rel = rel[2:]
        if not f.closed:
            return WorkerResult(False, f"the reply ended inside the file block for {rel!r}", wrote=wrote)
        why = _unsafe(rel)
        if why:
            return WorkerResult(False, f"file block has an unsafe path ({why}): {rel!r}", wrote=wrote)
        dest = (root / rel).resolve()
        if root not in dest.parents or (root / ".git") in (dest, *dest.parents):
            return WorkerResult(False, f"file block points outside the worktree: {rel!r}", wrote=wrote)
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(f.body, encoding="utf-8", errors="replace", newline="\n")
        except OSError as e:
            return WorkerResult(False, f"file block could not be written: {rel!r}: {e}", wrote=wrote)
        wrote.append(rel)
    return WorkerResult(True, f"wrote {len(wrote)} file(s)", wrote=wrote)


def _without_files(diff: str, paths: set[str]) -> str:
    """Drop the file sections of a diff whose target a whole-file block already wrote."""
    cleaned = clean_diff(diff)
    if not cleaned:
        return diff
    keep: list[str] = []
    skip = False
    for line in cleaned.splitlines():
        if line.startswith("diff --git "):
            skip = line.split(" b/", 1)[-1] in paths
        if not skip:
            keep.append(line)
    return "\n".join(keep) + "\n" if any(x.startswith("@@") for x in keep) else ""


def apply_reply(worktree: Path, reply: str) -> WorkerResult:
    """Apply a model reply: whole-file blocks first, then the diff, if either is present.

    A diff section aimed at a file a whole-file block already wrote is left to the block.
    """
    files = extract_files(reply)
    diff = extract_diff(reply)
    if not files and diff is None:
        return WorkerResult(False, "model reply held no unified diff and no file block", reply)
    notes: list[str] = []
    wrote: list[str] = []
    if files:
        r = write_files(worktree, files)
        wrote = r.wrote
        if not r.ok:
            return WorkerResult(False, r.note, reply, wrote)
        notes.append(r.note)
    if diff is not None:
        if wrote:
            diff = _without_files(diff, set(wrote))
        if diff.strip():
            r = apply_diff(worktree, diff)
            if not r.ok:
                return WorkerResult(False, r.note, reply, wrote)
            notes.append(r.note)
    return WorkerResult(True, "; ".join(notes), reply, wrote)


# Ollama's /api/generate reply carries its own timing next to the text: token counts, and
# durations in nanoseconds. Kept so a slow attempt can say whether reading the prompt or
# writing the reply took the time, which decides whether prompt caching is worth doing.
OLLAMA_COUNTS = ("prompt_eval_count", "eval_count")
OLLAMA_DURATIONS = ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration")


def ollama_stats(body: dict) -> dict:
    """The counts as ints and the durations as seconds (to a tenth, ``_s`` names), present keys only."""
    out: dict = {}
    for k in OLLAMA_COUNTS:
        if isinstance(body.get(k), int):
            out[k] = body[k]
    for k in OLLAMA_DURATIONS:
        if isinstance(body.get(k), (int, float)):
            out[k.removesuffix("_duration") + "_s"] = round(body[k] / 1e9, 1)
    return out


class OllamaWorker:
    def __init__(self, spec: WorkerSpec):
        self.spec = spec

    def payload(self, prompt: str, profile: Profile) -> dict:
        body: dict = {"model": self.spec.model, "prompt": prompt, "stream": False}
        options = dict(profile.ollama_options)
        if self.spec.num_ctx > 0:
            # Without it the server's default window can drop the front of a long prompt,
            # which is where the mission's rules sit.
            options["num_ctx"] = self.spec.num_ctx
        if options:
            body["options"] = options
        return body

    def attempt(self, worktree: Path, prompt: str, profile: Profile) -> WorkerResult:
        req = urllib.request.Request(
            self.spec.host.rstrip("/") + "/api/generate",
            data=json.dumps(self.payload(prompt, profile)).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.spec.timeout_s) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 - network, timeout, bad JSON all mean no attempt
            return WorkerResult(False, f"ollama call failed: {type(e).__name__}: {e}")
        if not isinstance(body, dict):
            return WorkerResult(False, "ollama call failed: the reply was not a JSON object")
        res = apply_reply(worktree, body.get("response", "") or "")
        res.stats = ollama_stats(body)
        return res


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
