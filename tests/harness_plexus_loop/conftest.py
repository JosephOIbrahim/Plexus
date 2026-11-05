"""Shared by the harness's own tests."""

from __future__ import annotations

import pytest

from harness.plexus_loop import loop


@pytest.fixture(autouse=True)
def _child_pytest_without_plugins(monkeypatch):
    # A real pytest metric starts a child pytest, and a plugin on this machine pulls in torch: an empty run takes 3.6 s
    # against 0.34 s without it, and every attempt's unit gate pays that for each child.
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")


@pytest.fixture(autouse=True)
def _no_wait_for_the_model_server(monkeypatch):
    # A test of a refused load must not sit out five real minutes inside an attempt's unit gate. The tests of the wait set their own.
    monkeypatch.setattr(loop, "WORKER_WAIT_S", 0.0)
    monkeypatch.setattr(loop, "WORKER_POLL_S", 0.0)
