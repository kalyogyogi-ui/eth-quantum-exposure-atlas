-- Step 5 (build). Net token balance per (candidate token, EOA holder), from transfer history.
-- One scan of token_transfers: each transfer becomes a +amount leg and a -amount leg.
-- Amounts are summed as hi * 10**18 + lo so the sums cannot overflow BIGNUMERIC; a net
-- balance too large for BIGNUMERIC (spam tokens) is kept with raw_balance NULL and
-- balance_overflow TRUE, so step 06 can count it instead of silently dropping it.
-- Limits: rebasing tokens (e.g. stETH) and fee-on-transfer tokens are approximate;
-- `atlas verify` spot-checks balances against balanceOf over RPC.
CREATE OR REPLACE TABLE `{{work}}.token_holdings` AS
WITH cand AS (
  SELECT address FROM `{{work}}.token_candidates`
),
xfer AS (
  SELECT
    t.token_address AS token,
    t.from_address,
    t.to_address,
    SAFE_CAST(t.value AS BIGNUMERIC) AS v  -- NULL above BIGNUMERIC's range: spam, both legs dropped
  FROM `{{src}}.token_transfers` AS t
  JOIN cand ON cand.address = t.token_address
),
legs AS (
  SELECT
    xfer.token,
    leg.holder,
    leg.sign * DIV(xfer.v, CAST('{{AMOUNT_SPLIT}}' AS BIGNUMERIC)) AS hi,
    leg.sign * MOD(xfer.v, CAST('{{AMOUNT_SPLIT}}' AS BIGNUMERIC)) AS lo
  FROM xfer,
  UNNEST([
    STRUCT(xfer.to_address AS holder, 1 AS sign),
    STRUCT(xfer.from_address AS holder, -1 AS sign)
  ]) AS leg
  WHERE xfer.v IS NOT NULL AND xfer.v >= 0
),
sums AS (
  SELECT token, holder, SUM(hi) AS hi, SUM(lo) AS lo
  FROM legs
  WHERE holder IS NOT NULL AND holder != '{{ZERO_ADDRESS}}'
  GROUP BY token, holder
),
bal AS (
  SELECT
    token,
    holder,
    hi,
    SAFE_ADD(SAFE_MULTIPLY(hi, CAST('{{AMOUNT_SPLIT}}' AS BIGNUMERIC)), lo) AS raw_balance  -- NULL on overflow
  FROM sums
),
contract_addrs AS (
  SELECT DISTINCT address FROM `{{src}}.contracts`
)
SELECT
  b.token,
  b.holder,
  b.raw_balance,
  b.raw_balance IS NULL AS balance_overflow,
  COALESCE(a.has_sent, FALSE) AS holder_exposed
FROM bal AS b
LEFT JOIN `{{work}}.accounts` AS a ON a.address = b.holder
LEFT JOIN contract_addrs AS c ON c.address = b.holder
WHERE c.address IS NULL  -- EOA holders only (EIP-7702-delegated EOAs are not in contracts)
  AND (b.raw_balance > 0 OR (b.raw_balance IS NULL AND b.hi > 0));
