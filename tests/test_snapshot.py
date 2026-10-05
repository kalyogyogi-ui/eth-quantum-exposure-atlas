"""Snapshot directory and manifest."""
import json
import subprocess
from datetime import datetime, timezone

import pytest

from atlas import snapshot as S


def outputs(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "02_exposed_eth_summary.csv").write_text("eth_in_eoas,data_freshness_last_tx\n1,2026-10-04 23:59:59 UTC\n")
    (out / "summary.json").write_text("{}")
    (out / "SUMMARY.md").write_text("# s\n")
    (out / "verify.json").write_text("{}")
    (out / "bq_ledger.jsonl").write_text("")
    (out / "notes.txt").write_text("not copied")
    return out


JOBS = [
    {"utc": "2026-10-05T01:00:00+00:00", "label": "01", "billed_bytes": 100, "job_id": "a", "status": "ok"},
    {"utc": "2026-10-05T02:00:00+00:00", "label": "01", "billed_bytes": 120, "job_id": "b", "status": "ok"},
    {"utc": "2026-10-05T03:00:00+00:00", "label": "05", "billed_bytes": 50, "job_id": None, "status": "error"},
    {"utc": "2026-10-05T04:00:00+00:00", "label": "V1", "billed_bytes": 7, "job_id": "c", "status": "ok"},
]


def test_manifest(tmp_path):
    out = outputs(tmp_path)
    dest = S.make(out, tmp_path / "snaps", "2026-10-05", "abc123", False, JOBS,
                  now=datetime(2026, 10, 5, 12, tzinfo=timezone.utc))
    m = json.loads((dest / "manifest.json").read_text())
    assert dest == tmp_path / "snaps" / "2026-10-05"
    assert m["git_commit"] == "abc123" and m["git_dirty"] is False
    assert m["data_freshness_last_tx"] == "2026-10-04 23:59:59 UTC"
    assert m["bytes_billed"] == {"01": 120, "V1": 7} and m["bytes_billed_total"] == 127  # latest ok per step
    assert set(m["files_sha256"]) == {"02_exposed_eth_summary.csv", "summary.json", "SUMMARY.md", "verify.json"}
    assert m["files_sha256"]["SUMMARY.md"] == S.sha256(dest / "SUMMARY.md")
    assert not (dest / "notes.txt").exists() and not (dest / "bq_ledger.jsonl").exists()


def test_refuses_without_verify(tmp_path):
    out = outputs(tmp_path)
    (out / "verify.json").unlink()
    with pytest.raises(S.SnapshotError, match="verify.json"):
        S.make(out, tmp_path / "snaps", "2026-10-05", "abc", False, [])


def test_refuses_dirty_tree_and_overwrite(tmp_path):
    out = outputs(tmp_path)
    with pytest.raises(S.SnapshotError, match="uncommitted"):
        S.make(out, tmp_path / "snaps", "2026-10-05", "abc", True, [])
    S.make(out, tmp_path / "snaps", "2026-10-05", "abc", True, [], allow_dirty=True)
    with pytest.raises(S.SnapshotError, match="exists"):
        S.make(out, tmp_path / "snaps", "2026-10-05", "abc", False, [])
    S.make(out, tmp_path / "snaps", "2026-10-05", "abc", False, [], force=True)


def test_rejects_bad_date(tmp_path):
    with pytest.raises(ValueError):
        S.make(outputs(tmp_path), tmp_path / "snaps", "05-10-2026", "abc", False, [])


def test_git_state(tmp_path):
    git = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q")
    (tmp_path / "f").write_text("1")
    git("add", "f")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x")
    commit, dirty = S.git_state(tmp_path)
    assert len(commit) == 40 and dirty is False
    (tmp_path / "f").write_text("2")
    assert S.git_state(tmp_path)[1] is True
