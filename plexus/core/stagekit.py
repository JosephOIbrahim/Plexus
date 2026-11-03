"""Project layer creation."""

from pathlib import Path
from pxr import Sdf

def create_project(path: Path, exchange: Path, project_id: str) -> Path:
    """Writes a project root layer whose def /Exchange carries Sdf.Reference(<exchange.usda path>, '/Exchange') with an explicit prim path, because without one or a defaultPrim on exchange.usda B gets an unresolved-reference error and composes nothing; and whose /Project has PlexusProjectAPI with plexus:projectId."""
    from pathlib import Path
    
    layer = Sdf.Layer.FindOrOpen(str(path)) or Sdf.Layer.CreateNew(str(path))
    
    # Create the Exchange prim with reference
    exchange_prim = layer.GetPrimAtPath("/Exchange") or Sdf.CreatePrimInLayer(layer, "/Exchange")
    exchange_prim.specifier = Sdf.SpecifierDef
    
    # Add reference to the exchange root
    ref = Sdf.Reference(str(exchange), "/Exchange")
    exchange_prim.referenceList.Prepend(ref)
    
    # Create Project prim with PlexusProjectAPI
    project_prim = layer.GetPrimAtPath("/Project") or Sdf.CreatePrimInLayer(layer, "/Project")
    project_prim.specifier = Sdf.SpecifierDef
    
    # Apply the API schema and set plexus:projectId
    project_prim.SetInfo("apiSchemas", Sdf.TokenListOp.Create(prependedItems=["PlexusProjectAPI"]))
    
    # Add plexus:projectId attribute
    attr = Sdf.AttributeSpec(project_prim, "plexus:projectId", Sdf.ValueTypeNames.String)
    attr.default = project_id
    
    layer.Save()
    return path
