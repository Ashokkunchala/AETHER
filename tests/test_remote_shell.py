import json

import pytest
from fastapi.testclient import TestClient

from windows_agent import remote_shell as mod
from windows_agent.agent import app
from windows_agent.remote_read import RemoteReadStore


EXECUTED = {
    "classification": "safe",
    "exit_code": 0,
    "timed_out": False,
    "stdout": "hello",
    "stderr": "",
}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHER_AGENT_APPROVAL_DB", str(tmp_path / "approvals.db"))
    monkeypatch.setenv("AETHER_AGENT_TOKEN", "legacy-token-" + "a" * 48)
    device, token = RemoteReadStore().provision_local()
    store = mod.RemoteShellStore()
    monkeypatch.setattr(mod, "_execute", lambda command: dict(EXECUTED))
    return store, device, token, TestClient(app)


def auth(token):
    return {"Authorization": "Bearer " + token}


def test_command_protocol_to_local_review_to_bounded_result(setup):
    store, device, token, client = setup
    request = client.post(
        "/v1/remote-shell/requests", headers=auth(token), json={"command": "echo hello"}
    )
    assert request.status_code == 201
    body = request.json()
    assert body["state"] == "pending_local_review" and body["executed"] is False
    assert body["classification"] == "safe"
    key = body["request_id"]
    before = client.get("/v1/remote-shell/requests/" + key, headers=auth(token)).json()
    assert before["result"] is None and before["state"] == "pending_local_review"
    item = store.inspect_local(key)
    assert item["device_id"] == device and item["command"] == "echo hello"
    assert store.review_local(key, device, True)["state"] == "completed"
    result = client.get("/v1/remote-shell/requests/" + key, headers=auth(token))
    assert result.status_code == 200
    assert result.json()["result"]["stdout"] == "hello"
    assert token not in json.dumps(result.json())
    with pytest.raises(ValueError):
        store.review_local(key, device, True)


def test_blocked_commands_can_never_queue_or_run(setup, monkeypatch):
    store, device, token, client = setup
    monkeypatch.setattr(mod, "_execute", lambda command: pytest.fail("Blocked must not execute"))
    for command in ["diskpart", "format C:", "rm -rf /"]:
        assert (
            client.post(
                "/v1/remote-shell/requests", headers=auth(token), json={"command": command}
            ).status_code
            == 409
        )


def test_api_cannot_execute_or_supply_other_args(setup, monkeypatch):
    store, device, token, client = setup
    monkeypatch.setattr(mod, "_execute", lambda command: pytest.fail("No HTTP request can execute"))
    for body in [
        {"command": "echo hi", "approved": True},
        {"command": "echo hi", "timeout": 5},
        {"command": ""},
        {"command": "x" * 301},
        {},
    ]:
        assert (
            client.post("/v1/remote-shell/requests", headers=auth(token), json=body).status_code
            == 422
        )
    assert (
        client.post(
            "/v1/remote-shell/requests", headers=auth("wrong"), json={"command": "echo hi"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/v1/remote-shell/requests", headers=auth(token), json={"command": " echo hi"}
        ).status_code
        == 409
    )


def test_dangerous_command_still_needs_local_review_and_denial_holds(setup, monkeypatch):
    store, device, token, client = setup
    monkeypatch.setattr(mod, "_execute", lambda command: pytest.fail("Denied must not execute"))
    body = client.post(
        "/v1/remote-shell/requests", headers=auth(token), json={"command": "tasklist"}
    ).json()
    assert body["classification"] == "safe"
    dangerous = client.post(
        "/v1/remote-shell/requests", headers=auth(token), json={"command": "net user"}
    ).json()
    assert dangerous["classification"] == "confirm"
    assert store.review_local(dangerous["request_id"], device, False)["state"] == "denied"
    outcome = client.get(
        "/v1/remote-shell/requests/" + dangerous["request_id"], headers=auth(token)
    ).json()
    assert outcome["state"] == "denied" and outcome["result"] is None


def test_cancel_pending_prevents_execution(setup, monkeypatch):
    store, device, token, client = setup
    monkeypatch.setattr(mod, "_execute", lambda command: pytest.fail("Cancelled must not execute"))
    key = client.post(
        "/v1/remote-shell/requests", headers=auth(token), json={"command": "echo hi"}
    ).json()["request_id"]
    cancelled = client.post(
        "/v1/remote-shell/requests/" + key + "/cancel", headers=auth(token), json={}
    ).json()
    assert cancelled["state"] == "cancelled_before_review" and cancelled["execution_prevented"]
    assert cancelled["running_operation_termination_verified"] is False
    with pytest.raises(ValueError):
        store.review_local(key, device, True)


def test_failed_execution_records_failed_state(setup, monkeypatch):
    store, device, token, client = setup
    monkeypatch.setattr(mod, "_execute", lambda command: (_ for _ in ()).throw(OSError("no shell")))
    key = client.post(
        "/v1/remote-shell/requests", headers=auth(token), json={"command": "echo hi"}
    ).json()["request_id"]
    assert store.review_local(key, device, True)["state"] == "failed"
    outcome = client.get("/v1/remote-shell/requests/" + key, headers=auth(token)).json()
    assert outcome["state"] == "failed" and outcome["result"] is None


def test_closed_result_schema():
    assert mod._closed_result(dict(EXECUTED))["exit_code"] == 0
    with pytest.raises(ValueError):
        mod._closed_result(dict(EXECUTED, classification="blocked"))
    with pytest.raises(ValueError):
        mod._closed_result(dict(EXECUTED, stdout="x" * 4001))
    with pytest.raises(ValueError):
        mod._closed_result(dict(EXECUTED, extra="nope"))
