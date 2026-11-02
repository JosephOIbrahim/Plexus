"""Plexus schema plugin."""

from pathlib import Path

def plugin_dir() -> Path:
    return Path(__file__).parent
