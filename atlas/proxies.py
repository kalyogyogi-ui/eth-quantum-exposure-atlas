"""Resolve proxy tokens to their implementation and decide whether permit is reachable.

A proxy's own bytecode contains no permit selector; the permit code (if any) lives in
the implementation. We read the standard storage slots over RPC, then look for the
PUSH4 permit selector in the implementation's bytecode.
"""
import csv
from pathlib import Path

from . import constants as K

UPGRADEABLE = {"eip1967": True, "beacon": True, "zos": True, "eip1822": True,
               "implementation()": True, "eip1167": False}


def strip0x(h: str) -> str:
    return (h or "").lower().removeprefix("0x")


def word_to_address(word: str) -> str | None:
    """Last 20 bytes of a 32-byte word, or None if the word is zero or malformed."""
    w = strip0x(word)
    if len(w) < 40:
        return None
    addr = w[-40:]
    return None if int(addr, 16) == 0 else "0x" + addr


def eip1167_target(code: str) -> str | None:
    c = strip0x(code)
    if c.startswith(K.EIP1167_PREFIX) and len(c) >= len(K.EIP1167_PREFIX) + 40:
        return "0x" + c[len(K.EIP1167_PREFIX):len(K.EIP1167_PREFIX) + 40]
    return None


def permit_kind(code: str) -> str | None:
    c = strip0x(code)
    if K.PUSH4 + K.SEL_PERMIT_2612 in c:
        return "erc2612"
    if K.PUSH4 + K.SEL_PERMIT_DAI in c:
        return "dai"
    return None


def is_eoa_code(code: str) -> bool:
    """Empty code, or an EIP-7702 delegation indicator (still an EOA with a live ECDSA key)."""
    c = strip0x(code)
    return c == "" or (c.startswith(K.EIP7702_PREFIX) and len(c) == 46)


def find_implementation(rpc, token: str, code: str) -> tuple[str | None, str | None]:
    """Return (implementation_address, mechanism)."""
    target = eip1167_target(code)
    if target:
        return target, "eip1167"
    for slot, mech in ((K.SLOT_EIP1967_IMPL, "eip1967"), (K.SLOT_ZOS_IMPL, "zos"), (K.SLOT_EIP1822, "eip1822")):
        addr = word_to_address(rpc.get_storage(token, slot))
        if addr:
            return addr, mech
    beacon = word_to_address(rpc.get_storage(token, K.SLOT_EIP1967_BEACON))
    if beacon:
        try:
            addr = word_to_address(rpc.eth_call(beacon, "0x" + K.SEL_IMPLEMENTATION))
            if addr:
                return addr, "beacon"
        except Exception:
            pass
    try:  # Aragon AppProxy (e.g. stETH) and many custom proxies expose implementation()
        addr = word_to_address(rpc.eth_call(token, "0x" + K.SEL_IMPLEMENTATION))
        if addr and addr.lower() != token.lower():
            return addr, "implementation()"
    except Exception:
        pass
    return None, None


def classify(rpc, row: dict) -> dict:
    """Classify one token row from 06_permit_token_exposure.csv."""
    token = row["token"]
    truthy = lambda v: str(v).lower() in ("true", "1")
    out = {"token": token, "permit": False, "permit_kind": "", "permit_source": "",
           "upgradeable": "", "mechanism": "", "implementation": "", "error": ""}
    try:
        if truthy(row.get("permit_direct")) and not truthy(row.get("proxy_signal")):
            out.update(permit=True, permit_source="direct", upgradeable="no_signal",
                       permit_kind="erc2612" if truthy(row.get("permit_2612_direct")) else "dai")
            return out
        code = rpc.get_code(token)
        direct = permit_kind(code)
        impl, mech = find_implementation(rpc, token, code)
        if impl:
            out.update(implementation=impl, mechanism=mech, upgradeable=UPGRADEABLE[mech])
            kind = permit_kind(rpc.get_code(impl))
            if kind:
                out.update(permit=True, permit_kind=kind, permit_source="implementation")
        elif direct:
            out.update(upgradeable="no_signal")
        if direct and not out["permit"]:
            out.update(permit=True, permit_kind=direct, permit_source="direct")
    except Exception as e:
        out["error"] = str(e)[:200]
    return out


def resolve_file(rpc, in_csv: Path, out_csv: Path, top: int, log=print) -> dict:
    rows = list(csv.DictReader(in_csv.open()))
    rows.sort(key=lambda r: int(r.get("exposed_holders") or 0), reverse=True)
    needs_rpc = [r for r in rows if str(r.get("proxy_signal")).lower() in ("true", "1")]
    rpc_rows = needs_rpc[:top]
    skipped = {r["token"] for r in needs_rpc[top:]}
    results = []
    for i, r in enumerate(rows):
        if r["token"] in skipped:
            continue
        results.append(classify(rpc, r))
        if (i + 1) % 100 == 0:
            log(f"  classified {i + 1} tokens")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()) if results else ["token"])
        w.writeheader()
        w.writerows(results)
    return {"tokens": len(rows), "proxy_candidates": len(needs_rpc),
            "proxy_candidates_resolved": len(rpc_rows), "proxy_candidates_skipped": len(skipped),
            "permit_confirmed": sum(1 for r in results if r["permit"]),
            "errors": sum(1 for r in results if r["error"])}
