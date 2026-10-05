-- Step 6 (query). Per candidate token: how much is held by exposed vs unexposed EOAs.
-- Raw amounts are exported as strings to keep full precision; decimals come from the tokens table
-- and are double-checked against DefiLlama in `atlas price`. Sums use the same hi/lo split as
-- step 05; a total too large for BIGNUMERIC is exported empty with amount_overflow TRUE.
WITH tk AS (
  SELECT address, ANY_VALUE(symbol) AS symbol, ANY_VALUE(SAFE_CAST(decimals AS INT64)) AS decimals
  FROM `{{src}}.tokens`
  GROUP BY address
),
parts AS (
  SELECT
    token,
    holder_exposed,
    balance_overflow,
    DIV(raw_balance, CAST('{{AMOUNT_SPLIT}}' AS BIGNUMERIC)) AS hi,
    MOD(raw_balance, CAST('{{AMOUNT_SPLIT}}' AS BIGNUMERIC)) AS lo
  FROM `{{work}}.token_holdings`
),
sums AS (
  SELECT
    token,
    COUNTIF(holder_exposed) AS exposed_holders,
    COUNTIF(NOT holder_exposed) AS unexposed_eoa_holders,
    COUNTIF(balance_overflow) AS overflow_holders,
    SUM(IF(holder_exposed, hi, 0)) AS hi_exposed,
    SUM(IF(holder_exposed, lo, 0)) AS lo_exposed,
    SUM(IF(NOT holder_exposed, hi, 0)) AS hi_unexposed,
    SUM(IF(NOT holder_exposed, lo, 0)) AS lo_unexposed
  FROM parts
  GROUP BY token
),
agg AS (
  SELECT
    token,
    exposed_holders,
    unexposed_eoa_holders,
    overflow_holders,
    SAFE_ADD(SAFE_MULTIPLY(hi_exposed, CAST('{{AMOUNT_SPLIT}}' AS BIGNUMERIC)), lo_exposed) AS raw_exposed,
    SAFE_ADD(SAFE_MULTIPLY(hi_unexposed, CAST('{{AMOUNT_SPLIT}}' AS BIGNUMERIC)), lo_unexposed) AS raw_unexposed_eoa
  FROM sums
)
SELECT
  agg.token,
  tk.symbol,
  tk.decimals,
  agg.exposed_holders,
  agg.unexposed_eoa_holders,
  CAST(agg.raw_exposed AS STRING) AS raw_exposed,
  CAST(agg.raw_unexposed_eoa AS STRING) AS raw_unexposed_eoa,
  agg.overflow_holders,
  (agg.overflow_holders > 0 OR agg.raw_exposed IS NULL OR agg.raw_unexposed_eoa IS NULL) AS amount_overflow,
  c.is_erc20,
  c.permit_direct,
  c.permit_2612_direct,
  c.permit_dai_direct,
  c.proxy_signal,
  c.sig_eip1967_impl,
  c.sig_eip1967_beacon,
  c.sig_zos_impl,
  c.sig_eip1822,
  c.sig_eip1167,
  c.sig_small_delegatecall
FROM agg
JOIN `{{work}}.token_candidates` AS c ON c.address = agg.token
LEFT JOIN tk ON tk.address = agg.token
ORDER BY agg.exposed_holders DESC;
