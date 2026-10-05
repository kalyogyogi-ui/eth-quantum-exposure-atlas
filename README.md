# Ethereum Quantum Exposure Atlas

An open, reproducible measurement of how much value on Ethereum a future quantum
computer could steal, including a surface nobody has measured before: token value
reachable through ECDSA `permit` signatures in contracts that cannot be changed.

**Status:** pipeline complete and unit-tested (131 tests); not yet run on live data.

## What it measures

| # | Question | Why it matters |
| --- | --- | --- |
| 1 | How much ETH sits in accounts that have revealed their public key? | Every account that has sent a transaction exposes its secp256k1 key. The widely quoted 50–65% figure rests on a 2021 scan with no public re-measurement. |
| 2 | How is that ETH distributed, and how much sits in long-dormant accounts? | Dormant owners are least likely to migrate. |
| 3 | How much token value, held by exposed accounts, can be moved by a `permit` signature? | After an account migrates to a post-quantum key, EIP-8298 blocks old-key transactions but not permit signatures. EIP-8151 exists to close that gap; this measures what it protects. |
| 4 | *(optional)* How many owners have live approvals to Uniswap Permit2? | Permit2 extends signature-based transfers to tokens without native permit. |

Admin-key exposure is deliberately out of scope: the Google Quantum AI × EF whitepaper
already measured it (about 2.5M ETH in admin-controlled contracts). Cite it instead.

## What you need

1. **Python 3.10+.**
2. **A Google Cloud project with BigQuery enabled.** The on-demand plan has included
   1 TiB of free query scanning per month; check current
   [BigQuery pricing](https://cloud.google.com/bigquery/pricing).
3. **An Ethereum JSON-RPC URL**, e.g. a free key from any node provider, or a public
   endpoint such as `https://ethereum-rpc.publicnode.com`.

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
python -m pytest                # 131 tests, no network needed

gcloud auth application-default login
set P=your-gcp-project-id       # macOS/Linux: export P=your-gcp-project-id

# 1. Price every query first, including verify's. Runs nothing, costs nothing.
#    Steps that read work tables can only be priced once earlier steps have built them,
#    so plan again after running 01 and 04.
python -m atlas plan --project %P% --work %P%.atlas

# 2. Run the BigQuery steps. Each query is dry-run again, refused if it would pass the
#    monthly budget (--budget-gb, default 900 GiB, or ATLAS_MONTHLY_BUDGET_GIB), and
#    hard-capped by BigQuery at the smaller of --max-gb and the budget left.
#    Every job is logged to out/bq_ledger.jsonl.
python -m atlas run --project %P% --work %P%.atlas

# 3. Resolve proxy tokens (USDC, stETH and many others are proxies) and confirm permit.
python -m atlas resolve --rpc-url https://ethereum-rpc.publicnode.com

# 4. Prices, then the summary.
python -m atlas price
python -m atlas summarize          # writes out/SUMMARY.md and out/summary.json

# 5. Independent check against a live node.
python -m atlas verify --project %P% --work %P%.atlas --rpc-url https://ethereum-rpc.publicnode.com

# 6. Freeze the outputs into data/snapshots/YYYY-MM-DD/ with a manifest
#    (commit hash, data freshness, bytes billed per step, SHA-256 of every file).
python -m atlas snapshot

# Optional: Permit2 approvals (scans the large logs table; run `plan --include-optional` first).
python -m atlas run --project %P% --work %P%.atlas --steps 07 08 --include-optional
```

## Per-organisation exposure

Separate from the headline numbers: for each organisation in `orgs/registry.yaml`, which keys
control its contracts, and are those keys quantum-exposed? RPC only, no BigQuery.

```bash
# Reads every address at one block; prints the block so a re-run gives identical files.
python -m atlas orgs --rpc-url https://ethereum-rpc.publicnode.com [--slug lido] [--block N]
# Also look for Safe owners revealed by their signatures (slow on free endpoints):
python -m atlas orgs --rpc-url URL --sig-scan-from 10000000
```

Writes `orgs/out/<slug>.json` and `<slug>.md`: findings by rule (R0–R5), the control graph,
unresolved items, and the evidence for every read. `orgs/out/` is git-ignored: every report
is a draft until the owner sets `published: true`, after notifying the organisation.

## Outputs (`out/`)

| File | Contents |
| --- | --- |
| `SUMMARY.md`, `summary.json` | Headline numbers, top tokens, caveats |
| `02_exposed_eth_summary.csv` | Exposed vs unexposed ETH, top-1,000 concentration |
| `03_exposure_distribution.csv` | Exposed ETH by balance bucket and last-active year |
| `06_permit_token_exposure.csv` | Per candidate token: holders and raw amounts |
| `token_classification.csv` | Permit support, proxy mechanism, upgradeability per token |
| `prices.csv` | DefiLlama prices used |
| `VERIFY.md`, `verify.json` | Node spot-check results |
| `bq_ledger.jsonl` | Every BigQuery job: estimate, bytes billed, job id (not copied into snapshots; the manifest summarises it) |

The budget ledger only counts queries run through `atlas` on this machine. As a backstop,
set a custom quota on query usage per day in your Google Cloud project; Google enforces
it whatever runs the query.

## Layout

```
sql/        one file per step; constants are injected from atlas/constants.py
atlas/      CLI, BigQuery runner, RPC client, proxy resolver, pricing, summary, verification
atlas/orgs/ per-organisation registry, control-graph resolver, rules, Safe signature check, reports
orgs/       registry.yaml (contracts with source URLs); reports go to orgs/out/ (git-ignored)
tests/      constants recomputed with keccak; SQL parsed as BigQuery; logic tested on fakes
docs/       METHODOLOGY.md and a draft ethresear.ch post
```

See [docs/METHODOLOGY.md](docs/METHODOLOGY.md) for definitions and limits.

## License

MIT. Author: Nagnath Savant.
