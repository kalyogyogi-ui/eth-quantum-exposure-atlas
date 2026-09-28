-- Step 3 (query). Exposed ETH by balance size and by the year the account last sent a tx.
-- Long-dormant exposed accounts are the ones least likely to ever migrate.
WITH e AS (
  SELECT eth_wei / POW(10, 18) AS eth, EXTRACT(YEAR FROM last_sent) AS last_sent_year
  FROM `{{work}}.accounts`
  WHERE NOT is_contract AND has_sent AND eth_wei > 0
)
SELECT
  CASE
    WHEN eth < 0.01 THEN '1: <0.01'
    WHEN eth < 1 THEN '2: 0.01-1'
    WHEN eth < 10 THEN '3: 1-10'
    WHEN eth < 100 THEN '4: 10-100'
    WHEN eth < 1000 THEN '5: 100-1k'
    WHEN eth < 10000 THEN '6: 1k-10k'
    ELSE '7: >=10k'
  END AS balance_bucket_eth,
  last_sent_year,
  COUNT(*) AS n_accounts,
  SUM(eth) AS eth
FROM e
GROUP BY balance_bucket_eth, last_sent_year
ORDER BY balance_bucket_eth, last_sent_year;
