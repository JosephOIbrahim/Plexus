"""Spec v2.1 §10 T8: the core is blind to the engine.

Engine vocabulary (sampler terms, ComfyUI node class names, ComfyUI's job id)
may appear only inside the Cozy organ. Everything else under plexus/ and the
Rust crates must not know ComfyUI exists.
"""

from __future__ import annotations

import re

from tests.acceptance._support import REPO

ENGINE_TERMS = re.compile(
    r"KSampler|\bcfg\b|\bprompt_id\b|CheckpointLoaderSimple|CLIPTextEncode|VAEDecode|VAEEncode"
    r"|EmptyLatentImage|SaveImage|LoadImage|LoraLoader|ControlNetApply|class_type"
)
# Rust's own conditional-compilation syntax is not the sampler's cfg.
RUST_CFG = re.compile(r"#!?\[cfg(_attr)?\(|\bcfg!\(")
SOURCE = {".py", ".pyi", ".rs", ".usda", ".json", ".toml"}


def _allowed(rel: str) -> bool:
    return rel == "plexus/organs/cozy.py" or rel.startswith("plexus/organs/cozy/")


def _files():
    for top in ("plexus", "crates"):
        root = REPO / top
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            rel = p.relative_to(REPO).as_posix()
            if p.is_file() and p.suffix in SOURCE and "/target/" not in rel and not _allowed(rel):
                yield rel, p


def test_core_exists_so_blindness_is_not_vacuous():
    core = REPO / "plexus" / "core"
    assert core.is_dir() and any(core.rglob("*.py")), "plexus/core must exist before T8 can pass"


def test_no_engine_terms_outside_the_cozy_organ():
    hits = []
    for rel, p in _files():
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if p.suffix == ".rs":
                line = RUST_CFG.sub("", line)
            m = ENGINE_TERMS.search(line)
            if m:
                hits.append(f"{rel}:{n}: {m.group(0)}")
    assert hits == [], "engine vocabulary leaked into the core:\n" + "\n".join(hits)
