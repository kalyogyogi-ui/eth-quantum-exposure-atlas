"""Report building: deterministic output, unpublished banner, CLI wiring. No network."""
import json

from atlas import cli
from atlas.orgs import report
from atlas.orgs.registry import parse

from test_org_resolve import FakeChain, addr, eoa, owned, safe, word
from atlas import constants as K

TOKEN, PA, SAFE_ADDR, HOT, COLD = addr(0x70), addr(0x71), addr(0x72), addr(1), addr(2)
ACCOUNTS = {
    TOKEN: {"code": "0x6080", "storage": {K.SLOT_EIP1967_ADMIN: word(PA)},
            "calls": {K.SEL_OWNER: word(SAFE_ADDR), K.SEL_TOTAL_SUPPLY: "0x" + f"{10**30:064x}",
                      K.SEL_DECIMALS: "0x" + f"{6:064x}"}},
    PA: owned(HOT), SAFE_ADDR: safe([HOT, COLD], 2), HOT: eoa(4), COLD: eoa(0),
}
REGISTRY = {"organisations": [{"slug": "acme", "name": "Acme", "category": "issuer", "contracts": [
    {"address": TOKEN, "role": "token", "label": "ACME", "source_url": "https://docs.acme.example/a"}]}]}


def build():
    (org,) = parse(REGISTRY)
    return report.run_org(FakeChain(ACCOUNTS), org, 19_000_000)


def test_report_content():
    r = build()
    (c,) = r["contracts"]
    assert {(f["role"], f["rule"]) for f in c["findings"]} == {("upgrade_admin", "R1"), ("owner", "R4")}
    assert c["value"]["total_supply_raw"] == str(10 ** 30) and r["rule_counts"] == {"R1": 1, "R4": 1}
    assert r["nodes"][COLD]["signature_checks"][0]["note"].startswith("not checked")
    md = report.to_markdown(r)
    assert "Draft, not published" in md and "Safe 2-of-2" in md and "https://docs.acme.example/a" in md
    assert "Block 19,000,000" in md


def test_same_block_gives_identical_files(tmp_path):
    j1, m1 = report.write(build(), tmp_path / "a")
    j2, m2 = report.write(build(), tmp_path / "b")
    assert j1.read_bytes() == j2.read_bytes() and m1.read_bytes() == m2.read_bytes()
    assert "rpc" not in json.loads(j1.read_text())


def test_cli_pins_one_block(tmp_path, monkeypatch):
    import yaml
    reg = tmp_path / "registry.yaml"
    reg.write_text(yaml.safe_dump(REGISTRY))
    pinned = []

    class FakeRPC(FakeChain):
        def __init__(self, url):
            super().__init__(ACCOUNTS)

        def block_number(self):
            return 123

        def block_timestamp(self, b):
            return 1_759_700_000

        def pinned(self, b):
            pinned.append(b)
            return self

    monkeypatch.setattr("atlas.rpc.RPC", FakeRPC)
    rc = cli.main(["orgs", "--rpc-url", "http://x", "--registry", str(reg), "--out", str(tmp_path / "out")])
    assert rc == 0 and pinned == [123]
    out = json.loads((tmp_path / "out" / "acme.json").read_text())
    assert out["block"] == 123 and out["block_timestamp"] == 1_759_700_000
    assert cli.main(["orgs", "--rpc-url", "http://x", "--registry", str(reg), "--slug", "nope"]) == 2
