"""Registry validation."""
import pytest

from atlas.orgs.registry import RegistryError, parse

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
