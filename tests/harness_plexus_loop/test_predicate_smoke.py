"""The predicate_smoke gate: the frozen tests' predicates must compile once predicate.py exists.

Run 14 attempt 2 (d626436) rejected every predicate and was kept, because the only frozen test
S3 targets checks rejection. The gate runs the frozen tests' own predicates before the metric.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PY = sys.executable
SCRIPT = Path(__file__).resolve().parents[2] / "harness" / "plexus_loop" / "predicate_smoke.py"

ACCEPTS_AND_REJECTS = '''
class PredicateError(ValueError):
    pass


class _Pred:
    def __init__(self, src):
        self.src = src

    def paths(self):
        return ["/Exchange/LookState.temperature"]


def compile_predicate(source, scope):
    if " OR " in source or "/Exchange/Elsewhere" in source:
        raise PredicateError("bad")
    return _Pred(source)
'''

REJECTS_EVERYTHING = '''
class PredicateError(ValueError):
    pass


def compile_predicate(source, scope):
    raise PredicateError("Invalid clause")
'''

ACCEPTS_EVERYTHING = '''
class PredicateError(ValueError):
    pass


class _Pred:
    def paths(self):
        return ["/Exchange/LookState.temperature"]


def compile_predicate(source, scope):
    return _Pred()
'''


def _fake_package(root: Path, predicate_py: str) -> None:
    (root / "plexus" / "core").mkdir(parents=True)
    (root / "plexus" / "__init__.py").write_text('"""fake"""\n')
    (root / "plexus" / "core" / "__init__.py").write_text('"""fake"""\n')
    (root / "plexus" / "core" / "predicate.py").write_text(predicate_py)


def _run(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run([PY, "-I", str(SCRIPT)], cwd=root, capture_output=True, text=True,
                          errors="replace", check=False)


def test_before_s3_lands_there_is_nothing_to_check(tmp_path):
    r = _run(tmp_path)
    assert r.returncode == 0 and "nothing to check" in r.stdout


def test_a_predicate_module_that_rejects_everything_fails_the_gate_and_names_the_predicate(tmp_path):
    _fake_package(tmp_path, REJECTS_EVERYTHING)
    r = _run(tmp_path)
    assert r.returncode == 1
    assert "a predicate the frozen tests register does not compile" in r.stdout
    assert "changed(/Exchange/LookState.temperature)" in r.stdout and "Invalid clause" in r.stdout
    # the hint for this pattern names the keyword and scope rules, not the trim rule
    assert "parse_clause does not read the keyword" in r.stdout and "trim the rest" not in r.stdout


REJECTS_COMPARATORS = '''
class PredicateError(ValueError):
    pass


class _Pred:
    def paths(self):
        return ["/Exchange/LookState.temperature"]


def compile_predicate(source, scope):
    if " OR " in source or "/Exchange/Elsewhere" in source or ">" in source:
        raise PredicateError("bad")
    return _Pred()
'''


def test_a_module_that_compiles_changed_but_not_the_comparators_gets_the_trim_hint(tmp_path):
    _fake_package(tmp_path, REJECTS_COMPARATORS)
    r = _run(tmp_path)
    assert r.returncode == 1
    assert "trim the rest before parse_cmp and parse_number" in r.stdout
    assert "parse_clause does not read the keyword" not in r.stdout


def test_a_predicate_module_that_accepts_everything_fails_the_gate(tmp_path):
    _fake_package(tmp_path, ACCEPTS_EVERYTHING)
    r = _run(tmp_path)
    assert r.returncode == 1 and "it must raise PredicateError" in r.stdout


def test_the_frozen_predicates_compiling_and_the_bad_ones_raising_passes(tmp_path):
    _fake_package(tmp_path, ACCEPTS_AND_REJECTS)
    r = _run(tmp_path)
    assert r.returncode == 0, r.stdout
    assert "compile and the bad ones raise" in r.stdout
