"""Monthly BigQuery scan budget, enforced before every query.

Every query goes through `run_priced`: it is dry-run first, refused if the bytes it would
scan do not fit in what is left of this month's budget, and then run with
maximum_bytes_billed set to the smaller of the per-query cap and the remaining budget, so
BigQuery itself refuses anything larger. Each job is appended to a JSON-lines ledger.

The ledger only knows about queries run through `atlas` with this ledger file. Queries run
elsewhere in the same Google Cloud project are not counted; a project-level custom quota on
query usage is the backstop for those.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import bq

DEFAULT_MONTHLY_GIB = 900.0   # headroom under the 1 TiB/month free on-demand allowance
ENV_MONTHLY_GIB = "ATLAS_MONTHLY_BUDGET_GIB"


class BudgetExceeded(RuntimeError):
    pass


def default_monthly_gib() -> float:
    return float(os.environ.get(ENV_MONTHLY_GIB, DEFAULT_MONTHLY_GIB))


class Budget:
    def __init__(self, ledger: Path, monthly_bytes: int, now=None):
        self.ledger = Path(ledger)
        self.monthly_bytes = int(monthly_bytes)
        self._now = now or (lambda: datetime.now(timezone.utc))

    def _month(self) -> str:
        return self._now().strftime("%Y-%m")

    def entries(self) -> list[dict]:
        if not self.ledger.exists():
            return []
        return [json.loads(line) for line in self.ledger.read_text().splitlines() if line.strip()]

    def spent_this_month(self) -> int:
        month = self._month()
        return sum(int(e["billed_bytes"]) for e in self.entries() if e["utc"].startswith(month))

    def remaining(self) -> int:
        return max(self.monthly_bytes - self.spent_this_month(), 0)

    def check(self, label: str, estimate: int) -> None:
        left = self.remaining()
        if estimate > left:
            raise BudgetExceeded(
                f"[{label}] would scan {estimate / bq.GIB:,.1f} GiB but only {left / bq.GIB:,.1f} GiB "
                f"of the {self.monthly_bytes / bq.GIB:,.0f} GiB monthly budget is left. Nothing was run.")

    def record(self, label: str, estimate: int, billed: int, job_id: str | None, status: str) -> dict:
        entry = {"utc": self._now().isoformat(timespec="seconds"), "label": label,
                 "estimate_bytes": int(estimate), "billed_bytes": int(billed),
                 "job_id": job_id, "status": status}
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger.open("a") as f:
            f.write(json.dumps(entry) + "\n")
        return entry


def run_priced(client, budget: Budget, label: str, sql: str, cap_bytes: int, bqmod=bq, log=print):
    """Dry-run, check the budget, run with a hard billing cap, record the bytes billed.

    Returns (rows, entry). A query that fails after starting is recorded at its estimate,
    so a failure can only make the ledger more conservative.
    """
    estimate = bqmod.dry_run_bytes(client, sql)
    budget.check(label, estimate)
    if estimate > cap_bytes:
        raise BudgetExceeded(f"[{label}] would scan {estimate / bq.GIB:,.1f} GiB, above the per-query "
                             f"cap of {cap_bytes / bq.GIB:,.1f} GiB. Nothing was run.")
    cap = min(cap_bytes, budget.remaining())
    log(f"      priced {estimate / bq.GIB:,.2f} GiB; billing cap {cap / bq.GIB:,.2f} GiB")
    try:
        job, rows = bqmod.run(client, sql, cap)
    except Exception:
        budget.record(label, estimate, estimate, None, "error")
        raise
    billed = job.total_bytes_billed or 0
    return rows, budget.record(label, estimate, billed, getattr(job, "job_id", None), "ok")
