"""Load and validate orgs/registry.yaml.

Every contract must carry a source_url pointing to the organisation's own documentation:
addresses are never taken from memory. Organisations default to published: false, and the
public site shows only those the owner has explicitly set to true.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

ROLES = ("token", "vault", "bridge", "governance", "treasury")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")


class RegistryError(ValueError):
    pass


@dataclass(frozen=True)
class Contract:
    address: str          # lower-case
    role: str
    source_url: str
    label: str = ""


@dataclass(frozen=True)
class Org:
    slug: str
    name: str
    category: str
    published: bool
    contracts: tuple = field(default_factory=tuple)


def parse(data: dict) -> list[Org]:
    if not isinstance(data, dict) or not isinstance(data.get("organisations"), list):
        raise RegistryError("registry needs a top-level 'organisations' list")
    orgs, seen = [], set()
    for i, o in enumerate(data["organisations"]):
        where = f"organisations[{i}]"
        for key in ("slug", "name", "category", "contracts"):
            if not o.get(key):
                raise RegistryError(f"{where}: missing {key}")
        slug = o["slug"]
        if not SLUG.match(slug):
            raise RegistryError(f"{where}: bad slug {slug!r}")
        if slug in seen:
            raise RegistryError(f"{where}: duplicate slug {slug!r}")
        seen.add(slug)
        published = o.get("published", False)
        if not isinstance(published, bool):
            raise RegistryError(f"{slug}: published must be true or false")
        contracts, addrs = [], set()
        for j, c in enumerate(o["contracts"]):
            cw = f"{slug}.contracts[{j}]"
            addr = str(c.get("address", ""))
            if not ADDRESS.match(addr):
                raise RegistryError(f"{cw}: bad address {addr!r}")
            if c.get("role") not in ROLES:
                raise RegistryError(f"{cw}: role must be one of {', '.join(ROLES)}")
            url = str(c.get("source_url", ""))
            if not url.startswith("https://"):
                raise RegistryError(f"{cw}: source_url (https) is required")
            if addr.lower() in addrs:
                raise RegistryError(f"{cw}: duplicate address {addr}")
            addrs.add(addr.lower())
            contracts.append(Contract(addr.lower(), c["role"], url, str(c.get("label", ""))))
        orgs.append(Org(slug, str(o["name"]), str(o["category"]), published, tuple(contracts)))
    return orgs


def load(path: Path) -> list[Org]:
    import yaml
    return parse(yaml.safe_load(Path(path).read_text()))


def check_sources(orgs: list[Org], fetch) -> list[str]:
    """Confirm every address still appears in its source_url. `fetch(url) -> str`.

    Returns a list of problems; empty means every address was found in its source.
    """
    pages, problems = {}, []
    for o in orgs:
        for c in o.contracts:
            if c.source_url not in pages:
                try:
                    pages[c.source_url] = fetch(c.source_url).lower()
                except Exception as e:
                    pages[c.source_url] = None
                    problems.append(f"{c.source_url}: could not fetch ({str(e)[:80]})")
            page = pages[c.source_url]
            if page is not None and c.address not in page:
                problems.append(f"{o.slug}: {c.label or c.address} {c.address} not found in {c.source_url}")
    return problems
