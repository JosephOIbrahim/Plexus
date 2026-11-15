"""The posix gate builds plexus._core for Linux and runs the lifecycle's POSIX cases in WSL2 Ubuntu, on the gate's own worktree."""

from __future__ import annotations

from pathlib import Path

from harness.plexus_loop import posix_gate


def test_argv_runs_bash_in_the_worktree_and_not_as_a_login_shell(tmp_path):
    a = posix_gate.argv(tmp_path)
    assert a[:7] == ["wsl.exe", "-d", "Ubuntu", "--cd", str(tmp_path), "--exec", "bash"]
    # A login shell's ~/.bash_logout turned `exit 2` into 1 under set -e; -c keeps the script's own exit code.
    assert a[7] == "-c"
    assert a[8] == posix_gate.script()


def test_the_script_checks_its_tools_before_it_builds_and_builds_before_it_tests():
    s = posix_gate.script()
    order = [s.index('test -x "$PY"'), s.index("command -v cargo"), s.index("command -v cc"),
             s.index("harness/plexus_loop/build_core.py"), s.index("-m pytest")]
    assert order == sorted(order)
    assert s.startswith("set -e\n")


def test_the_script_runs_the_three_lifecycle_files_and_no_live_test():
    s = posix_gate.script()
    for f in ("test_organ_hardening_posix.py", "test_organ_lifecycle.py", "test_organ_isolation.py"):
        assert f"phase2/{f}" in s
    assert '-m "not integration"' in s
    assert "live/" not in s


def test_the_linux_build_never_shares_the_windows_target_directory():
    s = posix_gate.script()
    assert 'CARGO_TARGET_DIR="$HOME/.cache/plexus-cargo"' in s
    assert 'PYO3_PYTHON="$PY"' in s


def test_the_cpu_profiles_job_cap_is_carried_into_wsl():
    assert "export CARGO_BUILD_JOBS=4" in posix_gate.script("4")
    assert "CARGO_BUILD_JOBS" not in posix_gate.script(None)


def test_no_wsl_fails_the_gate_and_never_skips(monkeypatch, capsys):
    monkeypatch.setattr(posix_gate.shutil, "which", lambda name: None)
    assert posix_gate.main(Path.cwd()) == 2
    assert "wsl.exe is not on PATH" in capsys.readouterr().err
