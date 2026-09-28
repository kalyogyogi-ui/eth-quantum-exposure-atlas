"""Independent spot-check of the BigQuery results against a live node.

An EOA that has sent a transaction has nonce > 0, so the node confirms exposure
directly. Balances are compared with a tolerance because the BigQuery balances
table is refreshed daily while the node reports the latest block.
"""
from decimal import Decimal

from . import constants as K
from .proxies import is_eoa_code


def check_accounts(rpc, rows: list[dict], tol: float = 0.01) -> dict:
    n = ok_nonce = ok_code = ok_bal = 0
    bad = []
    for r in rows:
        n += 1
        a = r["address"]
        try:
            nonce, code, bal = rpc.get_nonce(a), rpc.get_code(a), rpc.get_balance(a)
        except Exception as e:
            bad.append({"address": a, "issue": f"rpc error: {e}"})
            continue
        want = int(Decimal(r["eth_wei"]))
        ok_nonce += nonce > 0
        ok_code += is_eoa_code(code)
        close = abs(bal - want) <= max(tol * max(want, 1), 10 ** 15)  # 1% or 0.001 ETH
        ok_bal += close
        if not (nonce > 0 and is_eoa_code(code) and close):
            bad.append({"address": a, "nonce": nonce, "eoa_code": is_eoa_code(code),
                        "bq_wei": want, "node_wei": bal})
    return {"checked": n, "nonce_gt_0": ok_nonce, "eoa_code": ok_code,
            "balance_within_tolerance": ok_bal, "mismatches": bad[:50]}


def check_holdings(rpc, rows: list[dict], tol: float = 0.01) -> dict:
    n = ok = 0
    bad = []
    for r in rows:
        n += 1
        holder = r["holder"].lower().removeprefix("0x")
        data = "0x" + K.SEL_BALANCE_OF + holder.rjust(64, "0")
        try:
            got = int(rpc.eth_call(r["token"], data), 16)
        except Exception as e:
            bad.append({"token": r["token"], "holder": r["holder"], "issue": f"rpc error: {e}"})
            continue
        want = int(Decimal(r["raw_balance"]))
        if abs(got - want) <= tol * max(want, 1):
            ok += 1
        else:
            bad.append({"token": r["token"], "holder": r["holder"], "bq_raw": want, "node_raw": got})
    return {"checked": n, "within_tolerance": ok, "mismatches": bad[:50]}


def to_markdown(acc: dict, hold: dict | None) -> str:
    L = ["# Verification report", "",
         "BigQuery results spot-checked against a live Ethereum node.", "",
         "| Check | Passed | Checked |", "| --- | --- | --- |",
         f"| Exposed account has nonce > 0 | {acc['nonce_gt_0']} | {acc['checked']} |",
         f"| Account is an EOA (no code, or EIP-7702 delegation) | {acc['eoa_code']} | {acc['checked']} |",
         f"| ETH balance within 1% (or 0.001 ETH) | {acc['balance_within_tolerance']} | {acc['checked']} |"]
    if hold:
        L.append(f"| Token balance within 1% of balanceOf | {hold['within_tolerance']} | {hold['checked']} |")
    L += ["", "Balance differences are expected for active accounts because BigQuery balances refresh daily.",
          "Token mismatches usually mean a rebasing or fee-on-transfer token; list them as known limits.", ""]
    return "\n".join(L)
