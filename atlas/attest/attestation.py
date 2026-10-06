"""Create and verify PQ-Attest attestations.

An attestation is a JSON file written beside the data it covers. It holds EIP-712 typed
data whose message names the subject, the block and data time it describes, the SHA-256 of
the covered file, the repo commit and the method version, plus a signature over it. Anyone
can verify it offline with `python -m atlas attest verify FILE`:

  1. the file's structure and EIP-712 types are exactly one of the two published schemas;
  2. the covered file's SHA-256 equals message.fileSha256;
  3. the EIP-712 digest recomputes to the recorded digest;
  4. the signature recovers to the recorded signer;
  5. the signer is one the reader trusts (--signer, or attest/signers.json in the repo).

Steps 1-4 prove the file is unchanged since a key signed it. Step 5 is what ties that key to
the author; it is a separate, explicit check so a valid signature from an unknown key is
never reported as trusted.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .. import __version__, crypto
from . import eip712

ATTESTATION_VERSION = 1
SCHEMA_VERSION = 1
DOMAIN = {"name": "PQ-Attest", "version": "1"}
DOMAIN_TYPE = [{"name": "name", "type": "string"}, {"name": "version", "type": "string"}]
FIELDS = [
    {"name": "schemaVersion", "type": "uint16"},
    {"name": "subject", "type": "string"},
    {"name": "blockNumber", "type": "uint64"},
    {"name": "dataTimestamp", "type": "uint64"},
    {"name": "fileSha256", "type": "bytes32"},
    {"name": "repoCommit", "type": "string"},
    {"name": "methodVersion", "type": "string"},
]
PRIMARY_TYPES = ("SnapshotAttestation", "OrgAttestation")
KEY_ENV = "ATLAS_ATTEST_KEY"
SUFFIX = ".attestation.json"


class AttestationError(ValueError):
    pass


def types_for(primary: str) -> dict:
    if primary not in PRIMARY_TYPES:
        raise AttestationError(f"unknown attestation type {primary!r}")
    return {"EIP712Domain": DOMAIN_TYPE, primary: FIELDS}


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return "0x" + h.hexdigest()


def parse_key(raw: str | None) -> int:
    if not raw:
        raise AttestationError(f"set {KEY_ENV} to a hex private key used only for attestations")
    try:
        d = int(raw.strip().removeprefix("0x"), 16)
    except ValueError:
        raise AttestationError(f"{KEY_ENV} is not hex") from None
    if not 0 < d < crypto.N:
        raise AttestationError(f"{KEY_ENV} is not a valid secp256k1 private key")
    return d


def to_unix(ts: str) -> int:
    """'2026-10-04 23:59:59 UTC', '2026-10-04 23:59:59+00:00' or ISO 8601 -> seconds."""
    t = str(ts).strip().replace(" UTC", "+00:00").replace("Z", "+00:00")
    dt = datetime.fromisoformat(t)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def build(primary: str, subject: str, covered: Path, block_number: int, data_timestamp: int,
          repo_commit: str, method_version: str = __version__) -> dict:
    return {
        "types": types_for(primary), "primaryType": primary, "domain": dict(DOMAIN),
        "message": {"schemaVersion": SCHEMA_VERSION, "subject": subject, "blockNumber": int(block_number),
                    "dataTimestamp": int(data_timestamp), "fileSha256": file_sha256(covered),
                    "repoCommit": repo_commit, "methodVersion": method_version},
    }


def sign(typed: dict, key: int, covered_name: str) -> dict:
    h = eip712.digest(typed)
    v, r, s = crypto.sign(h, key)
    return {
        "attestationVersion": ATTESTATION_VERSION, **typed, "file": covered_name,
        "digest": "0x" + h.hex(), "signer": crypto.private_key_to_address(key),
        "signature": {"v": v, "r": f"0x{r:064x}", "s": f"0x{s:064x}",
                      "bytes": f"0x{r:064x}{s:064x}{v:02x}"},
    }


def write(att: dict, covered: Path) -> Path:
    out = covered.with_name(covered.name + SUFFIX)
    out.write_text(json.dumps(att, indent=2) + "\n")
    return out


def snapshot_attestation(snapshot_dir: Path, key: int) -> Path:
    """Attest a snapshot by its manifest, which lists the SHA-256 of every file in it."""
    manifest_path = Path(snapshot_dir) / "manifest.json"
    if not manifest_path.exists():
        raise AttestationError(f"{manifest_path} not found; run `atlas snapshot` first")
    m = json.loads(manifest_path.read_text())
    if not m.get("data_freshness_last_tx"):
        raise AttestationError("manifest has no data_freshness_last_tx; refusing to attest an undated snapshot")
    if m.get("git_dirty"):
        raise AttestationError("snapshot was made from uncommitted code; its commit hash does not describe it")
    typed = build("SnapshotAttestation", f"eth-quantum-exposure-atlas/snapshot/{m['snapshot_date']}",
                  manifest_path, int(m.get("block_number", 0)), to_unix(m["data_freshness_last_tx"]),
                  m["git_commit"], m.get("method_version", __version__))
    return write(sign(typed, key, manifest_path.name), manifest_path)


def org_attestation(report_path: Path, key: int, repo_commit: str) -> Path:
    r = json.loads(Path(report_path).read_text())
    if not r.get("block") or not r.get("block_timestamp"):
        raise AttestationError("report has no block or block_timestamp; re-run `atlas orgs`")
    typed = build("OrgAttestation", f"eth-quantum-exposure-atlas/org/{r['slug']}", Path(report_path),
                  r["block"], r["block_timestamp"], repo_commit, r.get("method_version", __version__))
    return write(sign(typed, key, Path(report_path).name), Path(report_path))


def load_trusted(path: Path) -> dict:
    """attest/signers.json: {"signers": [{"address": "0x..", "label": "..."}]}."""
    if not Path(path).exists():
        return {}
    data = json.loads(Path(path).read_text())
    return {s["address"].lower(): s.get("label", "") for s in data.get("signers", [])}


def verify(att_path: Path, trusted: dict | None = None) -> dict:
    """Run every check and report each one; `ok` is true only if all pass, trust included."""
    att_path = Path(att_path)
    checks, ok = [], True

    def check(name: str, passed: bool, detail: str = ""):
        nonlocal ok
        ok = ok and passed
        checks.append({"check": name, "passed": passed, "detail": detail})
        return passed

    try:
        att = json.loads(att_path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        check("readable", False, str(e)[:120])
        return {"ok": False, "checks": checks}

    primary = att.get("primaryType")
    try:
        expected_types = types_for(primary)
    except AttestationError as e:
        check("schema", False, str(e))
        return {"ok": False, "checks": checks}
    structure_ok = (att.get("attestationVersion") == ATTESTATION_VERSION and att.get("types") == expected_types
                    and att.get("domain") == DOMAIN and isinstance(att.get("message"), dict)
                    and set(att["message"]) == {f["name"] for f in FIELDS}
                    and att["message"].get("schemaVersion") == SCHEMA_VERSION
                    and isinstance(att.get("file"), str) and "/" not in att["file"] and "\\" not in att["file"])
    if not check("schema", structure_ok, primary):
        return {"ok": False, "checks": checks}

    covered = att_path.parent / att["file"]
    if covered.exists():
        actual = file_sha256(covered)
        check("file_sha256", actual == att["message"]["fileSha256"].lower(),
              f"{att['file']}: {actual}" + ("" if actual == att["message"]["fileSha256"].lower()
                                             else f" != attested {att['message']['fileSha256']}"))
    else:
        check("file_sha256", False, f"{att['file']} not found beside the attestation")

    try:
        h = eip712.digest(att)
    except (ValueError, KeyError) as e:
        check("digest", False, str(e)[:120])
        return {"ok": False, "checks": checks}
    check("digest", "0x" + h.hex() == str(att.get("digest", "")).lower(), "0x" + h.hex())

    sig = att.get("signature", {})
    try:
        signer = crypto.recover(h, int(sig["v"]), int(sig["r"], 16), int(sig["s"], 16))
    except (KeyError, TypeError, ValueError):
        signer = None
    claimed = str(att.get("signer", "")).lower()
    check("signature", signer is not None and signer == claimed,
          f"recovers to {signer}" + ("" if signer == claimed else f", attestation claims {claimed}"))

    trusted = trusted or {}
    if signer and signer in trusted:
        check("trusted_signer", True, f"{signer} ({trusted[signer] or 'listed'})")
    else:
        check("trusted_signer", False, f"{signer} is not in the trusted signer list"
              if trusted else "no trusted signer given (--signer or attest/signers.json)")
    return {"ok": ok, "checks": checks, "signer": signer, "message": att["message"], "type": primary}
