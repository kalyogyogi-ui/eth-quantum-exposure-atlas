-- Step 2 (query). Headline exposed-ETH numbers. Reads only the small work table.
WITH a AS (
  SELECT
    *,
    NOT is_contract AND has_sent AS exposed,
    NOT is_contract AND NOT has_sent AS eoa_unexposed
  FROM `{{work}}.accounts`
),
top1000 AS (
  SELECT eth_wei FROM a WHERE exposed ORDER BY eth_wei DESC LIMIT 1000
)
SELECT
  SUM(eth_wei) / POW(10, 18) AS eth_all_accounts,
  SUM(IF(is_contract, eth_wei, 0)) / POW(10, 18) AS eth_in_contracts,
  SUM(IF(NOT is_contract, eth_wei, 0)) / POW(10, 18) AS eth_in_eoas,
  SUM(IF(exposed, eth_wei, 0)) / POW(10, 18) AS eth_in_exposed_eoas,
  SUM(IF(eoa_unexposed, eth_wei, 0)) / POW(10, 18) AS eth_in_unexposed_eoas,
  COUNTIF(exposed AND eth_wei > 0) AS n_exposed_eoas_with_balance,
  COUNTIF(eoa_unexposed AND eth_wei > 0) AS n_unexposed_eoas_with_balance,
  (SELECT SUM(eth_wei) FROM top1000) / POW(10, 18) AS eth_in_top1000_exposed_eoas,
  (SELECT MAX(last_sent) FROM a) AS data_freshness_last_tx
FROM a;
