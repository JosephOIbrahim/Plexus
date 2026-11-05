"""A redirected stdout can't end the process on text its locale cannot encode."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from harness.plexus_loop import loop
from harness.plexus_loop.__main__ import main as cli_main

PY = sys.executable
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def test_a_redirected_stdout_cannot_end_the_process_on_a_path_it_cannot_encode(tmp_path):
    r = tmp_path / "修改"
    (r / "sub").mkdir(parents=True)
    subprocess.run([*GIT, "init", "-q"], cwd=r, check=True, capture_output=True)
    env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="0")
    root = Path(loop.__file__).parents[2]
    out = subprocess.run([PY, "-m", "harness.plexus_loop", "stop", "--repo", str(r / "sub")], cwd=root, env=env, capture_output=True, check=False)
    assert out.returncode == 0, out.stderr.decode("cp1252", "replace")
    assert b"\\u4fee" in out.stdout
    # The file a run polls, at the repo's root, whatever folder the verb ran from.
    assert (r / ".plexus_loop" / "STOP").is_file() and not (r / "sub" / ".plexus_loop").exists()


def test_a_run_that_cannot_start_says_why_and_exits_two(tmp_path, capsys):
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run([*GIT, "init", "-q"], cwd=r, check=True, capture_output=True)
    toml = tmp_path / "m.toml"
    # A command worker has no model to load, so nothing here can reach a server even if a check above it goes missing.
    toml.write_text('[mission]\nname = "demo"\ngoal = "g"\nfocus = ["plexus/**"]\n[metric]\nkind = "command"\ncmd = ["x"]\n'
                    '[worker]\nkind = "command"\ncmd = ["x"]\n', encoding="utf-8")
    assert cli_main(["run", str(toml), "--repo", str(r)]) == 2
    assert "not started: the mission names no gates" in capsys.readouterr().err
    assert not (r / ".plexus_loop").exists()
    # A log redirected to a file is read while the run runs, and block buffering leaves it empty until exit.
    assert sys.stdout.line_buffering
    toml.write_text("not toml", encoding="utf-8")
    for verb in ("run", "check"):
        assert cli_main([verb, str(toml), "--repo", str(r)]) == 2
        assert "mission file problem" in capsys.readouterr().err
