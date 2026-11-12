r"""Closeout — CozyLifecycle closes what alpha.11's notes left open: CONTRACT's J1 to J8.

Three things alpha.11 could not see, and now can:

- A local admin share is the drive it names. `\\localhost\C$\...` and `\\?\UNC\localhost\C$\...` are `C:\...`, so an instance
  written that way inside the workspace's temp folder is refused like any other spelling, whether or not the folder exists yet
  (resolve() keeps both prefixes on a path that is not there, so only a lexical mapping reaches it).
- A host may declare where its own ComfyUI keeps its temp folder, with `workspace_temp=`. A workspace whose ComfyUI was started with
  `--temp-directory` deletes that folder at start and at a normal exit, and Plexus cannot read another process's argv to find it.
- ComfyUI's own database lock. `main.py` holds `<instance>/user/comfyui.db.lock` for as long as it runs (app/database/db.py:122-135),
  so an engine whose comfy-cli has died is still visible: `start()` refuses that instance instead of starting a second engine on it.

Nothing here runs the real comfy-cli or ComfyUI, touches port 8188 or leaves this machine. The Rig, its fakes, its guard and its
timing helpers are test_organ_isolation's and test_organ_lifecycle's, imported through test_organ_hardening.py, which also holds the
`build` and `outcome` helpers these cases use. Every case fails rather than passes when its premise does not hold.
"""

from __future__ import annotations

import os
import shutil
import sys

import pytest

from tests.acceptance.phase2.test_organ_hardening import (  # noqa: F401 - the 8188 guard applies once its module is imported
    CONSTRUCT_S,
    POLL_S,
    Reports,
    Rig,
    START_S,
    STOP_S,
    alive,
    build,
    cli_runs,
    engine_port,
    free_port,
    outcome,
    refused,
    rig,
    value_of,
    within,
)
from tests.acceptance.phase2.test_organ_lifecycle import organ_error

WINDOWS = sys.platform == "win32"

SENTENCE_J1 = (
    "CONTRACT J1: on Windows the constructor also raises ValueError when an instance is inside the workspace's temp folder written through a "
    "local admin share (`\\\\localhost\\C$\\...`, `\\\\127.0.0.1\\C$\\...`, the machine's own name, with or without the `\\\\?\\UNC\\` prefix), "
    "which names the drive it stands for whether or not the folder exists.")
SENTENCE_J2 = (
    "CONTRACT J2: a folder that only shares a name prefix with the workspace's temp folder, written the same way, is accepted.")
SENTENCE_J3 = (
    "CONTRACT J3: when `workspace_temp` is given, the constructor also raises ValueError when an instance is inside that folder, as it does for "
    "`<workspace>/temp`.")
SENTENCE_J4 = (
    "CONTRACT J4: an instance outside the declared `workspace_temp` is accepted, and the argument changes nothing about the rest of the command.")
SENTENCE_J5 = (
    "CONTRACT J5: without `workspace_temp` the constructor refuses exactly what it refused before, `<workspace>/temp` and the workspace itself.")
SENTENCE_J6 = (
    "CONTRACT J6: `start()` reports \"unavailable\" and raises OrganError naming the instance, spawning nothing, when a process holds ComfyUI's own "
    "database lock, `<instance>/user/comfyui.db.lock`.")
SENTENCE_J7 = (
    "CONTRACT J7: a database lock file nobody holds, which a killed ComfyUI leaves behind, does not make an instance in use: `start()` returns "
    "\"ready\".")

HOW_SHARE = (
    "A local admin share is written as `\\\\<host>\\<letter>$\\<rest>`; the host may be `localhost`, `127.0.0.1` or this machine's own name, and "
    "the `\\\\?\\UNC\\` prefix may come before it. Only this host's own shares count: another machine's C$ is another machine's folder.")


def _share(path, prefix=False):
    r"""This machine's admin-share spelling of a Windows path: \\localhost\C$\... or \\?\UNC\localhost\C$\..."""
    drive, rest = str(path)[:1].upper(), str(path)[3:]
    return ("\\\\?\\UNC\\localhost\\" if prefix else "\\\\localhost\\") + drive + "$\\" + rest


def _lock(fd):
    """Take the same lock ComfyUI's own FileLock takes on this platform, on fd's byte 0."""
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


@pytest.fixture
def instance_with_a_held_lock(tmp_path):
    """An instance whose <instance>/user/comfyui.db.lock this process holds, as a running main.py does."""
    inst = tmp_path / "instances" / "held"
    (inst / "user").mkdir(parents=True)
    fd = os.open(inst / "user" / "comfyui.db.lock", os.O_RDWR | os.O_CREAT, 0o644)
    try:
        _lock(fd)
    except OSError as e:  # a machine that cannot lock a file it just made
        os.close(fd)
        pytest.fail(f"Inconclusive, so this case fails: this machine could not lock its own lock file: {e}")
    try:
        yield inst
    finally:
        os.close(fd)


@pytest.mark.skipif(not WINDOWS, reason="a drive's admin share is Windows'")
@pytest.mark.parametrize("prefix", [False, True], ids=["plain", "unc-prefix"])
def test_an_instance_through_a_local_admin_share_is_refused(rig, prefix):
    """J1. The workspace's temp folder is written through this machine's admin share, and it does not exist yet."""
    ws = rig.workspace("j1")
    # The workspace's temp folder is not there yet, which is the spelling alpha.11 could not see: its only comparison was samefile(),
    # and that needs the folder to exist. A ComfyUI started from the workspace makes it, and deletes it at start and at a normal exit.
    shutil.rmtree(ws / "temp")
    target = ws / "temp" / "not" / "made" / "yet"
    assert not (ws / "temp").exists(), "Inconclusive, so this case fails: the workspace's temp folder exists, and this case needs it absent."
    given = _share(target, prefix)
    box, reports = build(rig, ws, engine_port(rig.engine()), instance=given)
    assert "raised" in box and isinstance(box["raised"], ValueError), (
        f"CozyLifecycle with instance {given} {outcome(box)}, and it raises ValueError: that spelling names the workspace's temp folder, and a "
        f"ComfyUI started from the workspace deletes it. {SENTENCE_J1} {HOW_SHARE}")
    assert reports.states == [], f"The constructor reported {reports.states} before it raised. {SENTENCE_J1}"
    assert not cli_runs(ws), f"The command ran: {cli_runs(ws)}. {SENTENCE_J1}"


@pytest.mark.skipif(not WINDOWS, reason="a drive's admin share is Windows'")
def test_a_sibling_through_a_local_admin_share_is_accepted(rig):
    """J2. Guard: the same spelling of a folder that is not the temp folder must still build."""
    ws = rig.workspace("j2")
    given = _share(ws / "temp2" / "inst")
    box, _reports = build(rig, ws, engine_port(rig.engine()), instance=given)
    assert "value" in box, f"CozyLifecycle with instance {given} {outcome(box)}, and a sibling of the temp folder is not inside it. {SENTENCE_J2}"


def test_an_instance_in_the_workspace_temp_a_host_declares_is_refused(rig):
    """J3. The workspace's ComfyUI was started with --temp-directory elsewhere; the host says where."""
    ws = rig.workspace("j3")
    declared = ws.parent / "declared_temp"
    declared.mkdir()
    box, reports = build(rig, ws, engine_port(rig.engine()), instance=declared / "inst", workspace_temp=declared)
    assert "raised" in box and isinstance(box["raised"], ValueError), (
        f"CozyLifecycle with workspace_temp={declared} and instance inside it {outcome(box)}, and it raises ValueError, because that ComfyUI "
        f"deletes the folder at start and at a normal exit. {SENTENCE_J3}")
    assert reports.states == [], f"The constructor reported {reports.states} before it raised. {SENTENCE_J3}"


def test_an_instance_beside_the_declared_workspace_temp_is_accepted(rig):
    """J4. Guard: the declared folder is the boundary, not everything near it."""
    ws = rig.workspace("j4")
    declared = ws.parent / "declared_temp2"
    declared.mkdir()
    # A sibling whose name starts with the declared folder's: a string-prefix check refuses it, a folder check does not.
    box, _reports = build(rig, ws, engine_port(rig.engine()), instance=ws.parent / "declared_temp2_sibling", workspace_temp=declared)
    assert "value" in box, f"CozyLifecycle beside a declared workspace_temp {outcome(box)}. {SENTENCE_J4}"


def test_without_a_declared_temp_the_default_still_governs(rig):
    """J5. Guard: the new argument changes nothing when it is not given."""
    ws = rig.workspace("j5")
    (ws / "temp").mkdir(exist_ok=True)
    box, _reports = build(rig, ws, engine_port(rig.engine()), instance=ws / "temp" / "inst")
    assert "raised" in box and isinstance(box["raised"], ValueError), (
        f"CozyLifecycle with instance in <workspace>/temp and no workspace_temp {outcome(box)}. {SENTENCE_J5}")


def test_an_instance_a_comfyui_holds_by_its_database_lock_is_refused(rig, instance_with_a_held_lock):
    """J6. A bystander holds <instance>/user/comfyui.db.lock, as a main.py whose comfy-cli has died still does."""
    ws = rig.workspace("j6")
    inst = instance_with_a_held_lock
    box, reports = build(rig, ws, free_port(), instance=inst)
    assert "value" in box, f"CozyLifecycle with instance {inst} {outcome(box)}. {SENTENCE_J6}"
    life = box["value"]
    got = within(life.start, "start()", START_S, must_return=False)
    assert "raised" in got and isinstance(got["raised"], organ_error()), (
        f"start() on an instance whose database lock another process holds {outcome(got)}: it reports 'unavailable' and raises OrganError "
        f"naming the instance, spawning nothing. {SENTENCE_J6}")
    assert str(inst) in str(got["raised"]), f"The OrganError reads {str(got['raised'])!r}, without the instance. {SENTENCE_J6}"
    assert reports.states[-1:] == ["unavailable"], f"report last saw {reports.states[-1:]}, and 'unavailable' is last. {SENTENCE_J6}"
    assert not cli_runs(ws), f"The refused start ran the command: {cli_runs(ws)}. {SENTENCE_J6}"


@pytest.mark.parametrize("lock_file", ["left behind", "never made"], ids=["unheld-file", "no-file"])
def test_a_database_lock_nobody_holds_does_not_make_an_instance_in_use(rig, lock_file):
    """J7. Guard: a killed ComfyUI leaves the lock file behind, unheld, and a fresh instance has none at all."""
    ws = rig.workspace("j7")
    inst = ws.parent / "instances" / ("j7" if lock_file == "left behind" else "j7_new")
    (inst / "user").mkdir(parents=True)
    if lock_file == "left behind":
        (inst / "user" / "comfyui.db.lock").write_bytes(b"")
    port = free_port()
    reports = Reports()
    box, _ = build(rig, ws, port, instance=inst, ready_s=START_S - 2)
    assert "value" in box, f"CozyLifecycle with instance {inst} {outcome(box)}. {SENTENCE_J7}"
    life = box["value"]
    got = value_of(within(life.start, "start()", START_S), "start()", SENTENCE_J7)
    assert got == "ready", f"start() returned {got!r} on an instance whose lock file nobody holds. {SENTENCE_J7}"
    stopped = value_of(within(life.stop, "stop()", STOP_S), "stop()", SENTENCE_J7)
    assert stopped == "stopped" and refused(port), f"stop() returned {stopped!r} with port {port} {'closed' if refused(port) else 'answering'}. {SENTENCE_J7}"
    # Its own probe must have let the database lock go, or the next lifecycle on the instance would refuse it as in use.
    again_port = free_port()
    box2, _ = build(rig, ws, again_port, instance=inst, ready_s=START_S - 2)
    assert "value" in box2, f"A second lifecycle on the same instance {outcome(box2)}, after the first stopped. {SENTENCE_J7}"
    second = value_of(within(box2["value"].start, "start() on a stopped instance", START_S), "start()", SENTENCE_J7)
    assert second == "ready", f"A second lifecycle on the same instance returned {second!r} after the first stopped. {SENTENCE_J7}"
    value_of(within(box2["value"].stop, "stop()", STOP_S), "stop()", SENTENCE_J7)
