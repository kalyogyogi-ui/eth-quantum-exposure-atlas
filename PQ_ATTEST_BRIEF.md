# PQ-Attest: build brief for Claude Code

Owner: Nagnath Savant
Repo: `kalyogyogi-ui/eth-quantum-exposure-atlas` (work in this repo, on a new branch `pq-attest`)
Written: 5 Oct 2026

## How to use this file

Put this file in the repo root, open Claude Code in the repo, and say:
"Read PQ_ATTEST_BRIEF.md and start with WP0. Stop at every STOP point."

## 1. Goal

Turn the existing Ethereum Quantum Exposure Atlas pipeline into **PQ-Attest**:

1. a live, reproducible measurement of quantum exposure on Ethereum,
2. a per-organisation exposure report (protocols, issuers, custodians),
3. a free public dashboard,
4. signed attestations of each result, published on-chain.

The owner has **no budget**. Every step must be free or cost a few rupees of gas at most.

## 2. What already exists (do not rebuild)

- `atlas/` Python package with CLI: `plan -> run -> resolve -> price -> summarize -> verify`.
- `sql/01..08` BigQuery steps against `bigquery-public-data.crypto_ethereum`.
- 39 unit tests, no network needed (`python -m pytest`).
- `docs/METHODOLOGY.md` and `docs/ethresearch_post_draft.md`.
- README status: "pipeline complete and unit-tested; not yet run on live data."
- The Atlas measures: exposed ETH (accounts that have sent a transaction), its
  distribution and dormancy, token value reachable through `permit` signatures,
  and optionally Permit2 approvals.
- The README deliberately leaves **aggregate admin-key exposure** out of scope because
  the Google Quantum AI paper measured it. Keep that decision for the Atlas headline.
  The per-organisation module in WP2 is a separate, new output.

## 3. Hard rules

1. **Money.** Never run a BigQuery query that has not been priced with `atlas plan`
   (dry run) first. Keep the existing `--max-gb` hard cap. Keep total scanning inside the
   free monthly allowance; check current BigQuery pricing before the first run. If any
   step would cost money, STOP and ask.
2. **No paid services.** Free tiers only: public RPC endpoints, GitHub Pages, GitHub Actions.
3. **No token.** Do not write, deploy or propose any ERC-20, coin, staking or sale code.
4. **No mainnet transactions** without the owner typing an explicit approval in the session.
   Testnet first, always.
5. **Secrets.** Never commit keys, tokens or credentials. Read them from environment
   variables. Add patterns to `.gitignore`. The attestation signing key must be a new key
   used for nothing else, never the owner's main wallet.
6. **Named organisations.** Per-organisation pages are built with `published: false` by
   default and are hidden on the public site until the owner flips the flag. The owner
   will notify each organisation first. Do not send any email or post anywhere.
7. **Honesty of numbers.** Every published figure must come from a file in the snapshot
   directory. State known limits beside the figure. Report agreement rates from `verify`.
   If a number cannot be verified, say so in the output; do not round it into certainty.
8. **Do not trust memory for addresses.** Contract addresses, storage slots, attestation
   contract addresses and schema registry addresses must be taken from official
   documentation or the chain itself, with the source URL recorded.
9. Small commits, clear messages, tests for every new module, no network in unit tests.

## 4. What the owner must provide (ask for these, do not guess)

- Google Cloud project ID with BigQuery enabled, and `gcloud auth application-default login` done.
- An Ethereum JSON-RPC URL (a public endpoint is acceptable).
- Confirmation that GitHub Pages may be enabled on the repo.
- For WP4 only: a fresh signing key in an environment variable, and testnet ETH from a faucet.

## 5. Work packages

Do them in order. Each ends with a short report: what changed, what it cost, what is
still unverified.

### WP0. Orient (no changes)

- Read `README.md`, `docs/METHODOLOGY.md`, `atlas/`, `sql/`, `tests/`.
- Run `python -m pytest`. Report failures, if any, before touching anything.
- Report anything in this brief that conflicts with the code.

**STOP.** Wait for the owner's go-ahead and the items in section 4.

### WP1. First live run

- `python -m atlas plan` and show the priced total per step. **STOP** for approval.
- Run steps 01-06, then `resolve`, `price`, `summarize`, `verify`.
- Leave optional steps 07-08 (Permit2, large logs scan) out unless `plan --include-optional`
  shows they fit the free allowance, and the owner approves.
- Fix real bugs found on live data; add a regression test for each.
- Save a dated snapshot: `data/snapshots/YYYY-MM-DD/` containing the CSVs, `summary.json`,
  `SUMMARY.md`, `verify.json`, the git commit hash, the data-freshness timestamp, and the
  bytes billed per step.
- Add `python -m atlas snapshot` to produce that directory in one command.
- Update the README status line with the snapshot date.

Done when: a snapshot exists, `verify` agreement rates are reported, and total cost is stated.

### WP2. Per-organisation exposure module (`atlas/orgs/`)

Purpose: for one named organisation, answer "which keys control this system, and are
those keys quantum-exposed?"

- `orgs/registry.yaml`: one entry per organisation with `slug`, `name`, `category`,
  `published: false`, and a list of contracts. Each contract has `address`, `role`
  (token, vault, bridge, governance, treasury) and `source_url` pointing to the
  organisation's own documentation. Start with 20 well-documented protocols and issuers.
  Never invent an address; skip an organisation if its contracts cannot be sourced.
- Resolver, RPC only (reuse `atlas/rpc.py` and `atlas/proxies.py`):
  - controlling addresses via `owner()`, the EIP-1967 admin slot, proxy admin contracts,
    timelock admins, and Safe `getOwners()` / `getThreshold()`;
  - classify each controller: exposed EOA, unexposed EOA, Safe m-of-n with k exposed
    signers, timelock, other contract (unresolved);
  - an EOA is exposed if its nonce is above zero. Also investigate and document:
    a Safe signer whose signature appears in the calldata of an executed Safe
    transaction has a recoverable public key even at nonce zero. Implement this check
    if it is feasible on free data; otherwise record it as a stated limit.
  - value context: ETH balance and token total supply or balance held by each contract.
- Output per organisation: `orgs/out/<slug>.json` and a readable `<slug>.md` with the
  control graph, each controller's class, the evidence (block number, call, result),
  and unresolved items listed explicitly.
- A transparent exposure summary with written rules, for example: "single exposed EOA
  can upgrade the contract", "threshold reachable using exposed signers only", "no
  exposed path found". No opaque score. Put the rules in `docs/METHODOLOGY.md`.
- Unit tests on fakes for every classification rule. No network in tests.

Done when: 20 organisations resolve, unresolved cases are listed, and a second run at
the same block gives identical output.

**STOP.** Show three sample reports to the owner before WP3.

### WP3. Public dashboard (`site/`)

- Static HTML, CSS and plain JavaScript that reads the snapshot JSON. No framework, no
  build step unless it is clearly needed, no trackers, no external fonts or scripts.
- Pages: headline exposure; distribution by balance and dormancy; permit-token exposure;
  organisations (only entries with `published: true`); methodology and limits; data
  freshness and snapshot history.
- Every figure shows its snapshot date and links to the CSV or JSON it came from.
- Works at phone width, in light and dark mode, and with JavaScript errors shown plainly.
- Deploy with a GitHub Actions workflow to GitHub Pages. The workflow only publishes
  committed snapshot files; it does not run BigQuery.

Done when: the site builds from a clean clone and shows the WP1 snapshot.

### WP4. Signed attestations (`atlas/attest/`)

- Define two JSON schemas: `SnapshotAttestation` and `OrgAttestation`. Fields: schema
  version, subject, block number, data timestamp, the SHA-256 of the snapshot or report
  file, the repo commit hash, and the method version.
- Off-chain first: sign each as EIP-712 typed data with the key from an environment
  variable; write `*.attestation.json` beside the data; add `python -m atlas attest verify`
  so anyone can check a signature and file hash.
- On-chain second: publish the same payload through an existing attestation service on
  a low-fee Ethereum rollup **testnet**. Take contract and schema-registry addresses from
  the service's official documentation and record the source URL. Do not write a custom
  contract.
- Mainnet publishing sits behind a separate command and an explicit flag, and still
  requires the owner's typed approval and a gas estimate shown first.
- The dashboard shows a "verify this figure" link for each attested result.

Done when: an attestation made on testnet is verified by the `verify` command from a
clean clone.

**STOP** before any mainnet action.

### WP5. Documents

- Update `README.md` and `docs/METHODOLOGY.md` for everything added.
- Replace placeholders in `docs/ethresearch_post_draft.md` with real figures and limits.
- Write `docs/RESULTS_SUMMARY.md`: one page of results suitable for attaching to a grant
  application. State what was measured, the figures, the agreement rates and the limits.
- Write `docs/NOTIFY_TEMPLATE.md`: a short, neutral email the owner can send to a named
  organisation before its page is published, with a correction window.
- Write `docs/REFRESH.md`: how to produce the next snapshot by hand and what it costs.
- Add `CHANGELOG.md`.

## 6. Out of scope

Tokens, coins, staking, fundraising, marketing, paid data sources, custom smart
contracts, other chains (rollups and bridges come later), and sending any message to a
third party.

## 7. Definition of finished

A stranger can clone the repo, run the tests, read the latest snapshot, open the public
dashboard, and verify a signed attestation against the data file, without paying for
anything and without trusting the author.

## Decisions recorded during WP0 (5 Oct 2026)

- Work happens on branch `claude/pq-attest-build-brief-g5zpiu` instead of `pq-attest`.
- DefiLlama's free, keyless price API is approved for `atlas price`.
