"""Control-graph resolution and every exposure rule, on a fake chain. No network."""
import pytest

from atlas import constants as K
from atlas.orgs.resolve import Probe, decode_address_array, resolve_graph, value_context
from atlas.orgs.rules import evaluate, findings
from atlas.rpc import RPCError, RPCTransportError


def addr(n: int) -> str:
    return "0x" + f"{n:040x}"


def word(a: str) -> str:
    return "0x" + "0" * 24 + a[2:]


def uint(n: int) -> str:
    return "0x" + f"{n:064x}"


def addr_array(addrs) -> str:
    return "0x" + f"{32:064x}" + f"{len(addrs):064x}" + "".join("0" * 24 + a[2:] for a in addrs)


CODE = "0x6080604052"  # any contract code without the selectors probed for


class FakeChain:
    """Accounts: {address: {"code", "nonce", "storage": {slot: word}, "calls": {selector+args: result}}}."""

    def __init__(self, accounts):
        self.accounts = accounts
        self.down = False

    def _a(self, a):
        return self.accounts.get(a, {})

    def get_code(self, a):
        return self._a(a).get("code", "0x")

    def get_nonce(self, a):
        return self._a(a).get("nonce", 0)

    def get_balance(self, a):
        return self._a(a).get("balance", 0)

    def get_storage(self, a, slot):
        return self._a(a).get("storage", {}).get(slot, uint(0))

    def eth_call(self, to, data):
        if self.down:
            raise RPCTransportError("node unreachable")
        out = self._a(to).get("calls", {}).get(data[2:])
        if out is None:
            raise RPCError("execution reverted")
        return out


def eoa(nonce):
    return {"code": "0x", "nonce": nonce}


def owned(owner):
    return {"code": CODE, "calls": {K.SEL_OWNER: word(owner)}}


def safe(owners, threshold):
    return {"code": CODE, "calls": {K.SEL_GET_OWNERS: addr_array(owners), K.SEL_GET_THRESHOLD: uint(threshold)}}


def run(accounts, root):
    nodes = resolve_graph(Probe(FakeChain(accounts)), [root])
    return nodes, findings(nodes, root)


TOKEN, PROXY_ADMIN, SAFE, TL = addr(0x70), addr(0x71), addr(0x72), addr(0x73)
HOT, COLD, COLD2 = addr(1), addr(2), addr(3)


def test_decode_address_array_rejects_garbage():
    assert decode_address_array(addr_array([HOT, COLD])) == [HOT, COLD]
    assert decode_address_array("0x" + "ff" * 64) is None
    assert decode_address_array(None) is None


def test_r1_exposed_eoa_upgrades_through_proxy_admin():
    nodes, (f,) = run({
        TOKEN: {"code": CODE, "storage": {K.SLOT_EIP1967_ADMIN: word(PROXY_ADMIN)}},
        PROXY_ADMIN: owned(HOT),
        HOT: eoa(12),
    }, TOKEN)
    assert nodes[PROXY_ADMIN]["kind"] == "owned_contract" and nodes[HOT]["exposed"]
    assert f["rule"] == "R1" and f["role"] == "upgrade_admin" and f["capability"] == "upgrade the contract"
    assert f["path"] == [TOKEN, PROXY_ADMIN, HOT]


def test_r2_safe_threshold_reachable_with_exposed_signers():
    nodes, (f,) = run({TOKEN: owned(SAFE), SAFE: safe([HOT, COLD, COLD2], 2),
                       HOT: eoa(1), COLD: eoa(4), COLD2: eoa(0)}, TOKEN)
    assert f["rule"] == "R2" and f["signers"] == [HOT, COLD]
    assert f["detail"] == "2 of 3 owners exposed; threshold 2"


def test_r4_safe_below_threshold():
    _, (f,) = run({TOKEN: owned(SAFE), SAFE: safe([HOT, COLD, COLD2], 2),
                   HOT: eoa(1), COLD: eoa(0), COLD2: eoa(0)}, TOKEN)
    assert f["rule"] == "R4" and f["status"] == "not_exposed"


def test_r4_unexposed_eoa_owner():
    _, (f,) = run({TOKEN: owned(COLD), COLD: eoa(0)}, TOKEN)
    assert f["rule"] == "R4"


def test_r3_openzeppelin_timelock_with_enumerable_proposer():
    _, (f,) = run({
        TOKEN: owned(TL),
        TL: {"code": CODE, "calls": {K.SEL_GET_MIN_DELAY: uint(172800),
                                     K.SEL_GET_ROLE_MEMBER_COUNT + K.PROPOSER_ROLE: uint(1),
                                     K.SEL_GET_ROLE_MEMBER + K.PROPOSER_ROLE + f"{0:064x}": word(HOT)}},
        HOT: eoa(3),
    }, TOKEN)
    assert f["rule"] == "R3" and f["timelock_delay_seconds"] == 172800 and f["path"] == [TOKEN, TL, HOT]


def test_r3_compound_timelock_admin():
    _, (f,) = run({
        TOKEN: owned(TL),
        TL: {"code": CODE, "calls": {K.SEL_DELAY: uint(86400), K.SEL_ADMIN: word(SAFE)}},
        SAFE: safe([HOT], 1), HOT: eoa(9),
    }, TOKEN)
    assert f["rule"] == "R3" and f["timelock_delay_seconds"] == 86400


def test_r5_timelock_with_hidden_proposers():
    _, (f,) = run({TOKEN: owned(TL), TL: {"code": CODE, "calls": {K.SEL_GET_MIN_DELAY: uint(3600)}}}, TOKEN)
    assert f["rule"] == "R5" and "not enumerable" in f["blocking"][0]


def test_r5_governor_and_unknown_contract():
    gov, mystery = addr(0x80), addr(0x81)
    _, (f,) = run({TOKEN: owned(gov), gov: {"code": CODE, "calls": {K.SEL_VOTING_PERIOD: uint(50400)}}}, TOKEN)
    assert f["rule"] == "R5" and "governor" in f["blocking"][0]
    _, (f,) = run({TOKEN: owned(mystery), mystery: {"code": CODE}}, TOKEN)
    assert f["rule"] == "R5" and "no known control interface" in f["blocking"][0]


def test_r5_safe_undecided_because_a_signer_is_unknown():
    mystery = addr(0x81)
    _, (f,) = run({TOKEN: owned(SAFE), SAFE: safe([HOT, mystery, COLD], 2),
                   HOT: eoa(1), mystery: {"code": CODE}, COLD: eoa(0)}, TOKEN)
    assert f["rule"] == "R5" and "1 unknown" in f["detail"]


def test_r0_no_controller_found_and_renounced_owner():
    nodes, (f,) = run({TOKEN: {"code": CODE, "calls": {K.SEL_OWNER: uint(0)}}}, TOKEN)
    assert f["rule"] == "R0"
    assert any("renounced" in n for n in nodes[TOKEN]["notes"])


def test_r5_access_control_not_enumerable():
    code = CODE + K.PUSH4 + K.SEL_HAS_ROLE
    _, fs = run({TOKEN: {"code": code}}, TOKEN)
    assert [f["rule"] for f in fs] == ["R5"]


def test_access_control_enumerable_default_admin():
    zero = K.DEFAULT_ADMIN_ROLE
    _, (f,) = run({TOKEN: {"code": CODE, "calls": {
        K.SEL_GET_ROLE_MEMBER_COUNT + zero: uint(1),
        K.SEL_GET_ROLE_MEMBER + zero + f"{0:064x}": word(HOT)}}, HOT: eoa(2)}, TOKEN)
    assert f["rule"] == "R1" and f["role"] == "default_admin"


def test_owner_plus_hidden_roles_reports_both():
    code = CODE + K.PUSH4 + K.SEL_HAS_ROLE
    _, fs = run({TOKEN: {"code": code, "calls": {K.SEL_OWNER: word(HOT)}}, HOT: eoa(1)}, TOKEN)
    assert [f["rule"] for f in fs] == ["R1", "R5"]


def test_beacon_owner_and_zos_admin():
    beacon = addr(0x90)
    _, fs = run({
        TOKEN: {"code": CODE, "storage": {K.SLOT_EIP1967_BEACON: word(beacon), K.SLOT_ZOS_ADMIN: word(COLD)}},
        beacon: {"code": CODE, "calls": {K.SEL_OWNER: word(HOT), K.SEL_IMPLEMENTATION: word(addr(0x91))}},
        HOT: eoa(5), COLD: eoa(0),
    }, TOKEN)
    assert {(f["role"], f["rule"]) for f in fs} == {("upgrade_admin", "R4"), ("upgrade_beacon", "R1")}


def test_eip7702_delegated_eoa_is_still_an_eoa():
    nodes, (f,) = run({TOKEN: owned(HOT), HOT: {"code": "0xef0100" + "22" * 20, "nonce": 1}}, TOKEN)
    assert nodes[HOT]["kind"] == "eoa" and nodes[HOT]["eip7702_delegated"] and f["rule"] == "R1"


def test_cycle_is_unknown_not_infinite():
    a, b = addr(0xA0), addr(0xB0)
    _, (f,) = run({TOKEN: owned(a), a: owned(b), b: owned(a)}, TOKEN)
    assert f["rule"] == "R5" and any("cycle" in x for x in f["blocking"])


def test_registered_safe_is_judged_as_a_whole():
    _, (f,) = run({SAFE: safe([HOT, COLD], 1), HOT: eoa(1), COLD: eoa(0)}, SAFE)
    assert f["role"] == "self" and f["rule"] == "R2" and f["path"] == [SAFE]


def test_transport_failure_is_not_read_as_revert():
    chain = FakeChain({TOKEN: {"code": CODE}})
    chain.down = True
    with pytest.raises(RPCTransportError):
        resolve_graph(Probe(chain), [TOKEN])


def test_evidence_and_value_context():
    probe = Probe(FakeChain({TOKEN: {**owned(HOT), "balance": 7, "calls": {
        K.SEL_OWNER: word(HOT), K.SEL_TOTAL_SUPPLY: uint(10 ** 24), K.SEL_DECIMALS: uint(18)}}, HOT: eoa(1)}))
    nodes = resolve_graph(probe, [TOKEN])
    calls = [e["call"] for e in nodes[TOKEN]["evidence"]]
    assert "eth_getCode" in calls and f"eth_call 0x{K.SEL_OWNER}" in calls
    assert value_context(probe, TOKEN, "token") == {"eth_balance_wei": "7", "total_supply_raw": str(10 ** 24),
                                                    "decimals": 18}


def test_most_direct_exposure_is_reported():
    """With both a timelocked path and a direct path exposed, the direct one (R1) is shown."""
    _, (f,) = run({TOKEN: owned(PROXY_ADMIN),
                   PROXY_ADMIN: {"code": CODE, "calls": {K.SEL_GET_ROLE_MEMBER_COUNT + K.DEFAULT_ADMIN_ROLE: uint(2),
                                                        K.SEL_GET_ROLE_MEMBER + K.DEFAULT_ADMIN_ROLE + f"{0:064x}": word(TL),
                                                        K.SEL_GET_ROLE_MEMBER + K.DEFAULT_ADMIN_ROLE + f"{1:064x}": word(HOT)}},
                   TL: {"code": CODE, "calls": {K.SEL_DELAY: uint(10), K.SEL_ADMIN: word(HOT)}},
                   HOT: eoa(1)}, TOKEN)
    assert f["rule"] == "R1" and f["path"] == [TOKEN, PROXY_ADMIN, HOT]
    assert evaluate({}, HOT)["status"] == "unknown"
