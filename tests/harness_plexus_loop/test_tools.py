"""The small read-only tools a run leans on: the branch check before a restart, the row reader and the stats."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "harness" / "plexus_loop" / "tools"))

import ledger_row  # noqa: E402
import report_stats  # noqa: E402
import worktree_reads_diff  # noqa: E402


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True, capture_output=True)


def two_branches(tmp_path: Path) -> Path:
    repo = tmp_path
    missions = repo / "harness" / "plexus_loop" / "missions"
    missions.mkdir(parents=True)
    (missions / "m.toml").write_text('[mission]\ncontext = ["brief.md"]\n', encoding="utf-8")
    (repo / "brief.md").write_text("one\n", encoding="utf-8")
    (repo / "other.md").write_text("one\n", encoding="utf-8")
    git(repo, "init", "-q", "-b", "mission/m")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "first")
    git(repo, "branch", "plexus-loop/m")
    return repo


def test_the_branch_check_reads_none_when_the_context_files_match(tmp_path):
    assert worktree_reads_diff.differing(two_branches(tmp_path), "m") == (1, [])


def test_the_branch_check_names_a_brief_only_the_mission_has(tmp_path):
    repo = two_branches(tmp_path)
    (repo / "brief.md").write_text("two\n", encoding="utf-8")
    git(repo, "commit", "-qam", "brief")
    assert worktree_reads_diff.differing(repo, "m") == (1, ["brief.md"])


def test_the_branch_check_ignores_a_file_the_worktree_does_not_read(tmp_path):
    repo = two_branches(tmp_path)
    (repo / "other.md").write_text("two\n", encoding="utf-8")
    git(repo, "commit", "-qam", "other")
    assert worktree_reads_diff.differing(repo, "m") == (1, [])


def row(metric=None, failing=None, **more):
    return {"metric": metric, "failing": failing, **more}


def test_the_row_reader_compares_with_the_last_row_that_ran_the_metric():
    rows = [
        row(2.0, ["phase1.test_a.test_one", "phase1.test_a.test_two"]),
        row(None, None),  # a dropped attempt never reached the metric
        row(2.0, ["phase1.test_a.test_two", "phase1.test_b.test_three"]),
    ]
    assert ledger_row.changes(rows, 3) == {"passing_now": ["test_one"], "newly_failing": ["test_three"], "still_failing": ["test_two"]}


def test_the_row_reader_says_when_a_row_never_reached_the_metric():
    rows = [row(1.0, ["t"]), row(None, None, reason="worker: ollama call failed: URLError: refused", n=2)]
    assert ledger_row.changes(rows, 2) is None
    assert "no metric on this row, so no test changed" in ledger_row.describe(rows, 2)


def test_the_row_reader_keeps_a_parametrized_name_whole():
    assert ledger_row.short("phase1.test_t2::test_delta[one-0.3-wakes-once]") == "test_delta[one-0.3-wakes-once]"
    assert ledger_row.short("phase1.test_a.test_one[0.5]") == "test_one[0.5]"
    rows = [row(1.0, ["p.t::test_x[a-0.3-b]"]), row(1.0, ["p.t::test_y[c-0.3-b]"])]
    assert ledger_row.changes(rows, 2) == {"passing_now": ["test_x[a-0.3-b]"], "newly_failing": ["test_y[c-0.3-b]"], "still_failing": []}


def test_the_row_reader_never_reads_a_missing_wall_time_as_zero():
    assert "wall not measured" in ledger_row.describe([row(None, None, n=1)], 1)[1]


def test_a_row_with_no_server_is_not_an_attempt_and_stays_out_of_the_means():
    rows = [
        {"reason": "strict gain", "kept": True, "device": "cpu", "wall_s": 1800},
        {"reason": "worker: ollama call failed: URLError: refused", "device": "cpu", "wall_s": 3},
        {"reason": "worker: ollama call failed: RemoteDisconnected: closed", "device": "cpu", "wall_s": 199},
        {"reason": "worker: ollama call failed: timed out", "device": "cpu", "wall_s": 3600},
    ]
    assert len(report_stats.real_attempts(rows)) == 2
    assert report_stats.wall_by_device(rows)["cpu"] == (2, 45.0, 45.0)
    assert report_stats.drop_reasons(rows)["no server"] == 2
