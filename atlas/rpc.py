"""Minimal Ethereum JSON-RPC client using only the standard library."""
import json
import time
import urllib.request


class RPCError(RuntimeError):
    pass


class RPC:
    def __init__(self, url: str, timeout: float = 30.0, pause: float = 0.05, retries: int = 3):
        self.url = url
        self.timeout = timeout
        self.pause = pause
        self.retries = retries
        self._id = 0

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
        raise RPCError(f"RPC request failed after {self.retries} tries: {last}")

    def call(self, method: str, params: list):
        self._id += 1
        out = self._post({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        if "error" in out:
            raise RPCError(f"{method}: {out['error']}")
        return out["result"]

    # Convenience wrappers --------------------------------------------------
    def get_code(self, address: str) -> str:
        return self.call("eth_getCode", [address, "latest"])

    def get_storage(self, address: str, slot_hex: str) -> str:
        return self.call("eth_getStorageAt", [address, "0x" + slot_hex, "latest"])

    def get_balance(self, address: str) -> int:
        return int(self.call("eth_getBalance", [address, "latest"]), 16)

    def get_nonce(self, address: str) -> int:
        return int(self.call("eth_getTransactionCount", [address, "latest"]), 16)

    def eth_call(self, to: str, data: str) -> str:
        return self.call("eth_call", [{"to": to, "data": data}, "latest"])
