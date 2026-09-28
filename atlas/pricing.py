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
    tokens = [r["token"] for r in csv.DictReader(classification_csv.open())
              if str(r["permit"]).lower() in ("true", "1")]
    keys = [f"ethereum:{t}" for t in tokens] + [ETH_KEY]
    got = fetch(keys)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    kept = 0
    with out_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["key", "symbol", "decimals", "price_usd", "confidence", "timestamp"])
        for k in keys:
            p = got.get(k)
            if not p or p.get("confidence", 1.0) < min_confidence:
                continue
            kept += 1
            w.writerow([k.split(":", 1)[1], p.get("symbol", ""), p.get("decimals", ""),
                        p["price"], p.get("confidence", ""), p.get("timestamp", "")])
    return {"requested": len(keys), "priced": kept}
