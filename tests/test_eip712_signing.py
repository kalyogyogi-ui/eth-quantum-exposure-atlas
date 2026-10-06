"""EIP-712 hashing and RFC 6979 signing against the EIP's own reference example.

Expected values are from
https://raw.githubusercontent.com/ethereum/EIPs/master/assets/eip-712/Example.js
"""
from atlas import crypto
from atlas.attest import eip712

MAIL = {
    "types": {
        "EIP712Domain": [{"name": "name", "type": "string"}, {"name": "version", "type": "string"},
                         {"name": "chainId", "type": "uint256"}, {"name": "verifyingContract", "type": "address"}],
        "Person": [{"name": "name", "type": "string"}, {"name": "wallet", "type": "address"}],
        "Mail": [{"name": "from", "type": "Person"}, {"name": "to", "type": "Person"},
                 {"name": "contents", "type": "string"}],
    },
    "primaryType": "Mail",
    "domain": {"name": "Ether Mail", "version": "1", "chainId": 1,
               "verifyingContract": "0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC"},
    "message": {"from": {"name": "Cow", "wallet": "0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826"},
                "to": {"name": "Bob", "wallet": "0xbBbBBBBbbBBBbbbBbbBbbbbBBbBbbbbBbBbbBBbB"},
                "contents": "Hello, Bob!"},
}


def test_encode_type_and_hashes():
    t = MAIL["types"]
    assert eip712.encode_type("Mail", t) == "Mail(Person from,Person to,string contents)Person(string name,address wallet)"
    assert eip712.type_hash("Mail", t).hex() == "a0cedeb2dc280ba39b857546d74f5549c3a1d7bdc2dd96bf881f76108e23dac2"
    assert eip712.hash_struct("Mail", MAIL["message"], t).hex() == \
        "c52c0ee5d84264471806290a3f2c4cecfc5490626bf912d01f240d7a274b371e"
    assert eip712.hash_struct("EIP712Domain", MAIL["domain"], t).hex() == \
        "f2cee375fa42b42143804025fc449deafd50cc031ca257e0b194a650a912090f"
    assert eip712.digest(MAIL).hex() == "be609aee343fb3c4b28e1df9e632fca64fcfaede20f02e86244efddf30957bd2"


def test_deterministic_signature_matches_reference():
    d = int.from_bytes(crypto.keccak256(b"cow"), "big")
    assert crypto.private_key_to_address(d) == "0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826"
    v, r, s = crypto.sign(eip712.digest(MAIL), d)
    assert v == 28
    assert f"{r:064x}" == "4355c47d63924e8a72e509b65029052eb6c299d53a04e167c5775fd466751c9d"
    assert f"{s:064x}" == "07299936d304c153f6443dfa05f40ff007d72911b6f72307f996231605b91562"
    assert crypto.recover(eip712.digest(MAIL), v, r, s) == "0xcd2a3d9f938e13cd947ec05abc7fe734df8dd826"


def test_sign_is_low_s_and_recoverable_for_many_keys():
    h = crypto.keccak256(b"pq-attest")
    for d in (1, 2, 12345, crypto.N - 1):
        v, r, s = crypto.sign(h, d)
        assert s <= crypto.N // 2 and crypto.recover(h, v, r, s) == crypto.private_key_to_address(d)
