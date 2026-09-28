"""Proxy resolution and permit detection against a fake node."""
from atlas import constants as K
from atlas import proxies as P

IMPL = "0x" + "ab" * 20
BEACON = "0x" + "cd" * 20
TOKEN = "0x" + "11" * 20
PERMIT_CODE = "0x6080" + "63" + K.SEL_PERMIT_2612 + "14"
PLAIN_CODE = "0x608060405234"


def word(addr):
    return "0x" + "0" * 24 + addr[2:]


class FakeRPC:
    def __init__(self, storage=None, code=None, calls=None):
        self.storage, self.code, self.calls = storage or {}, code or {}, calls or {}

    def get_storage(self, a, slot):
        return self.storage.get((a, slot), "0x" + "0" * 64)

    def get_code(self, a):
        return self.code.get(a, "0x")

    def eth_call(self, to, data):
        if (to, data) in self.calls:
            return self.calls[(to, data)]
        raise RuntimeError("revert")


def test_word_to_address():
    assert P.word_to_address(word(IMPL)) == IMPL
    assert P.word_to_address("0x" + "0" * 64) is None


def test_eip1167():
    code = "0x" + K.EIP1167_PREFIX + IMPL[2:] + "5af43d82803e903d91602b57fd5bf3"
    assert P.eip1167_target(code) == IMPL


def test_permit_kind():
    assert P.permit_kind(PERMIT_CODE) == "erc2612"
    assert P.permit_kind("0x63" + K.SEL_PERMIT_DAI) == "dai"
    assert P.permit_kind(PLAIN_CODE) is None


def test_eoa_code():
    assert P.is_eoa_code("0x")
    assert P.is_eoa_code("0xef0100" + "22" * 20)
    assert not P.is_eoa_code(PLAIN_CODE)


def test_eip1967_proxy_with_permit_impl():
    rpc = FakeRPC(storage={(TOKEN, K.SLOT_EIP1967_IMPL): word(IMPL)},
                  code={TOKEN: PLAIN_CODE, IMPL: PERMIT_CODE})
    out = P.classify(rpc, {"token": TOKEN, "permit_direct": "false", "proxy_signal": "true"})
    assert out["permit"] and out["permit_source"] == "implementation"
    assert out["mechanism"] == "eip1967" and out["upgradeable"] is True


def test_usdc_style_zos_slot():
    rpc = FakeRPC(storage={(TOKEN, K.SLOT_ZOS_IMPL): word(IMPL)}, code={TOKEN: PLAIN_CODE, IMPL: PERMIT_CODE})
    out = P.classify(rpc, {"token": TOKEN, "permit_direct": "false", "proxy_signal": "true"})
    assert out["mechanism"] == "zos" and out["permit"]


def test_beacon_proxy():
    rpc = FakeRPC(storage={(TOKEN, K.SLOT_EIP1967_BEACON): word(BEACON)},
                  code={TOKEN: PLAIN_CODE, IMPL: PERMIT_CODE},
                  calls={(BEACON, "0x" + K.SEL_IMPLEMENTATION): word(IMPL)})
    out = P.classify(rpc, {"token": TOKEN, "permit_direct": "false", "proxy_signal": "true"})
    assert out["mechanism"] == "beacon" and out["permit"]


def test_aragon_style_implementation_call():
    rpc = FakeRPC(code={TOKEN: PLAIN_CODE, IMPL: PERMIT_CODE},
                  calls={(TOKEN, "0x" + K.SEL_IMPLEMENTATION): word(IMPL)})
    out = P.classify(rpc, {"token": TOKEN, "permit_direct": "false", "proxy_signal": "true"})
    assert out["mechanism"] == "implementation()" and out["permit"]


def test_clone_is_not_upgradeable():
    code = "0x" + K.EIP1167_PREFIX + IMPL[2:] + "5af43d"
    rpc = FakeRPC(code={TOKEN: code, IMPL: PERMIT_CODE})
    out = P.classify(rpc, {"token": TOKEN, "permit_direct": "false", "proxy_signal": "true"})
    assert out["mechanism"] == "eip1167" and out["upgradeable"] is False and out["permit"]


def test_direct_permit_needs_no_rpc():
    class NoRPC:
        def __getattr__(self, name):
            raise AssertionError("RPC should not be called")
    out = P.classify(NoRPC(), {"token": TOKEN, "permit_direct": "true", "permit_2612_direct": "true",
                               "proxy_signal": "false"})
    assert out["permit"] and out["upgradeable"] == "no_signal"


def test_proxy_without_permit():
    rpc = FakeRPC(storage={(TOKEN, K.SLOT_EIP1967_IMPL): word(IMPL)}, code={TOKEN: PLAIN_CODE, IMPL: PLAIN_CODE})
    out = P.classify(rpc, {"token": TOKEN, "permit_direct": "false", "proxy_signal": "true"})
    assert not out["permit"]
