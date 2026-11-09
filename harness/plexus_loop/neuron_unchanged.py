"""The neuron_unchanged gate of mission organ. Every class, function and statement of plexus/core/neuron.py stands as the last kept commit has it, and the file may gain one method, _Ctx.author_asset.

Step O2 sends the file whole, and many of its lines are read by no frozen test: ctx.author's lock is one, and losing it kills the interpreter on two neurons. So this reads the code itself. It compares parsed code
and not text, because author_asset ends with the same lines author does, and a line-based read counts a lost Save as kept. Comments, blank lines, docstrings and the order of the module's imports do not count.

Run from the root of an attempt's worktree, where HEAD is the last kept commit and the reply is uncommitted. Exit 0 when the file passes. It changes nothing.

With no option the one name it lets in is _Ctx.author_asset, so mission organ's gate command runs as it always has. Each --may-add NAME replaces that set with the names given, so a later mission names its own one new method, as M2 does with --may-add NeuronRuntime.publish_organ.
"""
from __future__ import annotations

import argparse
import ast
import copy
import difflib
import subprocess
import sys
from pathlib import Path

FILE = "plexus/core/neuron.py"
MAY_ADD = {"_Ctx.author_asset"}
STATEMENTS = "<statements>"
SHOWN_LINES = 12


def _drop_docstrings(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                node.body = body[1:] or ([] if isinstance(node, ast.Module) else [ast.Pass()])


def parts(text: str) -> dict[str, list[str]]:
    """The code of a file by dotted name: each function whole, each class's header, and the statements between them in order, with the module's imports sorted."""
    tree = ast.parse(text)
    _drop_docstrings(tree)
    out: dict[str, list[str]] = {}

    def walk(body: list[ast.stmt], prefix: str) -> None:
        rest: list[str] = []
        imports: list[str] = []
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out[prefix + node.name] = ast.unparse(node).splitlines()
            elif isinstance(node, ast.ClassDef):
                header = copy.copy(node)
                header.body = [ast.Pass()]
                out[prefix + node.name] = ast.unparse(header).splitlines()
                walk(node.body, f"{prefix}{node.name}.")
            elif isinstance(node, (ast.Import, ast.ImportFrom)) and not prefix:
                imports.append(ast.unparse(node))
            else:
                rest.extend(ast.unparse(node).splitlines())
        out[prefix + STATEMENTS] = sorted(imports) + rest

    walk(tree.body, "")
    return out


def verdict(base: str, now: str, may_add: set[str] | frozenset[str] = frozenset(MAY_ADD)) -> tuple[list[str], list[str], list[str]]:
    """The names that changed, went or are new, against the last kept commit."""
    old, new = parts(base), parts(now)
    changed = [k for k in old if k in new and old[k] != new[k] and k not in may_add]
    gone = [k for k in old if k not in new and k not in may_add and old[k]]
    gained = [k for k in new if k not in old and k not in may_add and new[k]]
    return changed, gone, gained


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Exit 0 when plexus/core/neuron.py changes nothing against HEAD but the names it may add.")
    ap.add_argument("--may-add", action="append", metavar="NAME", default=None,
                    help="a dotted name the file may add or change, such as NeuronRuntime.publish_organ; repeatable; replaces the default _Ctx.author_asset")
    args = ap.parse_args(argv)
    may_add = set(args.may_add) if args.may_add else set(MAY_ADD)
    base = subprocess.run(["git", "show", f"HEAD:{FILE}"], capture_output=True, text=True, encoding="utf-8", check=True).stdout
    try:
        now = Path(FILE).read_text(encoding="utf-8")
        changed, gone, gained = verdict(base, now, may_add)
    except (OSError, SyntaxError) as e:
        print(f"{FILE}: cannot read this file: {e}")
        return 1
    if not (changed or gone or gained):
        print(f"{FILE}: every statement of the last kept commit stands")
        return 0
    # Mission organ's known fix matches the default line word for word, so only a named set changes the step's name.
    step = "O2" if may_add == MAY_ADD else "this step"
    print(f"{FILE}: {step} adds {' and '.join(sorted(may_add))} and changes nothing else. Start again from the copy of neuron.py in this prompt.")
    for label, names in (("changed", changed), ("gone", gone), ("new", gained)):
        if names:
            print(f"  {label}: {', '.join(names)}")
    old, new = parts(base), parts(now)
    for name in changed:
        diff = [x for x in difflib.unified_diff(old[name], new[name], lineterm="", n=0) if not x.startswith(("---", "+++", "@@"))]
        print(f"  in {name}:")
        for x in diff[:SHOWN_LINES]:
            print(f"    {x}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
