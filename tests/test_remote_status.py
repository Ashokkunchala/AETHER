import json
import time

import pytest
from fastapi.testclient import TestClient

from windows_agent import remote_status as mod
from windows_agent.agent import app
from windows_agent.remote_read import RemoteReadStore


SNAPSHOT = {
    "cpu_percent_reported": 12.5,
    "cpu_cores_logical": 8,
    "memory_total_bytes": 1000,
    "memory_available_bytes": 500,
    "disks": [
        {"mount": "C:\\", "total_bytes": 2000, "free_bytes": 800, "used_percent_reported": 60.0}
    ],
    "battery": {"percent_reported": 91.0, "plugged": True},
    "network_links_up": 2,
}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHER_AGENT_APPROVAL_DB", str(tmp_path / "approvals.db"))
    monkeypatch.setenv("AETHER_AGENT_TOKEN", "legacy-token-" + "a" * 48)
    device, token = RemoteReadStore().provision_local()
    store = mod.RemoteStatusStore()
    monkeypatch.setattr(mod, "system_snapshot", lambda: dict(SNAPSHOT))
    return store, device, token, TestClient(app)


def auth(token):
    return {"Authorization": "Bearer " + token}


def test_status_protocol_to_local_review_to_result_end_to_end(setup):
    store, device, token, client = setup
    request = client.post(
        "/v1/remote-status/requests", headers=auth(token), json={"action": "system_snapshot"}
    )
    assert request.status_code == 201
    body = request.json()
    assert body["state"] == "pending_local_review" and body["executed"] is False
    key = body["request_id"]
    before = client.get("/v1/remote-status/requests/" + key, headers=auth(token)).json()
    assert before["result"] is None and before["state"] == "pending_local_review"
    item = store.inspect_local(key)
    assert item["device_id"] == device and item["action"] == "system_snapshot"
    assert store.review_local(key, device, True)["state"] == "completed"
    result = client.get("/v1/remote-status/requests/" + key, headers=auth(token))
    assert result.status_code == 200
    payload = result.json()["result"]
    assert payload["cpu_percent_reported"] == 12.5
    assert payload["disks"][0]["mount"] == "C:\\"
    assert payload["battery"] == {"percent_reported": 91.0, "plugged": True}
    assert token not in json.dumps(result.json())
    with pytest.raises(ValueError):
        store.review_local(key, device, True)


def test_api_cannot_collect_or_supply_other_args(setup, monkeypatch):
    store, device, token, client = setup
    monkeypatch.setattr(mod, "system_snapshot", lambda: pytest.fail("No HTTP request can execute"))
    for body in [
        {"action": "shell_command"},
        {"action": "system_snapshot", "approved": True},
        {"action": "system_snapshot", "scope": "everything"},
        {},
    ]:
        assert (
            client.post("/v1/remote-status/requests", headers=auth(token), json=body).status_code
            == 422
        )
    assert (
        client.post("/v1/remote-status/requests", headers=auth("wrong"), json={"action": "system_snapshot"}).status_code
        == 409
    )


def test_denial_and_expiry_and_cancel(setup, monkeypatch):
    store, device, token, client = setup
    denied_key = client.post(
        "/v1/remote-status/requests", headers=auth(token), json={"action": "system_snapshot"}
    ).json()["request_id"]
    assert store.review_local(denied_key, device, False)["state"] == "denied"
    outcome = client.get("/v1/remote-status/requests/" + denied_key, headers=auth(token)).json()
    assert outcome["state"] == "denied" and outcome["result"] is None

    monkeypatch.setattr(mod, "system_snapshot", lambda: pytest.fail("Cancelled request must not collect"))
    cancel_key = client.post(
        "/v1/remote-status/requests", headers=auth(token), json={"action": "system_snapshot"}
    ).json()["request_id"]
    cancelled = client.post(
        "/v1/remote-status/requests/" + cancel_key + "/cancel", headers=auth(token), json={}
    ).json()
    assert cancelled["state"] == "cancelled_before_read" and cancelled["collection_prevented"]
    with pytest.raises(ValueError):
        store.review_local(cancel_key, device, True)

    expired_key = client.post(
        "/v1/remote-status/requests", headers=auth(token), json={"action": "system_snapshot"}
    ).json()["request_id"]
    real_time = time.time
    monkeypatch.setattr(mod.time, "time", lambda: real_time() + 1000)
    expired = client.get("/v1/remote-status/requests/" + expired_key, headers=auth(token)).json()
    assert expired["state"] == "expired" and expired["result"] is None


def test_closed_schema_rejects_out_of_shape_values():
    bad_cpu = dict(SNAPSHOT, cpu_percent_reported=180.0)
    with pytest.raises(ValueError):
        mod._closed_status(bad_cpu)
    bad_disk = dict(SNAPSHOT, disks=[{"mount": "\\\\share\\x", "total_bytes": 1, "free_bytes": 0, "used_percent_reported": 0}])
    with pytest.raises(ValueError):
        mod._closed_status(bad_disk)
    extra = dict(SNAPSHOT, hostname="laptop")
    with pytest.raises(ValueError):
        mod._closed_status(extra)
    assert mod._closed_status(dict(SNAPSHOT))["network_links_up"] == 2
