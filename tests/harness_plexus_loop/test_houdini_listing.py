"""The Windows process list as tasklist prints it.

The hard rule is that Houdini open, or a check that cannot tell, runs on the CPU. Every other test hands
houdini_state a ready list of names, so a parse that stopped matching would read "absent" and put an
attempt on the GPU beside Houdini, with every test green.
"""

from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace

import pytest

from harness.plexus_loop.profile import houdini_state

OTHERS = '"System Idle Process","0","Services","0","8 K"\n"explorer.exe","9000","Console","1","123,456 K"\n'


@pytest.mark.parametrize("listing, state", [
    (OTHERS + '"houdinifx.exe","4242","Console","1","2,048,000 K"\n', "running"),
    (OTHERS + '"HServer.EXE","4243","Console","1","20,000 K"\n', "running"),
    (OTHERS, "absent"),
    ("INFO: No tasks are running which match the specified criteria.\n", "unknown"),
    (None, "unknown"),
], ids=["houdini", "another case, another tool", "clearly absent", "no process lines", "the reader died"])
def test_the_listing_is_read_as_tasklist_prints_it(monkeypatch, listing, state):
    with monkeypatch.context() as mp:  # undone here: the shared fixtures' teardown runs later and imports modules
        mp.delenv("PLEXUS_LOOP_HOUDINI", raising=False)
        mp.setattr(sys, "platform", "win32")
        mp.setattr(subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout=listing))
        seen = houdini_state()
    assert seen == state
