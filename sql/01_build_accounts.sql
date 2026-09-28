-- Step 1 (build). One row per address that holds ETH or has ever sent a transaction.
-- An EOA that has sent a transaction has revealed its secp256k1 public key on-chain,
-- so a quantum computer running Shor's algorithm could derive its private key.
-- Reads: transactions(from_address, block_timestamp), balances, contracts(address).
CREATE OR REPLACE TABLE `{{work}}.accounts` AS
WITH senders AS (
  SELECT
    from_address AS address,
    COUNT(*) AS tx_count,
    MIN(block_timestamp) AS first_sent,
    MAX(block_timestamp) AS last_sent
  FROM `{{src}}.transactions`
  GROUP BY from_address
),
contract_addrs AS (
  SELECT DISTINCT address FROM `{{src}}.contracts`
),
bal AS (
  SELECT address, eth_balance AS eth_wei
  FROM `{{src}}.balances`
  WHERE eth_balance > 0
)
SELECT
  COALESCE(b.address, s.address) AS address,
  COALESCE(b.eth_wei, 0) AS eth_wei,
  c.address IS NOT NULL AS is_contract,
  s.address IS NOT NULL AS has_sent,
  s.tx_count,
  s.first_sent,
  s.last_sent
FROM bal AS b
FULL OUTER JOIN senders AS s ON b.address = s.address
LEFT JOIN contract_addrs AS c ON c.address = COALESCE(b.address, s.address);
