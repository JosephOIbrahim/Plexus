"""A small Plexus session you drive from a terminal: two projects, one exchange, one neuron.

    python examples/plexus_session.py
    python examples/plexus_session.py --script "temp 1.5; status; quit"

Project A writes /Exchange/LookState.temperature with plain Sdf. A change over 0.2 wakes the neuron. It writes a
grade hint, sends a job to ComfyUI through the Cozy organ, and authors what comes back as an asset in its own layer,
and project B reads all of it through composition. It calls only what tests/acceptance/CONTRACT.md lists, plus plain
pxr, so it keeps working whatever moves below that surface.

The job is a swatch by default: a 256 by 256 square whose colour follows the temperature, from cool blue at 0 to warm
orange at 3. It needs no model, so it runs in seconds even on the CPU. --workflow sends any ComfyUI API-format graph
instead, and the organ writes the neuron's seed into its seed inputs. --no-organ keeps the hint alone.

Every launch makes a new session folder: stagekit.create_project and NeuronRuntime.register want fresh layers.
"""

from __future__ import annotations

import argparse
import json
import os
import uuid
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
ASSET = "/Exchange/lookNeuron/Assets/swatch"
JOB_DEADLINE_S = 600.0  # one job, start to file on disk; a swatch takes about 13 s on the CPU, most of it two /object_info reads
SWATCH_SIZE = 256

HELP = """Commands:
  temp <value>   project A writes the temperature; over 0.2 the neuron wakes and ComfyUI renders a swatch
  status         ComfyUI, the organ, the neuron and what project B reads
  help           this list
  quit           stop the neuron and leave"""


def swatch_color(value: float) -> int:
    """The temperature as one colour: cool blue at 0, warm orange at 3 and past it, as EmptyImage's 0xRRGGBB int."""
    t = max(0.0, min(1.0, value / 3.0))
    cool, warm = (40, 110, 255), (255, 140, 30)
    r, g, b = (round(c + (w - c) * t) for c, w in zip(cool, warm))
    return (r << 16) | (g << 8) | b


def swatch_graph(value: float) -> dict:
    """A ComfyUI API graph with no model in it: one flat square, saved."""
    return {
        "1": {"class_type": "EmptyImage", "inputs": {"width": SWATCH_SIZE, "height": SWATCH_SIZE, "batch_size": 1, "color": swatch_color(value)}},
        "2": {"class_type": "SaveImage", "inputs": {"images": ["1", 0], "filename_prefix": "plexus_swatch"}},
    }


def load_workflow(path: Path) -> dict:
    """An API-format graph from a file: a dict of node id to a node with class_type and inputs."""
    graph = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(graph, dict) or not graph or not all(isinstance(n, dict) and "class_type" in n and isinstance(n.get("inputs"), dict) for n in graph.values()):
        raise ValueError(f"{path} is not a ComfyUI API-format graph: export it with Save (API) in ComfyUI.")
    return graph


class Session:
    def __init__(self, root: Path, organ_url: str | None = None, graph: dict | None = None):
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
        self.organ = None
        self.graph = graph
        self.last_record = None
        self.last_error = None
        if organ_url is not None:
            from plexus.organs.cozy import CozyOrgan

            self.organ = CozyOrgan(organ_url, root / "assets", deadline_s=JOB_DEADLINE_S)
        self.runtime = NeuronRuntime(exchange, "lookNeuron")
        self.neuron = self.runtime.register("gradeHint", scope=LOOK, predicate=PREDICATE, action=self._act, budget_wakes=10, budget_window=60.0)
        self.runtime.start()
        self.project_b = Usd.Stage.Open(str(project_b))

    def _act(self, ctx) -> None:
        """The neuron's action: the hint first, then one job through the organ, and the result as an asset in its own layer.
        Each wake first marks its render pending, so the render line never reports an earlier wake. Whatever goes wrong,
        an OrganError or anything else, lands as a failed line on the stage, not a traceback, so project B and status see it."""
        value = self.runtime.stage.GetAttributeAtPath(TEMP).Get()
        string = self._sdf.ValueTypeNames.String
        ctx.author(HINTS, "grade_hint", "warmer" if value > START_TEMPERATURE else "cooler", string)
        if self.organ is None:
            return
        from plexus.organs.protocol import Job, OrganError

        ctx.author(HINTS, "render", f"pending: wake {self.neuron.wakes}", string)
        graph = self.graph if self.graph is not None else swatch_graph(value)
        try:
            job = Job(graph=json.loads(json.dumps(graph)), seed=self.neuron.wakes, colorspace="srgb", correlation_id=f"look-{uuid.uuid4().hex}")
            record = self.organ.result(self.organ.submit(job))
            ctx.author_asset(ASSET, record)
        except Exception as e:  # noqa: BLE001 - an OrganError is the contract, and anything else must not leave the last wake's line standing
            self.last_error = str(e) if isinstance(e, OrganError) else f"{type(e).__name__}: {e}"
            ctx.author(HINTS, "render", f"failed: {self.last_error}", string)
            return
        self.last_record, self.last_error = record, None
        ctx.author(HINTS, "render", f"landed {Path(record.path).name}", string)

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
        idle_s = IDLE_S + (JOB_DEADLINE_S if self.organ is not None else 0.0)
        if not self.runtime.wait_idle(idle_s):
            return f"Project A wrote {value:g}, and the runtime did not go idle in {idle_s:.0f} s."
        if self.neuron.wakes > before:
            if self.organ is None:
                return f"Project A wrote {value:g}. The neuron woke. Wakes so far: {self.neuron.wakes}."
            render = self._read(HINTS + ".render") or "no render line"
            return f"Project A wrote {value:g}. The neuron woke, and ComfyUI's job {render}. Wakes so far: {self.neuron.wakes}."
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
        organ = "off (--no-organ)" if self.organ is None else f"cozy, sending {'the --workflow graph' if self.graph is not None else 'the swatch'} to {url}"
        lines = [
            f"ComfyUI   {comfyui}",
            f"Organ     {organ}",
            f"Neuron    {self.neuron.name}: {self.neuron.state}. Wakes so far: {self.neuron.wakes}.",
        ]
        spec = self.runtime.edit_layer.GetPrimAtPath(self.neuron.prim_path)
        for name in spec.attributes.keys() if spec else ():
            if name.startswith("plexus:flag") or name in ("plexus:state", "plexus:lastWake"):
                lines.append(f"  {name} = {spec.attributes[name].default}")
        lines.append(f"Project B temperature {self._read(TEMP)}, grade_hint {self._read(HINTS + '.grade_hint')}, render {self._read(HINTS + '.render')}")
        asset = self.project_b.GetPrimAtPath(ASSET)
        if asset and "PlexusAssetAPI" in asset.GetAppliedSchemas():
            path = asset.GetAttribute("plexus:assetPath").Get()
            sha = asset.GetAttribute("plexus:sha256").Get() or ""
            lines.append(f"Project B asset {ASSET}: {Path(path.path).name if path else '?'}, sha256 {sha[:12]}, from {asset.GetAttribute('plexus:sourceLayer').Get()}")
        else:
            lines.append("Project B asset none yet")
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
    p.add_argument("--workflow", type=Path, help="a ComfyUI API-format graph to send on each wake, instead of the swatch")
    p.add_argument("--no-organ", action="store_true", help="write the grade hint only, and send ComfyUI nothing")
    args = p.parse_args(argv)

    try:
        graph = load_workflow(args.workflow) if args.workflow else None
    except (OSError, ValueError) as e:
        print(f"The workflow does not load: {e}", file=sys.stderr)
        return 1
    try:
        session = Session(new_session_folder(args.sessions_root), organ_url=None if args.no_organ else args.url, graph=graph)
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
