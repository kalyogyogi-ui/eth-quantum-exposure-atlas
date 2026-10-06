"""Price filtering, with DefiLlama replaced by a fake."""
import csv

from atlas import pricing


def test_confidence_filter(tmp_path, monkeypatch):
    """Regression: a price with no confidence value was treated as confidence 1.0."""
    cls = tmp_path / "token_classification.csv"
    with cls.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["token", "permit"])
        w.writerows([["0xa", "True"], ["0xb", "True"], ["0xc", "True"], ["0xd", "True"], ["0xe", "False"]])
    fake = {
        "ethereum:0xa": {"price": 1.0, "symbol": "A", "decimals": 6, "confidence": 0.99, "timestamp": 1},
        "ethereum:0xb": {"price": 2.0, "symbol": "B", "decimals": 18, "timestamp": 1},           # no confidence
        "ethereum:0xc": {"price": 3.0, "symbol": "C", "decimals": 18, "confidence": 0.5, "timestamp": 1},
        "coingecko:ethereum": {"price": 2000.0, "symbol": "ETH", "confidence": 0.99, "timestamp": 1},
    }
    seen = []
    monkeypatch.setattr(pricing, "fetch", lambda keys: seen.extend(keys) or fake)
    stats = pricing.price_tokens(cls, tmp_path / "prices.csv")
    assert "ethereum:0xe" not in seen                       # only permit tokens are priced
    assert stats == {"requested": 5, "priced": 2, "not_found": 1,
                     "excluded_no_confidence": 1, "excluded_low_confidence": 1}
    rows = list(csv.DictReader((tmp_path / "prices.csv").open()))
    assert [r["key"] for r in rows] == ["0xa", "ethereum"]
