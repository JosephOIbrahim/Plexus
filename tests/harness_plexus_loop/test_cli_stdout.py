"""A redirected stdout can't end the process on text its locale cannot encode."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from harness.plexus_loop import loop

PY = sys.executable
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def test_a_redirected_stdout_cannot_end_the_process_on_a_path_it_cannot_encode(tmp_path):
    r = tmp_path / "修改"
    r.mkdir()
    subprocess.run([*GIT, "init", "-q"], cwd=r, check=True, capture_output=True)
    env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="0")
    root = Path(loop.__file__).parents[2]
    out = subprocess.run([PY, "-m", "harness.plexus_loop", "stop", "--repo", str(r)], cwd=root, env=env, capture_output=True, check=False)
    assert out.returncode == 0, out.stderr.decode("cp1252", "replace")
    assert b"\\u4fee" in out.stdout
