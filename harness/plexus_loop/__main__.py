"""Command line: python -m harness.plexus_loop {run,check,stop} ..."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import gitops
from .loop import STATE_DIR, MissionRun, RefuseToStart
from .mission import MissionError, load_mission
from .profile import choose_profile, houdini_state


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="plexus_loop", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run one mission until it stops")
    r.add_argument("mission", type=Path)
    r.add_argument("--repo", type=Path, default=Path.cwd())
    c = sub.add_parser("check", help="validate a mission and show how the next attempt would run")
    c.add_argument("mission", type=Path)
    c.add_argument("--repo", type=Path, default=Path.cwd())
    s = sub.add_parser("stop", help="ask a running mission to stop after its current attempt")
    s.add_argument("--repo", type=Path, default=Path.cwd())
    args = ap.parse_args(argv)

    if args.cmd == "stop":
        state = gitops.repo_root(args.repo) / STATE_DIR
        state.mkdir(parents=True, exist_ok=True)
        (state / "STOP").touch()
        print(f"stop file written at {state / 'STOP'}; delete it before the next run")
        return 0

    try:
        mission = load_mission(args.mission)
    except (MissionError, OSError, ValueError) as e:
        print(f"mission file problem: {e}", file=sys.stderr)
        return 2

    if args.cmd == "check":
        state = houdini_state()
        p = choose_profile(mission.houdini, state)
        repo = gitops.repo_root(args.repo)
        missing = [x for x in mission.requires if not (repo / x).exists()]
        print(f"mission {mission.name}: worker {mission.worker.kind} ({mission.worker.model}), "
              f"{len(mission.gates)} gate(s), metric {mission.metric.kind}")
        print(f"Houdini: {state}; next attempt runs on the {p.device}")
        print("ready" if not missing else f"not ready: missing {', '.join(missing)}")
        return 0 if not missing else 2

    try:
        report = MissionRun(mission, args.repo).run()
    except RefuseToStart as e:
        print(f"not started: {e}", file=sys.stderr)
        return 2
    print(f"{report.stop_reason}: {report.baseline:g} -> {report.best:g} on {report.branch}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
