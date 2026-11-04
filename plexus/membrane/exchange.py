"""Exchange layer stack management."""

from pathlib import Path
from pxr import Sdf, Tf, Usd, Plug

def create_exchange(directory: Path) -> Path:
    """Writes directory/exchange.usda with an /Exchange prim and an empty sublayer list. Returns the path. Idempotent."""
    exchange_path = directory / "exchange.usda"
    layer = Sdf.Layer.FindOrOpen(str(exchange_path)) or Sdf.Layer.CreateNew(str(exchange_path))
    if not layer.GetPrimAtPath("/Exchange"):
        prim = Sdf.CreatePrimInLayer(layer, "/Exchange")
        prim.specifier = Sdf.SpecifierDef
    layer.Save()
    return exchange_path

def register_participant(exchange: Path, participant_id: str, grants=()) -> Path:
    """Appends from_<participantId>.usda as the weakest sublayer and returns its path. Idempotent."""
    participant_path = Path(exchange).parent / f"from_{participant_id}.usda"
    exchange_layer = Sdf.Layer.FindOrOpen(str(exchange))
    
    # Ensure the participant layer exists
    if not participant_path.exists():
        part_layer = Sdf.Layer.CreateNew(str(participant_path))
        prim = Sdf.CreatePrimInLayer(part_layer, "/Exchange")
        prim.specifier = Sdf.SpecifierDef
        
        # Add child prim for this participant
        child_prim = Sdf.CreatePrimInLayer(part_layer, f"/Exchange/{participant_id}")
        child_prim.specifier = Sdf.SpecifierDef
        
        part_layer.Save()
    
    # Append to sublayers if not already present
    if str(participant_path) not in exchange_layer.subLayerPaths:
        exchange_layer.subLayerPaths.append(str(participant_path))
        exchange_layer.Save()
        
    return participant_path

def participants(exchange: Path) -> list[str]:
    """Participant ids, strongest first, read from exchange.usda itself."""
    layer = Sdf.Layer.FindOrOpen(str(exchange))
    if not layer:
        return []
    sublayers = [Path(p) for p in layer.subLayerPaths]
    participant_ids = [p.stem[5:] for p in sublayers if p.name.startswith("from_") and p.name.endswith(".usda")]
    return participant_ids

# Register the plugin at import time
Plug.Registry().RegisterPlugins(str(Path(__file__).parent.parent / "schema"))
