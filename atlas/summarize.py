"""Turn the CSV outputs into summary.json and a readable SUMMARY.md."""
import csv
import json
from datetime import datetime, timezone
from decimal import Decimal, getcontext
from pathlib import Path

getcontext().prec = 80


def _read(path: Path) -> list[dict]:
    return list(csv.DictReader(path.open())) if path.exists() and path.stat().st_size else []


def _f(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _truthy(v) -> bool:
    return str(v).lower() in ("true", "1")


def token_values(exposure: list[dict], classes: dict, prices: dict) -> list[dict]:
    """USD value held by exposed and unexposed EOAs, for tokens confirmed to support permit."""
    out = []
    for r in exposure:
        c = classes.get(r["token"])
        if not c or not _truthy(c["permit"]):
            continue
        p = prices.get(r["token"])
        dec = p.get("decimals") if p else None
        dec = int(dec) if dec not in (None, "") else (int(r["decimals"]) if r.get("decimals") else None)
        price = Decimal(p["price_usd"]) if p else None
        row = {"token": r["token"], "symbol": (p or {}).get("symbol") or r.get("symbol") or "",
               "exposed_holders": int(r["exposed_holders"] or 0),
               "upgradeable": c["upgradeable"], "mechanism": c["mechanism"],
               "permit_kind": c["permit_kind"], "priced": price is not None and dec is not None,
               "usd_exposed": 0.0, "usd_unexposed_eoa": 0.0}
        if row["priced"]:
            scale = Decimal(10) ** dec
            row["usd_exposed"] = float(Decimal(r["raw_exposed"] or 0) / scale * price)
            row["usd_unexposed_eoa"] = float(Decimal(r["raw_unexposed_eoa"] or 0) / scale * price)
        out.append(row)
    out.sort(key=lambda x: x["usd_exposed"], reverse=True)
    return out


def build(out_dir: Path, resolve_stats: dict | None = None) -> dict:
    s02 = _read(out_dir / "02_exposed_eth_summary.csv")
    dist = _read(out_dir / "03_exposure_distribution.csv")
    exposure = _read(out_dir / "06_permit_token_exposure.csv")
    classes = {r["token"]: r for r in _read(out_dir / "token_classification.csv")}
    prices = {r["key"]: r for r in _read(out_dir / "prices.csv")}
    p2 = _read(out_dir / "08_permit2_summary.csv")

    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    eth_price = _f(prices.get("ethereum", {}).get("price_usd"), None) if prices.get("ethereum") else None

    if s02:
        a = s02[0]
        eoa = _f(a["eth_in_eoas"])
        allv = _f(a["eth_all_accounts"])
        exp = _f(a["eth_in_exposed_eoas"])
        summary["eth"] = {
            "eth_all_accounts": allv, "eth_in_contracts": _f(a["eth_in_contracts"]),
            "eth_in_eoas": eoa, "eth_in_exposed_eoas": exp,
            "eth_in_unexposed_eoas": _f(a["eth_in_unexposed_eoas"]),
            "share_of_all_eth": exp / allv if allv else None,
            "share_of_eoa_eth": exp / eoa if eoa else None,
            "n_exposed_eoas_with_balance": int(_f(a["n_exposed_eoas_with_balance"])),
            "eth_in_top1000_exposed_eoas": _f(a["eth_in_top1000_exposed_eoas"]),
            "usd_in_exposed_eoas": exp * eth_price if eth_price else None,
            "data_freshness_last_tx": a.get("data_freshness_last_tx"),
        }

    if dist:
        dormant = sum(_f(r["eth"]) for r in dist if r["last_sent_year"] and int(r["last_sent_year"]) <= datetime.now().year - 5)
        summary["dormancy"] = {"eth_exposed_last_active_5plus_years_ago": dormant}

    if exposure and classes:
        vals = token_values(exposure, classes, prices)
        for v in vals:
            v["no_upgrade_signal"] = str(v["upgradeable"]) in ("no_signal", "False")
        summary["permit"] = {
            "candidate_tokens_with_eoa_holders": len(exposure),
            "tokens_classified": len(classes),
            "permit_tokens_confirmed": len(vals),
            "permit_tokens_priced": sum(1 for v in vals if v["priced"]),
            "usd_exposed_all_permit_tokens": sum(v["usd_exposed"] for v in vals),
            "usd_exposed_no_upgrade_signal": sum(v["usd_exposed"] for v in vals if v["no_upgrade_signal"]),
            "usd_exposed_upgradeable": sum(v["usd_exposed"] for v in vals if not v["no_upgrade_signal"]),
            "usd_unexposed_eoa_all_permit_tokens": sum(v["usd_unexposed_eoa"] for v in vals),
            "top_tokens": vals[:25],
        }
        if resolve_stats:
            summary["permit"]["resolution"] = resolve_stats

    if p2:
        summary["permit2"] = {k: int(_f(v)) for k, v in p2[0].items()}

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    (out_dir / "SUMMARY.md").write_text(to_markdown(summary))
    return summary


def _usd(x) -> str:
    if x is None:
        return "n/a"
    return f"${x / 1e9:,.2f}B" if abs(x) >= 1e9 else f"${x / 1e6:,.1f}M"


def _pct(x) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def to_markdown(s: dict) -> str:
    L = ["# Ethereum Quantum Exposure Atlas: results", "", f"Generated {s['generated_utc']}.", ""]
    if "eth" in s:
        e = s["eth"]
        L += ["## 1. ETH in accounts with a revealed public key", "",
              "| Measure | Value |", "| --- | --- |",
              f"| ETH in exposed EOAs | {e['eth_in_exposed_eoas']:,.0f} ETH ({_usd(e['usd_in_exposed_eoas'])}) |",
              f"| Share of all ETH on the execution layer | {_pct(e['share_of_all_eth'])} |",
              f"| Share of ETH held by EOAs | {_pct(e['share_of_eoa_eth'])} |",
              f"| Exposed EOAs with a balance | {e['n_exposed_eoas_with_balance']:,} |",
              f"| ETH in the 1,000 largest exposed EOAs | {e['eth_in_top1000_exposed_eoas']:,.0f} ETH |",
              f"| Data freshness (latest tx seen) | {e['data_freshness_last_tx']} |", ""]
    if "dormancy" in s:
        L += [f"Exposed ETH in accounts inactive for 5+ years: "
              f"{s['dormancy']['eth_exposed_last_active_5plus_years_ago']:,.0f} ETH.", ""]
    if "permit" in s:
        p = s["permit"]
        L += ["## 2. Token value reachable by permit signatures", "",
              "Tokens that accept an ECDSA `permit` signature, held by EOAs whose key is exposed. "
              "After an account migrates, EIP-8298 alone does not stop these signatures; EIP-8151 does.", "",
              "| Measure | Value |", "| --- | --- |",
              f"| Permit tokens confirmed | {p['permit_tokens_confirmed']:,} (priced: {p['permit_tokens_priced']:,}) |",
              f"| Value held by exposed EOAs | {_usd(p['usd_exposed_all_permit_tokens'])} |",
              f"| ...in tokens with no upgrade signal | {_usd(p['usd_exposed_no_upgrade_signal'])} |",
              f"| ...in upgradeable tokens | {_usd(p['usd_exposed_upgradeable'])} |",
              f"| Value held by EOAs with no on-chain key exposure | {_usd(p['usd_unexposed_eoa_all_permit_tokens'])} |", ""]
        if p.get("resolution"):
            r = p["resolution"]
            L += [f"Proxy coverage: resolved {r['proxy_candidates_resolved']:,} of {r['proxy_candidates']:,} "
                  f"proxy candidates ({r['errors']} RPC errors).", ""]
        L += ["| Token | Upgradeable | Exposed holders | USD held by exposed EOAs |", "| --- | --- | --- | --- |"]
        for t in p["top_tokens"][:15]:
            L.append(f"| {t['symbol'] or t['token']} | {t['upgradeable']} | {t['exposed_holders']:,} | {_usd(t['usd_exposed'])} |")
        L.append("")
    if "permit2" in s:
        q = s["permit2"]
        L += ["## 3. Live Permit2 approvals", "",
              f"{q.get('distinct_owners', 0):,} owners ({q.get('distinct_exposed_owners', 0):,} with exposed keys) "
              f"hold live approvals to Permit2 across {q.get('distinct_tokens', 0):,} tokens.", ""]
    L += ["## Caveats", "",
          "- On-chain counts are a lower bound: public keys also leak through off-chain signatures.",
          "- Token balances come from transfer history; rebasing and fee-on-transfer tokens are approximate.",
          "- \"No upgrade signal\" means no known proxy pattern was found, not proof of immutability.",
          "- Prices are a point-in-time snapshot from DefiLlama; low-confidence prices are excluded.", ""]
    return "\n".join(L)
