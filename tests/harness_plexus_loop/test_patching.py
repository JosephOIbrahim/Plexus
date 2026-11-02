"""Tests for reply handling: whole-file blocks, diff rebuilding, saved replies, and safety."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from harness.plexus_loop import MissionRun
from harness.plexus_loop.mission import mission_from_dict
from harness.plexus_loop.profile import Profile
from harness.plexus_loop.workers import (
    WorkerResult, apply_diff, apply_reply, clean_diff, extract_diff, extract_files, fenced_blocks,
)

PY = sys.executable
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def _repo(tmp_path: Path, gitignore: str = "") -> Path:
    r = tmp_path / "repo"
    (r / "plexus").mkdir(parents=True)
    (r / "plexus" / "a.py").write_text("one\ntwo\nthree\n")
    if gitignore:
        (r / ".gitignore").write_text(gitignore)
    for args in (["init", "-q", "-b", "master"], ["add", "-A"], ["commit", "-q", "-m", "s"]):
        subprocess.run([*GIT, *args], cwd=r, check=True, capture_output=True)
    return r


EDIT = "--- a/plexus/a.py\n+++ b/plexus/a.py\n@@ -1,3 +1,3 @@\n one\n-two\n+TWO\n three\n"


# -- parsing ------------------------------------------------------------------

def test_fenced_blocks_never_mistake_a_closing_fence_for_an_opening_one():
    reply = "intro\n```file:plexus/b.py\nx = 1\n```\nthen prose\n```diff\n" + EDIT + "```\n"
    assert [b.info for b in fenced_blocks(reply)] == ["file:plexus/b.py", "diff"]
    assert [(f.info, f.body) for f in extract_files(reply)] == [("plexus/b.py", "x = 1\n")]
    assert extract_diff(reply) == EDIT


def test_a_docstring_example_fence_nests_inside_a_file_block():
    body = 'def f():\n    """Use it:\n\n    ```python\n    f()\n    ```\n    """\n'
    files = extract_files(f"```file:plexus/f.py\n{body}```\n")
    assert files[0].body == body and files[0].closed


@pytest.mark.parametrize("opener", ["```file: plexus/b.py", "```python file:plexus/b.py", "````file:`plexus/b.py`"])
def test_file_block_info_strings_are_read_loosely(opener):
    fence = opener[: len(opener) - len(opener.lstrip("`"))]
    assert [f.info for f in extract_files(f"{opener}\nx\n{fence}\n")] == ["plexus/b.py"]


def test_text_inside_a_file_block_is_never_taken_as_a_diff():
    assert extract_diff("```file:docs/x.md\ntitle\n--- \nsee +++ here\n```\n") is None


# -- diff rebuilding ----------------------------------------------------------

def test_clean_diff_drops_stray_lines_and_rebuilds_headers():
    dirty = "Here is the diff:\n" + EDIT.replace(" one\n", " one\n?\n") + "Hope this helps!\n"
    assert clean_diff(dirty) == "diff --git a/plexus/a.py b/plexus/a.py\n" + EDIT


def test_multi_file_new_file_diff_without_git_headers_applies(tmp_path):
    r = _repo(tmp_path)
    diff = ("--- /dev/null\n+++ b/plexus/core/axon.py\n@@ -0,0 +1,2 @@\n+class A:\n+    pass\n"
            "--- /dev/null\n+++ plexus/core/stagekit.py\n@@ -0,0 +1,3 @@\n+def f():\n?\n+    return 1\n")
    res = apply_diff(r, diff)
    assert res.ok, res.note
    assert (r / "plexus" / "core" / "axon.py").read_text() == "class A:\n    pass\n"
    assert (r / "plexus" / "core" / "stagekit.py").read_text() == "def f():\n\n    return 1\n"


def test_headers_without_prefixes_land_at_the_right_path(tmp_path):
    r = _repo(tmp_path)
    res = apply_diff(r, EDIT.replace("a/plexus", "plexus").replace("b/plexus", "plexus"))
    assert res.ok and (r / "plexus" / "a.py").read_text() == "one\nTWO\nthree\n"
    assert not (r / "a.py").exists()


def test_a_failed_diff_reports_the_first_real_error_without_temp_paths(tmp_path):
    res = apply_diff(_repo(tmp_path), EDIT.replace(" one\n", " ONE\n"))
    assert not res.ok and "error" in res.note and "tmp" not in res.note.lower()


# -- replies --------------------------------------------------------------------

def test_apply_reply_writes_whole_files_then_applies_the_diff(tmp_path):
    r = _repo(tmp_path)
    reply = "```file:plexus/core/axon.py\nclass PlexusAxon:\n    pass\n```\n\n```diff\n" + EDIT + "```\n"
    res = apply_reply(r, reply)
    assert res.ok and res.reply == reply and res.wrote == ["plexus/core/axon.py"]
    assert (r / "plexus" / "core" / "axon.py").read_text() == "class PlexusAxon:\n    pass\n"
    assert (r / "plexus" / "a.py").read_text() == "one\nTWO\nthree\n"


def test_a_diff_for_a_file_a_block_already_wrote_is_left_to_the_block(tmp_path):
    r = _repo(tmp_path)
    reply = ("```file:plexus/core/neuron.py\nX = 1\n```\n```diff\n--- /dev/null\n+++ b/plexus/core/neuron.py\n"
             "@@ -0,0 +1 @@\n+X = 2\n```\n")
    res = apply_reply(r, reply)
    assert res.ok, res.note
    assert (r / "plexus" / "core" / "neuron.py").read_text() == "X = 1\n"
    assert not (r / "b").exists()


def test_a_reply_cut_off_inside_a_file_block_is_refused(tmp_path):
    res = apply_reply(_repo(tmp_path), "```file:plexus/b.py\nx = 1\n")
    assert not res.ok and "ended inside" in res.note


@pytest.mark.parametrize("path", ["../escape.py", "/abs.py", "C:/x.py", "plexus/../../x.py", ".git/config",
                                  ".GIT/config", ".git", ".git./x", "GIT~1/config", "plexus/x?.py",
                                  "plexus/nul.py", "plexus/con"])
def test_file_blocks_refuse_unsafe_paths_cleanly(tmp_path, path):
    r = _repo(tmp_path)
    res = apply_reply(r, f"```file:{path}\nx\n```\n")
    assert not res.ok and "path" in res.note
    subprocess.run(["git", "status"], cwd=r, check=True, capture_output=True)  # .git still intact


def test_a_file_block_on_an_existing_directory_fails_cleanly(tmp_path):
    res = apply_reply(_repo(tmp_path), "```file:plexus\nx\n```\n")
    assert not res.ok and "could not be written" in res.note


def test_apply_reply_with_nothing_usable_keeps_the_reply(tmp_path):
    res = apply_reply(_repo(tmp_path), "I could not do it.")
    assert not res.ok and res.reply == "I could not do it."
    assert WorkerResult(True).reply == "" and WorkerResult(True).wrote == []


# -- the loop -------------------------------------------------------------------

def _mission(attempts=1):
    return mission_from_dict({
        "mission": {"name": "demo", "goal": "g", "requires": ["tests/acceptance"], "focus": ["plexus/**"],
                    "frozen": ["tests/acceptance/**"]},
        "metric": {"kind": "command", "cmd": [PY, "-c", (
            "import pathlib; b=pathlib.Path('plexus/build/score.txt'); "
            "print((b if b.exists() else pathlib.Path('plexus/score.txt')).read_text().strip())")]},
        "gates": [{"name": "ok", "cmd": [PY, "-c", "pass"]}],
        "budget": {"attempts": attempts, "hours": 1, "max_consecutive_failures": 5},
    })


def _loop_repo(tmp_path, gitignore=""):
    r = _repo(tmp_path, gitignore)
    (r / "tests" / "acceptance").mkdir(parents=True)
    (r / "tests" / "acceptance" / "f.txt").write_text("x")
    (r / "plexus" / "score.txt").write_text("3\n")
    for args in (["add", "-A"], ["commit", "-q", "-m", "t"]):
        subprocess.run([*GIT, *args], cwd=r, check=True, capture_output=True)
    return r


class Replying:
    def __init__(self, *replies):
        self.replies = list(replies)

    def attempt(self, wt, prompt, profile):
        return apply_reply(wt, self.replies.pop(0))


def _run(r, worker, attempts=1):
    return MissionRun(_mission(attempts), r, worker=worker, log=lambda s: None,
                      profile_fn=lambda: Profile(device="cpu", houdini="running")).run()


def test_run_saves_each_raw_reply_and_records_its_path(tmp_path):
    r = _loop_repo(tmp_path)
    report = _run(r, Replying("```file:plexus/score.txt\n2\n```\n"))
    a = report.attempts[0]
    assert a.kept and a.reply_file.startswith(".plexus_loop/demo/replies/")
    assert (r / a.reply_file).read_text(encoding="utf-8") == "```file:plexus/score.txt\n2\n```\n"


def test_writing_an_ignored_path_drops_the_attempt(tmp_path):
    r = _loop_repo(tmp_path, gitignore="build/\n")
    report = _run(r, Replying("```file:plexus/build/score.txt\n0\n```\n```file:plexus/note.txt\nhi\n```\n"))
    a = report.attempts[0]
    assert not a.kept and "git ignores" in a.reason


def test_a_bad_reply_costs_one_attempt_not_the_run(tmp_path):
    r = _loop_repo(tmp_path)
    report = _run(r, Replying("```file:plexus/x?.py\nx\n```\n", "```file:plexus/score.txt\n2\n```\n"), attempts=2)
    assert [a.kept for a in report.attempts] == [False, True]
    assert (r / ".plexus_loop" / "demo" / "REVIEW.md").is_file()


def test_prompt_renders_files_in_the_form_it_asks_for(tmp_path):
    from harness.plexus_loop.loop import build_prompt
    m = mission_from_dict({"mission": {"name": "x", "goal": "g", "focus": ["plexus/**"]},
                           "metric": {"kind": "command", "cmd": ["true"]},
                           "gates": [{"name": "ok", "cmd": ["true"]}]})
    r = _repo(tmp_path)
    (r / "plexus" / "doc.md").write_text("```python\nx\n```\n")
    subprocess.run([*GIT, "add", "-A"], cwd=r, check=True)
    p = build_prompt(m, r, 1, None, [], 50_000)
    assert "```file:plexus/a.py\none" in p
    assert "````file:plexus/doc.md" in p  # a longer fence when the file holds backticks
    assert p.rstrip().endswith("Nothing else inside either.")
