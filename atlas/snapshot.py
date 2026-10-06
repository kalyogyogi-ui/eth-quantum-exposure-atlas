"""Freeze the current outputs into data/snapshots/YYYY-MM-DD/ with a manifest.

The manifest records what a reader needs to trust or reproduce the numbers: the git commit
that produced them, the data-freshness timestamp, the bytes BigQuery billed per step, and the
SHA-256 of every file in the snapshot.
"""
import csv
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import __version__

REQUIRED = ("summary.json", "SUMMARY.md", "verify.json")
SUFFIXES = (".csv", ".json", ".md")


class SnapshotError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_state(repo: Path) -> tuple[str, bool]:
    """(commit hash, whether tracked files have uncommitted changes)."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout
    return git("rev-parse", "HEAD").strip(), bool(git("status", "--porcelain", "--untracked-files=no").strip())


def data_freshness(out_dir: Path) -> str | None:
    path = out_dir / "02_exposed_eth_summary.csv"
    if not path.exists() or not path.stat().st_size:
        return None
    rows = list(csv.DictReader(path.open()))
    return rows[0].get("data_freshness_last_tx") if rows else None


def latest_jobs(entries: list[dict]) -> dict:
    """The most recent successful job per step label: the run that produced the current files."""
    jobs = {}
    for e in entries:
        if e.get("status") == "ok":
            jobs[e["label"]] = e
    return dict(sorted(jobs.items()))


def make(out_dir: Path, dest_root: Path, date: str, commit: str, dirty: bool, ledger_entries: list[dict],
         allow_dirty: bool = False, force: bool = False, now=None) -> Path:
    missing = [f for f in REQUIRED if not (out_dir / f).exists()]
    if missing:
        raise SnapshotError(f"missing in {out_dir}: {', '.join(missing)}; run summarize and verify first")
    if dirty and not allow_dirty:
        raise SnapshotError("uncommitted changes to tracked files: the commit hash would not describe "
                            "the code that ran; commit first or pass --allow-dirty")
    datetime.strptime(date, "%Y-%m-%d")  # raises ValueError on a malformed date
    dest = dest_root / date
    if dest.exists():
        if not force:
            raise SnapshotError(f"{dest} already exists; pass --force to replace it")
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    files = {}
    for src in sorted(out_dir.iterdir()):
        if src.is_file() and src.suffix in SUFFIXES:
            shutil.copy2(src, dest / src.name)
            files[src.name] = sha256(dest / src.name)

    jobs = latest_jobs(ledger_entries)
    manifest = {
        "snapshot_date": date,
        "created_utc": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
        "method_version": __version__,
        "git_commit": commit,
        "git_dirty": dirty,
        "data_freshness_last_tx": data_freshness(out_dir),
        "bytes_billed": {label: int(e["billed_bytes"]) for label, e in jobs.items()},
        "bytes_billed_total": sum(int(e["billed_bytes"]) for e in jobs.values()),
        "bigquery_jobs": list(jobs.values()),
        "files_sha256": files,
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return dest
