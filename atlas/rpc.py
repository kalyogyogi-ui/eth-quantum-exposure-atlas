"""Minimal Ethereum JSON-RPC client using only the standard library."""
import json
import time
import urllib.request


class RPCError(RuntimeError):
    """The node answered with an error, e.g. an eth_call that reverted."""


class RPCTransportError(RPCError):
    """The node could not be reached. Never read this as "the call reverted"."""


class RPC:
    """`block` pins every state read to one block (an int, or a tag such as "latest").

    Reads at a fixed block older than about 128 blocks need an archive node; most free
    public endpoints are not archive nodes, so pin to a recent block and finish the run
    promptly, or use an endpoint that serves historical state.
    """

    def __init__(self, url: str, timeout: float = 30.0, pause: float = 0.05, retries: int = 3,
                 block: int | str = "latest"):
        self.url = url
        self.timeout = timeout
        self.pause = pause
        self.retries = retries
        self.block = block
        self._id = 0

    def pinned(self, block: int | str) -> "RPC":
        return RPC(self.url, self.timeout, self.pause, self.retries, block)

    def _tag(self) -> str:
        return hex(self.block) if isinstance(self.block, int) else self.block

    def _post(self, payload):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(self.url, data=data, headers={"Content-Type": "application/json"})
        last = None
        for attempt in range(self.retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    out = json.loads(resp.read())
                time.sleep(self.pause)
                return out
            except Exception as e:  # network hiccup or rate limit: back off and retry
                last = e
                time.sleep(1.5 * (attempt + 1))
        raise RPCTransportError(f"RPC request failed after {self.retries} tries: {last}")

    def call(self, method: str, params: list):
        self._id += 1
        out = self._post({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        if "error" in out:
            raise RPCError(f"{method}: {out['error']}")
        return out["result"]

    # Convenience wrappers --------------------------------------------------
    def block_number(self) -> int:
        return int(self.call("eth_blockNumber", []), 16)

    def block_timestamp(self, block: int) -> int:
        return int(self.call("eth_getBlockByNumber", [hex(block), False])["timestamp"], 16)

    def get_code(self, address: str) -> str:
        return self.call("eth_getCode", [address, self._tag()])

    def get_storage(self, address: str, slot_hex: str) -> str:
        return self.call("eth_getStorageAt", [address, "0x" + slot_hex, self._tag()])

    def get_balance(self, address: str) -> int:
        return int(self.call("eth_getBalance", [address, self._tag()]), 16)

    def get_nonce(self, address: str) -> int:
        return int(self.call("eth_getTransactionCount", [address, self._tag()]), 16)

    def eth_call(self, to: str, data: str) -> str:
        return self.call("eth_call", [{"to": to, "data": data}, self._tag()])

    def get_logs(self, address: str, topics: list, from_block: int, to_block: int) -> list[dict]:
        return self.call("eth_getLogs", [{"address": address, "topics": topics,
                                          "fromBlock": hex(from_block), "toBlock": hex(to_block)}])

    def get_transaction(self, tx_hash: str) -> dict:
        return self.call("eth_getTransactionByHash", [tx_hash])
