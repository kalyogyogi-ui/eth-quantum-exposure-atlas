-- Step 7 (build, OPTIONAL: scans the large logs table, check `atlas plan` first).
-- Owners whose latest ERC-20 Approval to Uniswap Permit2 is non-zero. Permit2 is immutable
-- and moves tokens on an ECDSA signature, so these approvals extend signature-based exposure
-- to tokens that never implemented permit themselves.
CREATE OR REPLACE TABLE `{{work}}.permit2_approvals` AS
WITH appr AS (
  SELECT
    address AS token,
    CONCAT('0x', SUBSTR(topics[SAFE_OFFSET(1)], 27)) AS owner,
    data,
    block_number,
    log_index
  FROM `{{src}}.logs`
  WHERE block_timestamp >= TIMESTAMP('2022-11-01')  -- Permit2 deployed Nov 2022
    AND ARRAY_LENGTH(topics) = 3                    -- ERC-20 (ERC-721 Approval has 4 topics)
    AND topics[SAFE_OFFSET(0)] = '{{TOPIC_ERC20_APPROVAL}}'
    AND topics[SAFE_OFFSET(2)] = '{{PERMIT2_TOPIC}}'
),
latest AS (
  SELECT
    token,
    owner,
    ARRAY_AGG(data ORDER BY block_number DESC, log_index DESC LIMIT 1)[OFFSET(0)] AS data
  FROM appr
  GROUP BY token, owner
)
SELECT
  l.token,
  l.owner,
  COALESCE(a.has_sent AND NOT a.is_contract, FALSE) AS owner_exposed
FROM latest AS l
LEFT JOIN `{{work}}.accounts` AS a ON a.address = l.owner
WHERE l.data != CONCAT('0x', REPEAT('0', 64));
