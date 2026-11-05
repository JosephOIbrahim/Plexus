"""A small Plexus session you drive from a terminal: two projects, one exchange, one neuron.

    python examples/plexus_session.py
    python examples/plexus_session.py --script "temp 1.5; status; quit"

Project A writes /Exchange/LookState.temperature with plain Sdf. A change over 0.2 wakes the neuron, its
hint lands in the neuron's own layer, and project B reads both through composition. It calls only what
tests/acceptance/CONTRACT.md lists, plus plain pxr, so it keeps working whatever moves below that surface.

Every launch makes a new session folder: stagekit.create_project and, until S8, NeuronRuntime.register
raise on specs they find already in a layer. The organ joins here once phase 2 has one.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # plexus imports from this repo, whatever the working directory is

from plexus_live import COMFYUI_URL, READ_ERRORS, NotComfyUI, comfyui_stats, describe  # noqa: E402

LOOK = "/Exchange/LookState"
TEMP = LOOK + ".temperature"
HINTS = "/Exchange/lookNeuron/Hints"
PREDICATE = f"changed({TEMP}) AND delta({TEMP}) > 0.2"
START_TEMPERATURE = 1.0
IDLE_S = 30.0

HELP = """Commands:
  temp <value>   project A writes the temperature, and the neuron wakes if it moved more than 0.2
  status         ComfyUI, the neuron and what project B reads
  help           this list
  quit           stop the neuron and leave"""


class Session:
    def __init__(self, root: Path):
        from plexus.core import stagekit
        from plexus.core.neuron import NeuronRuntime
        from plexus.membrane import exchange as ex
        from pxr import Sdf, Usd

        self._sdf = Sdf
        self.root = root
        exchange = ex.create_exchange(root / "shared" / "exchange")
        self.a_layer = Sdf.Layer.FindOrOpen(str(ex.register_participant(exchange, "projectA", grants=[LOOK])))
        stagekit.create_project(root / "projectA.usda", exchange, "projectA")
        project_b = stagekit.create_project(root / "projectB.usda", exchange, "projectB")
        self._write_temperature(START_TEMPERATURE)
        self.runtime = NeuronRuntime(exchange, "lookNeuron")
        self.neuron = self.runtime.register("gradeHint", scope=LOOK, predicate=PREDICATE, action=self._hint, budget_wakes=10, budget_window=60.0)
        self.runtime.start()
        self.project_b = Usd.Stage.Open(str(project_b))

    def _hint(self, ctx) -> None:
        value = self.runtime.stage.GetAttributeAtPath(TEMP).Get()
        ctx.author(HINTS, "grade_hint", "warmer" if value > START_TEMPERATURE else "cooler", self._sdf.ValueTypeNames.String)

    def _write_temperature(self, value: float) -> None:
        prim = self.a_layer.GetPrimAtPath(LOOK) or self._sdf.CreatePrimInLayer(self.a_layer, LOOK)
        prim.specifier = self._sdf.SpecifierDef
        attr = prim.attributes.get("temperature") or self._sdf.AttributeSpec(prim, "temperature", self._sdf.ValueTypeNames.Double)
        attr.default = value
        self.a_layer.Save()

    def set_temperature(self, value: float) -> str:
        """Writes, then waits for the runtime, so the next command never writes under a dispatcher that is still reading."""
        before = self.neuron.wakes
        self._write_temperature(value)
        time.sleep(0.01)
        if not self.runtime.wait_idle(IDLE_S):
            return f"Project A wrote {value:g}, and the runtime did not go idle in {IDLE_S:.0f} s."
        if self.neuron.wakes > before:
            return f"Project A wrote {value:g}. The neuron woke. Wakes so far: {self.neuron.wakes}."
        return f"Project A wrote {value:g}. The neuron stayed {self.neuron.state}."

    def _read(self, path: str):
        attr = self.project_b.GetAttributeAtPath(path)
        return attr.Get() if attr else None

    def status(self, url: str) -> list[str]:
        try:
            stats = comfyui_stats(url)
            comfyui = f"up at {url}: {describe(stats)}" if stats else f"not running at {url}"
        except (NotComfyUI, *READ_ERRORS) as e:
            comfyui = str(e)
        lines = [
            f"ComfyUI   {comfyui}",
            f"Neuron    {self.neuron.name}: {self.neuron.state}. Wakes so far: {self.neuron.wakes}.",
        ]
        spec = self.runtime.edit_layer.GetPrimAtPath(self.neuron.prim_path)
        for name in spec.attributes.keys() if spec else ():
            if name.startswith("plexus:flag") or name in ("plexus:state", "plexus:lastWake"):
                lines.append(f"  {name} = {spec.attributes[name].default}")
        lines.append(f"Project B temperature {self._read(TEMP)}, grade_hint {self._read(HINTS + '.grade_hint')}")
        return lines

    def close(self) -> None:
        self.runtime.stop()


def new_session_folder(sessions_root: Path | None) -> Path:
    if sessions_root is None:
        base = os.environ.get("LOCALAPPDATA")
        sessions_root = (Path(base) if base else Path.home()) / "Plexus" / "sessions"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for n in range(100):
        folder = sessions_root / (stamp if n == 0 else f"{stamp}-{n}")
        try:
            folder.mkdir(parents=True)
            return folder
        except FileExistsError:
            continue
    raise FileExistsError(f"no free session folder under {sessions_root} for {stamp}")


def commands(script: str | None):
    if script is not None:
        yield from (c.strip() for c in script.split(";") if c.strip())
        return
    while True:
        try:
            yield input("plexus> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return


def drive(session: Session, url: str, script: str | None) -> None:
    for line in commands(script):
        if script is not None:
            print(f"plexus> {line}")
        word, *rest = line.split() or [""]
        if word == "":
            continue
        if word in ("quit", "exit"):
            return
        if word == "help":
            print(HELP)
        elif word == "status":
            print("\n".join(session.status(url)))
        elif word == "temp" and len(rest) == 1:
            try:
                value = float(rest[0])
            except ValueError:
                print(f"{rest[0]} is not a number.")
                continue
            print(session.set_temperature(value))
        else:
            print(f"Not a command: {line}\n{HELP}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Drive a small Plexus session from a terminal.")
    p.add_argument("--url", default=COMFYUI_URL, help="where to read ComfyUI's status from")
    p.add_argument("--script", help="commands separated by semicolons, instead of the prompt")
    p.add_argument("--sessions-root", type=Path, help="where the session folder goes")
    args = p.parse_args(argv)

    try:
        session = Session(new_session_folder(args.sessions_root))
    except ImportError as e:
        print(f"The Plexus core does not load ({e}). Build it: python harness/plexus_loop/build_core.py", file=sys.stderr)
        return 1
    print(f"Session   {session.root}")
    print(f"Watching  {TEMP}, starting at {START_TEMPERATURE:g}. Type help for the commands.\n")
    try:
        drive(session, args.url, args.script)
    finally:
        session.close()
    print(f"\nSession ended. Its layers stay in {session.root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
