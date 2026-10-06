"""Thin BigQuery wrapper with a hard cost cap on every query."""
import csv
from pathlib import Path

GIB = 1024 ** 3
TIB = 1024 ** 4
# BigQuery on-demand list price per TiB scanned at the time of writing. Check
# https://cloud.google.com/bigquery/pricing before relying on it; the first
# 1 TiB per month has been free on the on-demand plan.
USD_PER_TIB = 6.25


CREDENTIALS_ENV = "GOOGLE_APPLICATION_CREDENTIALS_JSON"
SCOPES = ["https://www.googleapis.com/auth/bigquery"]


def client(project: str | None):
    """BigQuery client. Uses a service-account key held in $GOOGLE_APPLICATION_CREDENTIALS_JSON
    (the key's JSON text, for environments where files are awkward) when set, otherwise
    Application Default Credentials (`gcloud auth application-default login`)."""
    import json
    import os
    from google.cloud import bigquery  # imported lazily so tests run without it
    raw = os.environ.get(CREDENTIALS_ENV)
    if not raw:
        return bigquery.Client(project=project)
    from google.oauth2 import service_account
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        raise SystemExit(f"{CREDENTIALS_ENV} is set but is not valid JSON (paste the whole key file)") from None
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return bigquery.Client(project=project or info.get("project_id"), credentials=creds)


def ensure_dataset(bq, work: str, location: str = "US") -> None:
    """The public dataset lives in the US multi-region, so the work dataset must too."""
    from google.cloud import bigquery
    ds = bigquery.Dataset(work)
    ds.location = location
    bq.create_dataset(ds, exists_ok=True)


def table_exists(bq, table_id: str) -> bool:
    from google.api_core.exceptions import NotFound
    try:
        bq.get_table(table_id)
        return True
    except NotFound:
        return False


def dry_run_bytes(bq, sql: str) -> int:
    from google.cloud import bigquery
    cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    return bq.query(sql, job_config=cfg).total_bytes_processed


def run(bq, sql: str, max_bytes_billed: int):
    """Run a query; BigQuery itself refuses it if it would bill more than the cap."""
    from google.cloud import bigquery
    cfg = bigquery.QueryJobConfig(maximum_bytes_billed=max_bytes_billed)
    job = bq.query(sql, job_config=cfg)
    rows = job.result()
    return job, [dict(r.items()) for r in rows]


def cost_usd(n_bytes: int) -> float:
    return n_bytes / TIB * USD_PER_TIB


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        if not rows:
            f.write("")
            return
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})
