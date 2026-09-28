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

# EIP-1167 minimal proxy runtime prefix; the next 20 bytes are the implementation.
EIP1167_PREFIX = "363d3d373d3d3d363d73"
# EIP-7702 delegation indicator: an EOA whose code is 0xef0100 || address.
EIP7702_PREFIX = "ef0100"

# --- Addresses ---
# Uniswap Permit2 (same address on every chain; immutable, no admin).
PERMIT2 = "0x000000000022d473030f116ddee9f6b43ac78ba3"
ZERO_ADDRESS = "0x" + "0" * 40

# Transfers above this raw amount are treated as junk (spam tokens) so sums
# cannot overflow BIGNUMERIC. Real ERC-20 supplies are far below 1e45.
MAX_RAW_TRANSFER = "1e45"

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
        "MAX_RAW_TRANSFER": MAX_RAW_TRANSFER,
    }
