"""Find Safe owners whose public key is revealed by a signature, even at nonce 0.

A Safe owner who never sends a transaction still reveals their secp256k1 public key when
their ECDSA signature appears in the calldata of an executed Safe transaction: anyone can
recover the key from (hash, v, r, s). This module looks for that evidence:

  1. eth_getLogs for ExecutionSuccess on the Safe (txHash is in the log data for Safe
     v1.1.1-v1.3.0 and in topics[1] for v1.4.1);
  2. eth_getTransactionByHash for each, decoding execTransaction's `signatures` argument;
  3. recovering each ECDSA signer (v 27/28 over the Safe tx hash, v > 30 over the eth_sign
     digest). Contract signatures (v 0) and approved hashes (v 1) reveal no key from the Safe
     owner's signature, so they are skipped.

Signature checking rules follow Safe's checkNSignatures:
https://raw.githubusercontent.com/safe-global/safe-smart-account/v1.3.0/contracts/GnosisSafe.sol

Limits (stated in the report): Safe v1.0.0 emits no ExecutionSuccess; Safe transactions
executed through another contract (relayers, modules, batched calls) have no top-level
execTransaction calldata to decode and are counted as undecodable; free RPC endpoints cap
eth_getLogs ranges, so scanning a Safe's full history can be slow or refused.
"""
from .. import constants as K
from ..proxies import strip0x
from ..crypto import G, N, P, keccak256, point_add, point_mul, pubkey_to_address, recover  # noqa: F401
from ..rpc import RPCError, RPCTransportError

def eth_sign_digest(h: bytes) -> bytes:
    return keccak256(b"\x19Ethereum Signed Message:\n32" + h)


def exec_signatures(input_hex: str) -> bytes | None:
    """The `signatures` bytes from execTransaction calldata, or None if not execTransaction."""
    d = strip0x(input_hex)
    if not d.startswith(K.SEL_SAFE_EXEC) or len(d) < 8 + 64 * 10:
        return None
    body = bytes.fromhex(d[8:])
    off = int.from_bytes(body[9 * 32:10 * 32], "big")
    if off + 32 > len(body):
        return None
    n = int.from_bytes(body[off:off + 32], "big")
    sig = body[off + 32:off + 32 + n]
    return sig if len(sig) == n else None


def signers(signatures: bytes, safe_tx_hash: bytes) -> list[dict]:
    """Owners recovered from ECDSA signatures; contract and approved-hash entries are listed
    with the address encoded in r but reveal no key."""
    out, end, i = [], len(signatures), 0
    while (i + 1) * 65 <= end:
        chunk = signatures[i * 65:(i + 1) * 65]
        r, s, v = int.from_bytes(chunk[:32], "big"), int.from_bytes(chunk[32:64], "big"), chunk[64]
        if v == 0:
            out.append({"signer": "0x" + chunk[12:32].hex(), "kind": "contract", "reveals_key": False})
            end = min(end, s)  # dynamic contract-signature data starts at offset s
        elif v == 1:
            out.append({"signer": "0x" + chunk[12:32].hex(), "kind": "approved_hash", "reveals_key": False})
        elif v > 30:
            a = recover(eth_sign_digest(safe_tx_hash), v - 4, r, s)
            if a:
                out.append({"signer": a, "kind": "eth_sign", "reveals_key": True})
        else:
            a = recover(safe_tx_hash, v, r, s)
            if a:
                out.append({"signer": a, "kind": "ecdsa", "reveals_key": True})
        i += 1
    return out


def _safe_tx_hash(log: dict) -> bytes | None:
    topics = log.get("topics", [])
    if len(topics) > 1:                     # v1.4.1: indexed
        return bytes.fromhex(strip0x(topics[1]))
    data = strip0x(log.get("data"))
    return bytes.fromhex(data[:64]) if len(data) >= 64 else None   # v1.1.1-v1.3.0


class SignatureFinder:
    """Scans a Safe's executed transactions once and answers for any of its owners."""

    def __init__(self, rpc, from_block: int, to_block: int, chunk: int = 10_000, min_chunk: int = 500):
        self.rpc, self.from_block, self.to_block = rpc, from_block, to_block
        self.chunk, self.min_chunk = chunk, min_chunk
        self._cache: dict[str, dict] = {}

    def _logs(self, safe: str) -> list[dict]:
        logs, start, chunk = [], self.from_block, self.chunk
        while start <= self.to_block:
            end = min(start + chunk - 1, self.to_block)
            try:
                logs += self.rpc.get_logs(safe, [K.TOPIC_SAFE_EXECUTION_SUCCESS], start, end)
            except RPCTransportError:
                raise
            except RPCError:
                if chunk <= self.min_chunk:
                    raise
                chunk //= 2                 # endpoint refused the range: retry smaller
                continue
            start = end + 1
        return logs

    def scan(self, safe: str) -> dict:
        if safe in self._cache:
            return self._cache[safe]
        result = {"from_block": self.from_block, "to_block": self.to_block, "executions": 0,
                  "decoded": 0, "undecodable": 0, "revealed": {}}
        try:
            logs = self._logs(safe)
        except RPCError as e:
            result["error"] = f"eth_getLogs refused: {str(e)[:120]}"
            self._cache[safe] = result
            return result
        for log in logs:
            result["executions"] += 1
            h = _safe_tx_hash(log)
            tx = self.rpc.get_transaction(log["transactionHash"])
            sigs = exec_signatures(tx.get("input", "")) if (tx and str(tx.get("to", "")).lower() == safe) else None
            if h is None or sigs is None:
                result["undecodable"] += 1
                continue
            result["decoded"] += 1
            for s in signers(sigs, h):
                if s["reveals_key"] and s["signer"] not in result["revealed"]:
                    result["revealed"][s["signer"]] = {"tx_hash": log["transactionHash"],
                                                       "block": int(log["blockNumber"], 16),
                                                       "safe_tx_hash": "0x" + h.hex(), "kind": s["kind"]}
        self._cache[safe] = result
        return result


def apply(nodes: dict, finder: SignatureFinder) -> None:
    """Mark nonce-0 Safe owners as exposed when their signature was found in Safe calldata."""
    for node in nodes.values():
        if node["kind"] != "safe":
            continue
        owners = [c["address"] for c in node["controllers"]]
        quiet = [o for o in owners if nodes.get(o, {}).get("kind") == "eoa" and not nodes[o]["exposed"]]
        if not quiet:
            continue
        scan = finder.scan(node["address"])
        node["signature_scan"] = {k: v for k, v in scan.items() if k != "revealed"}
        for o in quiet:
            hit = scan["revealed"].get(o)
            check = {"safe": node["address"], "found": bool(hit)}
            if hit:
                check.update(hit)
                nodes[o].update(exposed=True, exposure_basis=f"public key recoverable from a {hit['kind']} "
                                f"signature in Safe transaction {hit['tx_hash']} (block {hit['block']})")
            elif "error" in scan:
                check["note"] = scan["error"]
            nodes[o].setdefault("signature_checks", []).append(check)
