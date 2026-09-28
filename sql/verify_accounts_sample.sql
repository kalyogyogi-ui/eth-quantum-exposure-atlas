-- Verification sample: top exposed accounts plus a deterministic pseudo-random sample.
(SELECT address, CAST(eth_wei AS STRING) AS eth_wei, 'top' AS sample_kind
 FROM `{{work}}.accounts`
 WHERE NOT is_contract AND has_sent
 ORDER BY eth_wei DESC LIMIT {{top_n}})
UNION ALL
(SELECT address, CAST(eth_wei AS STRING) AS eth_wei, 'random' AS sample_kind
 FROM `{{work}}.accounts`
 WHERE NOT is_contract AND has_sent AND eth_wei > 0
 ORDER BY FARM_FINGERPRINT(address) LIMIT {{random_n}});
