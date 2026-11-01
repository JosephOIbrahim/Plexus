"""Shared helpers for the frozen Plexus acceptance tests (Spec v2.1 §9, §10).

The slice is Blueprint §10: two projects, one exchange stack, one neuron that
watches /Exchange/LookState. "Project A" is a plain Sdf writer on purpose, so
the tests prove that any USD writer can be a participant.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LOOK = "/Exchange/LookState"
TEMP = LOOK + ".temperature"
NEURON_PARTICIPANT = "lookNeuron"
HINT_PRIM = f"/Exchange/{NEURON_PARTICIPANT}/Hints"


def child_env() -> dict[str, str]:
    """Environment for a child Python that must import plexus from this repo."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def p95(samples: list[float]) -> float:
    s = sorted(samples)
    return s[max(0, round(0.95 * len(s)) - 1)]


class FakeClock:
    """Budget clock the test moves by hand, so T3 doesn't sleep ten seconds."""

    def __init__(self, t: float = 1000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


@dataclass
class Slice:
    root: Path
    exchange: Path
    a_layer_path: Path
    project_a: Path
    project_b: Path
    clock: FakeClock
    runtime: object = None
    wakes: list = field(default_factory=list)

    def a_layer(self):
        from pxr import Sdf

        return Sdf.Layer.FindOrOpen(str(self.a_layer_path))

    def set_temperature(self, value: float) -> None:
        """Project A authors /Exchange/LookState.temperature with plain Sdf and saves."""
        from pxr import Sdf

        layer = self.a_layer()
        prim = layer.GetPrimAtPath(LOOK) or Sdf.CreatePrimInLayer(layer, LOOK)
        prim.specifier = Sdf.SpecifierDef
        attr = prim.attributes.get("temperature") or Sdf.AttributeSpec(
            prim, "temperature", Sdf.ValueTypeNames.Double
        )
        attr.default = float(value)
        layer.Save()

    def start_neuron(
        self,
        *,
        predicate: str,
        budget_wakes: int = 100,
        budget_window: float = 10.0,
        action=None,
        name: str = "gradeHint",
    ):
        from plexus.core.neuron import NeuronRuntime
        from pxr import Sdf

        rt = NeuronRuntime(self.exchange, NEURON_PARTICIPANT, clock=self.clock)

        def default_action(ctx):
            self.wakes.append(self.clock())
            ctx.author(HINT_PRIM, "grade_hint", "warmer", Sdf.ValueTypeNames.String)

        handle = rt.register(
            name,
            scope=LOOK,
            predicate=predicate,
            action=action or default_action,
            budget_wakes=budget_wakes,
            budget_window=budget_window,
        )
        rt.start()
        self.runtime = rt
        return rt, handle


def settle(rt, timeout: float = 5.0) -> None:
    """Let the runtime drain, and fail loudly if it can't."""
    time.sleep(0.01)
    assert rt.wait_idle(timeout), "runtime did not go idle"


PY = sys.executable
