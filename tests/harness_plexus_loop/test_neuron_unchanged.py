"""The neuron_unchanged gate: one named method may come in, and any other change to neuron.py's code drops the reply."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from harness.plexus_loop import neuron_unchanged

PY = sys.executable
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
SCRIPT = Path(neuron_unchanged.__file__).resolve()

BASE = '''"""A neuron.py in miniature."""

from pxr import Sdf


def _set_attr(spec, name, value, type_name):
    attr = spec.attributes.get(name) or Sdf.AttributeSpec(spec, name, type_name)
    attr.default = value


class _Ctx:
    def author(self, prim_path, attr_name, value, type_name):
        return Sdf.Path(prim_path)


class NeuronRuntime:
    def register(self, name, *, scope):
        handle = name
        return handle

    def start(self):
        return None
'''

AUTHOR_ASSET = '''        return Sdf.Path(prim_path)

    def author_asset(self, prim_path, record):
        return record
'''

PUBLISH_ORGAN = '''        return handle

    def publish_organ(self, profile):
        root = "/Plexus/Organs"
        return Sdf.Path(root).AppendChild(profile.organ_id)
'''


def _with_author_asset(text: str) -> str:
    return text.replace("        return Sdf.Path(prim_path)\n", AUTHOR_ASSET, 1)


def _with_publish_organ(text: str) -> str:
    return text.replace("        return handle\n", PUBLISH_ORGAN, 1)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "plexus" / "core").mkdir(parents=True)
    (r / neuron_unchanged.FILE).write_text(BASE, encoding="utf-8")
    subprocess.run([*GIT, "init", "-q"], cwd=r, check=True, capture_output=True)
    subprocess.run([*GIT, "add", "-A"], cwd=r, check=True, capture_output=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "base"], cwd=r, check=True, capture_output=True)
    return r


def _gate(repo: Path, text: str, *args: str) -> subprocess.CompletedProcess:
    (repo / neuron_unchanged.FILE).write_text(text, encoding="utf-8")
    return subprocess.run([PY, "-I", str(SCRIPT), *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", check=False)


def test_the_file_as_head_has_it_passes_with_or_without_the_option(repo):
    assert _gate(repo, BASE).returncode == 0
    out = _gate(repo, BASE, "--may-add", "NeuronRuntime.publish_organ")
    assert out.returncode == 0, out.stdout
    assert "every statement of the last kept commit stands" in out.stdout


def test_with_no_option_the_default_still_lets_author_asset_in(repo):
    assert neuron_unchanged.MAY_ADD == {"_Ctx.author_asset"}
    out = _gate(repo, _with_author_asset(BASE))
    assert out.returncode == 0, out.stdout


def test_with_no_option_publish_organ_drops_and_the_default_line_stands_word_for_word(repo):
    out = _gate(repo, _with_publish_organ(BASE))
    assert out.returncode == 1
    # Mission organ's known fix matches this line, so the default output must not move.
    assert "O2 adds _Ctx.author_asset and changes nothing else" in out.stdout
    assert "new: NeuronRuntime.publish_organ" in out.stdout


def test_may_add_lets_that_one_method_in(repo):
    out = _gate(repo, _with_publish_organ(BASE), "--may-add", "NeuronRuntime.publish_organ")
    assert out.returncode == 0, out.stdout


def test_may_add_replaces_the_default_so_author_asset_then_drops(repo):
    out = _gate(repo, _with_author_asset(_with_publish_organ(BASE)), "--may-add", "NeuronRuntime.publish_organ")
    assert out.returncode == 1
    assert "new: _Ctx.author_asset" in out.stdout
    assert "this step adds NeuronRuntime.publish_organ and changes nothing else" in out.stdout


def test_may_add_repeats(repo):
    text = _with_author_asset(_with_publish_organ(BASE))
    out = _gate(repo, text, "--may-add", "NeuronRuntime.publish_organ", "--may-add", "_Ctx.author_asset")
    assert out.returncode == 0, out.stdout


@pytest.mark.parametrize(
    ("old", "new", "label"),
    [
        # A one-line change in another method.
        ("        handle = name\n", "        handle = name.strip()\n", "changed: NeuronRuntime.register"),
        # A new module-level constant.
        ("from pxr import Sdf\n", "from pxr import Sdf\n\nORGAN_ROOT = '/Plexus/Organs'\n", "changed: <statements>"),
        # A new import.
        ("from pxr import Sdf\n", "from pxr import Sdf, Usd\n", "changed: <statements>"),
        # A new module-level helper.
        ("class _Ctx:\n", "def _organ_path(organ_id):\n    return organ_id\n\n\nclass _Ctx:\n", "new: _organ_path"),
        # A method gone.
        ("    def start(self):\n        return None\n", "", "gone: NeuronRuntime.start"),
    ],
)
def test_with_may_add_a_change_anywhere_else_still_drops(repo, old, new, label):
    text = _with_publish_organ(BASE)
    assert old in text
    out = _gate(repo, text.replace(old, new, 1), "--may-add", "NeuronRuntime.publish_organ")
    assert out.returncode == 1, out.stdout
    assert label in out.stdout


def test_comments_blank_lines_and_docstrings_do_not_count(repo):
    text = _with_publish_organ(BASE).replace("    def start(self):\n", "    # a comment\n\n    def start(self):\n        \"\"\"A docstring.\"\"\"\n", 1)
    out = _gate(repo, text, "--may-add", "NeuronRuntime.publish_organ")
    assert out.returncode == 0, out.stdout


def test_verdict_takes_the_names_it_may_add():
    now = _with_publish_organ(BASE)
    assert neuron_unchanged.verdict(BASE, now) == ([], [], ["NeuronRuntime.publish_organ"])
    assert neuron_unchanged.verdict(BASE, now, {"NeuronRuntime.publish_organ"}) == ([], [], [])
