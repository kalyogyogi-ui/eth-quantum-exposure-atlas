"""Build one organisation's report and write it as <slug>.json and <slug>.md.

Output is deterministic for a given block: no timestamps, sorted keys, stable ordering,
and the RPC URL is never written (it may carry an API key).
"""
import json
from pathlib import Path

from .. import __version__
from .registry import Org
from .resolve import Probe, resolve_graph, value_context
from .rules import RULES, findings
from . import safesig

LIMITS = [
    "On-chain evidence only: a key also leaks through off-chain signatures (permits, EIP-712 "
    "messages, exported public keys), so 'not exposed' means 'no exposure found on-chain'.",
    "Control is found through known interfaces only: owner(), EIP-1967 and zos admin slots, "
    "EIP-1967 beacon, AccessControlEnumerable, Safe, OpenZeppelin and Compound timelocks. "
    "Other admin mechanisms appear as unresolved, never as safe.",
    "AccessControl roles that are not enumerable, and OpenZeppelin timelock proposers, can only "
    "be listed from event history; they are reported as unresolved.",
    "Token-voting governors are not followed to their voters.",
    "Safe signature evidence covers Safe v1.1.1 and later, executed directly (not through a "
    "relayer or module), within the scanned block range.",
    "Contract addresses come from the organisation's own documentation (source_url); the "
    "resolver reports what is on-chain at that address.",
]


def run_org(rpc, org: Org, block: int, finder=None) -> dict:
    probe = Probe(rpc)
    roots = [c.address for c in org.contracts]
    nodes = resolve_graph(probe, roots)
    if finder is not None:
        safesig.apply(nodes, finder)
    else:
        for n in nodes.values():
            if n["kind"] == "safe":
                for c in n["controllers"]:
                    o = nodes.get(c["address"])
                    if o and o["kind"] == "eoa" and not o["exposed"]:
                        o.setdefault("signature_checks", []).append(
                            {"safe": n["address"], "found": False, "note": "not checked (no scan range given)"})
    contracts = []
    for c in org.contracts:
        contracts.append({"address": c.address, "label": c.label, "role": c.role, "source_url": c.source_url,
                          "kind": nodes[c.address]["kind"], "value": value_context(probe, c.address, c.role),
                          "findings": findings(nodes, c.address)})
    # value reads add evidence after the graph was built; attach it now
    for address, node in nodes.items():
        node["evidence"] = probe.evidence.get(address, [])
    rule_counts = {}
    for c in contracts:
        for f in c["findings"]:
            rule_counts[f["rule"]] = rule_counts.get(f["rule"], 0) + 1
    unresolved = sorted({b for c in contracts for f in c["findings"] for b in f["blocking"]})
    return {
        "slug": org.slug, "name": org.name, "category": org.category, "published": org.published,
        "block": block, "method_version": __version__,
        "rules": RULES, "rule_counts": dict(sorted(rule_counts.items())),
        "contracts": contracts, "unresolved": unresolved,
        "nodes": dict(sorted(nodes.items())), "limits": LIMITS,
    }


def _short(a: str) -> str:
    return a[:8] + "…" + a[-4:]


def _tree(nodes: dict, address: str, depth: int, seen: set, lines: list, role: str = "") -> None:
    node = nodes.get(address)
    pad = "  " * depth
    label = f"{role}: " if role else ""
    if node is None:
        lines.append(f"{pad}- {label}`{address}` (not resolved: depth limit)")
        return
    desc = node["kind"]
    if node["kind"] == "eoa":
        desc = f"EOA, nonce {node['nonce']}, {'EXPOSED' if node['exposed'] else 'no exposure found'}"
        if node.get("eip7702_delegated"):
            desc += ", EIP-7702 delegated"
    elif node["kind"] == "safe":
        desc = f"Safe {node['threshold']}-of-{node['n_owners']}"
    elif node["kind"] == "timelock":
        desc = f"timelock ({node['timelock_type']}), min delay {node['min_delay']} s"
    lines.append(f"{pad}- {label}`{address}` — {desc}")
    if address in seen:
        lines.append(f"{pad}  - (already shown above)")
        return
    seen = seen | {address}
    for c in node["controllers"]:
        _tree(nodes, c["address"], depth + 1, seen, lines, c["role"])


def to_markdown(r: dict) -> str:
    L = [f"# {r['name']}: who controls it, and are those keys quantum-exposed?", "",
         f"Block {r['block']:,} · method version {r['method_version']} · category {r['category']}", ""]
    if not r["published"]:
        L += ["> **Draft, not published.** The organisation has not yet been notified. "
              "Do not distribute.", ""]
    L += ["## Findings", "", "| Contract | Role | Rule | Can | Path |", "| --- | --- | --- | --- | --- |"]
    for c in r["contracts"]:
        for f in c["findings"]:
            path = " → ".join(f"`{_short(a)}`" for a in f["path"])
            extra = f" ({f['detail']})" if f.get("detail") else ""
            if f.get("timelock_delay_seconds"):
                extra += f" (delay {f['timelock_delay_seconds']:,} s)"
            L.append(f"| {c['label'] or _short(c['address'])} | {f['role'] or '-'} | "
                     f"{f['rule']} {f['name']}{extra} | {f['capability'] or '-'} | {path} |")
    L += ["", "Rules: " + "; ".join(f"{k} {v}" for k, v in sorted(r["rules"].items())) + ". "
          "Definitions are in docs/METHODOLOGY.md.", ""]

    L += ["## Contracts", ""]
    for c in r["contracts"]:
        v = c["value"]
        L += [f"### {c['label'] or c['address']}", "",
              f"- Address: `{c['address']}` ({c['kind']})",
              f"- Role: {c['role']}",
              f"- Source: {c['source_url']}",
              f"- ETH balance (wei): {v['eth_balance_wei']}"]
        if "total_supply_raw" in v:
            L.append(f"- Total supply (raw units): {v['total_supply_raw']} (decimals: {v['decimals']})")
        L.append("")

    L += ["## Control graph", ""]
    for c in r["contracts"]:
        lines: list = []
        _tree(r["nodes"], c["address"], 0, set(), lines)
        L += lines + [""]

    L += ["## Unresolved", ""]
    L += [f"- {u}" for u in r["unresolved"]] or ["- None."]
    L.append("")

    L += ["## Evidence", "", f"Every read was made at block {r['block']:,}.", ""]
    for address, node in r["nodes"].items():
        L += [f"### `{address}` ({node['kind']})", ""]
        if node.get("exposure_basis"):
            L.append(f"Exposure: {node['exposure_basis']}.")
        for chk in node.get("signature_checks", []):
            L.append(f"Signature check in Safe `{chk['safe']}`: "
                     + ("found" if chk["found"] else chk.get("note", "not found in scanned range")) + ".")
        for note in node.get("notes", []):
            L.append(f"Note: {note}.")
        L += ["", "| Call | Result |", "| --- | --- |"]
        L += [f"| {e['call']} | `{e['result']}` |" for e in node["evidence"]]
        L.append("")

    L += ["## Limits", ""] + [f"- {x}" for x in r["limits"]] + [""]
    return "\n".join(L)


def write(r: dict, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    j, m = out_dir / f"{r['slug']}.json", out_dir / f"{r['slug']}.md"
    j.write_text(json.dumps(r, indent=2, sort_keys=True) + "\n")
    m.write_text(to_markdown(r))
    return j, m
