"""T1b · Propagation across processes (pending, not one of the frozen 18).

T1 measures A to B in one process, as Spec v2.1 §9 says. Joe's film shows
two processes, and the Spec never says how a change made in one process
reaches another's axon. Until that event transport and its latency budget
are decided, this test only records what it will check:

- Project A authors /Exchange/LookState.temperature from its own process
  with plain Sdf and saves.
- Project B, in a second process, has a PlexusAxon on its stage.
- B's callback sees the new composed value within the budget chosen with
  the transport, p95 over 50 trials.

It lives outside phase1/ and phase2/ so no harness mission counts it.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="pending: event transport across processes is undecided (Blueprint v5.3 §14.3)"
)
def test_a_to_b_visibility_across_processes():
    raise AssertionError("write this once the event transport is decided")
