"""Single source of truth for every magic number the Atlas uses.

Every selector, event topic and storage slot below is recomputed from its
text definition in tests/test_constants.py, so a typo fails the tests.
"""

# Default source: Google's public Ethereum dataset (blockchain-etl).
DEFAULT_SRC = "bigquery-public-data.crypto_ethereum"

# --- Function selectors (first 4 bytes of keccak256(signature)) ---
# ERC-2612: permit(address,address,uint256,uint256,uint8,bytes32,bytes32)
SEL_PERMIT_2612 = "d505accf"
# DAI-style: permit(address,address,uint256,uint256,bool,uint8,bytes32,bytes32)
SEL_PERMIT_DAI = "8fcbaf0c"
# balanceOf(address)
SEL_BALANCE_OF = "70a08231"
# implementation()  (Aragon / Transparent proxies / beacons)
SEL_IMPLEMENTATION = "5c60da1b"

# --- Event topics (keccak256 of the event signature) ---
TOPIC_ERC20_APPROVAL = "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925"

# --- Proxy storage slots ---
# EIP-1967: keccak256("eip1967.proxy.implementation") - 1
SLOT_EIP1967_IMPL = "360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
# EIP-1967: keccak256("eip1967.proxy.beacon") - 1
SLOT_EIP1967_BEACON = "a3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50"
# OpenZeppelin legacy (zos): keccak256("org.zeppelinos.proxy.implementation"). Used by USDC.
SLOT_ZOS_IMPL = "7050c9e0f4ca769c69bd3a8ef740bc37934f8e2c036e5a723fd8ee048ed3f8c3"
# EIP-1822 (UUPS draft): keccak256("PROXIABLE")
SLOT_EIP1822 = "c5f16f0fcc639fa48a6947836d9850f504798523bf8c9a3a87d5876cf622bcf7"

# EIP-1967: keccak256("eip1967.proxy.admin") - 1. Holds the address allowed to upgrade.
SLOT_EIP1967_ADMIN = "b53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"
# OpenZeppelin legacy (zos): keccak256("org.zeppelinos.proxy.admin"). Used by USDC.
SLOT_ZOS_ADMIN = "10d6a54a4754c8869d6886b5f5d7fbfa5b4522237ea5c60d11bc4e7a1ff9390b"

# --- Control interfaces probed by the per-organisation resolver (atlas/orgs) ---
SEL_OWNER = "8da5cb5b"                    # owner()
SEL_ADMIN = "f851a440"                    # admin()  (Compound-style timelock)
SEL_GET_OWNERS = "a0e67e2b"               # getOwners()  (Safe)
SEL_GET_THRESHOLD = "e75235b8"            # getThreshold()  (Safe)
SEL_GET_MIN_DELAY = "f27a0c92"            # getMinDelay()  (OpenZeppelin TimelockController)
SEL_DELAY = "6a42b8f8"                    # delay()  (Compound-style timelock)
SEL_GET_ROLE_MEMBER_COUNT = "ca15c873"    # getRoleMemberCount(bytes32)
SEL_GET_ROLE_MEMBER = "9010d07c"          # getRoleMember(bytes32,uint256)
SEL_HAS_ROLE = "91d14854"                 # hasRole(bytes32,address)
SEL_VOTING_PERIOD = "02a251a3"            # votingPeriod()  (Governor)
SEL_KERNEL = "d4aae0c4"                   # kernel()  (Aragon app; aragonOS AppStorage.sol)
SEL_TOTAL_SUPPLY = "18160ddd"             # totalSupply()
SEL_DECIMALS = "313ce567"                 # decimals()
# execTransaction(address,uint256,bytes,uint8,uint256,uint256,uint256,address,address,bytes)  (Safe)
SEL_SAFE_EXEC = "6a761202"
DEFAULT_ADMIN_ROLE = "0" * 64             # OpenZeppelin AccessControl: bytes32(0)
PROPOSER_ROLE = "b09aa5aeb3702cfd50b6b62bc4532604938f21248a27a1d5ca736082b6819cc1"  # keccak256("PROPOSER_ROLE")
# keccak256("ExecutionSuccess(bytes32,uint256)"). Safe v1.1.1-v1.3.0 put txHash in the log data;
# v1.4.1 indexes it (topics[1]). v1.0.0 emits no ExecutionSuccess. Sources:
# https://raw.githubusercontent.com/safe-global/safe-smart-account/v1.3.0/contracts/GnosisSafe.sol
# https://raw.githubusercontent.com/safe-global/safe-smart-account/v1.4.1/contracts/Safe.sol
TOPIC_SAFE_EXECUTION_SUCCESS = "0x442e715f626346e8c54381002da614f62bee8d27386535b2521ec8540898556e"

# EIP-1167 minimal proxy runtime prefix; the next 20 bytes are the implementation.
EIP1167_PREFIX = "363d3d373d3d3d363d73"
# EIP-7702 delegation indicator: an EOA whose code is 0xef0100 || address.
EIP7702_PREFIX = "ef0100"

# --- Addresses ---
# Uniswap Permit2 (same address on every chain; immutable, no admin).
PERMIT2 = "0x000000000022d473030f116ddee9f6b43ac78ba3"
ZERO_ADDRESS = "0x" + "0" * 40

# BigQuery BIGNUMERIC holds integers up to about 5.79e38 (precision 76.76, scale 38).
# https://cloud.google.com/bigquery/docs/reference/standard-sql/data-types#decimal_types
# Transfer values above it (spam tokens) fail SAFE_CAST and are dropped, both legs at once.
BIGNUMERIC_MAX = "578960446186580977117854925043439539266.34992332820282019728792003956564819967"
# Raw amounts are summed as hi * 10**18 + lo so that adding millions of legs cannot
# overflow BIGNUMERIC: hi <= 5.8e20 and lo < 1e18 for every leg.
AMOUNT_SPLIT = "1000000000000000000"

# PUSH4 opcode (0x63) followed by a selector: how solc embeds a dispatch check.
PUSH4 = "63"


def pad_topic_address(address: str) -> str:
    """Left-pad a 20-byte address to a 32-byte log topic, lower-case."""
    a = address.lower().removeprefix("0x")
    if len(a) != 40:
        raise ValueError(f"not a 20-byte address: {address}")
    return "0x" + "0" * 24 + a


def sql_params() -> dict:
    """Constants substituted into the SQL templates as {{NAME}}."""
    return {
        "SEL_PERMIT_2612": SEL_PERMIT_2612,
        "SEL_PERMIT_DAI": SEL_PERMIT_DAI,
        "PUSH_PERMIT_2612": PUSH4 + SEL_PERMIT_2612,
        "PUSH_PERMIT_DAI": PUSH4 + SEL_PERMIT_DAI,
        "SLOT_EIP1967_IMPL": SLOT_EIP1967_IMPL,
        "SLOT_EIP1967_BEACON": SLOT_EIP1967_BEACON,
        "SLOT_ZOS_IMPL": SLOT_ZOS_IMPL,
        "SLOT_EIP1822": SLOT_EIP1822,
        "EIP1167_PREFIX": EIP1167_PREFIX,
        "TOPIC_ERC20_APPROVAL": TOPIC_ERC20_APPROVAL,
        "PERMIT2_TOPIC": pad_topic_address(PERMIT2),
        "ZERO_ADDRESS": ZERO_ADDRESS,
        "AMOUNT_SPLIT": AMOUNT_SPLIT,
    }
