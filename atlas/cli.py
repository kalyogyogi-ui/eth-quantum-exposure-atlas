"""Command line: plan -> run -> resolve -> price -> summarize -> verify.

  python -m atlas plan      --project P --work P.atlas
  python -m atlas run       --project P --work P.atlas
  python -m atlas resolve   --rpc-url URL
  python -m atlas price
  python -m atlas summarize
  python -m atlas verify    --project P --work P.atlas --rpc-url URL
  python -m atlas snapshot
  python -m atlas orgs      --rpc-url URL [--block N] [--slug lido ...]
  python -m atlas attest    sign-snapshot DIR | sign-org REPORT.json | verify FILE.attestation.json

Every BigQuery query is dry-run first and checked against the monthly budget
(--budget-gb, or ATLAS_MONTHLY_BUDGET_GIB); jobs are logged to out/bq_ledger.jsonl.
"""
import argparse
import json
import sys
from pathlib import Path

from . import bq, steps
from .budget import Budget, BudgetExceeded, default_monthly_gib, run_priced
from .constants import DEFAULT_SRC

OUT = Path("out")
LEDGER = OUT / "bq_ledger.jsonl"
SNAPSHOTS = Path("data") / "snapshots"


def log(msg: str) -> None:
    print(msg, flush=True)


def budget_from(a) -> Budget:
    return Budget(Path(a.ledger), int(a.budget_gb * bq.GIB))


def cmd_plan(a) -> int:
    client = bq.client(a.project)
    budget = budget_from(a)
    plan = steps.select(a.steps, a.include_optional)
    if not a.steps:
        plan += steps.VERIFY_STEPS
    extra = steps.verify_extra(a.top, a.sample)
    total, unpriced = 0, []
    for s in plan:
        missing = [t for t in s.needs if not bq.table_exists(client, f"{a.work}.{t}")]
        if missing:
            unpriced.append(s.key)
            log(f"[{s.key}] {s.title}: priced after earlier steps create {', '.join(missing)}")
            continue
        n = bq.dry_run_bytes(client, steps.load(s, a.work, a.src, extra))
        total += n
        log(f"[{s.key}] {s.title}: {n / bq.GIB:,.2f} GiB  (~${bq.cost_usd(n):,.2f} at on-demand list price)")
    spent, left = budget.spent_this_month(), budget.remaining()
    log(f"Priced: {total / bq.GIB:,.2f} GiB. Ledger this month: {spent / bq.GIB:,.2f} GiB spent, "
        f"{left / bq.GIB:,.2f} GiB left of the {budget.monthly_bytes / bq.GIB:,.0f} GiB budget.")
    if total > left:
        log("DOES NOT FIT the remaining budget. Run fewer steps or wait for next month.")
    if unpriced:
        log(f"Not yet priced: {' '.join(unpriced)}. Run plan again after the steps they depend on.")
    return 0


def cmd_run(a) -> int:
    client = bq.client(a.project)
    budget = budget_from(a)
    bq.ensure_dataset(client, a.work)
    cap = int(a.max_gb * bq.GIB)
    for s in steps.select(a.steps, a.include_optional):
        log(f"[{s.key}] {s.title} ...")
        try:
            rows, entry = run_priced(client, budget, s.key, steps.load(s, a.work, a.src), cap, log=log)
        except BudgetExceeded as e:
            log(str(e))
            return 2
        billed = entry["billed_bytes"]
        log(f"      billed {billed / bq.GIB:,.2f} GiB (~${bq.cost_usd(billed):,.2f} at list price); "
            f"{budget.remaining() / bq.GIB:,.2f} GiB of budget left")
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
    budget = budget_from(a)
    extra = steps.verify_extra(a.top, a.sample)
    v_acc, v_hold = steps.VERIFY_STEPS
    try:
        acc_rows, _ = run_priced(client, budget, v_acc.key, steps.load(v_acc, a.work, a.src, extra),
                                 int(5 * bq.GIB), log=log)
        h_rows = None
        if bq.table_exists(client, f"{a.work}.token_holdings"):
            h_rows, _ = run_priced(client, budget, v_hold.key, steps.load(v_hold, a.work, a.src, extra),
                                   int(20 * bq.GIB), log=log)
    except BudgetExceeded as e:
        log(str(e))
        return 2
    rpc = RPC(a.rpc_url)
    acc = check_accounts(rpc, acc_rows)
    hold = check_holdings(rpc, h_rows) if h_rows is not None else None
    (OUT / "verify.json").write_text(json.dumps({"accounts": acc, "holdings": hold}, indent=2, default=str))
    (OUT / "VERIFY.md").write_text(to_markdown(acc, hold))
    log(to_markdown(acc, hold))
    return 0


def cmd_snapshot(a) -> int:
    from datetime import datetime, timezone
    from .snapshot import SnapshotError, git_state, make
    commit, dirty = git_state(Path("."))
    date = a.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        dest = make(OUT, Path(a.dest), date, commit, dirty, Budget(Path(a.ledger), 0).entries(),
                    allow_dirty=a.allow_dirty, force=a.force)
    except SnapshotError as e:
        log(f"snapshot refused: {e}")
        return 2
    log(f"wrote {dest} (commit {commit[:12]}{', DIRTY' if dirty else ''})")
    return 0


def cmd_orgs(a) -> int:
    from .orgs import registry, report
    from .orgs.safesig import SignatureFinder
    from .rpc import RPC
    orgs = registry.load(Path(a.registry))
    if a.slug:
        unknown = set(a.slug) - {o.slug for o in orgs}
        if unknown:
            log(f"unknown slug(s): {', '.join(sorted(unknown))}")
            return 2
        orgs = [o for o in orgs if o.slug in a.slug]
    base = RPC(a.rpc_url)
    block = a.block if a.block is not None else base.block_number()
    rpc = base.pinned(block)
    block_ts = base.block_timestamp(block)
    finder = SignatureFinder(rpc, a.sig_scan_from, block) if a.sig_scan_from is not None else None
    log(f"resolving {len(orgs)} organisation(s) at block {block:,}"
        + ("" if finder else "; Safe signature scan off (pass --sig-scan-from to enable)"))
    for o in orgs:
        r = report.run_org(rpc, o, block, finder, block_ts)
        j, _ = report.write(r, Path(a.out))
        log(f"  {o.slug}: {r['rule_counts']} -> {j}")
    log(f"Re-run with --block {block} to reproduce these reports exactly.")
    return 0


def cmd_orgs_check(a) -> int:
    import urllib.request
    from .orgs import registry
    orgs = registry.load(Path(a.registry))

    def fetch(url):
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read().decode("utf-8", "replace")

    problems = registry.check_sources(orgs, fetch)
    n = sum(len(o.contracts) for o in orgs)
    for p in problems:
        log(p)
    log(f"{n - len(problems)} of {n} addresses found in their sources" if problems
        else f"all {n} addresses found in their sources ({len(orgs)} organisations)")
    return 1 if problems else 0


def cmd_attest(a) -> int:
    import os
    from .attest import attestation as A
    if a.attest_cmd == "verify":
        trusted = A.load_trusted(Path(a.signers))
        trusted.update({x.lower(): "given with --signer" for x in a.signer or []})
        res = A.verify(Path(a.file), trusted)
        for c in res["checks"]:
            log(f"{'PASS' if c['passed'] else 'FAIL'}  {c['check']}: {c['detail']}")
        if "message" in res:
            m = res["message"]
            log(f"{res['type']} for {m['subject']}: block {m['blockNumber']}, data time {m['dataTimestamp']}, "
                f"commit {m['repoCommit'][:12]}, method {m['methodVersion']}")
        log("VERIFIED" if res["ok"] else "NOT VERIFIED")
        return 0 if res["ok"] else 1
    from .snapshot import git_state
    try:
        key = A.parse_key(os.environ.get(A.KEY_ENV))
        if a.attest_cmd == "sign-snapshot":
            out = A.snapshot_attestation(Path(a.dir), key)
        else:
            commit, dirty = git_state(Path("."))
            if dirty:
                raise A.AttestationError("uncommitted changes: the commit hash would not describe the code")
            out = A.org_attestation(Path(a.report), key, commit)
    except A.AttestationError as e:
        log(f"attest refused: {e}")
        return 2
    signer = json.loads(out.read_text())["signer"]
    log(f"wrote {out}, signed by {signer}")
    if signer not in A.load_trusted(Path(a.signers)):
        log(f"note: {signer} is not yet listed in {a.signers}; add it there so others can verify against it")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="atlas", description="Ethereum Quantum Exposure Atlas")
    sub = p.add_subparsers(dest="cmd", required=True)

    def bq_args(sp):
        sp.add_argument("--project", required=True, help="your Google Cloud project id (billing)")
        sp.add_argument("--work", required=True, help="dataset for intermediate tables, e.g. myproj.atlas")
        sp.add_argument("--src", default=DEFAULT_SRC, help="source dataset (default: Google public data)")
        sp.add_argument("--budget-gb", type=float, default=default_monthly_gib(),
                        help="monthly scan budget in GiB across all atlas queries "
                             "(default: $ATLAS_MONTHLY_BUDGET_GIB or 900)")
        sp.add_argument("--ledger", default=str(LEDGER), help="JSON-lines log of every BigQuery job")

    sp = sub.add_parser("plan", help="dry-run every step and print bytes and cost; runs nothing")
    bq_args(sp)
    sp.add_argument("--steps", nargs="*")
    sp.add_argument("--include-optional", action="store_true")
    sp.add_argument("--top", type=int, default=steps.VERIFY_TOP, help="as for verify")
    sp.add_argument("--sample", type=int, default=steps.VERIFY_SAMPLE, help="as for verify")
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
    sp.add_argument("--top", type=int, default=steps.VERIFY_TOP)
    sp.add_argument("--sample", type=int, default=steps.VERIFY_SAMPLE)
    sp.set_defaults(fn=cmd_verify)

    sp = sub.add_parser("snapshot", help="copy out/ into data/snapshots/YYYY-MM-DD/ with a manifest")
    sp.add_argument("--date", help="snapshot date, YYYY-MM-DD (default: today, UTC)")
    sp.add_argument("--dest", default=str(SNAPSHOTS))
    sp.add_argument("--ledger", default=str(LEDGER))
    sp.add_argument("--allow-dirty", action="store_true", help="snapshot despite uncommitted changes")
    sp.add_argument("--force", action="store_true", help="replace an existing snapshot for that date")
    sp.set_defaults(fn=cmd_snapshot)

    sp = sub.add_parser("orgs", help="per-organisation control graph and key exposure, over RPC")
    sp.add_argument("--rpc-url", required=True)
    sp.add_argument("--block", type=int, help="block to read at (default: latest; printed for re-runs)")
    sp.add_argument("--registry", default="orgs/registry.yaml")
    sp.add_argument("--slug", nargs="*", help="only these organisations")
    sp.add_argument("--out", default="orgs/out")
    sp.add_argument("--sig-scan-from", type=int,
                    help="scan Safe executions from this block for signatures of nonce-0 owners")
    sp.set_defaults(fn=cmd_orgs)

    sp = sub.add_parser("orgs-check", help="confirm every registry address appears in its source_url")
    sp.add_argument("--registry", default="orgs/registry.yaml")
    sp.set_defaults(fn=cmd_orgs_check)

    sp = sub.add_parser("attest", help="sign results (EIP-712) and verify attestations offline")
    att = sp.add_subparsers(dest="attest_cmd", required=True)
    s1 = att.add_parser("sign-snapshot", help="attest a snapshot via its manifest.json (key: $ATLAS_ATTEST_KEY)")
    s1.add_argument("dir")
    s2 = att.add_parser("sign-org", help="attest an organisation report (key: $ATLAS_ATTEST_KEY)")
    s2.add_argument("report")
    s3 = att.add_parser("verify", help="check file hash, digest, signature and signer")
    s3.add_argument("file")
    s3.add_argument("--signer", nargs="*", help="trusted signer address(es), in addition to --signers")
    for x in (s1, s2, s3):
        x.add_argument("--signers", default="attest/signers.json", help="trusted signer list")
    sp.set_defaults(fn=cmd_attest)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
