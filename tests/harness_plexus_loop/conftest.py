"""Shared by the harness's own tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _child_pytest_without_plugins(monkeypatch):
    # A real pytest metric starts a child pytest, and a plugin on this machine pulls in torch: an empty run takes 3.6 s
    # against 0.34 s without it, and every attempt's unit gate pays that for each child.
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
