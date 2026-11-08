"""A recognised target failure gets its fix from the brief quoted right under it.

Run 7 attempts 1-4 each failed T1 on `FindOrOpen` returning None in stagekit.create_project.
Each saw the error at the top of its prompt and none changed the line; S2 has moved forward
only when the fix was written down. The table puts the written fix next to the error.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from harness.plexus_loop.loop import KNOWN_FIX_CHARS, Attempt, build_prompt, known_fix_quotes
from harness.plexus_loop.mission import MissionError, load_mission, mission_from_dict

PY = sys.executable
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
REPO = Path(__file__).resolve().parents[2]
BRIEF = "docs/brief.md"
NULL_LAYER = ("tests.acceptance.phase1.test_t1::t\n[failure] pxr.Tf.ErrorException: Cannot create prim at "
              "path '/Exchange' in null or expired layer")


def _raw(fixes=None):
    return {
        "mission": {"name": "demo", "goal": "g", "requires": ["tests/acceptance"], "focus": ["plexus/**"],
                    "frozen": ["tests/acceptance/**"]},
        "metric": {"kind": "command", "cmd": [PY, "-c", "print(5)"]},
        "gates": [{"name": "ok", "cmd": [PY, "-c", "print('ok')"]}],
        "steps": [{"id": "S1", "targets": ["tests/acceptance/phase1/test_t1.py"], "text": "x"}],
        "router": {"kind": "first"},
        "known_fixes": fixes if fixes is not None else [
            {"match": "null or expired layer", "file": BRIEF, "anchor": "returns `None` for a missing file"},
            {"match": "NameError: name '(Sdf|Usd)' is not defined", "file": BRIEF, "anchor": "Import every"},
            {"match": "never seen", "file": BRIEF, "anchor": "no such anchor"},
        ],
    }


def _repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    (r / "docs").mkdir(parents=True)
    (r / "plexus").mkdir()
    (r / "tests" / "acceptance").mkdir(parents=True)
    (r / "tests" / "acceptance" / "f.txt").write_text("x")
    (r / BRIEF).write_text("# Brief\n\n- `FindOrOpen` returns `None` for a missing file, so write "
                           "`FindOrOpen(p) or CreateNew(p)`.\n- Import every `pxr` module a file names.\n")
    for args in (["init", "-q", "-b", "master"], ["add", "-A"], ["commit", "-q", "-m", "s"]):
        subprocess.run([*GIT, *args], cwd=r, check=True, capture_output=True)
    return r


def test_known_fixes_parse_and_bad_ones_are_refused():
    m = mission_from_dict(_raw())
    assert [k.anchor for k in m.known_fixes][:2] == ["returns `None` for a missing file", "Import every"]
    for bad in ([{"match": "(", "file": BRIEF, "anchor": "a"}], [{"match": "x", "file": "/abs", "anchor": "a"}],
                [{"match": "x", "file": "../up.md", "anchor": "a"}], [{"match": "", "file": BRIEF, "anchor": "a"}],
                [{"match": "x", "file": BRIEF}]):
        with pytest.raises(MissionError):
            mission_from_dict(_raw(bad))


def test_a_matching_failure_quotes_its_brief_line_once(tmp_path):
    m, r = mission_from_dict(_raw()), _repo(tmp_path)
    q = known_fix_quotes(m, r, [NULL_LAYER, NULL_LAYER])
    assert q == ["- `FindOrOpen` returns `None` for a missing file, so write `FindOrOpen(p) or CreateNew(p)`."]
    assert known_fix_quotes(m, r, ["t\n[failure] AssertionError: nothing known"]) == []


def test_a_missing_anchor_or_file_quotes_nothing(tmp_path):
    r = _repo(tmp_path)
    m = mission_from_dict(_raw([{"match": "null or expired layer", "file": "docs/gone.md", "anchor": "x"},
                                {"match": "null or expired layer", "file": BRIEF, "anchor": "absent anchor"}]))
    assert known_fix_quotes(m, r, [NULL_LAYER]) == []


def test_long_lines_are_clipped(tmp_path):
    r = _repo(tmp_path)
    (r / BRIEF).write_text("- LONG " + "y" * 2000 + "\n")
    m = mission_from_dict(_raw([{"match": "null or expired layer", "file": BRIEF, "anchor": "LONG"}]))
    (q,) = known_fix_quotes(m, r, [NULL_LAYER])
    assert q.startswith("- LONG") and len(q) == KNOWN_FIX_CHARS


def test_a_fix_deep_in_a_long_line_is_quoted_from_its_anchor(tmp_path):
    r = _repo(tmp_path)
    (r / BRIEF).write_text("- " + "earlier fact. " * 80 + "ANCHOR: write `a or b(p)` here.\n")
    m = mission_from_dict(_raw([{"match": "null or expired layer", "file": BRIEF, "anchor": "ANCHOR:"}]))
    (q,) = known_fix_quotes(m, r, [NULL_LAYER])
    assert q == "…ANCHOR: write `a or b(p)` here."


def test_two_fixes_on_one_line_quote_each_fix_once(tmp_path):
    r = _repo(tmp_path)
    (r / BRIEF).write_text("- FIX-A do a. FIX-B do b.\n")
    m = mission_from_dict(_raw([
        {"match": "null or expired layer", "file": BRIEF, "anchor": "FIX-A"},
        {"match": "null or expired layer", "file": BRIEF, "anchor": "FIX-A"},
        {"match": "ListProxy", "file": BRIEF, "anchor": "FIX-B"}]))
    q = known_fix_quotes(m, r, [NULL_LAYER, "t\n[failure] ListProxy_SdfSubLayerTypePolicy"])
    assert q == ["- FIX-A do a. FIX-B do b.", "…FIX-B do b."]


def test_known_fixes_must_be_tables():
    for bad in ("x", ["x"], [1]):
        with pytest.raises(MissionError, match="list of tables"):
            mission_from_dict(_raw(bad))


def test_the_quote_sits_under_the_target_failure_in_the_prompt(tmp_path):
    m, r = mission_from_dict(_raw()), _repo(tmp_path)
    a = Attempt(n=1, started=0.0, houdini="off", device="gpu", reason="no strict gain (5 vs best 5)",
                route="S1 via first", detail="the end of the run", target_failures=[NULL_LAYER])
    fb = build_prompt(m, r, 5, None, [a], 100000, step=m.steps[0]).split("## Why the last attempt was dropped", 1)[1]
    i_err, i_quote, i_out = fb.index("null or expired layer"), fb.index("> - `FindOrOpen` returns"), fb.index("the end of the run")
    assert i_err < i_quote < i_out
    assert "This is a known error" in fb


def test_a_failing_gate_quotes_the_fix_under_its_output(tmp_path):
    # Run 11 attempts 1-2: `cargo build` failed in the core gate, so there were no target
    # failures, and the brief's fix for the error it printed was never quoted.
    m, r = mission_from_dict(_raw()), _repo(tmp_path)
    a = Attempt(n=1, started=0.0, houdini="off", device="gpu", reason="gate 'ok' failed",
                detail="$ build\nerror: null or expired layer near the top\n... the end of the gate output")
    fb = build_prompt(m, r, 5, None, [a], 100000, step=m.steps[0]).split("## Why the last attempt was dropped", 1)[1]
    i_out, i_note, i_quote = fb.index("the end of the gate output"), fb.index("It is a known error"), \
        fb.index("> - `FindOrOpen` returns")
    assert i_out < i_note < i_quote
    assert fb.count("> - `FindOrOpen` returns") == 1


def test_a_gate_failure_without_a_known_error_quotes_nothing(tmp_path):
    m, r = mission_from_dict(_raw()), _repo(tmp_path)
    a = Attempt(n=1, started=0.0, houdini="off", device="gpu", reason="gate 'ok' failed",
                detail="$ build\nerror[E0425]: cannot find value `x` in this scope")
    p = build_prompt(m, r, 5, None, [a], 100000, step=m.steps[0])
    assert "known error" not in p


@pytest.mark.parametrize("reason", ["no strict gain (5 vs best 5)", "metric unavailable: boom",
                                    "tests went missing (3 collected, was 5)", "gate 'ok' failed twice"])
def test_only_a_failing_gate_matches_its_output(tmp_path, reason):
    # Other drops show the end of the metric run; matching it would quote fixes for tests of
    # later steps, which are expected to fail.
    m, r = mission_from_dict(_raw()), _repo(tmp_path)
    a = Attempt(n=1, started=0.0, houdini="off", device="gpu", reason=reason,
                detail="null or expired layer, from a later step's test")
    p = build_prompt(m, r, 5, None, [a], 100000, step=m.steps[0])
    assert "known error" not in p


def test_every_acceptance_known_fix_resolves_to_one_brief_line():
    m = load_mission(REPO / "harness" / "plexus_loop" / "missions" / "acceptance.toml")
    assert m.known_fixes
    for k in m.known_fixes:
        lines = (REPO / k.file).read_text(encoding="utf-8").splitlines()
        assert sum(k.anchor in ln for ln in lines) == 1, k.anchor
        re.compile(k.match)


def test_every_organ_known_fix_resolves_to_one_brief_line():
    m = load_mission(REPO / "harness" / "plexus_loop" / "missions" / "organ.toml")
    assert m.known_fixes
    for k in m.known_fixes:
        lines = (REPO / k.file).read_text(encoding="utf-8").splitlines()
        assert sum(k.anchor in ln for ln in lines) == 1, k.anchor
        re.compile(k.match)


def test_runtime_did_not_go_idle_quotes_no_known_fix():
    # Retired Nov 4: the kept axon is right, and on row 86 the cause was a reply that dropped _run_action.
    m = load_mission(REPO / "harness" / "plexus_loop" / "missions" / "acceptance.toml")
    assert not known_fix_quotes(m, REPO, ["t\n[failure] AssertionError: runtime did not go idle"])


def test_the_real_null_layer_quote_carries_the_whole_fix():
    m = load_mission(REPO / "harness" / "plexus_loop" / "missions" / "acceptance.toml")
    quotes = known_fix_quotes(m, REPO, ["t\n[failure] Cannot create prim at path '/Exchange' in null or expired layer"])
    assert any("or Sdf.Layer.CreateNew(p)`" in q and "create_project" in q for q in quotes), quotes


@pytest.mark.parametrize("error, anchor", [
    ("Cannot create prim at path '/Exchange' in null or expired layer", "`FindOrOpen` returns `None`"),
    ("AttributeError: 'Prim' object has no attribute 'AddReference'", "`Usd.Prim` has no `AddReference`"),
    ("ApplyAPI: Cannot find a valid schema for the provided schema identifier 'PlexusProjectAPI'",
     "Never call `Usd.Prim.ApplyAPI`"),
    ("AttributeError: module 'pxr.Usd' has no attribute 'Plug'", "`Usd.Plug` does not exist"),
    ("AttributeError: type object 'Notice' has no attribute 'ObjectsChanged'", "`Tf.Notice.ObjectsChanged` does not exist"),
    ("None.None(Layer, ListProxy_SdfSubLayerTypePolicy) did not match C++ signature", "`layer.subLayerPaths` is a live"),
    ("NameError: name 'Usd' is not defined", "Import every `pxr` module"),
    # the S4 block's reviewers asked for this one, and S9 resends axon.py whole
    ("AttributeError: 'PlexusAxon' object has no attribute 'idle'", "Expose `idle() -> bool`"),
    # run 16 attempts 1 and 2: T5 target failure, as the junit report carries it
    ("AssertionError: assert invalid null prim\n +  where invalid null prim = GetPrimAtPath('/Exchange/lookNeuron/Hints')",
     "The dispatcher lives in `_on_event`"),
])
def test_each_real_run_error_finds_its_fix_in_the_real_brief(error, anchor):
    m = load_mission(REPO / "harness" / "plexus_loop" / "missions" / "acceptance.toml")
    quotes = known_fix_quotes(m, REPO, [f"t\n[failure] {error}"])
    assert any(anchor in q for q in quotes), (error, quotes)
