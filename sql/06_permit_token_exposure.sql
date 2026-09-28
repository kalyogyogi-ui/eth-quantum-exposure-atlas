-- Step 6 (query). Per candidate token: how much is held by exposed vs unexposed EOAs.
-- Raw amounts are exported as strings to keep full precision; decimals come from the tokens table
-- and are double-checked against DefiLlama in `atlas price`.
WITH tk AS (
  SELECT address, ANY_VALUE(symbol) AS symbol, ANY_VALUE(SAFE_CAST(decimals AS INT64)) AS decimals
  FROM `{{src}}.tokens`
  GROUP BY address
),
agg AS (
  SELECT
    token,
    COUNTIF(holder_exposed) AS exposed_holders,
    COUNTIF(NOT holder_exposed) AS unexposed_eoa_holders,
    SUM(IF(holder_exposed, raw_balance, 0)) AS raw_exposed,
    SUM(IF(NOT holder_exposed, raw_balance, 0)) AS raw_unexposed_eoa
  FROM `{{work}}.token_holdings`
  GROUP BY token
)
SELECT
  agg.token,
  tk.symbol,
  tk.decimals,
  agg.exposed_holders,
  agg.unexposed_eoa_holders,
  CAST(agg.raw_exposed AS STRING) AS raw_exposed,
  CAST(agg.raw_unexposed_eoa AS STRING) AS raw_unexposed_eoa,
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
