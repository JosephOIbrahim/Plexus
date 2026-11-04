"""Publication gate v0: the path allowlist check."""

from pxr import Sdf


def check_allowlist(prim_path: Sdf.Path, allowlist: list[Sdf.Path]) -> bool:
    return any(prim_path.HasPrefix(allowed) for allowed in allowlist)
