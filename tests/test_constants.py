"""Every magic number is recomputed from its definition."""
import pytest

from atlas import constants as K

keccak = pytest.importorskip("Crypto.Hash.keccak")


def k(text: str) -> str:
    h = keccak.new(digest_bits=256)
    h.update(text.encode())
    return h.hexdigest()


@pytest.mark.parametrize("value,signature", [
    (K.SEL_PERMIT_2612, "permit(address,address,uint256,uint256,uint8,bytes32,bytes32)"),
    (K.SEL_PERMIT_DAI, "permit(address,address,uint256,uint256,bool,uint8,bytes32,bytes32)"),
    (K.SEL_BALANCE_OF, "balanceOf(address)"),
    (K.SEL_IMPLEMENTATION, "implementation()"),
])
def test_selectors(value, signature):
    assert value == k(signature)[:8]


def test_approval_topic():
    assert K.TOPIC_ERC20_APPROVAL == "0x" + k("Approval(address,address,uint256)")


@pytest.mark.parametrize("value,label,minus_one", [
    (K.SLOT_EIP1967_IMPL, "eip1967.proxy.implementation", True),
    (K.SLOT_EIP1967_BEACON, "eip1967.proxy.beacon", True),
    (K.SLOT_ZOS_IMPL, "org.zeppelinos.proxy.implementation", False),
    (K.SLOT_EIP1822, "PROXIABLE", False),
])
def test_slots(value, label, minus_one):
    n = int(k(label), 16) - (1 if minus_one else 0)
    assert value == f"{n:064x}"


def test_pad_topic():
    assert K.pad_topic_address(K.PERMIT2) == "0x" + "0" * 24 + K.PERMIT2[2:]
    assert len(K.pad_topic_address(K.PERMIT2)) == 66
    with pytest.raises(ValueError):
        K.pad_topic_address("0x1234")
