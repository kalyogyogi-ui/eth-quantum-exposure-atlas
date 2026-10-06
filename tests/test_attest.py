"""Attestations: sign, verify, and every way verification must fail. No network."""
import json
from pathlib import Path

import pytest

from atlas import cli, crypto
from atlas.attest import attestation as A

KEY = 0xA77E57  # test-only key
SIGNER = crypto.private_key_to_address(KEY)
SCHEMAS = Path(__file__).resolve().parent.parent / "atlas" / "attest" / "schemas"


def snapshot(tmp_path, **manifest):
    d = tmp_path / "2026-10-05"
    d.mkdir(parents=True)
    m = {"snapshot_date": "2026-10-05", "git_commit": "ab" * 20, "git_dirty": False, "method_version": "0.1.0",
         "data_freshness_last_tx": "2026-10-04 23:59:59 UTC", "files_sha256": {}}
    m.update(manifest)
    (d / "manifest.json").write_text(json.dumps(m))
    return d


def test_snapshot_round_trip(tmp_path):
    out = A.snapshot_attestation(snapshot(tmp_path), KEY)
    assert out.name == "manifest.json.attestation.json"
    att = json.loads(out.read_text())
    assert att["signer"] == SIGNER and att["message"]["dataTimestamp"] == 1791158399  # 2026-10-04 23:59:59 UTC
    assert att["message"]["subject"] == "eth-quantum-exposure-atlas/snapshot/2026-10-05"
    res = A.verify(out, {SIGNER: "test"})
    assert res["ok"] and [c["check"] for c in res["checks"]] == [
        "schema", "file_sha256", "digest", "signature", "trusted_signer"]


def test_signing_is_deterministic(tmp_path):
    d = snapshot(tmp_path)
    first = A.snapshot_attestation(d, KEY).read_bytes()
    assert A.snapshot_attestation(d, KEY).read_bytes() == first


def failed(res):
    return [c["check"] for c in res["checks"] if not c["passed"]]


def test_tampered_file_fails(tmp_path):
    d = snapshot(tmp_path)
    out = A.snapshot_attestation(d, KEY)
    (d / "manifest.json").write_text((d / "manifest.json").read_text().replace("0.1.0", "9.9.9"))
    res = A.verify(out, {SIGNER: ""})
    assert not res["ok"] and failed(res) == ["file_sha256"]


def test_tampered_message_fails(tmp_path):
    out = A.snapshot_attestation(snapshot(tmp_path), KEY)
    att = json.loads(out.read_text())
    att["message"]["blockNumber"] = 999
    out.write_text(json.dumps(att))
    res = A.verify(out, {SIGNER: ""})
    assert failed(res) == ["digest", "signature", "trusted_signer"]  # tampered message recovers to another key


def test_forged_signer_claim_fails(tmp_path):
    out = A.snapshot_attestation(snapshot(tmp_path), KEY)
    att = json.loads(out.read_text())
    att["signer"] = "0x" + "11" * 20
    out.write_text(json.dumps(att))
    res = A.verify(out, {"0x" + "11" * 20: "impostor"})
    assert "signature" in failed(res) and not res["ok"]


def test_valid_signature_from_unknown_key_is_not_trusted(tmp_path):
    out = A.snapshot_attestation(snapshot(tmp_path), KEY)
    res = A.verify(out, {})
    assert failed(res) == ["trusted_signer"] and not res["ok"]
    res = A.verify(out, {"0x" + "22" * 20: "someone else"})
    assert failed(res) == ["trusted_signer"]


def test_type_substitution_and_path_escape_fail(tmp_path):
    out = A.snapshot_attestation(snapshot(tmp_path), KEY)
    att = json.loads(out.read_text())
    bad = dict(att, types={**att["types"], "SnapshotAttestation": att["types"]["SnapshotAttestation"][:-1]})
    out.write_text(json.dumps(bad))
    assert failed(A.verify(out, {SIGNER: ""})) == ["schema"]
    out.write_text(json.dumps(dict(att, file="../secret")))
    assert failed(A.verify(out, {SIGNER: ""})) == ["schema"]


def test_refuses_undated_or_dirty_snapshot(tmp_path):
    with pytest.raises(A.AttestationError, match="undated"):
        A.snapshot_attestation(snapshot(tmp_path, data_freshness_last_tx=None), KEY)
    with pytest.raises(A.AttestationError, match="uncommitted"):
        A.snapshot_attestation(snapshot(tmp_path / "x", git_dirty=True), KEY)


def test_org_attestation(tmp_path):
    report = tmp_path / "acme.json"
    report.write_text(json.dumps({"slug": "acme", "block": 21_000_000, "block_timestamp": 1_759_700_000}))
    out = A.org_attestation(report, KEY, "cd" * 20)
    att = json.loads(out.read_text())
    assert att["primaryType"] == "OrgAttestation" and att["message"]["blockNumber"] == 21_000_000
    assert A.verify(out, {SIGNER: ""})["ok"]
    report.write_text(json.dumps({"slug": "acme", "block": 1}))
    with pytest.raises(A.AttestationError, match="block_timestamp"):
        A.org_attestation(report, KEY, "cd" * 20)


@pytest.mark.parametrize("raw", [None, "", "zz", "0x0", hex(crypto.N)])
def test_bad_keys_are_refused(raw):
    with pytest.raises(A.AttestationError):
        A.parse_key(raw)


def test_schema_files_match_eip712_fields():
    for primary in A.PRIMARY_TYPES:
        schema = json.loads((SCHEMAS / f"{primary}.schema.json").read_text())
        assert schema["properties"]["primaryType"]["const"] == primary
        assert list(schema["properties"]["message"]["properties"]) == [f["name"] for f in A.FIELDS]
        assert schema["properties"]["domain"]["const"] == A.DOMAIN


def test_cli_sign_and_verify(tmp_path, monkeypatch, capsys):
    d = snapshot(tmp_path)
    signers = tmp_path / "signers.json"
    signers.write_text(json.dumps({"signers": [{"address": SIGNER, "label": "test"}]}))
    monkeypatch.delenv(A.KEY_ENV, raising=False)
    assert cli.main(["attest", "sign-snapshot", str(d), "--signers", str(signers)]) == 2
    monkeypatch.setenv(A.KEY_ENV, hex(KEY))
    assert cli.main(["attest", "sign-snapshot", str(d), "--signers", str(signers)]) == 0
    att = str(d / "manifest.json.attestation.json")
    assert cli.main(["attest", "verify", att, "--signers", str(signers)]) == 0
    assert "VERIFIED" in capsys.readouterr().out
    assert cli.main(["attest", "verify", att, "--signers", str(tmp_path / "none.json")]) == 1
    assert cli.main(["attest", "verify", att, "--signers", str(tmp_path / "none.json"), "--signer", SIGNER]) == 0
    assert hex(KEY)[2:] not in capsys.readouterr().out   # the key is never printed
