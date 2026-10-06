"""secp256k1 and keccak for Ethereum signatures, in pure Python (no native dependency).

Used to recover Safe signers (atlas/orgs/safesig.py) and to sign and verify attestations
(atlas/attest). Signing uses deterministic nonces (RFC 6979, HMAC-SHA256) and low-s form,
as Ethereum signers do; tests reproduce the EIP-712 reference signature exactly.
"""
import hashlib
import hmac

from Crypto.Hash import keccak

# secp256k1 domain parameters (SEC 2, section 2.4.1). tests/test_safesig.py checks that G is
# on the curve and has order N, so a typo here fails the tests.
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
     0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)


def keccak256(data: bytes) -> bytes:
    h = keccak.new(digest_bits=256)
    h.update(data)
    return h.digest()


def point_add(a, b):
    if a is None:
        return b
    if b is None:
        return a
    if a[0] == b[0] and (a[1] + b[1]) % P == 0:
        return None
    if a == b:
        lam = 3 * a[0] * a[0] * pow(2 * a[1], -1, P) % P
    else:
        lam = (b[1] - a[1]) * pow(b[0] - a[0], -1, P) % P
    x = (lam * lam - a[0] - b[0]) % P
    return x, (lam * (a[0] - x) - a[1]) % P


def point_mul(k: int, pt):
    out = None
    while k:
        if k & 1:
            out = point_add(out, pt)
        pt = point_add(pt, pt)
        k >>= 1
    return out


def pubkey_to_address(pt) -> str:
    return "0x" + keccak256(pt[0].to_bytes(32, "big") + pt[1].to_bytes(32, "big"))[12:].hex()


def recover(msg_hash: bytes, v: int, r: int, s: int) -> str | None:
    """Ethereum ecrecover: v is 27 or 28. Returns the signer address, or None if invalid."""
    if v not in (27, 28) or not (0 < r < N and 0 < s < N):
        return None
    y2 = (pow(r, 3, P) + 7) % P
    y = pow(y2, (P + 1) // 4, P)
    if y * y % P != y2:
        return None
    if y % 2 != v - 27:
        y = P - y
    e = int.from_bytes(msg_hash, "big") % N
    r_inv = pow(r, -1, N)
    q = point_add(point_mul(s * r_inv % N, (r, y)), point_mul((-e * r_inv) % N, G))
    return None if q is None else pubkey_to_address(q)




def private_key_to_address(d: int) -> str:
    return pubkey_to_address(point_mul(d, G))


def _rfc6979_k(d: int, h: bytes) -> int:
    """Deterministic nonce, RFC 6979 section 3.2 with HMAC-SHA256 (qlen = hlen = 256)."""
    x = d.to_bytes(32, "big")
    z = (int.from_bytes(h, "big") % N).to_bytes(32, "big")
    v, k = b"\x01" * 32, b"\x00" * 32
    k = hmac.new(k, v + b"\x00" + x + z, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    k = hmac.new(k, v + b"\x01" + x + z, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    while True:
        v = hmac.new(k, v, hashlib.sha256).digest()
        cand = int.from_bytes(v, "big")
        if 1 <= cand < N:
            return cand
        k = hmac.new(k, v + b"\x00", hashlib.sha256).digest()
        v = hmac.new(k, v, hashlib.sha256).digest()


def sign(msg_hash: bytes, d: int) -> tuple[int, int, int]:
    """Sign a 32-byte hash with private key d. Returns (v, r, s), v in {27, 28}, low s."""
    if not 0 < d < N:
        raise ValueError("private key out of range")
    e = int.from_bytes(msg_hash, "big") % N
    k = _rfc6979_k(d, msg_hash)
    R = point_mul(k, G)
    r = R[0] % N
    s = pow(k, -1, N) * (e + r * d) % N
    if r == 0 or s == 0:
        raise ValueError("invalid nonce; retry with a different message")
    parity = R[1] & 1
    if s > N // 2:
        s, parity = N - s, parity ^ 1
    return 27 + parity, r, s
