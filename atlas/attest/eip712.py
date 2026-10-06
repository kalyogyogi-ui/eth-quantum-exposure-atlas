"""EIP-712 typed-data hashing (https://eips.ethereum.org/EIPS/eip-712).

Supports the types the attestations need plus nested structs, so the EIP's own reference
example can be used as a test vector.
"""
from ..crypto import keccak256


def _deps(primary: str, types: dict, found: set) -> set:
    if primary in found or primary not in types:
        return found
    found.add(primary)
    for f in types[primary]:
        _deps(f["type"].rstrip("[]"), types, found)
    return found


def encode_type(primary: str, types: dict) -> str:
    deps = sorted(_deps(primary, types, set()) - {primary})
    return "".join(f"{t}({','.join(f['type'] + ' ' + f['name'] for f in types[t])})" for t in [primary] + deps)


def type_hash(primary: str, types: dict) -> bytes:
    return keccak256(encode_type(primary, types).encode())


def _bytes(v) -> bytes:
    return bytes.fromhex(v[2:] if isinstance(v, str) and v.startswith("0x") else v) if isinstance(v, str) else bytes(v)


def _encode_value(typ: str, value, types: dict) -> bytes:
    if typ in types:
        return hash_struct(typ, value, types)
    if typ == "string":
        return keccak256(value.encode())
    if typ == "bytes":
        return keccak256(_bytes(value))
    if typ == "bool":
        return int(bool(value)).to_bytes(32, "big")
    if typ == "address":
        b = _bytes(value)
        if len(b) != 20:
            raise ValueError(f"address must be 20 bytes: {value}")
        return b.rjust(32, b"\0")
    if typ.startswith("bytes"):
        n = int(typ[5:])
        b = _bytes(value)
        if len(b) != n:
            raise ValueError(f"{typ} must be {n} bytes, got {len(b)}")
        return b.ljust(32, b"\0")
    if typ.startswith("uint"):
        bits = int(typ[4:] or 256)
        v = int(value)
        if not 0 <= v < 2 ** bits:
            raise ValueError(f"{value} does not fit {typ}")
        return v.to_bytes(32, "big")
    raise ValueError(f"unsupported EIP-712 type: {typ}")


def encode_data(primary: str, data: dict, types: dict) -> bytes:
    out = type_hash(primary, types)
    for f in types[primary]:
        if f["name"] not in data:
            raise ValueError(f"{primary}.{f['name']} missing")
        out += _encode_value(f["type"], data[f["name"]], types)
    return out


def hash_struct(primary: str, data: dict, types: dict) -> bytes:
    return keccak256(encode_data(primary, data, types))


def digest(typed: dict) -> bytes:
    """keccak256("\\x19\\x01" || domainSeparator || hashStruct(message))."""
    types = typed["types"]
    return keccak256(b"\x19\x01" + hash_struct("EIP712Domain", typed["domain"], types)
                     + hash_struct(typed["primaryType"], typed["message"], types))
