"""Neuron runtime and neuron prim management."""

from dataclasses import dataclass
from pathlib import Path
import threading
import time
from typing import Callable, Optional

from pxr import Sdf, Tf, Usd

from plexus.core.axon import PlexusAxon
from plexus.core.predicate import compile_predicate
from plexus.membrane.exchange import register_participant


@dataclass(frozen=True)
class NeuronHandle:
    """A handle to a neuron."""
    name: str
    prim_path: Sdf.Path
    wakes: int
    state: str


class NeuronRuntime:
    """Neuron runtime that manages neurons and their actions."""

    def __init__(self, exchange: Path, participant_id: str, *, clock=time.monotonic, global_wakes_per_min: int = 60):
        self._exchange = exchange
        self._participant_id = participant_id
        self._clock = clock
        self._global_wakes_per_min = global_wakes_per_min
        self._stage = None
        self._edit_layer = None
        self._axon = None
        self._stop_event = threading.Event()
        self._neurons = {}  # name -> neuron info
        self._register_participant()

    def _register_participant(self):
        """Register this participant in the exchange."""
        register_participant(self._exchange, self._participant_id)

    @property
    def stage(self):
        """The runtime's Usd.Stage."""
        if self._stage is None:
            self._stage = Usd.Stage.Open(str(self._exchange))
        return self._stage

    @property
    def edit_layer(self):
        """The participant's Sdf.Layer; every opinion the runtime or its neurons author lands here and nowhere else."""
        if self._edit_layer is None:
            from pathlib import Path
            layer_path = Path(self._exchange).parent / f"from_{self._participant_id}.usda"
            self._edit_layer = Sdf.Layer.FindOrOpen(str(layer_path))
        return self._edit_layer

    def register(self, name: str, *, scope: str, predicate: str, action: Callable, budget_wakes: int = 100,
                 budget_window: float = 10.0, budget_tokens: int = 0, tools=()) -> NeuronHandle:
        """Define a neuron with the given parameters."""
        # Compile the predicate
        compiled = compile_predicate(predicate, scope)
        
        # Create neuron prim in edit layer
        neuron_path = Sdf.Path(f"/Plexus/Neurons/{name}")
        neuron_prim = self.edit_layer.GetPrimAtPath(str(neuron_path)) or Sdf.CreatePrimInLayer(self.edit_layer, str(neuron_path))
        neuron_prim.specifier = Sdf.SpecifierDef
        
        # Apply API schema
        neuron_prim.SetInfo("apiSchemas", Sdf.TokenListOp.Create(prependedItems=["PlexusNeuronAPI"]))
        
        # Set attributes
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
        
        # Add tools if any
        if tools:
            attr = Sdf.AttributeSpec(neuron_prim, "plexus:tools", Sdf.ValueTypeNames.StringArray)
            attr.default = list(tools)
        
        self.edit_layer.Save()
        
        # Return handle
        return NeuronHandle(
            name=name,
            prim_path=neuron_path,
            wakes=0,
            state="dormant"
        )

    def start(self) -> None:
        """Start the neuron runtime."""
        if self._axon is not None:
            return  # Already started

        self._stop_event.clear()
        self._axon = PlexusAxon(self.stage)
        self._axon.subscribe(self._on_event)
        self._axon.start()

    def stop(self) -> None:
        """Stop the neuron runtime."""
        if self._axon is not None:
            self._axon.cool()
            self._axon = None

    def wait_idle(self, timeout: float = 5.0) -> bool:
        """Wait for the runtime to become idle."""
        # For now, just return True as we don't have a real implementation
        return True

    def _on_event(self, event):
        """Handle events from the axon."""
        pass  # Placeholder for future implementation
