"""The layers guard holds package __init__.py files to one docstring.

Run 9 attempt 4 was kept with `__doc__ = __file__` after the docstring in both
plexus/core/__init__.py and plexus/membrane/__init__.py. The brief has said "a docstring
only" since 950b997, but nothing checked it, so the reviewer caught it after the keep.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.plexus_loop.guards.test_layers import INIT_MAY_DEFINE, init_problem


@pytest.mark.parametrize("text", [
    '"""Plexus core."""\n',
    '"""Plexus core.\n\nTwo paragraphs.\n"""\n',
    "",
    "# a comment only\n",
])
def test_a_docstring_or_nothing_passes(tmp_path: Path, text: str):
    p = tmp_path / "__init__.py"
    p.write_text(text, encoding="utf-8")
    assert init_problem(p) is None


@pytest.mark.parametrize("text, line", [
    ('"""Plexus core."""\n\n__doc__ = __file__\n', 3),
    ('"""Plexus core."""\nfrom plexus.core.axon import PlexusAxon\n', 2),
    ("from . import axon\n", 1),
    ("x = 1\n", 1),
    ('"""a"""\n"""b"""\n', 2),
])
def test_anything_after_the_docstring_is_named_by_line(tmp_path: Path, text: str, line: int):
    p = tmp_path / "__init__.py"
    p.write_text(text, encoding="utf-8")
    assert init_problem(p) == f"line {line} is code; delete everything after the docstring"


def test_a_syntax_error_is_reported_not_raised(tmp_path: Path):
    p = tmp_path / "__init__.py"
    p.write_text('"""x"""\ndef (:\n', encoding="utf-8")
    assert init_problem(p).startswith("does not parse")


def test_only_the_schema_package_may_define_names():
    # CONTRACT.md: `from plexus.schema import plugin_dir`; no other package export is called.
    assert INIT_MAY_DEFINE == {"plexus/schema/__init__.py"}


def test_a_bom_is_fine_and_bad_bytes_are_named(tmp_path: Path):
    p = tmp_path / "__init__.py"
    p.write_bytes(b'\xef\xbb\xbf"""Plexus core."""\n')
    assert init_problem(p) is None
    p.write_bytes(b'"""caf\xe9"""\n')
    why = init_problem(p)
    assert why is not None and why.startswith(("does not parse", "does not decode"))
