"""Summary and verification logic on synthetic data."""
import csv
import json

from atlas import summarize, verify
from atlas import constants as K


def write(path, rows):
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def test_summary_end_to_end(tmp_path):
    write(tmp_path / "02_exposed_eth_summary.csv", [{
        "eth_all_accounts": "120000000", "eth_in_contracts": "50000000", "eth_in_eoas": "70000000",
        "eth_in_exposed_eoas": "60000000", "eth_in_unexposed_eoas": "10000000",
        "n_exposed_eoas_with_balance": "90000000", "n_unexposed_eoas_with_balance": "40000000",
        "eth_in_top1000_exposed_eoas": "20000000", "data_freshness_last_tx": "2026-09-27"}])
    write(tmp_path / "03_exposure_distribution.csv", [
        {"balance_bucket_eth": "3: 1-10", "last_sent_year": "2017", "n_accounts": "5", "eth": "100"},
        {"balance_bucket_eth": "3: 1-10", "last_sent_year": "2026", "n_accounts": "5", "eth": "50"}])
    write(tmp_path / "06_permit_token_exposure.csv", [
        {"token": "0xa", "symbol": "USDC", "decimals": "6", "exposed_holders": "10", "unexposed_eoa_holders": "2",
         "raw_exposed": "5000000000000", "raw_unexposed_eoa": "1000000"},
        {"token": "0xb", "symbol": "OLD", "decimals": "18", "exposed_holders": "3", "unexposed_eoa_holders": "0",
         "raw_exposed": "2000000000000000000", "raw_unexposed_eoa": "0"},
        {"token": "0xc", "symbol": "NOPE", "decimals": "18", "exposed_holders": "3", "unexposed_eoa_holders": "0",
         "raw_exposed": "1", "raw_unexposed_eoa": "0"}])
    write(tmp_path / "token_classification.csv", [
        {"token": "0xa", "permit": "True", "permit_kind": "erc2612", "permit_source": "implementation",
         "upgradeable": "True", "mechanism": "zos", "implementation": "0xi", "error": ""},
        {"token": "0xb", "permit": "True", "permit_kind": "erc2612", "permit_source": "direct",
         "upgradeable": "no_signal", "mechanism": "", "implementation": "", "error": ""},
        {"token": "0xc", "permit": "False", "permit_kind": "", "permit_source": "",
         "upgradeable": "True", "mechanism": "eip1967", "implementation": "0xj", "error": ""}])
    write(tmp_path / "prices.csv", [
        {"key": "0xa", "symbol": "USDC", "decimals": "6", "price_usd": "1.0", "confidence": "0.99", "timestamp": "1"},
        {"key": "0xb", "symbol": "OLD", "decimals": "18", "price_usd": "2.5", "confidence": "0.99", "timestamp": "1"},
        {"key": "ethereum", "symbol": "ETH", "decimals": "", "price_usd": "2000", "confidence": "0.99", "timestamp": "1"}])

    s = summarize.build(tmp_path)
    assert s["eth"]["share_of_all_eth"] == 0.5
    assert s["eth"]["usd_in_exposed_eoas"] == 60000000 * 2000
    assert s["dormancy"]["eth_exposed_last_active_5plus_years_ago"] == 100
    p = s["permit"]
    assert p["permit_tokens_confirmed"] == 2           # 0xc has no permit
    assert p["usd_exposed_upgradeable"] == 5_000_000   # 5e12 raw / 1e6 * $1
    assert p["usd_exposed_no_upgrade_signal"] == 5.0   # 2 tokens * $2.5
    assert (tmp_path / "SUMMARY.md").read_text().startswith("# Ethereum Quantum Exposure Atlas")
    json.loads((tmp_path / "summary.json").read_text())


class FakeNode:
    def __init__(self):
        self.addr_ok = "0x" + "01" * 20
        self.addr_contract = "0x" + "02" * 20

    def get_nonce(self, a):
        return 5

    def get_code(self, a):
        return "0x6080" if a == self.addr_contract else "0x"

    def get_balance(self, a):
        return 10 ** 18

    def eth_call(self, to, data):
        assert data.startswith("0x" + K.SEL_BALANCE_OF) and len(data) == 2 + 8 + 64
        return hex(1000)


def test_verify_accounts_flags_mismatch():
    node = FakeNode()
    res = verify.check_accounts(node, [
        {"address": node.addr_ok, "eth_wei": str(10 ** 18)},
        {"address": node.addr_contract, "eth_wei": str(10 ** 18)}])
    assert res["checked"] == 2 and res["nonce_gt_0"] == 2 and res["eoa_code"] == 1
    assert len(res["mismatches"]) == 1


def test_verify_holdings():
    res = verify.check_holdings(FakeNode(), [
        {"token": "0xt", "holder": "0x" + "03" * 20, "raw_balance": "1000"},
        {"token": "0xt", "holder": "0x" + "04" * 20, "raw_balance": "5000"}])
    assert res["within_tolerance"] == 1 and len(res["mismatches"]) == 1


def test_summary_with_no_outputs_yet(tmp_path):
    out = tmp_path / "does_not_exist_yet"
    s = summarize.build(out)
    assert "eth" not in s and (out / "SUMMARY.md").exists()
