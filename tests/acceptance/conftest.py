"""Fixtures for the frozen Plexus acceptance tests. Helpers live in _support.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.acceptance._support import LOOK, FakeClock, Slice


@pytest.fixture
def slice_(tmp_path: Path):
    from plexus.core import stagekit
    from plexus.membrane import exchange as ex

    root = tmp_path / "session"
    xpath = ex.create_exchange(root / "shared" / "exchange")
    a_layer = ex.register_participant(xpath, "projectA", grants=[LOOK])
    pa = stagekit.create_project(root / "projectA.usda", xpath, "projectA")
    pb = stagekit.create_project(root / "projectB.usda", xpath, "projectB")
    s = Slice(
        root=root,
        exchange=xpath,
        a_layer_path=a_layer,
        project_a=pa,
        project_b=pb,
        clock=FakeClock(),
    )
    s.set_temperature(1.0)
    yield s
    if s.runtime is not None:
        s.runtime.stop()
