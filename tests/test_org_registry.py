"""Registry validation."""
import pytest

from atlas.orgs.registry import RegistryError, check_sources, load, parse

A = "0x" + "aB" * 20


def org(**kw):
    base = {"slug": "acme", "name": "Acme", "category": "issuer",
            "contracts": [{"address": A, "role": "token", "source_url": "https://docs.acme.example/addresses"}]}
    base.update(kw)
    return {"organisations": [base]}


def test_defaults_to_unpublished_and_lowercases():
    (o,) = parse(org())
    assert o.published is False and o.contracts[0].address == A.lower()


@pytest.mark.parametrize("bad,match", [
    ({"slug": "Acme Inc"}, "bad slug"),
    ({"published": "yes"}, "published"),
    ({"contracts": [{"address": "0x12", "role": "token", "source_url": "https://x"}]}, "bad address"),
    ({"contracts": [{"address": A, "role": "oracle", "source_url": "https://x"}]}, "role"),
    ({"contracts": [{"address": A, "role": "token"}]}, "source_url"),
    ({"contracts": [{"address": A, "role": "token", "source_url": "http://x"}]}, "source_url"),
    ({"contracts": [{"address": A, "role": "token", "source_url": "https://x"},
                    {"address": A.lower(), "role": "vault", "source_url": "https://x"}]}, "duplicate address"),
    ({"name": ""}, "missing name"),
])
def test_rejects(bad, match):
    with pytest.raises(RegistryError, match=match):
        parse(org(**bad))


def test_duplicate_slug():
    data = org()
    data["organisations"].append(dict(data["organisations"][0]))
    with pytest.raises(RegistryError, match="duplicate slug"):
        parse(data)


def test_check_sources():
    (o,) = parse(org())
    assert check_sources([o], lambda url: f"Token: {A}") == []
    (problem,) = check_sources([o], lambda url: "no address here")
    assert "not found" in problem
    def boom(url):
        raise OSError("offline")
    assert "could not fetch" in check_sources([o], boom)[0]


def test_committed_registry_is_valid_and_unpublished():
    orgs = load("orgs/registry.yaml")
    assert len(orgs) >= 19 and not any(o.published for o in orgs)
    assert all(c.source_url.startswith("https://") for o in orgs for c in o.contracts)
