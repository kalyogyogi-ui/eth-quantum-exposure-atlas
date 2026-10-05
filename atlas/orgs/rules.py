"""Written exposure rules over a resolved control graph. No scores: each finding names a rule.

Status of an address (can its control be exercised using quantum-exposed keys only?):
  exposed      yes, by a path this module can show;
  not_exposed  every path ends at keys with no on-chain exposure found;
  unknown      some path reaches something the resolver could not interpret.

  EOA            exposed if it has sent a transaction (nonce > 0) or a signature of it was
                 found on-chain; otherwise not_exposed.
  Safe (t of n)  exposed if at least t owners are exposed; unknown if exposed + unknown owners
                 could reach t; otherwise not_exposed.
  Timelock       the status of its proposer/admin, marked as delayed by its minimum delay;
                 unknown if those are not enumerable.
  Owned contract (ProxyAdmin, beacon, Ownable, AccessControl): exposed if any controller is
                 exposed (each one alone can act), else unknown if any is unknown.
  Governor, unrecognised contract, cycle or depth limit: unknown.

Rules for each control edge of a registered contract:
  R1 single_exposed_eoa              one exposed key can act, with no multisig and no delay
  R2 threshold_reachable_exposed     a Safe threshold is reachable using exposed signers only
  R3 exposed_behind_timelock         an exposed path exists but passes through a timelock
  R4 no_exposed_path                 no exposed path found
  R5 unresolved                      could not decide; the blocking items are listed
  R0 no_controller_found             no owner, admin, beacon, role admin, Safe or timelock found
"""

RULES = {
    "R1": "single_exposed_eoa",
    "R2": "threshold_reachable_exposed",
    "R3": "exposed_behind_timelock",
    "R4": "no_exposed_path",
    "R5": "unresolved",
    "R0": "no_controller_found",
}
CAPABILITY = {
    "upgrade_admin": "upgrade the contract",
    "upgrade_beacon": "upgrade the contract (via its beacon)",
    "owner": "call owner-only functions",
    "default_admin": "grant any role",
    "safe_owner": "sign for the Safe",
    "timelock_proposer": "schedule timelock operations",
    "timelock_admin": "queue timelock operations",
    "self": "control this account",
}


def _rank(r: dict) -> tuple:
    """Lower is a more direct exposure; ties broken by path so output is deterministic."""
    return ("timelock" in r["via"], "safe" in r["via"], len(r["path"]), r["path"])


def evaluate(nodes: dict, address: str, _stack: tuple = ()) -> dict:
    node = nodes.get(address)
    base = {"path": [address], "via": [], "delay": 0, "blocking": []}
    if node is None:
        return {**base, "status": "unknown", "blocking": [f"{address}: not resolved (depth limit)"]}
    if address in _stack:
        return {**base, "status": "unknown", "blocking": [f"{address}: control cycle"]}
    stack = _stack + (address,)
    kind = node["kind"]

    if kind == "eoa":
        return {**base, "status": "exposed" if node.get("exposed") else "not_exposed"}

    if kind in ("contract", "governor"):
        return {**base, "status": "unknown", "blocking": [f"{address}: {u}" for u in node["unresolved"]]}

    subs = [evaluate(nodes, c["address"], stack) for c in node["controllers"]]

    if kind == "safe":
        t = node["threshold"]
        exposed = sorted((s for s in subs if s["status"] == "exposed"), key=_rank)
        unknown = [s for s in subs if s["status"] == "unknown"]
        if len(exposed) >= t:
            used = exposed[:t]
            via = sorted({"safe", *[v for s in used for v in s["via"]]})
            return {**base, "status": "exposed", "via": via, "delay": max(s["delay"] for s in used),
                    "signers": [s["path"][0] for s in used],
                    "detail": f"{len(exposed)} of {node['n_owners']} owners exposed; threshold {t}"}
        if len(exposed) + len(unknown) >= t:
            return {**base, "status": "unknown", "blocking": [b for s in unknown for b in s["blocking"]],
                    "detail": f"{len(exposed)} of {node['n_owners']} owners exposed, {len(unknown)} unknown; "
                              f"threshold {t}"}
        return {**base, "status": "not_exposed",
                "detail": f"{len(exposed)} of {node['n_owners']} owners exposed; threshold {t}"}

    # timelock or owned_contract: any single controller can act.
    if not subs:
        return {**base, "status": "unknown", "blocking": [f"{address}: {u}" for u in node["unresolved"]]}
    exposed = sorted((s for s in subs if s["status"] == "exposed"), key=_rank)
    extra_via = ["timelock"] if kind == "timelock" else []
    extra_delay = node.get("min_delay", 0) if kind == "timelock" else 0
    if exposed:
        best = exposed[0]
        out = {**best, "path": [address] + best["path"], "via": sorted(set(best["via"] + extra_via)),
               "delay": best["delay"] + extra_delay}
        return out
    unknown = [s for s in subs if s["status"] == "unknown"]
    blocking = [b for s in unknown for b in s["blocking"]] + [f"{address}: {u}" for u in node["unresolved"]]
    if unknown or node["unresolved"]:
        return {**base, "status": "unknown", "blocking": blocking}
    return {**base, "status": "not_exposed"}


def rule_for(result: dict) -> str:
    if result["status"] == "exposed":
        if "timelock" in result["via"]:
            return "R3"
        return "R2" if "safe" in result["via"] else "R1"
    return "R5" if result["status"] == "unknown" else "R4"


def findings(nodes: dict, root: str) -> list[dict]:
    """One finding per control edge of a registered contract (or of the account itself)."""
    node = nodes[root]
    if node["kind"] in ("eoa", "safe", "timelock", "governor"):
        edges = [{"role": "self", "address": root}]
        results = [evaluate(nodes, root)]
    else:
        edges = node["controllers"]
        results = [evaluate(nodes, e["address"], (root,)) for e in edges]
    if not edges:
        if node["kind"] == "contract" and any("not enumerable" in u for u in node["unresolved"]):
            return [{"rule": "R5", "name": RULES["R5"], "role": "", "capability": "",
                     "status": "unknown", "path": [root],
                     "blocking": [f"{root}: {u}" for u in node["unresolved"]]}]
        return [{"rule": "R0", "name": RULES["R0"], "role": "", "capability": "", "status": "none",
                 "path": [root], "blocking": []}]
    out = []
    for e, r in zip(edges, results):
        rule = rule_for(r)
        f = {"rule": rule, "name": RULES[rule], "role": e["role"],
             "capability": CAPABILITY.get(e["role"], e["role"]), "status": r["status"],
             "path": r["path"] if e["role"] == "self" else [root] + r["path"],
             "blocking": r["blocking"]}
        for k in ("signers", "detail"):
            if k in r:
                f[k] = r[k]
        if r["delay"]:
            f["timelock_delay_seconds"] = r["delay"]
        out.append(f)
    if node["kind"] == "owned_contract" and node["unresolved"]:
        # e.g. an owner was found, but AccessControl roles exist that cannot be listed
        out.append({"rule": "R5", "name": RULES["R5"], "role": "", "capability": "", "status": "unknown",
                    "path": [root], "blocking": [f"{root}: {u}" for u in node["unresolved"]]})
    return out
