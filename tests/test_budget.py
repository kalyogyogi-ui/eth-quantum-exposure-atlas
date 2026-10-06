"""Monthly scan budget and the priced runner, on a fake BigQuery."""
import json
from datetime import datetime, timezone

import pytest

from atlas import bq, cli, steps
from atlas.budget import Budget, BudgetExceeded, run_priced

GIB = bq.GIB
OCT = lambda: datetime(2026, 10, 5, tzinfo=timezone.utc)


class Job:
    def __init__(self, billed):
        self.total_bytes_billed, self.job_id = billed, "job-1"


class FakeBQ:
    """Stands in for the atlas.bq module: records what would be run and with which cap."""
    GIB = GIB

    def __init__(self, estimate, billed=None, fail=False):
        self.estimate, self.billed, self.fail, self.runs = estimate, billed, fail, []

    def dry_run_bytes(self, client, sql):
        return self.estimate

    def run(self, client, sql, cap):
        self.runs.append(cap)
        if self.fail:
            raise RuntimeError("job failed")
        return Job(self.billed if self.billed is not None else self.estimate), [{"x": 1}]


def ledger_with(path, *entries):
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))


def test_spent_counts_only_this_month(tmp_path):
    ledger_with(tmp_path / "l.jsonl",
                {"utc": "2026-09-30T23:59:00+00:00", "label": "01", "billed_bytes": 500 * GIB, "status": "ok"},
                {"utc": "2026-10-01T00:01:00+00:00", "label": "04", "billed_bytes": 100 * GIB, "status": "ok"})
    b = Budget(tmp_path / "l.jsonl", 900 * GIB, now=OCT)
    assert b.spent_this_month() == 100 * GIB and b.remaining() == 800 * GIB


def test_refuses_before_running_when_over_budget(tmp_path):
    ledger_with(tmp_path / "l.jsonl",
                {"utc": "2026-10-01T00:00:00+00:00", "label": "01", "billed_bytes": 850 * GIB, "status": "ok"})
    fake = FakeBQ(estimate=60 * GIB)
    with pytest.raises(BudgetExceeded):
        run_priced(None, Budget(tmp_path / "l.jsonl", 900 * GIB, now=OCT), "05", "SQL", 400 * GIB,
                   bqmod=fake, log=lambda m: None)
    assert fake.runs == []


def test_refuses_above_per_query_cap(tmp_path):
    fake = FakeBQ(estimate=500 * GIB)
    with pytest.raises(BudgetExceeded):
        run_priced(None, Budget(tmp_path / "l.jsonl", 900 * GIB, now=OCT), "05", "SQL", 400 * GIB,
                   bqmod=fake, log=lambda m: None)
    assert fake.runs == []


def test_billing_cap_is_remaining_budget_and_job_is_recorded(tmp_path):
    ledger_with(tmp_path / "l.jsonl",
                {"utc": "2026-10-01T00:00:00+00:00", "label": "01", "billed_bytes": 700 * GIB, "status": "ok"})
    b = Budget(tmp_path / "l.jsonl", 900 * GIB, now=OCT)
    fake = FakeBQ(estimate=150 * GIB, billed=151 * GIB)
    rows, entry = run_priced(None, b, "04", "SQL", 400 * GIB, bqmod=fake, log=lambda m: None)
    assert fake.runs == [200 * GIB]            # min(per-query cap, budget left)
    assert entry["billed_bytes"] == 151 * GIB and entry["label"] == "04" and entry["job_id"] == "job-1"
    assert b.spent_this_month() == 851 * GIB and rows == [{"x": 1}]


def test_failed_job_is_recorded_at_its_estimate(tmp_path):
    b = Budget(tmp_path / "l.jsonl", 900 * GIB, now=OCT)
    with pytest.raises(RuntimeError):
        run_priced(None, b, "05", "SQL", 400 * GIB, bqmod=FakeBQ(estimate=10 * GIB, fail=True), log=lambda m: None)
    (e,) = b.entries()
    assert e["status"] == "error" and e["billed_bytes"] == 10 * GIB


def patch_bq(monkeypatch, tmp_path, estimate=GIB):
    """Patch atlas.bq for CLI tests: every work table exists, every query scans `estimate`."""
    calls = {"dry": [], "run": []}
    monkeypatch.setattr(bq, "client", lambda project: object())
    monkeypatch.setattr(bq, "table_exists", lambda c, t: True)
    monkeypatch.setattr(bq, "ensure_dataset", lambda c, w: None)
    monkeypatch.setattr(bq, "dry_run_bytes", lambda c, sql: calls["dry"].append(sql) or estimate)
    monkeypatch.setattr(bq, "run", lambda c, sql, cap: calls["run"].append(sql) or (Job(estimate), []))
    monkeypatch.setattr(cli, "OUT", tmp_path)
    return calls


def test_plan_prices_the_verify_queries(monkeypatch, tmp_path):
    calls = patch_bq(monkeypatch, tmp_path)
    assert cli.main(["plan", "--project", "p", "--work", "p.w", "--ledger", str(tmp_path / "l.jsonl")]) == 0
    assert len(calls["dry"]) == len(steps.select(None, False)) + len(steps.VERIFY_STEPS)
    assert any("FARM_FINGERPRINT(CONCAT(token, holder))" in sql for sql in calls["dry"])
    assert calls["run"] == []


def test_run_dry_runs_each_query_and_stops_at_budget(monkeypatch, tmp_path):
    calls = patch_bq(monkeypatch, tmp_path, estimate=400 * GIB)
    rc = cli.main(["run", "--project", "p", "--work", "p.w", "--ledger", str(tmp_path / "l.jsonl"),
                   "--budget-gb", "900"])
    assert rc == 2                              # 01 and 02 fit (800 GiB); 03 would pass 900
    assert len(calls["run"]) == 2 and len(calls["dry"]) == 3
    labels = [json.loads(line)["label"] for line in (tmp_path / "l.jsonl").read_text().splitlines()]
    assert labels == ["01", "02"]
