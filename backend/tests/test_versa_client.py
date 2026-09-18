"""Tests for the real Versa pre-23 client (token + discovery mapping)."""
from __future__ import annotations

import httpx
import pytest

from app.adapters.versa.director22 import VersaDirectorPre23Client
from app.models.cpe import Director


def _director(**overrides) -> Director:
    base = dict(
        name="VD-LAB",
        host="director.lab",
        api_base_url="https://director.lab:9183",
        versa_version="22.1.3",
        oauth_client_id="cpe-manager",
        oauth_secret_ref="secret:vd",
    )
    base.update(overrides)
    return Director(**base)


def _make_transport(devices_payload) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/token"):
            data = dict(request.url.params) if request.url.params else {}
            # httpx: form data is on request.content; decode simply for assertions
            body = request.content.decode() if isinstance(request.content, bytes) else ""
            assert "grant_type=password" in body
            return httpx.Response(200, json={"access_token": "tok-123"})
        if request.url.path.endswith("/vnms/sdwan/vnf/cpes"):
            assert request.headers["Authorization"] == "Bearer tok-123"
            return httpx.Response(200, json=devices_payload)
        return httpx.Response(404, json={"error": "unexpected"})

    return httpx.MockTransport(handler)


def test_discover_devices_maps_list_payload(db_session):
    devices = [
        {
            "deviceName": "CPE-2213-0001",
            "hostname": "BR-EDGE-01",
            "serialNumber": "VS-0001",
            "organizationName": "Mumbai DC",
            "managementIp": "10.10.1.11",
            "operationalStatus": "up",
        },
        {
            "deviceName": "CPE-2213-0002",
            "serialNumber": "VS-0002",
            "operationalStatus": "down",
        },
    ]
    client = VersaDirectorPre23Client(
        _director(), transport=_make_transport(devices)
    )
    rows = client.discover_devices(_director())
    assert rows[0]["cpe_id"] == "CPE-2213-0001"
    assert rows[0]["serial_number"] == "VS-0001"
    assert rows[0]["site"] == "Mumbai DC"
    assert rows[0]["management_ip"] == "10.10.1.11"
    assert rows[0]["status"] == "online"
    assert rows[1]["status"] == "unknown"
    assert rows[1]["device_name"] is None  # tolerates missing hostname


def test_discover_devices_accepts_device_wrapped_payload(db_session):
    payload = {"device": [{"deviceName": "CPE-X", "serialNumber": "VS-X"}]}
    client = VersaDirectorPre23Client(_director(), transport=_make_transport(payload))
    rows = client.discover_devices(_director())
    assert len(rows) == 1
    assert rows[0]["cpe_id"] == "CPE-X"


def test_discover_skips_records_without_identifier(db_session):
    client = VersaDirectorPre23Client(
        _director(), transport=_make_transport([{}])
    )
    rows = client.discover_devices(_director())
    assert rows == [{"cpe_id": "", "device_name": None, "serial_number": None, "site": None, "management_ip": None, "status": "unknown"}]


def test_token_sends_password_grant_and_client_secret(db_session, secret_store):
    # oauth_secret_ref resolved through the store → sent as client_secret
    secret_store.create_secret("secret:vd", "super-secret")
    calls = {}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["body"] = request.content.decode()
        return httpx.Response(200, json={"access_token": "tok"})

    client = VersaDirectorPre23Client(
        _director(),
        secret_store=secret_store,
        username="apiuser",
        password="apipass",
        transport=httpx.MockTransport(handler),
    )
    assert client._token() == "tok"
    assert "grant_type=password" in calls["body"]
    assert "username=apiuser" in calls["body"]
    assert "password=apipass" in calls["body"]
    assert "client_secret=super-secret" in calls["body"]


def test_credential_ops_remain_lab_pending(db_session):
    client = VersaDirectorPre23Client(_director())
    from app.models.cpe import CPE

    cpe = CPE(cpe_id="x")
    with pytest.raises(NotImplementedError):
        client.update_credential(cpe, "pw")
    with pytest.raises(NotImplementedError):
        client.verify_credential(cpe, "pw")
    with pytest.raises(NotImplementedError):
        client.get_device_status(cpe)