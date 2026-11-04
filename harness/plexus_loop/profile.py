"""Step aside for Houdini.

Before every attempt the harness checks whether Houdini is running. When it
is, or when the check can't tell, the attempt runs on the CPU: the worker puts
no layers on the GPU, the gates run with the GPU hidden, and compile jobs are
capped. When Houdini is clearly absent the attempt may use the GPU.

The check is cheap and runs each attempt, so the harness moves back to the GPU
once Houdini closes.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field, replace

from .mission import HoudiniPolicy

# Process names Houdini and its command-line tools run under, lower case, with
# any ".exe" removed.
HOUDINI_PROCESS_NAMES = frozenset({
    "houdini", "houdinifx", "houdinicore", "happrentice", "hindie",
    "hython", "hbatch", "husk", "hserver", "houdini-bin", "houdinifx-bin",
})

# Lets a test, or Joe, force the answer: "running", "absent" or "unknown".
OVERRIDE_ENV = "PLEXUS_LOOP_HOUDINI"


def _list_process_names() -> list[str]:
    if sys.platform.startswith("win"):
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, errors="replace",
            timeout=15, check=True
        ).stdout or ""
        names = []
        for line in out.splitlines():
            line = line.strip()
            if line.startswith('"'):
                names.append(line.split('","', 1)[0].strip('"'))
        return names
    out = subprocess.run(
        ["ps", "-A", "-o", "comm="], capture_output=True, text=True, timeout=15, check=True
    ).stdout
    return [os.path.basename(x.strip()) for x in out.splitlines() if x.strip()]


def houdini_state(lister=_list_process_names) -> str:
    """Return "running", "absent" or "unknown"."""
    forced = os.environ.get(OVERRIDE_ENV, "").strip().lower()
    if forced in ("running", "absent", "unknown"):
        return forced
    try:
        names = lister()
    except Exception:  # noqa: BLE001 - any failure means we can't tell
        return "unknown"
    if not names:
        return "unknown"
    for n in names:
        n = n.lower()
        n = n.removesuffix(".exe")
        if n in HOUDINI_PROCESS_NAMES:
            return "running"
    return "absent"


@dataclass(frozen=True)
class Profile:
    """How one attempt may use the machine."""

    device: str  # "cpu" or "gpu"
    houdini: str  # what the check saw
    env: dict[str, str] = field(default_factory=dict)  # added to gate and worker environments
    ollama_options: dict[str, int] = field(default_factory=dict)

    def environ(self) -> dict[str, str]:
        e = dict(os.environ)
        e.update(self.env)
        e["PLEXUS_LOOP_DEVICE"] = self.device
        e.pop("TYPESAFE_API_KEY", None)  # only the harness calls Jev; gates run code the worker wrote
        return e


def with_env(profile: Profile, **env: str) -> Profile:
    """The same profile with extra environment variables for gates and command workers."""
    return replace(profile, env={**profile.env, **env})


def choose_profile(policy: HoudiniPolicy, state: str | None = None) -> Profile:
    state = state or houdini_state()
    if state == "absent":
        return Profile(device="gpu", houdini=state)
    threads = str(max(1, policy.cpu_threads))
    env = {
        "CUDA_VISIBLE_DEVICES": "",
        "CARGO_BUILD_JOBS": str(max(1, policy.cargo_jobs)),
        "RAYON_NUM_THREADS": threads,
        "OMP_NUM_THREADS": threads,
    }
    return Profile(
        device="cpu",
        houdini=state,
        env=env,
        ollama_options={"num_gpu": 0, "num_thread": max(1, policy.cpu_threads)},
    )
