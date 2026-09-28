-- Step 5 (build). Net token balance per (candidate token, EOA holder), from transfer history.
-- One scan of token_transfers: each transfer becomes a +amount leg and a -amount leg.
-- Limits: rebasing tokens (e.g. stETH) and fee-on-transfer tokens are approximate;
-- `atlas verify` spot-checks balances against balanceOf over RPC.
CREATE OR REPLACE TABLE `{{work}}.token_holdings` AS
WITH cand AS (
  SELECT address FROM `{{work}}.token_candidates`
),
legs AS (
  SELECT t.token_address AS token, leg.holder, leg.amt
  FROM `{{src}}.token_transfers` AS t
  JOIN cand ON cand.address = t.token_address,
  UNNEST([
    STRUCT(t.to_address AS holder, SAFE_CAST(t.value AS BIGNUMERIC) AS amt),
    STRUCT(t.from_address AS holder, -SAFE_CAST(t.value AS BIGNUMERIC) AS amt)
  ]) AS leg
  WHERE SAFE_CAST(t.value AS BIGNUMERIC) <= CAST('{{MAX_RAW_TRANSFER}}' AS BIGNUMERIC)
),
bal AS (
  SELECT token, holder, SUM(amt) AS raw_balance
  FROM legs
  WHERE holder IS NOT NULL AND holder != '{{ZERO_ADDRESS}}'
  GROUP BY token, holder
  HAVING SUM(amt) > 0
),
contract_addrs AS (
  SELECT DISTINCT address FROM `{{src}}.contracts`
)
SELECT
  b.token,
  b.holder,
  b.raw_balance,
  COALESCE(a.has_sent, FALSE) AS holder_exposed
FROM bal AS b
LEFT JOIN `{{work}}.accounts` AS a ON a.address = b.holder
LEFT JOIN contract_addrs AS c ON c.address = b.holder
WHERE c.address IS NULL;  -- EOA holders only (EIP-7702-delegated EOAs are not in contracts)
