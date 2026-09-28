# Draft reply for ethresear.ch

Post as a reply in "Migration Strategies for EOAs under the Quantum Threat: Breakages,
and Open Questions" (https://ethresear.ch/t/23864), answering question 5 there.
Replace every [bracket] with a number from `out/SUMMARY.md` and `out/VERIFY.md`.
Do not post until `verify` passes.

---

**Title:** Measuring permit/ecrecover quantum exposure: first numbers and an open pipeline

Hi @Marcolopeez, thanks for the survey. Your question 5 asked for measurements of
`ecrecover` and `permit` usage in the wild. Here is a first pass, with open code so
anyone can reproduce or correct it: [GitHub link].

**What I measured (snapshot [date], latest tx in data [date])**

1. **ETH behind revealed keys.** [X] ETH ([Y]% of execution-layer ETH, [Z]% of ETH held
   by EOAs) sits in EOAs that have sent at least one transaction. The 1,000 largest hold
   [T] ETH. This is a fresh full-ledger recount, not a reuse of the 2021 figure.
2. **Dormancy.** [D] ETH of that sits in accounts inactive for 5+ years.
3. **Permit-reachable tokens.** [N] tokens accept ERC-2612 or DAI-style permit
   (detected in bytecode, with proxies resolved to their implementation). Exposed EOAs
   hold about [$V] in them; [$I] of that is in tokens with no upgrade path.
4. *(If run)* **Permit2.** [O] owners ([OE] with exposed keys) hold live Permit2
   approvals across [K] tokens.

**Why (3) matters for Hegotá.** Once an account migrates via EIP-8298, EIP-3607 blocks
its old-key transactions, but `permit` in immutable tokens still accepts the old key.
The [$I] figure is roughly what EIP-8151 protects that nothing else does.

**Limits.** Lower bound (off-chain signatures leak keys too); rebasing tokens are
approximate; unknown proxy patterns are missed. A node spot-check agreed on [a]/[b]
accounts and [c]/[d] token balances. Full list in METHODOLOGY.md.

**Asks.** Corrections to the method; known proxy patterns I miss; anyone who wants to
extend this to L2s. I plan to refresh it on a schedule and publish the data.
