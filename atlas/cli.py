"""Command line: plan -> run -> resolve -> price -> summarize -> verify.

  python -m atlas plan      --project P --work P.atlas
  python -m atlas run       --project P --work P.atlas
  python -m atlas resolve   --rpc-url URL
  python -m atlas price
  python -m atlas summarize
  python -m atlas verify    --project P --work P.atlas --rpc-url URL
"""
import argparse
import json
import sys
from pathlib import Path

from . import bq, steps
from .constants import DEFAULT_SRC

OUT = Path("out")


def log(msg: str) -> None:
    print(msg, flush=True)


def cmd_plan(a) -> int:
    client = bq.client(a.project)
    total = 0
    for s in steps.select(a.steps, a.include_optional):
        missing = [t for t in s.needs if not bq.table_exists(client, f"{a.work}.{t}")]
        if missing:
            log(f"[{s.key}] {s.title}: priced after earlier steps create {', '.join(missing)}")
            continue
        n = bq.dry_run_bytes(client, steps.load(s, a.work, a.src))
        total += n
        log(f"[{s.key}] {s.title}: {n / bq.GIB:,.1f} GiB  (~${bq.cost_usd(n):,.2f} on-demand)")
    log(f"Priced so far: {total / bq.GIB:,.1f} GiB (~${bq.cost_usd(total):,.2f}). "
        f"Later steps read only your small work tables unless marked optional.")
    return 0


def cmd_run(a) -> int:
    client = bq.client(a.project)
    bq.ensure_dataset(client, a.work)
    cap = int(a.max_gb * bq.GIB)
    for s in steps.select(a.steps, a.include_optional):
        log(f"[{s.key}] {s.title} ...")
        job, rows = bq.run(client, steps.load(s, a.work, a.src), cap)
        billed = job.total_bytes_billed or 0
        log(f"      billed {billed / bq.GIB:,.1f} GiB (~${bq.cost_usd(billed):,.2f})")
        if s.kind == "query":
            bq.write_csv(rows, OUT / s.output)
            log(f"      wrote {OUT / s.output} ({len(rows)} rows)")
    return 0


def cmd_resolve(a) -> int:
    from .proxies import resolve_file
    from .rpc import RPC
    stats = resolve_file(RPC(a.rpc_url), OUT / "06_permit_token_exposure.csv",
                         OUT / "token_classification.csv", a.top, log)
    (OUT / "resolve_stats.json").write_text(json.dumps(stats, indent=2))
    log(json.dumps(stats, indent=2))
    return 0


def cmd_price(a) -> int:
    from .pricing import price_tokens
    log(json.dumps(price_tokens(OUT / "token_classification.csv", OUT / "prices.csv"), indent=2))
    return 0


def cmd_summarize(a) -> int:
    from .summarize import build
    stats_path = OUT / "resolve_stats.json"
    stats = json.loads(stats_path.read_text()) if stats_path.exists() else None
    build(OUT, stats)
    log(f"wrote {OUT / 'summary.json'} and {OUT / 'SUMMARY.md'}")
    return 0


def cmd_verify(a) -> int:
    from .rpc import RPC
    from .verify import check_accounts, check_holdings, to_markdown
    client = bq.client(a.project)
    extra = {"top_n": a.top, "random_n": a.sample}
    _, acc_rows = bq.run(client, steps.load("verify_accounts_sample.sql", a.work, a.src, extra), int(5 * bq.GIB))
    rpc = RPC(a.rpc_url)
    acc = check_accounts(rpc, acc_rows)
    hold = None
    if bq.table_exists(client, f"{a.work}.token_holdings"):
        _, h_rows = bq.run(client, steps.load("verify_holdings_sample.sql", a.work, a.src, extra), int(20 * bq.GIB))
        hold = check_holdings(rpc, h_rows)
    (OUT / "verify.json").write_text(json.dumps({"accounts": acc, "holdings": hold}, indent=2, default=str))
    (OUT / "VERIFY.md").write_text(to_markdown(acc, hold))
    log(to_markdown(acc, hold))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="atlas", description="Ethereum Quantum Exposure Atlas")
    sub = p.add_subparsers(dest="cmd", required=True)

    def bq_args(sp):
        sp.add_argument("--project", required=True, help="your Google Cloud project id (billing)")
        sp.add_argument("--work", required=True, help="dataset for intermediate tables, e.g. myproj.atlas")
        sp.add_argument("--src", default=DEFAULT_SRC, help="source dataset (default: Google public data)")

    sp = sub.add_parser("plan", help="dry-run every step and print bytes and cost; runs nothing")
    bq_args(sp)
    sp.add_argument("--steps", nargs="*")
    sp.add_argument("--include-optional", action="store_true")
    sp.set_defaults(fn=cmd_plan)

    sp = sub.add_parser("run", help="run the BigQuery steps")
    bq_args(sp)
    sp.add_argument("--steps", nargs="*", help="e.g. --steps 01 02")
    sp.add_argument("--include-optional", action="store_true", help="also run the Permit2 logs scan")
    sp.add_argument("--max-gb", type=float, default=400, help="per-query billing cap (BigQuery enforces it)")
    sp.set_defaults(fn=cmd_run)

    sp = sub.add_parser("resolve", help="resolve proxy tokens over RPC and confirm permit support")
    sp.add_argument("--rpc-url", required=True)
    sp.add_argument("--top", type=int, default=2000, help="proxy candidates to resolve, by exposed holders")
    sp.set_defaults(fn=cmd_resolve)

    sp = sub.add_parser("price", help="fetch USD prices from DefiLlama")
    sp.set_defaults(fn=cmd_price)

    sp = sub.add_parser("summarize", help="write out/summary.json and out/SUMMARY.md")
    sp.set_defaults(fn=cmd_summarize)

    sp = sub.add_parser("verify", help="spot-check results against a live node")
    bq_args(sp)
    sp.add_argument("--rpc-url", required=True)
    sp.add_argument("--top", type=int, default=50)
    sp.add_argument("--sample", type=int, default=200)
    sp.set_defaults(fn=cmd_verify)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
