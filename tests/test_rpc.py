"""The RPC client sends the pinned block tag; no network (the transport is replaced)."""
from atlas.rpc import RPC


class Recorder(RPC):
    def __init__(self, *a, **k):
        super().__init__("http://unused", *a, **k)
        self.sent = []

    def _post(self, payload):
        self.sent.append(payload)
        return {"result": "0x1"}


def test_latest_by_default():
    r = Recorder()
    r.get_code("0xa")
    assert r.sent[-1]["params"] == ["0xa", "latest"]


def test_pinned_block_is_used_for_every_state_read():
    r = Recorder(block=19_000_000)
    r.get_code("0xa"); r.get_storage("0xa", "00"); r.get_balance("0xa"); r.get_nonce("0xa"); r.eth_call("0xa", "0x")
    assert all(p["params"][-1] == hex(19_000_000) for p in r.sent)
    assert r.pinned(5).block == 5 and r.block == 19_000_000
