"""Frozen guard: the import-layer rules from docs/plexus/NEXTGEN_SCAFFOLD_PLAN.md §2.

Joe's file (frozen, like everything under tests/acceptance/). The harness runs it as the
`layers` gate before every attempt's build and tests. It replaces the interim copy that
lived at harness/plexus_loop/guards/test_layers.py; the rules and code are the same.
It passes trivially while plexus/ and crates/ are empty.

Rules:
- Python: no import cycles among plexus modules ("from pkg import name" counts as importing
  the submodule pkg.name when that is a module); nothing under plexus/ imports agent.* or
  cognitive.*; plexus.core.* never imports plexus.organs.cozy; rank 0/1 modules and package
  __init__ files never import pxr. Imports are read at module AND function scope.
- Rust (crates/plexus-core/src): lib.rs only declares modules; a module may use crate::X
  only for a strictly lower rank; only py.rs names pyo3.
- Workspace: at most two members, plexus-core and plexus-usd; no build.rs.
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PLEXUS = REPO / "plexus"
CORE_SRC = REPO / "crates" / "plexus-core" / "src"

# Rank 0/1 modules and package __init__ files stay free of pxr, so `import plexus` is light.
NO_PXR = {
    "plexus", "plexus._core", "plexus.schema", "plexus.core", "plexus.membrane",
    "plexus.organs", "plexus.organs.protocol", "plexus.core.predicate", "plexus.core.ports",
}
RUST_RANK = {"error": 0, "outcome": 1, "predicate": 2, "budget": 2, "canon": 2, "graph": 2,
             "composer": 3, "py": 4}
WORKSPACE_ALLOWED = {"crates/plexus-core", "crates/plexus-usd"}


def _module_name(path: Path) -> str:
    rel = path.relative_to(REPO).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imports(path: Path) -> set[str]:
    """Every module this file imports, at any scope, with relative imports resolved."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    me = _module_name(path)
    pkg = me if path.name == "__init__.py" else me.rpartition(".")[0]
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg.split(".")
                base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                prefix = ".".join(base)
                mod = f"{prefix}.{node.module}" if node.module else prefix
            else:
                mod = node.module or ""
            found.add(mod)
            found.update(f"{mod}.{a.name}" for a in node.names)
    return {m for m in found if m}


def _python_graph() -> dict[str, set[str]]:
    if not PLEXUS.is_dir():
        return {}
    return {_module_name(p): _imports(p) for p in sorted(PLEXUS.rglob("*.py"))}


def test_guard_sees_the_repo():
    assert (REPO / "tests" / "acceptance" / "CONTRACT.md").is_file(), f"REPO resolved to {REPO}"


def test_python_never_imports_comfy_cozy():
    bad = [f"{m} imports {i}" for m, imps in _python_graph().items() for i in imps
           if i == "agent" or i.startswith("agent.") or i == "cognitive" or i.startswith("cognitive.")]
    assert bad == [], "Comfy-Cozy is a reference only (CLAUDE.md):\n" + "\n".join(bad)


def test_core_never_imports_the_cozy_organ():
    bad = [f"{m} imports {i}" for m, imps in _python_graph().items()
           if m.startswith("plexus.core") for i in imps if i.startswith("plexus.organs.cozy")]
    assert bad == [], "\n".join(bad)


def test_pxr_only_from_rank_two_up():
    bad = [f"{m} imports {i}" for m, imps in _python_graph().items() if m in NO_PXR
           for i in imps if i == "pxr" or i.startswith("pxr.")]
    assert bad == [], "these modules must stay free of pxr:\n" + "\n".join(bad)


def _targets(path: Path, mods: set[str]) -> set[str]:
    """The plexus modules this file depends on, for cycle detection.

    ``from pkg import name`` depends on ``pkg.name`` when that is a module (the idiomatic
    ``from . import axon``), and on ``pkg`` itself only when ``name`` is an attribute of it.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    me = _module_name(path)
    pkg = me if path.name == "__init__.py" else me.rpartition(".")[0]
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names if a.name in mods)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg.split(".")
                base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                mod = ".".join(base) + (f".{node.module}" if node.module else "")
            else:
                mod = node.module or ""
            for a in node.names:
                sub = f"{mod}.{a.name}"
                if sub in mods:
                    out.add(sub)
                elif mod in mods:
                    out.add(mod)
    out.discard(me)
    return out


def test_python_has_no_import_cycles():
    files = sorted(PLEXUS.rglob("*.py")) if PLEXUS.is_dir() else []
    mods = {_module_name(p) for p in files}
    edges = {_module_name(p): _targets(p, mods) for p in files}
    seen: dict[str, int] = {}
    cycle: list[str] = []

    def visit(m: str, stack: list[str]) -> bool:
        seen[m] = 1
        for n in sorted(edges[m]):
            if seen.get(n) == 1:
                cycle.extend(stack[stack.index(n):] + [n] if n in stack else [m, n])
                return True
            if n not in seen and visit(n, stack + [n]):
                return True
        seen[m] = 2
        return False

    for m in sorted(mods):
        if m not in seen and visit(m, [m]):
            break
    assert cycle == [], "import cycle: " + " -> ".join(cycle)


def _rust_files() -> list[Path]:
    return sorted(CORE_SRC.glob("*.rs")) if CORE_SRC.is_dir() else []


def test_rust_lib_only_declares_modules():
    lib = CORE_SRC / "lib.rs"
    if not lib.is_file():
        return
    allowed = re.compile(r"^\s*(//.*|#\[cfg\(feature = \"python\"\)\]|(pub(\(crate\))? )?mod \w+;)?\s*$")
    bad = [f"lib.rs:{n}: {line}" for n, line in enumerate(lib.read_text(encoding="utf-8").splitlines(), 1)
           if not allowed.match(line)]
    assert bad == [], "lib.rs may only declare modules:\n" + "\n".join(bad)


def test_rust_ranks_point_strictly_down():
    bad = []
    for f in _rust_files():
        name = f.stem
        if name == "lib":
            continue
        if name not in RUST_RANK:
            bad.append(f"{f.name}: not in the rank table (NEXTGEN_SCAFFOLD_PLAN.md §2.1); add it there first")
            continue
        text = f.read_text(encoding="utf-8")
        for used in sorted(set(re.findall(r"\bcrate::(\w+)", text))):
            if used not in RUST_RANK:
                bad.append(f"{f.name}: uses crate::{used}, which is not in the rank table")
            elif RUST_RANK[used] >= RUST_RANK[name]:
                bad.append(f"{f.name} (rank {RUST_RANK[name]}) uses crate::{used} (rank {RUST_RANK[used]})")
    assert bad == [], "\n".join(bad)


def test_only_py_rs_names_pyo3():
    bad = [f.name for f in _rust_files() if f.stem != "py" and re.search(r"\bpyo3\b", f.read_text(encoding="utf-8"))]
    assert bad == [], "only py.rs may name pyo3: " + ", ".join(bad)


def test_workspace_has_at_most_two_known_members_and_no_build_scripts():
    root = REPO / "Cargo.toml"
    if root.is_file():
        members = set(tomllib.loads(root.read_text(encoding="utf-8")).get("workspace", {}).get("members", []))
        assert members <= WORKSPACE_ALLOWED, f"unexpected workspace members: {sorted(members - WORKSPACE_ALLOWED)}"
    crates = REPO / "crates"
    scripts = sorted(p.relative_to(REPO).as_posix() for p in crates.glob("*/build.rs")) if crates.is_dir() else []
    assert scripts == [], f"no build.rs in crates/ (T8 scans cargo output words): {scripts}"
