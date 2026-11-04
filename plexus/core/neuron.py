"""Neuron runtime and neuron prim management."""

from dataclasses import dataclass
from plexus._core import Budget
from pathlib import Path
import threading
import time
import traceback
from typing import Callable

from pxr import Sdf, Usd

from plexus.core.axon import PlexusAxon
from plexus.core.predicate import compile_predicate
from plexus.membrane.exchange import register_participant
from plexus.membrane.gate import check_allowlist


@dataclass
class NeuronHandle:
    """Never frozen: the runtime changes wakes and state on this object in place, and callers hold it."""
    name: str
    prim_path: Sdf.Path
    wakes: int
    state: str


@dataclass
class _Record:
    compiled: object
    scope: str
    action: Callable
    budget_wakes: int
    budget_window: float
    budget_tokens: int
    handle: NeuronHandle
    budget: object = None


def _set_attr(spec, name, value, type_name):
    """A bare Sdf.AttributeSpec on a name that already exists raises Tf.ErrorException, so a second wake needs this."""
    attr = spec.attributes.get(name) or Sdf.AttributeSpec(spec, name, type_name)
    attr.default = value


class _Ctx:
    def __init__(self, runtime, record):
        self._runtime = runtime
        self._record = record

    def author(self, prim_path, attr_name, value, type_name):
        rt = self._runtime
        path = Sdf.Path(prim_path)
        if not check_allowlist(path, rt._allowlist):
            rt._author_on_neuron(self._record, "plexus:flag", f"denied: {path}", Sdf.ValueTypeNames.String)
            return
        layer = rt.edit_layer
        with rt._lock:
            with Sdf.ChangeBlock():
                spec = Sdf.CreatePrimInLayer(layer, path)
                for prefix in path.GetPrefixes():
                    layer.GetPrimAtPath(prefix).specifier = Sdf.SpecifierDef
                _set_attr(spec, attr_name, value, type_name)
                _set_attr(spec, "plexus:sourceLayer", layer.identifier, Sdf.ValueTypeNames.String)
            layer.Save()


class NeuronRuntime:
    def __init__(self, exchange: Path, participant_id: str, *, clock=time.monotonic, global_wakes_per_min: int = 60):
        self._exchange = exchange
        self._participant_id = participant_id
        self._clock = clock
        self._global_wakes_per_min = global_wakes_per_min
        self._stage = None
        self._edit_layer = None
        self._axon = None
        self._stop_event = threading.Event()
        self._neurons = {}  # name -> _Record
        self._lock = threading.RLock()
        self._running = 0
        self._allowlist = [Sdf.Path(f"/Exchange/{participant_id}")]
        self._register_participant()
        # Global budget for the session
        self._global_budget = Budget(global_wakes_per_min, 60.0)

    def _register_participant(self):
        register_participant(self._exchange, self._participant_id)

    @property
    def stage(self):
        if self._stage is None:
            self._stage = Usd.Stage.Open(str(self._exchange))
        return self._stage

    @property
    def edit_layer(self):
        if self._edit_layer is None:
            from pathlib import Path
            layer_path = Path(self._exchange).parent / f"from_{self._participant_id}.usda"
            self._edit_layer = Sdf.Layer.FindOrOpen(str(layer_path))
        return self._edit_layer

    def register(self, name: str, *, scope: str, predicate: str, action: Callable, budget_wakes: int = 100,
                 budget_window: float = 10.0, budget_tokens: int = 0, tools=()) -> NeuronHandle:
        """Call it before start(): it authors without the lock. Nothing wakes until start()."""
        compiled = compile_predicate(predicate, scope)
        neuron_path = Sdf.Path(f"/Plexus/Neurons/{name}")
        neuron_prim = self.edit_layer.GetPrimAtPath(str(neuron_path)) or Sdf.CreatePrimInLayer(self.edit_layer, str(neuron_path))
        neuron_prim.specifier = Sdf.SpecifierDef
        neuron_prim.SetInfo("apiSchemas", Sdf.TokenListOp.Create(prependedItems=["PlexusNeuronAPI"]))
        attr = Sdf.AttributeSpec(neuron_prim, "plexus:scope", Sdf.ValueTypeNames.String)
        attr.default = scope
        attr = Sdf.AttributeSpec(neuron_prim, "plexus:predicate", Sdf.ValueTypeNames.String)
        attr.default = predicate
        attr = Sdf.AttributeSpec(neuron_prim, "plexus:budgetWakes", Sdf.ValueTypeNames.Int)
        attr.default = budget_wakes
        attr = Sdf.AttributeSpec(neuron_prim, "plexus:budgetWindow", Sdf.ValueTypeNames.Double)
        attr.default = budget_window
        attr = Sdf.AttributeSpec(neuron_prim, "plexus:budgetTokens", Sdf.ValueTypeNames.Int)
        attr.default = budget_tokens
        if tools:
            attr = Sdf.AttributeSpec(neuron_prim, "plexus:tools", Sdf.ValueTypeNames.StringArray)
            attr.default = list(tools)
        for prefix in neuron_path.GetPrefixes():
            self.edit_layer.GetPrimAtPath(prefix).specifier = Sdf.SpecifierDef
        self.edit_layer.Save()
        handle = NeuronHandle(name=name, prim_path=neuron_path, wakes=0, state="dormant")
        record = _Record(compiled, scope, action, budget_wakes, budget_window, budget_tokens, handle)
        # S5 calls record.compiled.seed(self._values(record)) here.
        record.compiled.seed(self._values(record))
        record.budget = Budget(budget_wakes, budget_window)
        self._neurons[name] = record
        return handle

    def start(self) -> None:
        if self._axon is not None:
            return

        self._stop_event.clear()
        self._axon = PlexusAxon(self.stage)
        self._axon.subscribe(self._on_event)
        self._axon.start()

    def stop(self) -> None:
        self.wait_idle(5.0)
        if self._axon is not None:
            self._axon.cool()
            self._axon = None

    def wait_idle(self, timeout: float = 5.0) -> bool:
        """True once no event is pending, no window is open and no action is running."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if (self._axon is None or self._axon.idle()) and self._running == 0:
                return True
            time.sleep(0.005)
        return False

    def _author_on_neuron(self, record, name, value, type_name):
        """One saved opinion on the neuron prim: the deny flag now, S7's mute later."""
        with self._lock:
            with Sdf.ChangeBlock():
                _set_attr(self.edit_layer.GetPrimAtPath(record.handle.prim_path), name, value, type_name)
            self.edit_layer.Save()

    def _values(self, record):
        values = {}
        for p in record.compiled.paths():
            attr = self.stage.GetAttributeAtPath(p)
            value = attr.Get() if attr else None
            if value is not None:
                values[p] = value
        return values

    def _on_event(self, event):
        """Dispatcher: runs on the axon's thread, once per coalesced event."""
        for record in list(self._neurons.values()):
            scope = Sdf.Path(record.scope)
            if not (any(p.HasPrefix(scope) for p in event.paths | event.resynced)
                    or any(scope.HasPrefix(r) for r in event.resynced)):
                continue
            # str items only: an Sdf.Path here raises TypeError: 'Path' object is not an instance of 'str'.
            changed = [p for p in record.compiled.paths()
                       if Sdf.Path(p) in event.paths or any(Sdf.Path(p).HasPrefix(r) for r in event.resynced)]
            with self._lock:
                values = self._values(record)
                if not record.compiled.eval(changed, values):
                    continue
                # S7's budget check goes here.
                # Check neuron budget first
                now = self._clock()
                if record.budget.peek(now) != "wake":
                    # If the neuron's budget is not 'wake', admit it and check if it mutes
                    if record.budget.admit(now) == "mute":
                        record.handle.state = "muted"
                        try:
                            with Sdf.ChangeBlock():
                                spec = self.edit_layer.GetPrimAtPath(record.handle.prim_path)
                                _set_attr(spec, 'plexus:state', 'muted', Sdf.ValueTypeNames.Token)
                                _set_attr(spec, 'plexus:flag:budget', 'budget trip or mute', Sdf.ValueTypeNames.String)
                            self.edit_layer.Save()
                        except Exception:
                            # If saving fails, we still want to proceed with the next neuron
                            traceback.print_exc()
                    continue

                # Check global budget
                if self._global_budget.peek(now) != "wake":
                    continue

                # If we get here, both budgets allow the wake
                record.budget.admit(now)
                self._global_budget.admit(now)
                # S5 calls record.compiled.commit_wake(values) here.
                record.compiled.commit_wake(values)
                self._running += 1
                record.handle.wakes += 1
                record.handle.state = "awake"
            threading.Thread(target=self._run_action, args=(record,), daemon=True).start()

    def _run_action(self, record):
        try:
            record.action(_Ctx(self, record))
        except Exception:
            traceback.print_exc()
        finally:
            with self._lock:
                if record.handle.state == "awake":  # a mute outlives the action
                    record.handle.state = "dormant"
                self._running -= 1
