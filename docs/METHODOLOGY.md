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

## Why not use traces for `ecrecover`?

BigQuery's Parity-derived traces historically omitted precompile calls, and scanning
traces is expensive. Bytecode selectors are cheaper and more reliable for this question.

## Relation to prior work

- Exposed-ETH estimates: Deloitte (2021); Quantum Horizon (arXiv 2606.14484), which found
  no public re-measurement as of June 2026.
- Admin-key contracts: Google Quantum AI × EF whitepaper (March 2026). Not repeated here.
- `ecrecover`/permit exposure: requested by López (ethresear.ch, Jan 2026) and listed as
  undone by the AppliedPQC survey (Sep 2026). This project answers that request.
