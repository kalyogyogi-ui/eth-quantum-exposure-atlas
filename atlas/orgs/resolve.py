"""Find who controls a contract, at one block, using only RPC reads.

For each address the resolver records what it is (EOA, Safe, timelock, governor, a contract
with an owner or admin, or a contract it cannot interpret) and which addresses control it,
then follows those controllers until it reaches EOAs or something it cannot resolve.
Every read is kept as evidence. Nothing is guessed: a call that reverts means "this
interface is not there", while a transport failure aborts the run.
"""
from .. import constants as K
from ..proxies import find_implementation, is_eoa_code, strip0x, word_to_address
from ..rpc import RPCError, RPCTransportError

MAX_DEPTH = 8
MAX_ROLE_MEMBERS = 50

# Readable labels for the evidence table; the raw selector or slot is kept beside each.
CALL_NAMES = {
    K.SEL_OWNER: "owner()", K.SEL_ADMIN: "admin()", K.SEL_GET_OWNERS: "getOwners()",
    K.SEL_GET_THRESHOLD: "getThreshold()", K.SEL_GET_MIN_DELAY: "getMinDelay()", K.SEL_DELAY: "delay()",
    K.SEL_GET_ROLE_MEMBER_COUNT: "getRoleMemberCount(bytes32)",
    K.SEL_GET_ROLE_MEMBER: "getRoleMember(bytes32,uint256)", K.SEL_VOTING_PERIOD: "votingPeriod()",
    K.SEL_TOTAL_SUPPLY: "totalSupply()", K.SEL_DECIMALS: "decimals()",
    K.SEL_IMPLEMENTATION: "implementation()", K.SEL_KERNEL: "kernel()",
}
SLOT_NAMES = {
    K.SLOT_EIP1967_ADMIN: "eip1967.proxy.admin", K.SLOT_ZOS_ADMIN: "zos admin",
    K.SLOT_EIP1967_IMPL: "eip1967.proxy.implementation", K.SLOT_EIP1967_BEACON: "eip1967.proxy.beacon",
    K.SLOT_ZOS_IMPL: "zos implementation", K.SLOT_EIP1822: "eip1822 PROXIABLE",
}


def _call_label(data: str) -> str:
    sel, args = data[2:10], data[10:]
    name = CALL_NAMES.get(sel, "")
    label = f"eth_call {name} [0x{sel}]" if name else f"eth_call 0x{sel}"
    return label + (f" args 0x{args}" if args else "")


def uint_word(n: int) -> str:
    return f"{n:064x}"


def decode_uint(result: str | None) -> int | None:
    w = strip0x(result)
    return int(w[:64], 16) if len(w) >= 64 else None


def decode_address_array(result: str | None) -> list[str] | None:
    """ABI-decode a returned address[]; None if the data is not a plausible array."""
    w = strip0x(result)
    if len(w) < 128:
        return None
    off = int(w[:64], 16) * 2
    if off + 64 > len(w):
        return None
    n = int(w[off:off + 64], 16)
    if n == 0 or n > 1000 or len(w) < off + 64 + 64 * n:
        return None
    items = [w[off + 64 + 64 * i: off + 128 + 64 * i] for i in range(n)]
    if any(int(x[:24], 16) for x in items):  # high bytes of an address word must be zero
        return None
    return ["0x" + x[24:] for x in items]


class Probe:
    """Wraps an RPC client pinned to one block and records every read per address."""

    def __init__(self, rpc):
        self.rpc = rpc
        self.evidence: dict[str, list] = {}

    def _rec(self, address: str, call: str, result) -> None:
        self.evidence.setdefault(address, []).append({"call": call, "result": result})

    # RPC-compatible methods, so proxies.find_implementation can run through the probe.
    def get_code(self, address: str) -> str:
        code = self.rpc.get_code(address)
        c = strip0x(code)
        shown = "0x" + c if (c == "" or c.startswith(K.EIP7702_PREFIX)) else f"{len(c) // 2} bytes"
        self._rec(address, "eth_getCode", shown)
        return code

    def get_storage(self, address: str, slot: str) -> str:
        word = self.rpc.get_storage(address, slot)
        name = SLOT_NAMES.get(slot)
        self._rec(address, f"eth_getStorageAt {name} [0x{slot}]" if name else f"eth_getStorageAt 0x{slot}", word)
        return word

    def eth_call(self, to: str, data: str) -> str:
        try:
            out = self.rpc.eth_call(to, data)
        except RPCTransportError:
            raise
        except RPCError as e:
            self._rec(to, _call_label(data), f"error: {str(e)[:120]}")
            raise
        self._rec(to, _call_label(data), out)
        return out

    def get_nonce(self, address: str) -> int:
        n = self.rpc.get_nonce(address)
        self._rec(address, "eth_getTransactionCount", n)
        return n

    def get_balance(self, address: str) -> int:
        b = self.rpc.get_balance(address)
        self._rec(address, "eth_getBalance", str(b))
        return b

    def call(self, to: str, selector: str, args: str = "") -> str | None:
        """eth_call that returns None when the interface is absent (revert or empty result)."""
        try:
            out = self.eth_call(to, "0x" + selector + args)
        except RPCTransportError:
            raise
        except RPCError:
            return None
        return out if strip0x(out) else None


def _role_members(probe: Probe, address: str, role: str) -> list[str] | None:
    """Members of an AccessControlEnumerable role, or None if roles are not enumerable."""
    n = decode_uint(probe.call(address, K.SEL_GET_ROLE_MEMBER_COUNT, role))
    if n is None:
        return None
    members = []
    for i in range(min(n, MAX_ROLE_MEMBERS)):
        m = word_to_address(probe.call(address, K.SEL_GET_ROLE_MEMBER, role + uint_word(i)) or "")
        if m:
            members.append(m)
    return members


def _code_has(code: str, selector: str) -> bool:
    return K.PUSH4 + selector in strip0x(code)


def resolve_node(probe: Probe, address: str) -> dict:
    """Classify one address and list the addresses that control it."""
    node = {"address": address, "kind": "", "controllers": [], "unresolved": [], "notes": []}
    code = probe.get_code(address)

    if is_eoa_code(code):
        nonce = probe.get_nonce(address)
        node.update(kind="eoa", nonce=nonce, eip7702_delegated=bool(strip0x(code)),
                    exposed=nonce > 0, exposure_basis="nonce > 0 (has sent a transaction)" if nonce > 0 else "")
        return node

    owners = decode_address_array(probe.call(address, K.SEL_GET_OWNERS))
    threshold = decode_uint(probe.call(address, K.SEL_GET_THRESHOLD)) if owners else None
    if owners and threshold and 1 <= threshold <= len(owners):
        node.update(kind="safe", threshold=threshold, n_owners=len(owners))
        node["controllers"] = [{"role": "safe_owner", "address": o} for o in owners]
        return node

    min_delay = decode_uint(probe.call(address, K.SEL_GET_MIN_DELAY))
    if min_delay is not None:
        node.update(kind="timelock", timelock_type="openzeppelin", min_delay=min_delay)
        proposers = _role_members(probe, address, K.PROPOSER_ROLE)
        if proposers:
            node["controllers"] = [{"role": "timelock_proposer", "address": p} for p in proposers]
        else:
            node["unresolved"].append("proposer role is not enumerable by call; proposers are only "
                                      "visible in RoleGranted/RoleRevoked event history")
        return node

    delay = decode_uint(probe.call(address, K.SEL_DELAY))
    admin = word_to_address(probe.call(address, K.SEL_ADMIN) or "") if delay is not None else None
    if delay is not None and admin:
        node.update(kind="timelock", timelock_type="compound", min_delay=delay)
        node["controllers"] = [{"role": "timelock_admin", "address": admin}]
        return node

    if probe.call(address, K.SEL_VOTING_PERIOD) is not None:
        node.update(kind="governor")
        node["unresolved"].append("token-voting governor: control rests with voters, whose key exposure "
                                  "is not measured here")
        return node

    kernel = word_to_address(probe.call(address, K.SEL_KERNEL) or "")
    if kernel:
        node.update(kind="aragon_app", kernel=kernel)
        impl, mech = find_implementation(probe, address, code)
        if impl:
            node.update(implementation=impl, proxy_mechanism=mech)
        node["unresolved"].append(f"Aragon app: permissions, including upgrades, are held in the ACL of "
                                  f"kernel {kernel} and are not enumerable by call; they are only "
                                  f"visible in SetPermission event history")
        return node

    # A generic contract: upgrade admin slots, beacon, owner(), AccessControl default admin.
    ctl = []
    for slot, name in ((K.SLOT_EIP1967_ADMIN, "eip1967"), (K.SLOT_ZOS_ADMIN, "zos")):
        a = word_to_address(probe.get_storage(address, slot))
        if a:
            ctl.append({"role": "upgrade_admin", "address": a, "via": f"{name} admin slot"})
    beacon = word_to_address(probe.get_storage(address, K.SLOT_EIP1967_BEACON))
    if beacon:
        ctl.append({"role": "upgrade_beacon", "address": beacon, "via": "eip1967 beacon slot"})
    owner_word = probe.call(address, K.SEL_OWNER)
    owner = word_to_address(owner_word or "")
    if owner:
        ctl.append({"role": "owner", "address": owner, "via": "owner()"})
    elif owner_word is not None and decode_uint(owner_word) == 0:
        node["notes"].append("owner() returns the zero address (ownership renounced)")
    admins = _role_members(probe, address, K.DEFAULT_ADMIN_ROLE)
    for a in admins or []:
        ctl.append({"role": "default_admin", "address": a, "via": "AccessControl DEFAULT_ADMIN_ROLE"})

    impl, mech = find_implementation(probe, address, code)
    if impl:
        node.update(implementation=impl, proxy_mechanism=mech)
    if admins is None:
        impl_code = probe.get_code(impl) if impl else ""
        if _code_has(code, K.SEL_HAS_ROLE) or _code_has(impl_code, K.SEL_HAS_ROLE):
            node["unresolved"].append("uses AccessControl roles that are not enumerable by call")

    # Deduplicate (the same admin can appear through two slots) while keeping order stable.
    seen, node["controllers"] = set(), []
    for c in ctl:
        key = (c["role"], c["address"])
        if key not in seen:
            seen.add(key)
            node["controllers"].append(c)
    node["kind"] = "owned_contract" if node["controllers"] else "contract"
    if node["kind"] == "contract" and not node["unresolved"]:
        node["unresolved"].append("no known control interface found (owner, admin slots, beacon, "
                                  "AccessControl, Safe, timelock, governor)")
    return node


def resolve_graph(probe: Probe, roots: list[str], max_depth: int = MAX_DEPTH) -> dict[str, dict]:
    """Breadth-first walk from the registered contracts to their controllers."""
    nodes: dict[str, dict] = {}
    queue = [(r.lower(), 0) for r in roots]
    while queue:
        address, depth = queue.pop(0)
        if address in nodes:
            continue
        node = resolve_node(probe, address)
        nodes[address] = node
        for c in node["controllers"]:
            if c["address"] in nodes:
                continue
            if depth + 1 > max_depth:
                node["unresolved"].append(f"controller {c['address']} beyond depth limit {max_depth}")
            else:
                queue.append((c["address"], depth + 1))
    for address, node in nodes.items():
        node["evidence"] = probe.evidence.get(address, [])
    return nodes


def value_context(probe: Probe, address: str, role: str) -> dict:
    out = {"eth_balance_wei": str(probe.get_balance(address))}
    if role == "token":
        supply = decode_uint(probe.call(address, K.SEL_TOTAL_SUPPLY))
        decimals = decode_uint(probe.call(address, K.SEL_DECIMALS))
        out.update(total_supply_raw=None if supply is None else str(supply), decimals=decimals)
    return out
