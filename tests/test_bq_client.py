"""Credential selection for the BigQuery client. No network: the Google classes are faked."""
import json

import pytest

from atlas import bq

bigquery = pytest.importorskip("google.cloud.bigquery")
service_account = pytest.importorskip("google.oauth2.service_account")


@pytest.fixture
def captured(monkeypatch):
    seen = {}
    monkeypatch.setattr(bigquery, "Client", lambda **kw: seen.setdefault("client", kw) and kw)
    monkeypatch.setattr(service_account.Credentials, "from_service_account_info",
                        lambda info, scopes: seen.setdefault("creds", ("creds", info["client_email"], tuple(scopes))))
    return seen


def test_uses_key_from_environment(monkeypatch, captured):
    key = {"type": "service_account", "client_email": "atlas-runner@p.iam.gserviceaccount.com", "project_id": "p"}
    monkeypatch.setenv(bq.CREDENTIALS_ENV, json.dumps(key))
    bq.client(None)
    assert captured["creds"] == ("creds", key["client_email"], tuple(bq.SCOPES))
    assert captured["client"]["project"] == "p" and captured["client"]["credentials"] == captured["creds"]


def test_falls_back_to_default_credentials(monkeypatch, captured):
    monkeypatch.delenv(bq.CREDENTIALS_ENV, raising=False)
    bq.client("myproj")
    assert captured["client"] == {"project": "myproj"} and "creds" not in captured


def test_bad_json_is_a_clear_error(monkeypatch, captured):
    monkeypatch.setenv(bq.CREDENTIALS_ENV, "not json")
    with pytest.raises(SystemExit, match="not valid JSON"):
        bq.client("p")
