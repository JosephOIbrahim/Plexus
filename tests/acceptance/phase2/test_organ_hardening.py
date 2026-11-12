"""Hardening · CozyLifecycle closes what the alpha.10 review left open: CONTRACT's M3.2 lines.

M3.2 closes the gaps the alpha.10 review listed. On Windows the process start() runs is in its job before it runs an instruction of its own,
so nothing the root starts is ever outside the tree, and a root no job can hold is killed before it has run. On POSIX the root's process group
is signalled only while the root is not yet reaped, so its number is still this tree's, and a kill the system refuses is an OrganError that
leaves the tree this lifecycle's. Beside an instance the constructor also refuses every start of the four folder flags that ComfyUI's parser
reads as the flag, and an instance in the workspace's temp folder however it is spelt; and start() refuses an instance another lifecycle holds,
in this process or another, until that lifecycle's tree has ended.

Nothing here runs the real comfy-cli or ComfyUI, touches port 8188 or leaves this machine. FAKE_CLI and FAKE_MAIN are test_organ_isolation.py's,
written through its Rig with no new mode, as are alive(), main_pid(), untouched() and its 8188 guard, which this file imports so that it applies
to every case here; the timing helpers are test_organ_lifecycle.py's. Constructor cases measure a port where test_organ_malformed.py's Engine
answers, so a lifecycle built where it should have been refused costs milliseconds, not the second a closed port costs on Windows, and reports
the one measurement 'ready'.

Three levers reach what no outside observer can force:
- HOST_HELD, a child interpreter on Windows, installs an audit hook (sys.addaudithook) before it imports plexus. The hook arms at the
  subprocess.Popen event. At each later ctypes call it finds the root, the host's child running this interpreter, and reads every thread's
  suspend count (ThreadSuspendCount): while all are suspended it returns at once; once the root can run, it pauses the host until main.py has
  written main_pid, then disarms. A root kept suspended until its job holds it costs nothing; a root that runs before the hold starts main.py
  outside the job. In mode ceiling the host first nests itself in jobs until Windows refuses one more, so no job can hold the root; in mode
  raise the hook raises OSError at the first such call instead, so that call never runs. A case whose hook never armed, saw no ctypes call
  after the spawn, found no root, could not read a count, or paused without main.py starting fails as inconclusive: it never passes by not
  looking.
- On POSIX the group_signals fixture wraps os.killpg and os.kill. It records each signal, can refuse the next one with PermissionError, and,
  once the root has been reaped in this process (os.waitid with WNOWAIT finds no such child), answers signal 0 to the root's number as a group
  that took the number would, and withholds any other signal to it.
- HOST_HOLDING (Windows) and HOST_LEAVING (POSIX) start a lifecycle on an instance in another process: the first waits until the test kills
  it, the second exits without stop() and leaves its engine running.

Every child host has a guard of its own against port 8188. Teardown writes `die` into every workspace, stops every lifecycle, kills every host
and every fake of this case still running, closes every engine, and removes every link with os.rmdir or os.unlink, never through it.

What this file pins: the eight M3.2 lines of CONTRACT under plexus.organs, H1 to H8 in their order there; H8 discloses the levers above and no
case reads it. H1a, H2a, H2b, H6c and H7c run only on Windows, and H3, H4 and H7d only on POSIX, where the lines they read apply. Left open on
purpose: the words of every message past the path, port or instance it names; how the root is kept from running and how the tree is held;
where and how start() marks that it holds an instance; whether a start refused for its instance reports 'starting' first; a host that dies in
the moment between Popen's return and the hold, which leaves an inert, suspended root (a stated limit); ComfyUI's own comfyui.db.lock; and
--port, --listen and argument expansion in extra, which wait for a later mission.
"""

from __future__ import annotations

import errno
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.acceptance._support import PY, child_env
from tests.acceptance.phase2.test_organ_isolation import Rig as IsolationRig
from tests.acceptance.phase2.test_organ_isolation import (  # noqa: F401 - the autouse 8188 guard applies once imported
    SENTENCE_I6,
    alive,
    main_pid,
    nothing_reaches_the_real_comfy,
    untouched,
)
from tests.acceptance.phase2.test_organ_lifecycle import (
    CHILD_S,
    CONSTRUCT_S,
    FORBIDDEN_PORT,
    POLL_S,
    START_S,
    STOP_S,
    Reports,
    cli_runs,
    engine_port,
    free_port,
    lifecycle_class,
    organ_error,
    raised_organ_error,
    refused,
    until,
    value_of,
    within,
)
from tests.acceptance.phase2.test_organ_malformed import Engine

WINDOWS = sys.platform == "win32"
HOOK_PAUSE_S = 15.0  # HOST_HELD's hook waits this long for main.py once the root can run
GONE_S = 15.0  # an engine ends within this after its host, as IS8 waits
_KILL = os.kill  # teardown kills with the real call even while a case wraps os.kill

SENTENCE_H1 = (
    "CONTRACT H1: on Windows start() creates comfy-cli's process suspended and lets it run only once the job holds it, so nothing the root "
    "starts is ever outside the tree, however long the host takes between the spawn and the hold."
)
SENTENCE_H2 = (
    "CONTRACT H2: when start() cannot hold the tree, because the job cannot be made, the process cannot be put in it or let run, or anything "
    "raises between the spawn and the hold, it kills that process before it has run anything, reports 'unavailable' and raises OrganError; an "
    "interrupt such as KeyboardInterrupt is raised again as itself after the same kill and report. So nothing the root would have started runs, "
    "and nothing of the tree is left."
)
SENTENCE_H3 = (
    "CONTRACT H3: on POSIX the lifecycle signals the root's process group only while the root is not yet reaped, so the group's number is still "
    "this tree's: it learns that the root has exited without reaping it, reaps it only after the kill, and sends nothing to that number once the "
    "root has been reaped, so a kill never reaches a group that took the number after the tree ended."
)
SENTENCE_H4 = (
    "CONTRACT H4: a kill the system refuses is a kill that fails: a PermissionError, or any other OSError but ProcessLookupError, from the POSIX "
    "group kill leaves start() and stop() as OrganError and nothing else, and the tree stays this lifecycle's, so stop() can try again."
)
SENTENCE_H5 = (
    "CONTRACT H5: when instance is given, the constructor's ValueError also covers any item of extra whose name, the part before any '=', is "
    "'--' followed by at least one character and is the start of --user-directory, --database-url, --temp-directory or --output-directory, such "
    "as --user-dir, --da, --te=<folder>, --ou or --t, because ComfyUI's parser reads an unambiguous start of a flag as that flag and its last "
    "value wins over the instance's; every other item still passes, and without instance extra passes as before."
)
SENTENCE_H6 = (
    "CONTRACT H6: when instance is given, the constructor also raises ValueError before it measures or reports when instance is "
    "<workspace>/temp or a folder inside it, which a ComfyUI started from the workspace with its default temp folder deletes when it starts and "
    "again when it exits. This check and the workspace-itself check compare folders, not spellings: a '..', a link or junction, the \\\\?\\ "
    "prefix, a trailing space Windows drops and, on Windows, another case all name the same folder, while a sibling such as <workspace>/temp2 "
    "or another folder in the workspace is accepted."
)
SENTENCE_H7 = (
    "CONTRACT H7: start() holds its instance folder from before it spawns until its tree has ended: killed by stop() or by a start that fails, "
    "or, once its host is gone, with the host on Windows and with comfy-cli on POSIX. A start() whose instance another lifecycle holds, in this "
    "process or another, reports 'unavailable' and raises OrganError naming the instance, spawning nothing; a start that leaves no tree lets the "
    "folder go, and a lifecycle's own further start(), or its start() after its own stop(), is never refused."
)
SENTENCE_H8 = (
    "CONTRACT H8: on Windows the frozen tests may run a child host whose audit hook (sys.addaudithook) pauses it at a ctypes call made after "
    "subprocess.Popen has spawned the root while the root can run, until main.py has started, or makes the first such call raise, and a host "
    "already held in as many nested jobs as Windows allows; on POSIX they may wrap os.killpg and os.kill to record, refuse or withhold a signal. "
    "So on Windows start() spawns the root through subprocess.Popen and holds it through ctypes, and on POSIX it signals a group through "
    "os.killpg or os.kill, each looked up when it runs."
)
HOW_HOLD = (
    "On Windows, spawn the root through subprocess.Popen with CREATE_SUSPENDED added to its creation flags, put it in the kill-on-close job "
    "through ctypes, and only then let it run (NtResumeProcess through ctypes), checking the NTSTATUS it returns."
)
HOW_KILL = (
    "When the job cannot be made, the root cannot be put in it or resumed, or anything raises from Popen's return to a successful resume, kill "
    "the root through Popen's own handle while it is still suspended (proc.kill(), then proc.wait()), then close the job if one was made, report "
    "'unavailable' and raise OrganError from the cause; keep the process and the job only once the resume has succeeded."
)
HOW_REAP = (
    "Learn that the root has exited without reaping it (os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)), signal the group only "
    "while the root is not yet reaped, and reap it only after the kill. A killpg(pgid, 0) that succeeds proves nothing: a group that took the "
    "number answers it too."
)
HOW_REFUSED = (
    "Catch ProcessLookupError first, so a tree that ended on its own still stops, and turn any other OSError from the group kill into "
    "OrganError, keeping the process, so a later stop() can kill it."
)
HOW_TEMP = (
    "Compare folders: drop a leading \\\\?\\ or \\\\?\\UNC\\ on Windows, then resolve(). An instance equal to or below the resolved "
    "<workspace>/temp is refused; when that folder exists, os.path.samefile over the resolved instance and each of its existing parents "
    "refuses the rest. The workspace-itself check is equality or samefile."
)
HOW_LOCK = (
    "Open <instance>/.plexus-instance.lock as a bare descriptor and take a non-blocking lock on it: msvcrt.locking(fd, msvcrt.LK_NBLCK, 1) on "
    "Windows, fcntl.flock(fd, LOCK_EX | LOCK_NB) on POSIX, never lockf, which does not conflict inside one process. Take it after 'starting' is "
    "reported and before any folder is made or anything spawned, let it go with the job and on every start that leaves no tree, and on POSIX "
    "pass the descriptor to comfy-cli with pass_fds, so it stays held while the engine outlives its host."
)

# ComfyUI's option strings, read with ast from G:/COMFY/ComfyUI/comfy/cli_args.py as of Nov 11 (never imported): 105, built with
# argparse.ArgumentParser(), so abbreviations are on and the last value wins. Each of the four folder flags is read from its shortest
# unambiguous start up: --user (--use is ambiguous with the six --use-* flags), --da, --te and --ou. No ComfyUI flag is a start of the four.
SHORTEST = {"--user-directory": "--user", "--database-url": "--da", "--temp-directory": "--te", "--output-directory": "--ou"}
AMBIGUOUS = ("--u", "--us", "--use", "--d", "--t", "--o")
EMPTY_VALUES = ("--temp=", "--te=", "--output=")
OTHER_FLAGS = (
    "--listen", "--port", "--tls-keyfile", "--tls-certfile", "--enable-cors-header", "--max-upload-size", "--base-directory",
    "--extra-model-paths-config", "--input-directory", "--auto-launch", "--disable-auto-launch", "--cuda-device", "--default-device",
    "--cuda-malloc", "--disable-cuda-malloc", "--force-fp32", "--force-fp16", "--fp32-unet", "--fp64-unet", "--bf16-unet", "--fp16-unet",
    "--fp8_e4m3fn-unet", "--fp8_e5m2-unet", "--fp8_e8m0fnu-unet", "--fp16-vae", "--fp32-vae", "--bf16-vae", "--cpu-vae",
    "--fp8_e4m3fn-text-enc", "--fp8_e5m2-text-enc", "--fp16-text-enc", "--fp32-text-enc", "--bf16-text-enc", "--fp16-intermediates",
    "--force-channels-last", "--directml", "--oneapi-device-selector", "--supports-fp8-compute", "--enable-triton-backend",
    "--disable-triton-backend", "--preview-method", "--preview-size", "--cache-ram", "--cache-classic", "--cache-lru", "--cache-none",
    "--high-ram", "--use-split-cross-attention", "--use-quad-cross-attention", "--use-pytorch-cross-attention", "--use-sage-attention",
    "--use-flash-attention", "--use-ck-attention", "--disable-xformers", "--force-upcast-attention", "--dont-upcast-attention",
    "--enable-manager", "--disable-manager-ui", "--enable-manager-legacy-ui", "--gpu-only", "--highvram", "--lowvram", "--novram", "--cpu",
    "--reserve-vram", "--vram-headroom", "--disable-nvml-pressure", "--async-offload", "--disable-async-offload", "--disable-dynamic-vram",
    "--enable-dynamic-vram", "--fast-disk", "--disable-cuda-graphs", "--force-non-blocking", "--default-hashing-function",
    "--disable-smart-memory", "--deterministic", "--fast", "--debug-hang", "--disable-pinned-memory", "--mmap-torch-files",
    "--disable-mmap", "--dont-print-server", "--quick-test-for-ci", "--windows-standalone-build", "--disable-metadata",
    "--disable-all-custom-nodes", "--whitelist-custom-nodes", "--disable-api-nodes", "--multi-user", "--verbose", "--log-stdout",
    "--front-end-version", "--front-end-root", "--models-directory", "--enable-compress-response-body", "--comfy-api-base",
    "--enable-assets", "--enable-asset-hashing", "--feature-flag", "--list-feature-flags",
)
H5A_GROUPS = (*SHORTEST, "ambiguous", "empty-values")


def h5a_forms(group, elsewhere):
    """The extra lists H5a refuses beside an instance, for one group: each start of a flag from its shortest to one character short of the
    full name (IS2 pins the full name), or each ambiguous start, alone with a value after it and as name=value; or the empty-value forms."""
    if group == "empty-values":
        return [[form] for form in EMPTY_VALUES]
    names = AMBIGUOUS if group == "ambiguous" else [group[:n] for n in range(len(SHORTEST[group]), len(group))]
    return [form for name in names for form in ([name, elsewhere], [f"{name}={elsewhere}"])]


# A guard of every child host's own: no socket in it may connect to port 8188.
CHILD_GUARD = r'''
import socket as _socket
TOUCHED = [False]
def _guarded(connect):
    def guarded(self, address):
        if isinstance(address, tuple) and len(address) >= 2 and address[1] == FORBIDDEN_PORT:
            TOUCHED[0] = True
            raise AssertionError("this host connected to port FORBIDDEN_PORT, another session's ComfyUI")
        return connect(self, address)
    return guarded
_socket.socket.connect = _guarded(_socket.socket.connect)
_socket.socket.connect_ex = _guarded(_socket.socket.connect_ex)
'''.replace("FORBIDDEN_PORT", str(FORBIDDEN_PORT))

# Windows. argv: workspace, port, fake cli, mode (pause, ceiling or raise). Prints one OUT line; in modes ceiling and raise it then waits on stdin.
HOST_HELD = CHILD_GUARD + r'''
import ctypes, json, os, sys, time
from ctypes import wintypes
from pathlib import Path
ws, port, cli, mode = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4]
HANDLE = wintypes.HANDLE
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
nt = ctypes.WinDLL("ntdll")
k32.CreateToolhelp32Snapshot.restype, k32.CreateToolhelp32Snapshot.argtypes = HANDLE, (wintypes.DWORD, wintypes.DWORD)
k32.OpenProcess.restype, k32.OpenProcess.argtypes = HANDLE, (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
k32.CloseHandle.argtypes = (HANDLE,)
k32.CreateJobObjectW.restype, k32.CreateJobObjectW.argtypes = HANDLE, (wintypes.LPVOID, wintypes.LPCWSTR)
k32.SetInformationJobObject.argtypes = (HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD)
k32.AssignProcessToJobObject.argtypes = (HANDLE, HANDLE)
k32.GetCurrentProcess.restype = HANDLE
nt.NtGetNextThread.restype = ctypes.c_long
nt.NtGetNextThread.argtypes = (HANDLE, HANDLE, wintypes.DWORD, wintypes.ULONG, wintypes.ULONG, ctypes.POINTER(HANDLE))
nt.NtQueryInformationThread.restype = ctypes.c_long
nt.NtQueryInformationThread.argtypes = (HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.ULONG, ctypes.POINTER(wintypes.ULONG))


class Entry(ctypes.Structure):  # PROCESSENTRY32W
    _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t),
                ("module", wintypes.DWORD), ("threads", wintypes.DWORD), ("ppid", wintypes.DWORD), ("priority", ctypes.c_long),
                ("flags", wintypes.DWORD), ("exe", ctypes.c_wchar * 260)]


class Limits(ctypes.Structure):  # JOBOBJECT_EXTENDED_LIMIT_INFORMATION; only flags is set
    _fields_ = [("user_time", ctypes.c_int64 * 2), ("flags", wintypes.DWORD), ("working_set", ctypes.c_size_t * 2),
                ("process_limit", wintypes.DWORD), ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD), ("io", ctypes.c_uint64 * 6), ("memory", ctypes.c_size_t * 4)]


k32.Process32FirstW.argtypes = k32.Process32NextW.argtypes = (HANDLE, ctypes.POINTER(Entry))
EXE, ME = os.path.basename(sys.executable).lower(), os.getpid()
NO_SNAPSHOT = ctypes.c_void_p(-1).value  # INVALID_HANDLE_VALUE


def python_children():
    """This host's children that run this interpreter, from a Toolhelp process snapshot."""
    snap = k32.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
    if not snap or snap == NO_SNAPSHOT:
        return []
    found = []
    try:
        entry = Entry()
        entry.size = ctypes.sizeof(entry)
        more = k32.Process32FirstW(snap, ctypes.byref(entry))
        while more:
            if entry.ppid == ME and entry.exe.lower() == EXE:
                found.append(entry.pid)
            more = k32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snap)
    return found


def suspended(pid):
    """True when every thread of pid has a suspend count above zero, False when one has none, None when a count cannot be read."""
    process = k32.OpenProcess(0x0400, False, pid)  # PROCESS_QUERY_INFORMATION
    if not process:
        return None
    thread, counts = None, []
    try:
        while True:
            following = HANDLE()
            status = nt.NtGetNextThread(process, thread, 0x0800, 0, 0, ctypes.byref(following))  # THREAD_QUERY_LIMITED_INFORMATION
            if thread:
                k32.CloseHandle(thread)
            thread = following if status == 0 else None
            if status != 0:
                if status & 0xFFFFFFFF != 0x8000001A:  # STATUS_NO_MORE_ENTRIES ends the walk; any other status leaves a count unread
                    return None
                break
            count = wintypes.ULONG()
            if nt.NtQueryInformationThread(thread, 35, ctypes.byref(count), 4, None) != 0:  # ThreadSuspendCount
                return None
            counts.append(count.value)
    finally:
        if thread:
            k32.CloseHandle(thread)
        k32.CloseHandle(process)
    return all(counts) if counts else None


STALE = set(python_children())  # children that ran before the lifecycle's own
HOOK = {"armed": False, "done": False, "busy": False, "calls": 0, "skips": 0, "root": None, "unreadable": False,
        "paused_s": None, "main_during_pause": None, "raised_at_call": False}


def hook(event, args):
    if HOOK["done"] or HOOK["busy"]:
        return
    if event == "subprocess.Popen":
        HOOK["armed"] = True
        return
    if event != "ctypes.call_function" or not HOOK["armed"]:
        return
    HOOK["busy"] = True  # the hook's own ctypes calls come back here and return at once
    try:
        HOOK["calls"] += 1
        kids = python_children()
        if HOOK["root"] is None:
            fresh = [pid for pid in kids if pid not in STALE]
            if not fresh:
                HOOK["done"] = True  # no root to judge: the case is inconclusive
                return
            HOOK["root"] = fresh[0]
        elif HOOK["root"] not in kids:
            HOOK["done"] = True  # the root is gone: nothing more to judge
            return
        if mode == "raise":
            HOOK["raised_at_call"] = HOOK["done"] = True
            raise OSError(5, "raised by the test's audit hook at the first ctypes call after the spawn, before that call ran")
        held = suspended(HOOK["root"])
        if held is None:
            HOOK["unreadable"] = HOOK["done"] = True
            return
        if held:
            HOOK["skips"] += 1  # nothing can run while every thread is suspended
            return
        began, marker = time.monotonic(), ws / "main_pid"
        while not marker.exists() and time.monotonic() - began < HOOK_PAUSE_S:
            time.sleep(0.02)
        HOOK["paused_s"] = round(time.monotonic() - began, 3)
        HOOK["main_during_pause"] = marker.exists()
        HOOK["done"] = True
    finally:
        HOOK["busy"] = False


JOBS, out = [], {"mode": mode, "levels": 0, "refused_with": None}


def nest(kill_on_close):
    """Put this host in one more job, kept open until it ends; returns False when Windows refuses."""
    job = k32.CreateJobObjectW(None, None)
    if job and kill_on_close:
        limits = Limits()
        limits.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: whatever this host leaves ends with it
        k32.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits))
    if job and k32.AssignProcessToJobObject(job, k32.GetCurrentProcess()):
        JOBS.append(job)
        return True
    out["refused_with"] = ctypes.get_last_error()
    if job:
        k32.CloseHandle(job)
    return False


if mode == "ceiling":
    while len(JOBS) < 1000 and nest(kill_on_close=not JOBS):
        pass
elif mode == "raise":
    nest(kill_on_close=True)
out["levels"] = len(JOBS)
sys.addaudithook(hook)
out["states"] = states = []
try:
    from plexus.organs.cozy import CozyLifecycle
    from plexus.organs.protocol import OrganError
    life = CozyLifecycle(ws, port, command=[sys.executable, cli], report=states.append, ready_s=18.0, poll_s=0.25)
    try:
        try:
            out["value"] = life.start()
        finally:
            HOOK["done"] = True  # disarmed before anything else runs
    except BaseException as e:
        out["raised"] = type(e).__name__ + ": " + " ".join(str(e).split())[:400]
        out["organ_error"] = isinstance(e, OrganError)
except BaseException as e:
    HOOK["done"] = True
    out["host_raised"] = type(e).__name__ + ": " + " ".join(str(e).split())[:400]
out["hook"] = {k: v for k, v in HOOK.items() if k != "busy"}
out["touched_8188"] = TOUCHED[0]
marker = ws / "main_pid"
text = marker.read_text() if marker.exists() else ""
out["main_pid"] = int(text) if text.strip() else None
print("OUT " + json.dumps(out), flush=True)
if mode != "pause":
    sys.stdin.readline()
os._exit(0)
'''.replace("HOOK_PAUSE_S", repr(HOOK_PAUSE_S))

# argv: workspace, port, fake cli, instance. Starts a lifecycle on the instance and prints one OUT line, or RAISED.
_HOST_ON_INSTANCE = CHILD_GUARD + r'''
import json, os, sys
from pathlib import Path
ws, port, cli, inst = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
try:
    from plexus.organs.cozy import CozyLifecycle
    life = CozyLifecycle(ws, port, command=[sys.executable, cli], report=lambda s: None, instance=inst, ready_s=18.0, poll_s=0.25)
    state = life.start()
    print("OUT " + json.dumps({"state": state, "main_pid": int((ws / "main_pid").read_text())}), flush=True)
except BaseException as e:
    print("RAISED " + type(e).__name__ + ": " + " ".join(str(e).split())[:400], flush=True)
'''
HOST_HOLDING = _HOST_ON_INSTANCE + "sys.stdin.readline()\nos._exit(0)\n"  # Windows: waits until the test kills it
HOST_LEAVING = _HOST_ON_INSTANCE + "os._exit(0)\n"  # POSIX: exits without stop() and leaves its engine running


def _filetime_now():
    """Now as a Windows FILETIME: 100 ns since 1601."""
    return int((time.time() + 11644473600) * 10**7)


def _pids_in(ws):
    pids = []
    try:
        pids += [r.get("pid") for r in cli_runs(ws)]
    except (OSError, ValueError):
        pass
    try:
        pids.append(main_pid(ws))
    except (OSError, ValueError):
        pass
    return pids


def _end_leftover(pid, rig):
    """Kill pid if it still runs and is this case's: on Windows this interpreter's image, created after the case began; on POSIX a process
    whose working folder or command line lies under the case's folder. Anything else is left alone, so a reused pid is never killed."""
    if not pid or not alive(pid):
        return
    if WINDOWS:
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k32.GetProcessTimes.argtypes = (wintypes.HANDLE, *[ctypes.POINTER(ctypes.c_uint64)] * 4)
        k32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
        k32.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
        k32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = k32.OpenProcess(0x1000 | 0x0001 | 0x00100000, False, pid)  # QUERY_LIMITED_INFORMATION | TERMINATE | SYNCHRONIZE
        if not handle:
            return
        try:
            times = [ctypes.c_uint64() for _ in range(4)]
            name, size = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
            ours = (k32.GetProcessTimes(handle, *map(ctypes.byref, times)) and times[0].value >= rig.began
                    and k32.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size))
                    and os.path.basename(name.value).lower() == os.path.basename(PY).lower())
            if ours:
                k32.TerminateProcess(handle, 1)
                k32.WaitForSingleObject(handle, 5000)
        finally:
            k32.CloseHandle(handle)
        return
    try:
        cwd = os.readlink(f"/proc/{pid}/cwd")
        line = Path(f"/proc/{pid}/cmdline").read_bytes().decode("utf-8", "replace")
    except OSError:
        return
    if any(str(r) in cwd or str(r) in line for r in {rig.root, rig.root.resolve()}):
        try:
            _KILL(pid, signal.SIGKILL)
        except OSError:
            pass


class Rig(IsolationRig):
    """test_organ_isolation.py's Rig, plus in-test engines, child hosts and links, all ended at teardown."""

    def __init__(self, tmp_path):
        super().__init__(tmp_path)
        self.engines, self.hosts, self.links, self.pids = [], [], [], []
        self.began = _filetime_now() - 2 * 10**7 if WINDOWS else None

    def engine(self):
        """test_organ_malformed.py's Engine on a port of its own; it answers /system_stats as ComfyUI does."""
        e = Engine()
        self.engines.append(e)
        return e

    def life(self, ws, port, report, why, **kw):
        """CozyLifecycle(ws, port, command=FAKE_CLI's command, report=report, poll_s=POLL_S, **kw) under CONSTRUCT_S; it has to build."""
        cls = lifecycle_class()
        assert port != FORBIDDEN_PORT
        kw.setdefault("poll_s", POLL_S)
        box = within(lambda: cls(ws, port, command=self.command, report=report, **kw), "CozyLifecycle(...)", CONSTRUCT_S)
        if "raised" in box:
            e = box["raised"]
            raise AssertionError(f"CozyLifecycle({ws.name}, {port}, {', '.join(f'{k}=...' for k in kw)}) raised {type(e).__name__}: {e}. {why}")
        self.lifes.append(box["value"])
        return box["value"]

    def host(self, script, *args):
        """A child interpreter running script with child_env(): stdin and stdout are pipes, stderr goes to a file."""
        err = self.root / f"host_{len(self.hosts)}.err"
        with open(err, "w", encoding="utf-8") as f:
            p = subprocess.Popen([PY, "-c", script, *map(str, args)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=f, text=True,
                                 errors="replace", env=child_env())
        self.hosts.append(p)
        return p

    def link(self, target, name="wslink"):
        """<root>/name pointing at target: a junction on Windows, which needs no admin, a symlink on POSIX."""
        path = self.root / name
        if WINDOWS:
            import _winapi

            _winapi.CreateJunction(str(target), str(path))
        else:
            os.symlink(target, path, target_is_directory=True)
        self.links.append(path)
        return path

    def close(self):
        super().close()  # `die` into every workspace, then stop() on every lifecycle
        for p in self.hosts:
            if p.poll() is None:
                p.kill()
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            for f in (p.stdin, p.stdout):
                try:
                    f.close()
                except (OSError, ValueError):
                    pass
        for e in self.engines:
            e.close()
        left = {pid for ws in self.spaces for pid in _pids_in(ws)} | set(self.pids)
        left.discard(None)
        until(lambda: not any(alive(pid) for pid in left), 5.0, every=0.1)
        for pid in left:
            _end_leftover(pid, self)
        for path in self.links:
            try:
                (os.rmdir if WINDOWS else os.unlink)(path)  # the link itself, never what it points at
            except OSError:
                pass


@pytest.fixture
def rig(tmp_path):
    r = Rig(tmp_path)
    yield r
    r.close()


def two_ports():
    a = free_port()
    b = free_port()
    while b == a:
        b = free_port()
    return a, b


def build(rig, workspace, port, **kw):
    """CozyLifecycle(workspace, port, ...) under CONSTRUCT_S: (box, reports). A lifecycle that was built is stopped at teardown."""
    assert port != FORBIDDEN_PORT
    reports = Reports()
    cls = lifecycle_class()
    box = within(lambda: cls(workspace, port, command=rig.command, report=reports, poll_s=POLL_S, **kw), "CozyLifecycle(...)", CONSTRUCT_S)
    if "value" in box:
        rig.lifes.append(box["value"])
    return box, reports


def outcome(box):
    if "raised" in box:
        return f"raised {type(box['raised']).__name__}: {box['raised']}"
    return "was built"


def shown(rig, extra):
    """extra as a message shows it, with the case's folder written <root>."""
    return [str(x).replace(str(rig.root), "<root>") for x in extra]


def host_out(rig, host):
    """The host's OUT line as a dict, or {'host_raised': ...} from its RAISED line or its silence, read under CHILD_S."""
    def read():
        for line in host.stdout:
            if line.startswith("OUT "):
                return json.loads(line[4:])
            if line.startswith("RAISED "):
                return {"host_raised": line[7:].strip()}
        return {"host_raised": "the host ended without its line"}

    box = within(read, "the host", CHILD_S, must_return=False)
    err = (rig.root / f"host_{rig.hosts.index(host)}.err").read_text(encoding="utf-8", errors="replace")
    if "value" not in box:
        why = f"raised {type(box['raised']).__name__}: {box['raised']}" if "raised" in box else f"had not written its line after {CHILD_S:g} s"
        raise AssertionError(f"The host {why}. Its stderr ends: {err[-600:]}")
    got = box["value"]
    if "host_raised" in got and err.strip():
        got["host_raised"] += f". Its stderr ends: {err[-600:]}"
    return got


def release(host):
    """Let a host that waits on stdin end, and wait for it; teardown kills one that does not."""
    try:
        host.stdin.write("\n")
        host.stdin.flush()
    except (OSError, ValueError):
        pass
    try:
        host.wait(timeout=CHILD_S)
    except subprocess.TimeoutExpired:
        pass


def said(got):
    """What start() did in a host, in words."""
    return f"raised {got['raised']}" if "raised" in got else f"returned {got.get('value')!r}"


def held_premises(got, why, ceiling=False):
    """Fails, never passes, when HOST_HELD could not see the moment between the spawn and the hold, or, at the ceiling, was not there."""
    assert not got.get("touched_8188"), f"The host connected to port {FORBIDDEN_PORT}, another session's ComfyUI. Use the port given."
    assert "host_raised" not in got, f"The host could not build its lifecycle: {got['host_raised']}. {why}"
    if ceiling:
        assert got["levels"] > 0 and got["refused_with"], (
            f"Inconclusive, so this case fails: the host nested itself in {got['levels']} jobs and Windows "
            f"{'refused one more with error ' + str(got['refused_with']) if got['refused_with'] else 'never refused one more'}; this case "
            f"needs at least one level and then a refusal, so that no job can hold the root. {why}"
        )
    hook = got["hook"]
    missing = []
    if not hook["armed"]:
        missing.append("the audit hook never armed, so start() did not spawn the root through subprocess.Popen")
    elif not hook["calls"]:
        missing.append("the hook saw no ctypes call after subprocess.Popen had spawned the root, so it never looked at the root")
    elif hook["root"] is None:
        missing.append(f"at the first ctypes call after the spawn the hook found no child of the host running {os.path.basename(PY)}")
    if hook["unreadable"]:
        missing.append("a suspend count of the root's threads could not be read (ThreadSuspendCount needs Windows 8.1 or later)")
    if hook["paused_s"] is not None and not hook["main_during_pause"]:
        missing.append(f"the hook paused the host {hook['paused_s']:g} s for a root that could run, and main.py never wrote main_pid")
    assert not missing, (
        f"Inconclusive, so this case fails: {'; '.join(missing)}. The case sees the moment between the spawn and the hold only through that "
        f"hook. {SENTENCE_H8} {why}"
    )


def ran_in(ws):
    """The files that show the command ran in ws: the fake cli's record and main.py's pid."""
    return [name for name in ("cli_seen.jsonl", "main_pid") if (ws / name).exists()]


# ---------- H1 and H2: on Windows the root is held before it runs ----------


@pytest.mark.skipif(not WINDOWS, reason="H1 reads the moment between Popen's return and the job's hold, which is Windows'")
def test_a_process_the_root_starts_at_once_ends_with_its_host(rig):
    """H1a. HOST_HELD, mode pause, in no job of its own, starts the engine with its hook on and exits without stop()."""
    port = free_port()
    ws = rig.workspace("h1a")
    host = rig.host(HOST_HELD, ws, port, rig.cli, "pause")
    got = host_out(rig, host)
    try:
        host.wait(timeout=CHILD_S)
    except subprocess.TimeoutExpired:
        raise AssertionError(f"The host had not exited {CHILD_S:g} s after its line; it exits without stop().") from None
    if got.get("hook", {}).get("root"):
        rig.pids.append(got["hook"]["root"])
    held_premises(got, SENTENCE_H1)
    assert got.get("value") == "ready", (
        f"In the host, start() {said(got)}, and on a free port with a workspace that has main.py it returns 'ready'. {SENTENCE_H1} {HOW_HOLD}"
    )
    pid = got.get("main_pid")
    gone = until(lambda: refused(port) and not (pid and alive(pid)), GONE_S, every=0.25)
    paused = got["hook"]["paused_s"]
    assert gone, (
        f"The host exited {GONE_S:g} s ago without stop(), and main.py (pid {pid}) {'still runs' if pid and alive(pid) else 'is gone'} and port "
        f"{port} {'is closed' if refused(port) else 'still answers'}. "
        + (f"The hook paused the host {paused:g} s at the first ctypes call that found the root able to run, and main.py started during that "
           f"pause, before the job held the root, so it is outside the tree. " if paused is not None else "")
        + f"{SENTENCE_H1} {SENTENCE_I6} {HOW_HOLD}"
    )


@pytest.mark.skipif(not WINDOWS, reason="H2a reads a root that no job can hold, which is Windows'")
def test_a_tree_no_job_can_hold_is_killed_before_it_runs(rig):
    """H2a. HOST_HELD, mode ceiling, sits at Windows' job nesting limit, so no job can hold the root; its hook pauses the host at the first
    ctypes call that finds the root able to run. Its first job kills on close, so whatever the host leaves ends with it."""
    port = free_port()
    ws = rig.workspace("h2a")
    host = rig.host(HOST_HELD, ws, port, rig.cli, "ceiling")
    got = host_out(rig, host)
    try:
        if got.get("hook", {}).get("root"):
            rig.pids.append(got["hook"]["root"])
        held_premises(got, SENTENCE_H2, ceiling=True)
        root = got["hook"]["root"]
        assert got.get("organ_error"), (
            f"No job can hold the root here, and start() {said(got)}; it raises OrganError, because a tree it cannot hold would outlive its "
            f"host. {SENTENCE_H2} {HOW_KILL}"
        )
        assert got["states"][-1:] == ["unavailable"], (
            f"After a start whose tree no job could hold, report last saw {got['states'][-1:]}. {SENTENCE_H2}"
        )
        assert not alive(root), (
            f"start() raised, and comfy-cli's process (pid {root}) still runs: a root no job holds is killed before it has run. {SENTENCE_H2} {HOW_KILL}"
        )
        ran = ran_in(ws)
        assert not ran, (
            f"start() raised, and the command had run: {' and '.join(ran)} exist in the workspace. The root ran before the lifecycle knew no job "
            f"could hold it, and what it started then is outside any job of the lifecycle's, so killing the root alone leaves it running. "
            f"{SENTENCE_H2} {SENTENCE_H1} {HOW_HOLD} {HOW_KILL}"
        )
        assert refused(port), f"start() raised, and port {port} answers: something the root started holds it. {SENTENCE_H2}"
    finally:
        release(host)


@pytest.mark.skipif(not WINDOWS, reason="H2b reads the moment between Popen's return and the job's hold, which is Windows'")
def test_an_error_between_the_spawn_and_the_hold_kills_the_root(rig):
    """H2b. HOST_HELD, mode raise, in a kill-on-close job of its own: its hook raises OSError at the first ctypes call after the spawn, so
    that call never runs."""
    port = free_port()
    ws = rig.workspace("h2b")
    host = rig.host(HOST_HELD, ws, port, rig.cli, "raise")
    got = host_out(rig, host)
    try:
        if got.get("hook", {}).get("root"):
            rig.pids.append(got["hook"]["root"])
        held_premises(got, SENTENCE_H2)
        root = got["hook"]["root"]
        assert got.get("organ_error"), (
            f"The first ctypes call after the spawn raised OSError, and start() {said(got)}; it raises OrganError from it, so a host that "
            f"catches OrganError never meets an error a ctypes call or an audit hook raised. {SENTENCE_H2} {HOW_KILL}"
        )
        assert got["states"][-1:] == ["unavailable"], (
            f"After a start that raised between the spawn and the hold, report last saw {got['states'][-1:]}. {SENTENCE_H2}"
        )
        assert not alive(root), (
            f"start() raised, and comfy-cli's process (pid {root}) still runs outside any job of the lifecycle's. {SENTENCE_H2} {HOW_KILL}"
        )
        ran = ran_in(ws)
        assert not ran, f"start() raised, and the command had run: {' and '.join(ran)} exist in the workspace. {SENTENCE_H2} {HOW_HOLD}"
        assert refused(port), f"start() raised, and port {port} answers: something the root started holds it. {SENTENCE_H2}"
    finally:
        release(host)


# ---------- H3 and H4: the POSIX group ----------

# ---------- H5: a start of a folder flag beside an instance ----------


@pytest.mark.parametrize("group", H5A_GROUPS)
def test_an_abbreviated_folder_flag_beside_an_instance_is_refused(rig, group):
    """H5a. For one flag, each start of it ComfyUI's parser reads as that flag, from its shortest to one character short of the full name,
    alone with a value after it and as name=value; or the starts ComfyUI finds ambiguous; or the empty-value forms."""
    port = engine_port(rig.engine())
    ws = rig.workspace("h5a")
    let_through = []
    for extra in h5a_forms(group, str(rig.root / "elsewhere")):
        box, reports = build(rig, ws, port, instance=rig.root / "instances" / "x", extra=extra)
        if not ("raised" in box and isinstance(box["raised"], ValueError)):
            let_through.append(f"{shown(rig, extra)} {outcome(box)}")
        elif reports.states:
            let_through.append(f"{shown(rig, extra)} raised ValueError after it reported {reports.states}")
    assert not let_through, (
        f"Beside an instance, {len(let_through)} of {len(h5a_forms(group, ''))} forms were not refused with ValueError before any report: "
        f"{'; '.join(let_through[:6])}{'; ...' if len(let_through) > 6 else ''}. ComfyUI's parser reads an unambiguous start of a flag as the "
        f"flag and keeps its last value, so ComfyUI would take that folder from extra, not from the instance. {SENTENCE_H5}"
    )
    assert not cli_runs(ws), f"The command ran: {cli_runs(ws)}. {SENTENCE_H5}"


def test_other_flags_pass_beside_an_instance_and_any_without_one(rig):
    """H5b. Beside an instance, every other option string of ComfyUI's cli_args.py as of Nov 11, and '--feature-flag=--temp-directory',
    whose name is --feature-flag; without an instance, each form H5a refuses. One lifecycle with an instance and extra=['--cpu'] is also
    started and stopped."""
    port = engine_port(rig.engine())
    ws = rig.workspace("h5b")
    inst = rig.root / "instances" / "h5b"
    box, reports = build(rig, ws, port, instance=inst, extra=[*OTHER_FLAGS, "--feature-flag=--temp-directory"])
    value_of(box, "CozyLifecycle(..., instance=..., extra=ComfyUI's 101 other option strings and '--feature-flag=--temp-directory')",
             f"Refuse only a name, the part before any '=', that is the start of one of the four folder flags. {SENTENCE_H5}")
    assert reports.states == ["ready"], f"The constructor reported {reports.states}, and it reports its one measurement, 'ready' here. {SENTENCE_H5}"
    refused_without = []
    for group in H5A_GROUPS:
        for extra in h5a_forms(group, str(rig.root / "elsewhere")):
            box, reports = build(rig, ws, port, extra=extra)
            if "raised" in box or reports.states != ["ready"]:
                refused_without.append(f"{shown(rig, extra)} {outcome(box)} and reported {reports.states}")
    assert not refused_without, (
        f"Without an instance, {len(refused_without)} forms were not built with one measurement reported: "
        f"{'; '.join(refused_without[:6])}{'; ...' if len(refused_without) > 6 else ''}. {SENTENCE_H5}"
    )
    started = rig.workspace("h5b_started")
    port = free_port()
    life = rig.life(started, port, Reports(), SENTENCE_H5, instance=inst, extra=["--cpu"], ready_s=START_S - 2)
    got = value_of(within(life.start, "start()", START_S), "start() with an instance and extra=['--cpu']", SENTENCE_H5)
    assert got == "ready", f"start() with an instance and extra=['--cpu'] returned {got!r}, and it returns 'ready'. {SENTENCE_H5}"
    stopped = value_of(within(life.stop, "stop()", STOP_S), "stop()", SENTENCE_H5)
    assert stopped == "stopped", f"stop() returned {stopped!r}. {SENTENCE_H5}"


# ---------- H6: an instance in the workspace's temp folder ----------


def made(folder):
    folder.mkdir(parents=True)
    return folder


# Spellings of a folder in <workspace>/temp: id -> (what, (rig, ws) -> (the workspace as given, the instance)).
IN_TEMP = {
    "temp": ("ws/temp", lambda rig, ws: (ws, ws / "temp")),
    "temp-inst-exists": ("ws/temp/inst, which exists", lambda rig, ws: (ws, made(ws / "temp" / "inst"))),
    "temp-not-made-yet": ("ws/temp/not/made/yet", lambda rig, ws: (ws, ws / "temp" / "not" / "made" / "yet")),
    "x-dotdot-temp-inst": ("ws/x/../temp/inst, written as a string", lambda rig, ws: (ws, Path(str(ws) + "/x/../temp/inst"))),
    "link-temp-inst": ("<root>/wslink/temp/inst, wslink a link to ws", lambda rig, ws: (ws, rig.link(ws) / "temp" / "inst")),
    "workspace-as-link": ("ws/temp/inst, with the workspace given as wslink, a link to ws", lambda rig, ws: (rig.link(ws), ws / "temp" / "inst")),
}
if WINDOWS:
    IN_TEMP["TEMP-inst"] = ("ws/TEMP/inst", lambda rig, ws: (ws, ws / "TEMP" / "inst"))
    IN_TEMP["long-path-prefix"] = ("the \\\\?\\ prefix and ws/temp/inst", lambda rig, ws: (ws, Path("\\\\?\\" + str(ws / "temp" / "inst"))))
    IN_TEMP["trailing-space"] = ("ws/'temp '/inst, a trailing space Windows drops",
                                 lambda rig, ws: (ws, Path(str(ws) + os.sep + "temp " + os.sep + "inst")))

# Folders that only look like <workspace>/temp: what -> (rig, ws) -> the instance.
BESIDE_TEMP = {
    "ws/temp2/inst": lambda rig, ws: ws / "temp2" / "inst",
    "ws/temporary": lambda rig, ws: ws / "temporary",
    "ws/temp_inst": lambda rig, ws: ws / "temp_inst",
    "ws/temp/../instances/a, written as a string": lambda rig, ws: Path(str(ws) + "/temp/../instances/a"),
    "<root>/elsewhere/temp/inst": lambda rig, ws: rig.root / "elsewhere" / "temp" / "inst",
    "ws/instances/a": lambda rig, ws: ws / "instances" / "a",
}
if not WINDOWS:
    BESIDE_TEMP["ws/TEMP/inst"] = lambda rig, ws: ws / "TEMP" / "inst"


@pytest.mark.parametrize("case", list(IN_TEMP))
def test_an_instance_in_the_workspaces_temp_folder_is_refused(rig, case):
    """H6a. A ComfyUI started from the workspace with its default temp folder deletes <workspace>/temp when it starts and again when it exits
    (ComfyUI's main.py:531 and 616), and an instance there would lose its user folder, database and output with it."""
    what, spell = IN_TEMP[case]
    port = engine_port(rig.engine())
    ws = rig.workspace("h6a")
    given, inst = spell(rig, ws)
    box, reports = build(rig, given, port, instance=inst)
    assert "raised" in box and isinstance(box["raised"], ValueError), (
        f"CozyLifecycle with instance {what} ({inst}) {outcome(box)}, and it raises ValueError. {SENTENCE_H6} {HOW_TEMP}"
    )
    assert reports.states == [], f"The constructor reported {reports.states} before it raised, and it raises before it measures. {SENTENCE_H6}"
    assert not cli_runs(ws), f"The command ran: {cli_runs(ws)}. {SENTENCE_H6}"
    assert (ws / "temp" / "keep.txt").exists(), f"The workspace's temp/keep.txt is gone after CozyLifecycle with instance {what}. {SENTENCE_H6}"


def test_folders_that_only_look_like_the_workspaces_temp_are_accepted(rig):
    """H6b. Siblings whose names begin with temp, a '..' out of temp, a temp folder elsewhere and a folder in the workspace are all accepted;
    ws/temp2/inst is also started and stopped."""
    port = engine_port(rig.engine())
    ws = rig.workspace("h6b")
    refused_here = []
    for what, spell in BESIDE_TEMP.items():
        box, reports = build(rig, ws, port, instance=spell(rig, ws))
        if "raised" in box or reports.states != ["ready"]:
            refused_here.append(f"{what} {outcome(box)} and reported {reports.states}")
    assert not refused_here, (
        f"Instances outside the workspace's temp folder were not built with one measurement reported: {'; '.join(refused_here)}. Compare "
        f"resolved folders, not strings, and walk samefile over the resolved instance's parents, not the spelling's. {SENTENCE_H6} {HOW_TEMP}"
    )
    port = free_port()
    life = rig.life(ws, port, Reports(), SENTENCE_H6, instance=ws / "temp2" / "inst", ready_s=START_S - 2)
    got = value_of(within(life.start, "start()", START_S), "start() with instance ws/temp2/inst", SENTENCE_H6)
    assert got == "ready", f"start() with instance ws/temp2/inst returned {got!r}, and it returns 'ready'. {SENTENCE_H6}"
    stopped = value_of(within(life.stop, "stop()", STOP_S), "stop()", SENTENCE_H6)
    assert stopped == "stopped", f"stop() returned {stopped!r}. {SENTENCE_H6}"
    changed = untouched(ws)
    assert not changed, f"Starting and stopping a ComfyUI with instance ws/temp2/inst changed the workspace's own files: {changed}. {SENTENCE_H6}"


@pytest.mark.skipif(not WINDOWS, reason="the \\\\?\\ prefix is Windows'")
def test_the_workspace_itself_with_the_long_path_prefix_is_refused(rig):
    """H6c. instance is the \\\\?\\ prefix and the workspace: the workspace itself, which would hand ComfyUI the workspace's own user folder
    and database (CONTRACT I2)."""
    port = engine_port(rig.engine())
    ws = rig.workspace("h6c")
    inst = Path("\\\\?\\" + str(ws))
    box, reports = build(rig, ws, port, instance=inst)
    assert "raised" in box and isinstance(box["raised"], ValueError), (
        f"CozyLifecycle with instance {inst}, the workspace itself, {outcome(box)}, and it raises ValueError. {SENTENCE_H6} {HOW_TEMP}"
    )
    assert reports.states == [], f"The constructor reported {reports.states} before it raised, and it raises before it measures. {SENTENCE_H6}"
    assert not cli_runs(ws), f"The command ran: {cli_runs(ws)}. {SENTENCE_H6}"


# ---------- H7: an instance in use ----------


def test_an_instance_another_lifecycle_runs_is_refused_until_it_stops(rig):
    """H7a. Two lifecycles in this process, two workspaces, two ports, one instance."""
    inst = (rig.root / "instances" / "h7a").resolve()
    pa, pb = two_ports()
    wa, wb = rig.workspace("h7a_a"), rig.workspace("h7a_b")
    ra, rb = Reports(), Reports()
    a = rig.life(wa, pa, ra, SENTENCE_H7, instance=inst, ready_s=START_S - 2)
    b = rig.life(wb, pb, rb, SENTENCE_H7, instance=inst, ready_s=START_S - 2)
    first = value_of(within(a.start, "start()", START_S), "the first lifecycle's start()", SENTENCE_H7)
    assert first == "ready", f"The first lifecycle's start() returned {first!r} on a free port, and it returns 'ready'. {SENTENCE_H7}"
    e = raised_organ_error(within(b.start, "start()", START_S), "start() on an instance another lifecycle in this process runs",
                           f"{SENTENCE_H7} {HOW_LOCK}")
    assert str(inst) in str(e), f"The OrganError reads {str(e)!r}, without the instance {inst}. {SENTENCE_H7}"
    assert rb.states[-1:] == ["unavailable"], f"After a start refused for its instance, report last saw {rb.states[-1:]}. {SENTENCE_H7}"
    assert not cli_runs(wb), f"The refused start ran the command: {cli_runs(wb)}. {SENTENCE_H7}"
    assert refused(pb), f"The refused start's port {pb} answers. {SENTENCE_H7}"
    probed = value_of(within(a.probe, "probe()", CONSTRUCT_S), "probe()", SENTENCE_H7)
    assert probed == "ready", f"The first lifecycle's engine reads {probed!r} after the second start was refused, and it still reads 'ready'. {SENTENCE_H7}"
    again = value_of(within(a.start, "start()", START_S), "a further start() of the lifecycle that holds the instance", SENTENCE_H7)
    assert again == "ready" and len(cli_runs(wa)) == 1, (
        f"A further start() of the lifecycle that holds the instance returned {again!r} after {len(cli_runs(wa))} runs of the command, and it "
        f"returns 'ready' with the one run: its own hold is never in its way. {SENTENCE_H7}"
    )
    stopped = value_of(within(a.stop, "stop()", STOP_S), "the first lifecycle's stop()", SENTENCE_H7)
    assert stopped == "stopped", f"The first lifecycle's stop() returned {stopped!r}. {SENTENCE_H7}"
    got = value_of(within(b.start, "start()", START_S), "start() after the lifecycle that held the instance stopped", SENTENCE_H7)
    assert got == "ready", f"start() after the other lifecycle stopped returned {got!r}: stop() lets the instance go. {SENTENCE_H7}"
    stopped = value_of(within(b.stop, "stop()", STOP_S), "the second lifecycle's stop()", SENTENCE_H7)
    assert stopped == "stopped", f"The second lifecycle's stop() returned {stopped!r}. {SENTENCE_H7}"
    after = value_of(within(a.start, "start()", START_S), "start() of a lifecycle after its own stop()", SENTENCE_H7)
    assert after == "ready", f"start() of a lifecycle after its own stop() returned {after!r}, and it is never refused. {SENTENCE_H7}"
    stopped = value_of(within(a.stop, "stop()", STOP_S), "the first lifecycle's last stop()", SENTENCE_H7)
    assert stopped == "stopped", f"The first lifecycle's last stop() returned {stopped!r}. {SENTENCE_H7}"


def test_a_start_that_fails_lets_its_instance_go(rig):
    """H7b. The first lifecycle's root exits before main.py binds (orphan_early), so its start() raises; the instance is free again."""
    inst = (rig.root / "instances" / "h7b").resolve()
    pa, pb = two_ports()
    wa, wb = rig.workspace("h7b_a", mode="orphan_early"), rig.workspace("h7b_b")
    a = rig.life(wa, pa, Reports(), SENTENCE_H7, instance=inst, ready_s=START_S - 2)
    raised_organ_error(within(a.start, "start()", START_S), "start() whose root exited before main.py answered", SENTENCE_H7)
    b = rig.life(wb, pb, Reports(), SENTENCE_H7, instance=inst, ready_s=START_S - 2)
    got = value_of(within(b.start, "start()", START_S), "start() on an instance whose last start failed", SENTENCE_H7)
    assert got == "ready", f"start() on an instance whose last start failed returned {got!r}: a start that leaves no tree lets it go. {SENTENCE_H7}"
    stopped = value_of(within(b.stop, "stop()", STOP_S), "stop()", SENTENCE_H7)
    assert stopped == "stopped", f"stop() returned {stopped!r}. {SENTENCE_H7}"


@pytest.mark.skipif(not WINDOWS, reason="H7c reads a hold that ends with its host, as the engine does on Windows (I6); H7d reads POSIX")
def test_an_instance_another_host_runs_is_refused_until_that_host_ends(rig):
    """H7c. HOST_HOLDING runs an engine on the instance; this process's start() is refused; the host is killed without stop()."""
    inst = (rig.root / "instances" / "h7c").resolve()
    ph, pl = two_ports()
    wh, wl = rig.workspace("h7c_host"), rig.workspace("h7c_here")
    host = rig.host(HOST_HOLDING, wh, ph, rig.cli, inst)
    got = host_out(rig, host)
    assert got.get("state") == "ready", f"Inconclusive, so this case fails: the host could not start its engine on the instance: {got}."
    reports = Reports()
    life = rig.life(wl, pl, reports, SENTENCE_H7, instance=inst, ready_s=START_S - 2)
    e = raised_organ_error(within(life.start, "start()", START_S), "start() on an instance another host's lifecycle runs",
                           f"{SENTENCE_H7} {HOW_LOCK}")
    assert str(inst) in str(e), f"The OrganError reads {str(e)!r}, without the instance {inst}. {SENTENCE_H7}"
    assert reports.states[-1:] == ["unavailable"], f"After a start refused for its instance, report last saw {reports.states[-1:]}. {SENTENCE_H7}"
    assert not cli_runs(wl), f"The refused start ran the command: {cli_runs(wl)}. {SENTENCE_H7}"
    host.kill()  # TerminateProcess: the host ends without stop()
    host.wait(timeout=10)
    pid = got["main_pid"]
    assert until(lambda: refused(ph) and not alive(pid), GONE_S, every=0.25), (
        f"The host was killed, and {GONE_S:g} s later its engine (main.py, pid {pid}) {'still runs' if alive(pid) else 'is gone'} with port {ph} "
        f"{'closed' if refused(ph) else 'still answering'}. {SENTENCE_I6}"
    )
    again = value_of(within(life.start, "start()", START_S), "start() after the host that held the instance was killed", SENTENCE_H7)
    assert again == "ready", f"start() after the host that held the instance was killed returned {again!r}: the hold ends with that host. {SENTENCE_H7}"
    stopped = value_of(within(life.stop, "stop()", STOP_S), "stop()", SENTENCE_H7)
    assert stopped == "stopped", f"stop() returned {stopped!r}. {SENTENCE_H7}"

