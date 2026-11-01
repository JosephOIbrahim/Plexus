"""plexus-loop: Plexus's own build harness (Blueprint v5.2 §12).

Written fresh for Plexus. It runs one mission at a time, lets a local model
make attempts in throwaway git worktrees, keeps only strict gains on its own
branch, steps aside for Houdini, and leaves promotion to Joe.
"""

from .loop import MissionRun, RefuseToStart, RunReport
from .mission import Mission, MissionError, load_mission

__all__ = ["Mission", "MissionError", "MissionRun", "RefuseToStart", "RunReport", "load_mission"]
