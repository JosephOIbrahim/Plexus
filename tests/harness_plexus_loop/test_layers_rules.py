"""The `layers` gate fails on the trees it forbids and passes on the tree it allows.

It is the only thing that holds "nothing from Comfy-Cozy comes into plexus/" (CLAUDE.md: no hook enforces this yet),
and every attempt must pass it. A rule that stopped matching would pass every attempt with every test green, because
test_init_guard.py reaches one helper and nothing else calls the rules. So each one runs here on a small tree of its own.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.plexus_loop.guards import test_layers as layers

SRC = "crates/plexus-core/src"
# plugin.py is the idiomatic sibling import _targets allows: counted as a dependency on the package itself, it would
# read as a cycle through the one __init__ that may import.
CLEAN = {
    "Cargo.toml": '[workspace]\nmembers = ["crates/plexus-core"]\n',
    f"{SRC}/lib.rs": 'pub mod budget;\n#[cfg(feature = "python")]\nmod py;\n',
    f"{SRC}/budget.rs": "use crate::error::Error;\n",
    f"{SRC}/py.rs": "use crate::budget::Budget;\nuse pyo3::prelude::*;\n",
    "plexus/__init__.py": '"""Plexus."""\n',
    "plexus/core/__init__.py": '"""Core."""\n',
    "plexus/core/axon.py": "from pxr import Usd\n\nfrom . import stagekit\n",
    "plexus/core/stagekit.py": "X = 1\n",
    "plexus/schema/__init__.py": "from .plugin import plugin_dir\n",
    "plexus/schema/plugin.py": "from . import paths\n\n\ndef plugin_dir():\n    return paths\n",
    "plexus/schema/paths.py": "X = 1\n",
}
COMFY_COZY = "test_python_never_imports_comfy_cozy"
WORKSPACE = "test_workspace_has_at_most_two_known_members_and_no_build_scripts"


@pytest.fixture
def plant(tmp_path, monkeypatch):
    monkeypatch.setattr(layers, "REPO", tmp_path)
    monkeypatch.setattr(layers, "PLEXUS", tmp_path / "plexus")
    monkeypatch.setattr(layers, "CORE_SRC", tmp_path / SRC)

    def write(files: dict[str, str]) -> None:
        for rel, text in files.items():
            (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / rel).write_text(text, encoding="utf-8")
    return write


def test_the_guard_reads_this_repo():
    # Every rule passes on a folder that is not there, so a guard that resolved another root would guard nothing.
    repo = Path(__file__).resolve().parents[2]
    assert layers.PLEXUS == repo / "plexus" and layers.CORE_SRC == repo / SRC


def test_a_tree_that_keeps_every_rule_passes_all_of_them(plant):
    plant(CLEAN)
    for rule in [n for n in dir(layers) if n.startswith("test_")]:
        getattr(layers, rule)()


@pytest.mark.parametrize("rule, files", [
    (COMFY_COZY, {"plexus/core/axon.py": "import agent.tools\n"}),
    (COMFY_COZY, {"plexus/core/axon.py": "def f():\n    from cognitive.core import delta\n"}),
    ("test_core_never_imports_the_cozy_organ", {"plexus/core/axon.py": "def f():\n    from ..organs.cozy import Organ\n"}),
    ("test_pxr_only_from_rank_two_up", {"plexus/core/predicate.py": "def f():\n    from pxr import Usd\n"}),
    ("test_package_inits_hold_a_docstring_only", {"plexus/core/__init__.py": '"""Core."""\n\n__doc__ = __file__\n'}),
    ("test_python_has_no_import_cycles", {"plexus/core/stagekit.py": "def f():\n    from . import axon\n"}),
    ("test_rust_lib_only_declares_modules", {f"{SRC}/lib.rs": "pub fn f() {}\n"}),
    ("test_rust_ranks_point_strictly_down", {f"{SRC}/budget.rs": "use crate::predicate::Predicate;\n"}),
    ("test_rust_ranks_point_strictly_down", {f"{SRC}/other.rs": "pub struct Other;\n"}),
    ("test_only_py_rs_names_pyo3", {f"{SRC}/budget.rs": "use pyo3::prelude::*;\n"}),
    (WORKSPACE, {"Cargo.toml": '[workspace]\nmembers = ["crates/plexus-core", "crates/other"]\n'}),
    (WORKSPACE, {"crates/plexus-core/build.rs": "fn main() {}\n"}),
])
def test_each_rule_fails_on_the_tree_it_forbids(plant, rule, files):
    plant({**CLEAN, **files})
    with pytest.raises(AssertionError):
        getattr(layers, rule)()
