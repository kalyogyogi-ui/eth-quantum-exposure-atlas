# Methodology

## Definitions

**Exposed account.** An externally owned account (EOA) that has sent at least one
transaction. Ethereum signatures are recoverable, so every sent transaction publishes
the sender's secp256k1 public key permanently. Shor's algorithm recovers the private
key from it. EIP-7702-delegated accounts count as EOAs: their ECDSA key stays live.

**Unexposed EOA.** An EOA with no sent transaction in the data. It may still be exposed
off-chain (see limits), so it is reported separately, never as "safe".

**Permit token.** A contract whose own bytecode, or whose proxy implementation's
bytecode, dispatches on the ERC-2612 selector `0xd505accf` or the DAI-style selector
`0x8fcbaf0c`. Detection uses both the ETL's `function_sighashes` and a `PUSH4 <selector>`
search in bytecode. Every selector is recomputed from its signature in the tests.

**Upgradeable.** A token resolved to an implementation through the EIP-1967
implementation slot, EIP-1967 beacon, the legacy OpenZeppelin (zos) slot used by USDC,
the EIP-1822 slot, or an `implementation()` call (Aragon proxies such as stETH).
EIP-1167 clones are marked not upgradeable because their target is fixed.
"No upgrade signal" means none of these patterns was found, not proof of immutability.

## Pipeline

| Step | Source tables | Output |
| --- | --- | --- |
| 01 | `transactions` (from, time), `balances`, `contracts` (address) | `accounts` work table |
| 02–03 | `accounts` only | headline and distribution CSVs |
| 04 | `contracts` (bytecode, sighashes) | `token_candidates`: direct permit + proxy signals |
| 05 | `token_transfers` for candidates only, single scan | `token_holdings`: net balance per EOA holder |
| 06 | work tables + `tokens` | per-token exposed/unexposed raw amounts |
| resolve | RPC `eth_getCode`, `eth_getStorageAt`, `eth_call` | proxy mechanism and permit confirmation |
| price | DefiLlama, confidence ≥ 0.9 (prices without a confidence value are excluded) | USD values |
| 07–08 | `logs` since Nov 2022 (optional) | live Permit2 approvals |
| verify | RPC nonce, code, balance, `balanceOf` | agreement rates |

Source: `bigquery-public-data.crypto_ethereum` (blockchain-etl). Its `balances` table is
rebuilt daily from traces and holds wei as NUMERIC.

## Known limits (state these in any publication)

1. **Lower bound.** Public keys also leak through off-chain signatures (EIP-712 messages,
   signed permits, exported xpubs), even from accounts that never sent a transaction.
2. **Token balances from transfers.** Rebasing tokens (stETH) and fee-on-transfer tokens
   are approximate. `verify` compares a sample against `balanceOf` and reports mismatches.
   Transfers whose value exceeds BigQuery's BIGNUMERIC range (about 5.79e38 raw units) are
   dropped as spam. Balances and per-token totals that still overflow are flagged, valued
   at zero, and counted in the summary (`permit_tokens_with_amount_overflow`).
3. **Proxy coverage.** `resolve` handles the top N proxy candidates by exposed holders
   (default 2,000) and reports how many it skipped. Unknown proxy patterns are missed.
4. **Weak proxy signal.** Small contracts containing the byte `f4` are included as
   candidates; RPC resolution discards those that are not proxies.
5. **Prices** are a snapshot; low-confidence prices are excluded, so USD totals undercount.
6. **Data freshness.** The summary records the latest transaction timestamp seen.
   "Dormant 5+ years" means the account's last transaction was in year Y − 5 or earlier,
   where Y is the year of that timestamp, so a snapshot's figure does not change when it
   is re-summarized later. Year granularity means "5+ years" can include accounts last
   active between 5 and 6 years before the data date.

## Per-organisation exposure (`atlas orgs`)

A separate output from the headline Atlas numbers. For one organisation it answers: which
keys control these contracts, and have those keys revealed their public key on-chain?

**Inputs.** `orgs/registry.yaml` lists each organisation's contracts with a `source_url` to
the organisation's own documentation. Every organisation defaults to `published: false`.

**Resolution (RPC only, every read at one pinned block).** For each address:

| Found | Classified as | Followed to |
| --- | --- | --- |
| no code, or an EIP-7702 delegation | EOA | — |
| `getOwners()` and `getThreshold()` | Safe *t*-of-*n* | each owner |
| `getMinDelay()` | OpenZeppelin timelock | proposers, if enumerable |
| `delay()` and `admin()` | Compound-style timelock | admin |
| `votingPeriod()` | governor | not followed (voters) |
| `kernel()` | Aragon app | not followed (permissions sit in the kernel's ACL) |
| EIP-1967 or zos admin slot, EIP-1967 beacon, `owner()`, enumerable `DEFAULT_ADMIN_ROLE` | owned contract | each controller |
| none of these | contract, unresolved | — |

**Exposure of a key.** An EOA is exposed if its nonce is above zero, or if its ECDSA
signature appears in the calldata of an executed Safe transaction (`--sig-scan-from`). The
second case catches Safe signers who never send transactions themselves.

**Status of a controller.** *exposed* (control can be exercised using exposed keys only),
*not_exposed*, or *unknown*. A Safe is exposed when at least its threshold of owners are
exposed. A timelock or owned contract takes the most direct exposed path of its
controllers, since each can act alone. Governors, unrecognised contracts, cycles and the
depth limit (8) are unknown.

**Rules.** One finding per control edge of each registered contract. A registered Safe or
timelock is judged as a whole.

| Rule | Name | Meaning |
| --- | --- | --- |
| R1 | single_exposed_eoa | one exposed key can act, with no multisig and no delay |
| R2 | threshold_reachable_exposed | a Safe threshold is reachable using exposed signers only |
| R3 | exposed_behind_timelock | an exposed path exists but passes through a timelock (delay shown) |
| R4 | no_exposed_path | every path ends at keys with no on-chain exposure found |
| R5 | unresolved | could not decide; the blocking items are listed |
| R0 | no_controller_found | no known control interface; not proof of immutability |

There is no score. Each report lists the evidence (call, result, block) for every address.

**Sponsors.** If an organisation in `orgs/registry.yaml` sponsors this project (GitHub
Sponsors is the only channel), its report must say so before it is published. The report
generator has no sponsor field yet, so this is checked by hand when a new sponsor appears
(`docs/SPONSORS.md`, step 12).

**Limits.** On-chain evidence only, so "not exposed" means none was found. Non-enumerable
AccessControl roles and OpenZeppelin timelock proposers are only visible in event history and
are reported as unresolved. Governors are not followed to voters. Aragon apps (e.g. Lido, Curve DAO) keep
permissions in an ACL that cannot be listed by call, so they are reported as unresolved. The Safe signature check
covers Safe v1.1.1 and later (v1.0.0 emits no `ExecutionSuccess`). It only covers
transactions sent straight to the Safe, within the scanned range. Executions through
relayers or modules are counted as undecodable. Free RPC endpoints limit `eth_getLogs`
ranges. A refused range is halved down to a floor, then reported as not checked.

## Attestations

Two EIP-712 message types, `SnapshotAttestation` and `OrgAttestation`, share these fields:
`schemaVersion`, `subject`, `blockNumber`, `dataTimestamp`, `fileSha256`, `repoCommit` and
`methodVersion`. The EIP-712 domain is `{name: "PQ-Attest", version: "1"}`. It has no
chainId, because these signatures are made offline. A snapshot is attested through its
`manifest.json`, which lists the SHA-256 of every file in the snapshot, so one signature
covers them all. `blockNumber` is 0 for BigQuery snapshots, whose source tables do not
record a block. For those, `dataTimestamp` is the latest transaction time in the data.

What a valid attestation proves: the file is byte-for-byte what the listed key signed, and
names the commit of the code that produced it. It does not prove the numbers are right.
That comes from re-running the pipeline at that commit, which is what `verify`, the
snapshot manifest and the per-step bytes-billed record make possible.

Signing uses pure-Python secp256k1 with deterministic nonces (RFC 6979) and low-s form. The
tests reproduce the EIP-712 reference signature exactly (EIPs repository,
`assets/eip-712/Example.js`).

## Why not use traces for `ecrecover`?

BigQuery's Parity-derived traces historically omitted precompile calls, and scanning
traces is expensive. Bytecode selectors are cheaper and more reliable for this question.

## Relation to prior work

- Exposed-ETH estimates: Deloitte (2021); Quantum Horizon (arXiv 2606.14484), which found
  no public re-measurement as of June 2026.
- Admin-key contracts: Google Quantum AI × EF whitepaper (March 2026). Not repeated here.
- `ecrecover`/permit exposure: requested by López (ethresear.ch, Jan 2026) and listed as
  undone by the AppliedPQC survey (Sep 2026). This project answers that request.
