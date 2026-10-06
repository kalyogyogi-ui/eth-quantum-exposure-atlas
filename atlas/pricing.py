"""Current USD prices and decimals from DefiLlama's free, keyless price API."""
import csv
import json
import urllib.request
from pathlib import Path

API = "https://coins.llama.fi/prices/current/"
ETH_KEY = "coingecko:ethereum"


def fetch(keys: list[str], batch: int = 80, timeout: float = 30.0) -> dict:
    prices = {}
    for i in range(0, len(keys), batch):
        url = API + ",".join(keys[i:i + batch])
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            prices.update(json.loads(resp.read()).get("coins", {}))
    return prices


def price_tokens(classification_csv: Path, out_csv: Path, min_confidence: float = 0.9) -> dict:
    """Keep only prices DefiLlama reports with confidence >= min_confidence.

    A price with no confidence value is excluded, not assumed confident: the methodology
    promises confidence >= 0.9 for every price used, and a missing value cannot show that.
    """
    tokens = [r["token"] for r in csv.DictReader(classification_csv.open())
              if str(r["permit"]).lower() in ("true", "1")]
    keys = [f"ethereum:{t}" for t in tokens] + [ETH_KEY]
    got = fetch(keys)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    stats = {"requested": len(keys), "priced": 0, "not_found": 0,
             "excluded_no_confidence": 0, "excluded_low_confidence": 0}
    with out_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["key", "symbol", "decimals", "price_usd", "confidence", "timestamp"])
        for k in keys:
            p = got.get(k)
            if not p:
                stats["not_found"] += 1
                continue
            if p.get("confidence") is None:
                stats["excluded_no_confidence"] += 1
                continue
            if float(p["confidence"]) < min_confidence:
                stats["excluded_low_confidence"] += 1
                continue
            stats["priced"] += 1
            w.writerow([k.split(":", 1)[1], p.get("symbol", ""), p.get("decimals", ""),
                        p["price"], p["confidence"], p.get("timestamp", "")])
    return stats
