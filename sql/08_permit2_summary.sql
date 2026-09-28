-- Step 8 (query, OPTIONAL). Summary of live Permit2 approvals.
SELECT
  COUNT(*) AS live_approvals,
  COUNT(DISTINCT owner) AS distinct_owners,
  COUNT(DISTINCT IF(owner_exposed, owner, NULL)) AS distinct_exposed_owners,
  COUNT(DISTINCT token) AS distinct_tokens
FROM `{{work}}.permit2_approvals`;
