"""Positive gate for the predicate: what the frozen tests register must compile.

Run 14 attempt 2 (d626436) was kept because test_bad_predicates_fail_at_registration passed,
and it passed because compile() rejected every grammar-v0 predicate, the valid ones included:
parse_clause never read the keyword, so every clause fell to a catch-all Err. A rejection-only
target cannot see that, and no error text exists for a known fix to match. This gate runs after
`core` has built plexus._core, in the attempt's worktree: once plexus/core/predicate.py exists,
the three predicates the frozen tests register under scope /Exchange/LookState must compile and
name the attribute in paths(), and the two bad ones must raise PredicateError. Before S3 lands
there is nothing to check and the gate passes. The compile and raise checks are the frozen tests'
own, asserted before the metric instead of two steps later (the frozen test sees the raise through
NeuronRuntime.register, which the brief says calls compile_predicate first); the paths() check is
the brief's Option A contract that S5's seed reads, asked as a set so once-in-order stays the
skeleton's rule, not this gate's.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Copies of frozen constants: _support.py LOOK and TEMP; T5 (changed), T2 (delta), T3 and T4
# (changed AND delta); the two bad ones are T2's. If Joe edits those tests, these follow.
SCOPE = "/Exchange/LookState"
TEMP = SCOPE + ".temperature"
VALID = [f"changed({TEMP})", f"delta({TEMP}) > 0.2", f"changed({TEMP}) AND delta({TEMP}) > 0.2"]
BAD = [f"delta({TEMP}) > 0.2 OR exists({TEMP})", "changed(/Exchange/Elsewhere.x)"]
NOT_YET = "predicate_smoke: plexus/core/predicate.py does not exist yet; nothing to check"
DOES_NOT_COMPILE = "a predicate the frozen tests register does not compile"


def main(root: Path | None = None) -> int:
    root = root or Path.cwd()
    if not (root / "plexus" / "core" / "predicate.py").is_file():
        print(NOT_YET)
        return 0
    sys.path.insert(0, str(root))
    try:
        from plexus.core.predicate import PredicateError, compile_predicate
    except Exception as e:  # noqa: BLE001 - any import failure is the finding
        print(f"predicate_smoke: cannot import plexus.core.predicate: {type(e).__name__}: {e}")
        return 1
    bad = 0
    for src in VALID:
        try:
            pred = compile_predicate(src, SCOPE)
        except Exception as e:  # noqa: BLE001 - the error type is part of the report
            print(f"predicate_smoke: {DOES_NOT_COMPILE}: {src!r} -> {type(e).__name__}: {e}")
            bad += 1
            continue
        try:
            paths = list(pred.paths())
        except Exception as e:  # noqa: BLE001
            print(f"predicate_smoke: paths() of {src!r} raised {type(e).__name__}: {e}")
            bad += 1
            continue
        if set(paths) != {TEMP}:
            print(f"predicate_smoke: paths() of {src!r} is {paths!r}; expected it to name {TEMP!r} and nothing else")
            bad += 1
    for src in BAD:
        try:
            compile_predicate(src, SCOPE)
        except PredicateError:
            continue
        except Exception as e:  # noqa: BLE001
            print(f"predicate_smoke: {src!r} raised {type(e).__name__}, not PredicateError")
            bad += 1
            continue
        print(f"predicate_smoke: {src!r} compiled; it must raise PredicateError")
        bad += 1
    if bad:
        print(f"predicate_smoke: {bad} check(s) failed")
        return 1
    print("predicate_smoke: the frozen tests' predicates compile and the bad ones raise PredicateError")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
