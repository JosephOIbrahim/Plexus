"""Hardening on POSIX: CONTRACT's H3, H4 and H7d.

These three cases read what only POSIX has: the root's process group, which must be signalled only while the root is not yet reaped, so a
kill never reaches a group that took its number (H3); a kill the system refuses, which leaves the tree this lifecycle's and stop() able to
try again (H4); and an engine that outlives the host that started it, which keeps its instance (H7d).

They live apart from test_organ_hardening.py because the harness metric counts a skipped test as a failure, and these three skip on the
Windows machine the harness runs on. Everything else is that file's: the Rig, the sentences, the helpers and the child hosts, imported
here rather than copied. group_signals wraps os.killpg and os.kill in this process; it records each signal, can refuse the next one with
PermissionError, and, once the root has been reaped here (os.waitid with WNOWAIT finds no such child), answers signal 0 to the root's
number as a group that took it would and withholds any other signal to it. Each case fails rather than passes when its premise does not hold.
"""

from __future__ import annotations

import errno
import os

import pytest

from tests.acceptance.phase2.test_organ_hardening import (  # noqa: F401 - the 8188 guard applies once its module is imported
    CHILD_S,
    CONSTRUCT_S,
    HOST_LEAVING,
    HOW_LOCK,
    HOW_REFUSED,
    HOW_REAP,
    SENTENCE_H3,
    SENTENCE_H4,
    SENTENCE_H7,
    SENTENCE_H8,
    START_S,
    STOP_S,
    WINDOWS,
    Rig,  # noqa: F401 - the type the rig fixture builds
    alive,
    cli_runs,
    free_port,
    host_out,
    main_pid,
    organ_error,
    raised_organ_error,
    refused,
    rig,  # noqa: F401 - the fixture the cases take
    two_ports,
    until,
    value_of,
    within,
    Reports,
)




@pytest.fixture
def group_signals(monkeypatch):
    """Wraps os.killpg, and os.kill for pid < -1, passing every call through by default and recording each non-zero signal with whether the
    group had a process. raise_next = a group number: the next non-zero signal to it raises PermissionError(EPERM) instead of being sent.
    reaped_number(root): once os.waitid(P_PID, root, WEXITED | WNOHANG | WNOWAIT) raises ChildProcessError in this process, the root has
    been reaped, and from then on signal 0 to that number answers success, as a group that took the number would, and any other signal to it
    is recorded and withheld."""
    real_killpg, real_kill = os.killpg, os.kill

    class Signals:
        def __init__(self):
            self.calls, self.raise_next, self.watched = [], None, None

        def reaped_number(self, root):
            self.watched = root

        def reaped(self, number):
            if number != self.watched:
                return False
            try:
                os.waitid(os.P_PID, number, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            except ChildProcessError:
                return True
            return False

        def had_process(self, number):
            try:
                real_killpg(number, 0)
            except ProcessLookupError:
                return False
            except PermissionError:
                pass
            return True

        def send(self, number, sig, real):
            if self.reaped(number):
                if sig != 0:
                    self.calls.append({"group": number, "signal": sig, "what": "withheld"})
                return None
            if sig != 0:
                if self.raise_next == number:
                    self.raise_next = None
                    self.calls.append({"group": number, "signal": sig, "what": "refused", "had_process": self.had_process(number)})
                    raise PermissionError(errno.EPERM, os.strerror(errno.EPERM))
                self.calls.append({"group": number, "signal": sig, "what": "sent", "had_process": self.had_process(number)})
            return real()

        def which(self, what):
            return [(c["group"], c["signal"]) for c in self.calls if c["what"] == what]

    signals = Signals()
    monkeypatch.setattr(os, "killpg", lambda pgid, sig: signals.send(pgid, sig, lambda: real_killpg(pgid, sig)))
    monkeypatch.setattr(os, "kill", lambda pid, sig: signals.send(-pid, sig, lambda: real_kill(pid, sig)) if pid < -1 else real_kill(pid, sig))
    return signals


@pytest.mark.skipif(WINDOWS or not hasattr(os, "waitid"), reason="H3 reads the POSIX process group, through os.waitid")
def test_a_kill_never_reaches_the_roots_number_after_the_root_is_reaped(rig, group_signals):
    """H3. The engine and its cli end on their own; probe() measures that; from then on, once the root has been reaped in this process, the
    root's number counts as another group's."""
    port = free_port()
    ws = rig.workspace("h3")
    life = rig.life(ws, port, Reports(), SENTENCE_H3, ready_s=START_S - 2, stop_s=5.0)
    got = value_of(within(life.start, "start()", START_S), "start()", SENTENCE_H3)
    assert got == "ready", f"start() returned {got!r} on a free port with a workspace that has main.py, and it returns 'ready'. {SENTENCE_H3}"
    root, pid = cli_runs(ws)[0]["pid"], main_pid(ws)
    (ws / "die").write_text("")
    assert until(lambda: not alive(root) and not (pid and alive(pid)) and refused(port), 15.0, every=0.2), (
        "Inconclusive, so this case fails: main.py and the fake cli had not ended 15 s after the die file; this case needs the whole tree gone "
        "on its own."
    )
    value_of(within(life.probe, "probe()", CONSTRUCT_S), "probe() after the tree ended on its own", SENTENCE_H3)
    group_signals.reaped_number(root)
    box = within(life.stop, "stop() after the tree ended on its own", STOP_S)
    if "raised" in box:
        e = box["raised"]
        assert isinstance(e, organ_error()), (
            f"stop() after the tree ended on its own raised {type(e).__name__}: {e}, and it returns 'stopped' or raises OrganError. "
            f"{SENTENCE_H3} {SENTENCE_H4}"
        )
    else:
        assert box.get("value") == "stopped", f"stop() after the tree ended on its own returned {box.get('value')!r}. {SENTENCE_H3}"
    withheld = group_signals.which("withheld")
    assert not withheld, (
        f"After its root (pid {root}) had been reaped, the lifecycle sent {withheld} (group, signal) to that number. Once the root is reaped "
        f"the system may give the number to another group, and that group takes the kill; probe() or stop() reaped the root before the kill. "
        f"{SENTENCE_H3} {HOW_REAP}"
    )


@pytest.mark.skipif(WINDOWS, reason="H4 reads the POSIX group kill")
def test_a_kill_the_system_refuses_is_an_organ_error_and_stop_can_try_again(rig, group_signals):
    """H4. The next kill sent to the root's group raises PermissionError(EPERM); a second stop() has every call pass through."""
    port = free_port()
    ws = rig.workspace("h4")
    life = rig.life(ws, port, Reports(), SENTENCE_H4, ready_s=START_S - 2, stop_s=5.0)
    got = value_of(within(life.start, "start()", START_S), "start()", SENTENCE_H4)
    assert got == "ready", f"start() returned {got!r} on a free port with a workspace that has main.py, and it returns 'ready'. {SENTENCE_H4}"
    root = cli_runs(ws)[0]["pid"]
    group_signals.raise_next = root
    box = within(life.stop, "stop() whose kill the system refuses", STOP_S)
    assert any(g == root for g, _ in group_signals.which("refused")), (
        f"Inconclusive, so this case fails: stop() sent no signal to process group {root} through os.killpg or os.kill, so none could be "
        f"refused. {SENTENCE_H8} {SENTENCE_H4}"
    )
    raised_organ_error(box, "stop() whose group kill the system refused with PermissionError", f"{SENTENCE_H4} {HOW_REFUSED}")
    again = value_of(within(life.stop, "a second stop()", STOP_S), "a second stop() after a refused kill", SENTENCE_H4)
    assert again == "stopped" and refused(port), (
        f"A second stop(), whose kill the system allows, returned {again!r} with port {port} {'closed' if refused(port) else 'still answering'}: "
        f"after a refused kill the tree stays this lifecycle's, so stop() can try again. {SENTENCE_H4} {HOW_REFUSED}"
    )


@pytest.mark.skipif(WINDOWS, reason="H7d reads an engine that outlives its host, which happens on POSIX; on Windows it ends with the host (I6)")
def test_an_instance_stays_in_use_while_its_engine_outlives_its_host(rig):
    """H7d. HOST_LEAVING starts an engine on the instance and exits without stop(); the engine keeps running, and so does the hold."""
    inst = (rig.root / "instances" / "h7d").resolve()
    pa, pb = two_ports()
    wa, wb = rig.workspace("h7d_host"), rig.workspace("h7d_here")
    host = rig.host(HOST_LEAVING, wa, pa, rig.cli, inst)
    got = host_out(rig, host)
    assert got.get("state") == "ready", f"Inconclusive, so this case fails: the host could not start its engine on the instance: {got}."
    host.wait(timeout=CHILD_S)
    cli, pid = cli_runs(wa)[0]["pid"], got["main_pid"]
    assert alive(pid) and not refused(pa), (
        f"Inconclusive, so this case fails: after its host exited, the engine (main.py, pid {pid}) {'runs' if alive(pid) else 'is gone'} and "
        f"port {pa} {'answers' if not refused(pa) else 'is closed'}; this case needs it running on its own."
    )
    reports = Reports()
    life = rig.life(wb, pb, reports, SENTENCE_H7, instance=inst, ready_s=START_S - 2)
    e = raised_organ_error(within(life.start, "start()", START_S), "start() on an instance whose engine outlived its host",
                           f"{SENTENCE_H7} {HOW_LOCK}")
    assert str(inst) in str(e), f"The OrganError reads {str(e)!r}, without the instance {inst}. {SENTENCE_H7}"
    assert reports.states[-1:] == ["unavailable"], f"After a start refused for its instance, report last saw {reports.states[-1:]}. {SENTENCE_H7}"
    assert not cli_runs(wb), f"The refused start ran the command: {cli_runs(wb)}. {SENTENCE_H7}"
    (wa / "die").write_text("")
    assert until(lambda: not alive(cli) and not alive(pid), 15.0, every=0.2), (
        "Inconclusive, so this case fails: the other host's cli and main.py had not exited 15 s after the die file."
    )
    again = value_of(within(life.start, "start()", START_S), "start() after the engine that held the instance ended", SENTENCE_H7)
    assert again == "ready", f"start() after the engine that held the instance ended returned {again!r}: the hold ends with comfy-cli. {SENTENCE_H7}"
    stopped = value_of(within(life.stop, "stop()", STOP_S), "stop()", SENTENCE_H7)
    assert stopped == "stopped", f"stop() returned {stopped!r}. {SENTENCE_H7}"
