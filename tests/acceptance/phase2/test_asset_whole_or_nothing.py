"""Frozen: a record whose value has the wrong type for its attribute raises, and leaves nothing of itself in the file.

CONTRACT says a value that cannot land raises with nothing authored. test_organ_surface.py reads that for a seed past Int64 and a missing key, and both
fail before the lock. A value of the wrong type fails later, inside the ChangeBlock, after the attributes before it are set, and the neuron's own flag
Save then writes half an asset to disk that composes as if whole. The adversary on O2's keep, 6b7f657, found that for each case below.
"""
from __future__ import annotations

import pytest

from tests.acceptance.phase2.test_organ_surface import ASSET_PRIM, WHOLE_PRIM, asset_record, on_disk, wake

WRONG = {
    "an engineJobId that is not a string": {"engineJobId": 123},
    "modelHashes that are not strings": {"modelHashes": [1, 2]},
    "a colorspace that is not a token": {"colorspace": 5},
    "a createdAt that is not a string": {"createdAt": 5},
}


@pytest.mark.parametrize("broken", sorted(WRONG))
def test_a_value_of_the_wrong_type_raises_with_nothing_in_the_file(slice_, tmp_path, broken):
    whole = asset_record(tmp_path)
    bad = asset_record(tmp_path)
    bad.metadata.update(WRONG[broken])
    returned = []

    def act(ctx):
        ctx.author_asset(WHOLE_PRIM, whole)  # a reply that lands nothing must not pass here: this one has to land
        returned.append(True)
        ctx.author_asset(ASSET_PRIM, bad)
        returned.append(True)

    rt, _handle, raised = wake(slice_, act)
    assert returned, f"ctx.author_asset raised {type(raised).__name__}: {raised} on a whole record. CONTRACT: ctx.author_asset(prim_path, record) takes a record holding the five metadata keys."
    assert on_disk(rt, WHOLE_PRIM), "A whole record's asset is not in the file, so nothing here can say a bad one was stopped."
    assert len(returned) == 1 and raised is not None, f"CONTRACT: a value that cannot land raises, and ctx.author_asset returned with {broken}."
    assert on_disk(rt, ASSET_PRIM) == {}, (
        f"Half a record is in the file with {broken}, and it composes as if whole. Set every value on a prim in a scratch Sdf.Layer.CreateAnonymous() "
        "before taking rt._lock, so a value that cannot land raises there with nothing authored in the edit layer."
    )
