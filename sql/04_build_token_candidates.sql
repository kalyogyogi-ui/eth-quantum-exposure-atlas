-- Step 4 (build). Contracts that either implement permit directly, or look like a proxy
-- (whose permit code, if any, lives in an implementation contract resolved later over RPC).
-- Permit is detected two ways: the ETL's function_sighashes, and the PUSH4 selector in bytecode.
-- Reads: contracts(address, bytecode, function_sighashes, is_erc20).
CREATE OR REPLACE TABLE `{{work}}.token_candidates` AS
WITH c AS (
  SELECT
    address,
    is_erc20,
    LOWER(REPLACE(bytecode, '0x', '')) AS code,  -- hex without 0x prefix
    ARRAY(SELECT LOWER(REPLACE(h, '0x', '')) FROM UNNEST(function_sighashes) AS h) AS sighashes
  FROM `{{src}}.contracts`
),
flags AS (
  SELECT
    address,
    is_erc20,
    LENGTH(code) AS code_hex_len,
    ('{{SEL_PERMIT_2612}}' IN UNNEST(sighashes) OR STRPOS(code, '{{PUSH_PERMIT_2612}}') > 0) AS permit_2612_direct,
    ('{{SEL_PERMIT_DAI}}' IN UNNEST(sighashes) OR STRPOS(code, '{{PUSH_PERMIT_DAI}}') > 0) AS permit_dai_direct,
    STRPOS(code, '{{SLOT_EIP1967_IMPL}}') > 0 AS sig_eip1967_impl,
    STRPOS(code, '{{SLOT_EIP1967_BEACON}}') > 0 AS sig_eip1967_beacon,
    STRPOS(code, '{{SLOT_ZOS_IMPL}}') > 0 AS sig_zos_impl,
    STRPOS(code, '{{SLOT_EIP1822}}') > 0 AS sig_eip1822,
    STARTS_WITH(code, '{{EIP1167_PREFIX}}') AS sig_eip1167,
    -- Weak signal: small contract that contains a DELEGATECALL-like byte. Confirmed later by RPC.
    (LENGTH(code) <= 6000 AND STRPOS(code, 'f4') > 0) AS sig_small_delegatecall
  FROM c
)
SELECT
  *,
  (permit_2612_direct OR permit_dai_direct) AS permit_direct,
  (sig_eip1967_impl OR sig_eip1967_beacon OR sig_zos_impl OR sig_eip1822 OR sig_eip1167
    OR sig_small_delegatecall) AS proxy_signal
FROM flags
WHERE permit_2612_direct OR permit_dai_direct
   OR sig_eip1967_impl OR sig_eip1967_beacon OR sig_zos_impl OR sig_eip1822 OR sig_eip1167
   OR sig_small_delegatecall;
