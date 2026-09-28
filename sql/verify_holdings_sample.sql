-- Verification sample: token balances derived from transfers, to compare with balanceOf.
SELECT token, holder, CAST(raw_balance AS STRING) AS raw_balance
FROM `{{work}}.token_holdings`
WHERE holder_exposed
ORDER BY FARM_FINGERPRINT(CONCAT(token, holder))
LIMIT {{random_n}};
