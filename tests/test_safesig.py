"""Safe signature evidence: curve math, calldata decoding, log scanning. No network."""
import pytest

from atlas import constants as K
from atlas.orgs import safesig as S
from atlas.orgs.resolve import Probe, resolve_graph
from atlas.orgs.rules import findings
from atlas.rpc import RPCError

from test_org_resolve import FakeChain, addr, eoa, owned, safe


def sign(d: int, h: bytes, k: int):
    """Textbook ECDSA with a fixed nonce, for tests only."""
    R = S.point_mul(k, S.G)
    r = R[0] % S.N
    s = pow(k, -1, S.N) * (int.from_bytes(h, "big") + r * d) % S.N
    v = 27 + (R[1] & 1)
    if s > S.N // 2:                     # low-s form, as Ethereum signers produce
        s, v = S.N - s, 55 - v
    return v, r, s


def chunk(v, r, s) -> bytes:
    return r.to_bytes(32, "big") + s.to_bytes(32, "big") + bytes([v])


def exec_calldata(signatures: bytes) -> str:
    head = ["00" * 32] * 10
    head[2] = f"{10 * 32:064x}"                       # data offset -> empty bytes
    head[9] = f"{11 * 32:064x}"                       # signatures offset
    pad = (-len(signatures)) % 32
    tail = f"{0:064x}" + f"{len(signatures):064x}" + (signatures + b"\0" * pad).hex()
    return "0x" + K.SEL_SAFE_EXEC + "".join(head) + tail


def test_curve_parameters():
    x, y = S.G
    assert (y * y - x ** 3 - 7) % S.P == 0
    assert S.point_mul(S.N, S.G) is None


def test_known_address_for_private_key_one():
    assert S.pubkey_to_address(S.G) == "0x7e5f4552091a69125d5dfcb7b8c2659029395bdf"


@pytest.mark.parametrize("d,k", [(1, 2), (0xC0FFEE, 0x1234567), (S.N - 2, S.N - 5)])
def test_recover_round_trip(d, k):
    h = S.keccak256(b"safe tx")
    v, r, s = sign(d, h, k)
    assert S.recover(h, v, r, s) == S.pubkey_to_address(S.point_mul(d, S.G))


def test_recover_rejects_invalid():
    h = S.keccak256(b"x")
    assert S.recover(h, 29, 1, 1) is None and S.recover(h, 27, 0, 1) is None


def test_decode_all_signature_kinds():
    h = S.keccak256(b"safe tx hash")
    d1, d2 = 0xA11CE, 0xB0B
    a1, a2 = (S.pubkey_to_address(S.point_mul(d, S.G)) for d in (d1, d2))
    v2, r2, s2 = sign(d2, S.eth_sign_digest(h), 77)
    contract_owner, approver = int(addr(0xC0), 16), int(addr(0xA0), 16)
    sigs = (chunk(*sign(d1, h, 99)) + chunk(v2 + 4, r2, s2)
            + chunk(1, approver, 0) + chunk(0, contract_owner, 4 * 65)
            + (5).to_bytes(32, "big") + b"\x11" * 5)        # contract signature payload
    out = S.signers(S.exec_signatures(exec_calldata(sigs)), h)
    assert [(o["signer"], o["kind"], o["reveals_key"]) for o in out] == [
        (a1, "ecdsa", True), (a2, "eth_sign", True),
        (addr(0xA0), "approved_hash", False), (addr(0xC0), "contract", False)]


def test_not_exec_transaction():
    assert S.exec_signatures("0xa9059cbb" + "00" * 64) is None


SAFE_ADDR, QUIET, LOUD = addr(0x72), None, addr(1)
D_QUIET = 0x5EC12E7


class LogChain(FakeChain):
    """Adds logs and transactions to the fake chain."""

    def __init__(self, accounts, logs, txs, max_range=None):
        super().__init__(accounts)
        self.logs, self.txs, self.max_range, self.log_calls = logs, txs, max_range, []

    def get_logs(self, address, topics, a, b):
        self.log_calls.append((a, b))
        if self.max_range and b - a + 1 > self.max_range:
            raise RPCError("block range too large")
        assert topics == [K.TOPIC_SAFE_EXECUTION_SUCCESS]
        return [l for l in self.logs if a <= int(l["blockNumber"], 16) <= b and l["address"] == address]

    def get_transaction(self, h):
        return self.txs[h]


def scenario(indexed: bool, via_relayer: bool = False, max_range=None):
    quiet = S.pubkey_to_address(S.point_mul(D_QUIET, S.G))
    h = S.keccak256(b"exec 1")
    calldata = exec_calldata(chunk(*sign(D_QUIET, h, 4242)))
    log = {"address": SAFE_ADDR, "blockNumber": hex(1500), "transactionHash": "0xt1",
           "topics": [K.TOPIC_SAFE_EXECUTION_SUCCESS] + (["0x" + h.hex()] if indexed else []),
           "data": "0x" + ("" if indexed else h.hex()) + f"{0:064x}"}
    tx = {"to": addr(0x99) if via_relayer else SAFE_ADDR, "input": calldata}
    accounts = {addr(0x70): owned(SAFE_ADDR), SAFE_ADDR: safe([LOUD, quiet], 2), LOUD: eoa(3), quiet: eoa(0)}
    return quiet, LogChain(accounts, [log], {"0xt1": tx}, max_range)


@pytest.mark.parametrize("indexed", [False, True])   # Safe v1.3.0 data vs v1.4.1 indexed topic
def test_nonce_zero_signer_becomes_exposed(indexed):
    quiet, chain = scenario(indexed)
    nodes = resolve_graph(Probe(chain), [addr(0x70)])
    (before,) = findings(nodes, addr(0x70))
    assert before["rule"] == "R4"
    S.apply(nodes, S.SignatureFinder(chain, 0, 2000, chunk=1000))
    assert nodes[quiet]["exposed"] and "0xt1" in nodes[quiet]["exposure_basis"]
    assert nodes[quiet]["signature_checks"][0]["found"] is True
    (after,) = findings(nodes, addr(0x70))
    assert after["rule"] == "R2"


def test_relayed_execution_is_undecodable_not_exposed():
    quiet, chain = scenario(False, via_relayer=True)
    nodes = resolve_graph(Probe(chain), [addr(0x70)])
    S.apply(nodes, S.SignatureFinder(chain, 0, 2000))
    assert not nodes[quiet]["exposed"]
    assert nodes[SAFE_ADDR]["signature_scan"]["undecodable"] == 1


def test_log_range_is_halved_when_refused():
    quiet, chain = scenario(False, max_range=600)
    nodes = resolve_graph(Probe(chain), [addr(0x70)])
    S.apply(nodes, S.SignatureFinder(chain, 0, 1999, chunk=2000, min_chunk=250))
    assert nodes[quiet]["exposed"]
    accepted = [(a, b) for a, b in chain.log_calls if b - a + 1 <= 600]
    assert accepted[0][0] == 0 and accepted[-1][1] == 1999
    assert all(x[1] + 1 == y[0] for x, y in zip(accepted, accepted[1:]))   # no gaps, no overlaps


def test_scan_refused_is_reported_not_guessed():
    quiet, chain = scenario(False, max_range=100)
    nodes = resolve_graph(Probe(chain), [addr(0x70)])
    S.apply(nodes, S.SignatureFinder(chain, 0, 1999, chunk=2000, min_chunk=500))
    assert not nodes[quiet]["exposed"]
    assert "refused" in nodes[quiet]["signature_checks"][0]["note"]
