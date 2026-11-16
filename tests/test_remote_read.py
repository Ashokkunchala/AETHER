import concurrent.futures
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from windows_agent import remote_read as mod
from windows_agent.agent import app


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_AGENT_APPROVAL_DB", str(tmp_path / "approvals.db"))
    monkeypatch.setenv("JARVIS_AGENT_TOKEN", "legacy-token-" + "a" * 48)
    store = mod.RemoteReadStore()
    device, token = store.provision_local()
    monkeypatch.setattr(
        mod,
        "memory_snapshot",
        lambda: {"total_bytes": 1000, "available_bytes": 500, "used_percent_reported": 50.0},
    )
    return store, device, token, TestClient(app)


def auth(token):
    return {"Authorization": "Bearer " + token}


def test_android_protocol_to_local_review_to_result_end_to_end(setup):
    store, device, token, client = setup
    request = client.post(
        "/v1/remote-read/requests", headers=auth(token), json={"action": "memory_snapshot"}
    )
    assert request.status_code == 201
    body = request.json()
    assert body["state"] == "pending_local_review" and body["executed"] is False
    key = body["request_id"]
    before = client.get("/v1/remote-read/requests/" + key, headers=auth(token)).json()
    assert before["result"] is None and before["state"] == "pending_local_review"
    item = store.inspect_local(key)
    assert item["device_id"] == device
    assert store.review_local(key, device, True)["state"] == "completed"
    result = client.get("/v1/remote-read/requests/" + key, headers=auth(token))
    assert result.status_code == 200 and result.json()["result"]["total_bytes"] == 1000
    assert not result.json()["device_display_verified"]
    with pytest.raises(ValueError):
        store.review_local(key, device, True)
    assert token not in json.dumps(result.json())
    with store.connect() as db:
        assert token not in str(db.execute("SELECT * FROM remote_read_devices").fetchall())


def test_api_cannot_approve_or_dispatch_or_supply_other_args(setup, monkeypatch):
    store, device, token, client = setup
    monkeypatch.setattr(mod, "memory_snapshot", lambda: pytest.fail("No HTTP request can execute"))
    for body in [
        {"action": "run_shell"},
        {"action": "memory_snapshot", "approved": True},
        {"action": "memory_snapshot", "command": "whoami"},
        {"action": "memory_snapshot", "args": {}},
        {},
    ]:
        assert (
            client.post("/v1/remote-read/requests", headers=auth(token), json=body).status_code
            == 422
        )
    body = client.post(
        "/v1/remote-read/requests", headers=auth(token), json={"action": "memory_snapshot"}
    ).json()
    for suffix in ["/approve", "/execute", "/review"]:
        assert (
            client.post(
                "/v1/remote-read/requests/" + body["request_id"] + suffix,
                headers=auth(token),
                json={"approved": True},
            ).status_code
            == 404
        )
    assert (
        client.get("/v1/remote-read/requests/" + body["request_id"], headers=auth(token)).json()[
            "result"
        ]
        is None
    )


def test_token_owner_legacy_invalid_and_revoked_boundaries(setup, monkeypatch):
    store, device, token, client = setup
    other, other_token = store.provision_local()
    key = store.request_read(token, mod.ACTION)["request_id"]
    for bad in ["bad", "legacy-token-" + "a" * 48, other_token]:
        assert client.get("/v1/remote-read/requests/" + key, headers=auth(bad)).status_code == 409
    with pytest.raises(ValueError):
        store.review_local(key, other, True)
    store.revoke_local(device)
    assert client.get("/v1/remote-read/requests/" + key, headers=auth(token)).status_code == 409
    assert (
        client.post(
            "/v1/remote-read/requests", headers=auth(token), json={"action": mod.ACTION}
        ).status_code
        == 409
    )
    with pytest.raises(ValueError):
        store.inspect_local(key)


def test_deny_expire_result_expiry_stop_resume_no_resurrection(setup, monkeypatch):
    store, device, token, client = setup
    now = 10000
    monkeypatch.setattr(mod.time, "time", lambda: now)
    denied = store.request_read(token, mod.ACTION)["request_id"]
    store.review_local(denied, device, False)
    assert store.read_result(token, denied)["state"] == "denied"
    key = store.request_read(token, mod.ACTION)["request_id"]
    now += 121
    assert store.read_result(token, key)["state"] == "expired"
    with pytest.raises(ValueError):
        store.review_local(key, device, True)
    key = store.request_read(token, mod.ACTION)["request_id"]
    store.review_local(key, device, True)
    now += 121
    assert store.read_result(token, key)["state"] == "result_expired"
    key = store.request_read(token, mod.ACTION)["request_id"]
    store.set_stop(True)
    with pytest.raises(ValueError):
        store.request_read(token, mod.ACTION)
    with pytest.raises(ValueError):
        store.read_result(token, key)
    store.set_stop(False)
    assert store.read_result(token, key)["state"] == "stopped"
    with pytest.raises(ValueError):
        store.review_local(key, device, True)


def test_concurrent_review_executes_at_most_once(setup, monkeypatch):
    store, device, token, client = setup
    calls = []
    monkeypatch.setattr(
        mod,
        "memory_snapshot",
        lambda: (
            calls.append(1)
            or {"total_bytes": 1000, "available_bytes": 500, "used_percent_reported": 50}
        ),
    )
    key = store.request_read(token, mod.ACTION)["request_id"]

    def run(_):
        try:
            return store.review_local(key, device, True)["state"]
        except ValueError:
            return "refused"

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        states = list(pool.map(run, range(4)))
    assert states.count("completed") == 1 and len(calls) == 1


def test_revocation_or_stop_during_read_suppresses_result(setup, monkeypatch):
    store, device, token, client = setup
    key = store.request_read(token, mod.ACTION)["request_id"]

    def stop():
        store.set_stop(True)
        return {"total_bytes": 1, "available_bytes": 1, "used_percent_reported": 0}

    monkeypatch.setattr(mod, "memory_snapshot", stop)
    store.review_local(key, device, True)
    store.set_stop(False)
    assert store.read_result(token, key)["result"] is None
    key = store.request_read(token, mod.ACTION)["request_id"]

    def revoke():
        store.revoke_local(device)
        return {"total_bytes": 1, "available_bytes": 1, "used_percent_reported": 0}

    monkeypatch.setattr(mod, "memory_snapshot", revoke)
    store.review_local(key, device, True)
    with pytest.raises(ValueError):
        store.read_result(token, key)


def test_failure_consumed_no_raw_exception_or_retry(setup, monkeypatch):
    store, device, token, client = setup
    key = store.request_read(token, mod.ACTION)["request_id"]

    def fail():
        raise RuntimeError("PRIVATE_DETAILS")

    monkeypatch.setattr(mod, "memory_snapshot", fail)
    assert store.review_local(key, device, True)["state"] == "failed"
    result = store.read_result(token, key)
    assert result["result"] is None and "PRIVATE_DETAILS" not in str(result)
    with pytest.raises(ValueError):
        store.review_local(key, device, True)


def test_pending_capacity_and_strict_action_ids(setup):
    store, device, token, client = setup
    for _ in range(5):
        store.request_read(token, mod.ACTION)
    with pytest.raises(ValueError):
        store.request_read(token, mod.ACTION)
    for key in ["bad", "../path", "A" * 32, None]:
        with pytest.raises(ValueError):
            store.read_result(token, key)
    with pytest.raises(ValueError):
        store.request_read(token, "memory_snapshot;whoami")


def test_cli_noninteractive_refused(setup, monkeypatch):
    monkeypatch.setattr(mod.sys.stdin, "isatty", lambda: False)
    with pytest.raises(SystemExit):
        mod.main(["pair"])


def test_metrics_fixed_and_bounded(monkeypatch):
    import psutil

    monkeypatch.setattr(mod.platform, "system", lambda: "Windows")
    # restore actual function because this test does not use setup fixture
    monkeypatch.setattr(
        psutil, "virtual_memory", lambda: SimpleNamespace(total=1000, available=250, percent=75.04)
    )
    assert mod.memory_snapshot() == {
        "total_bytes": 1000,
        "available_bytes": 250,
        "used_percent_reported": 75.0,
    }
    for total, available, percent in [
        (0, 0, 0),
        (True, 0, 0),
        (1000, 1001, 0),
        (1000, 1, float("nan")),
        (1000, 1, 101),
    ]:
        monkeypatch.setattr(
            psutil,
            "virtual_memory",
            lambda: SimpleNamespace(total=total, available=available, percent=percent),
        )
        with pytest.raises(ValueError):
            mod.memory_snapshot()
    monkeypatch.setattr(mod.platform, "system", lambda: "Linux")
    with pytest.raises(ValueError):
        mod.memory_snapshot()


@pytest.mark.parametrize(
    "data",
    [
        {"private": "SECRET"},
        {"total_bytes": 1, "available_bytes": 1, "used_percent_reported": 0, "extra": "SECRET"},
        {"total_bytes": True, "available_bytes": 1, "used_percent_reported": 0},
        {"total_bytes": 1, "available_bytes": 1, "used_percent_reported": float("inf")},
    ],
)
def test_closed_result_schema_cannot_expand_disclosure(setup, monkeypatch, data):
    store, device, token, client = setup
    key = store.request_read(token, mod.ACTION)["request_id"]
    monkeypatch.setattr(mod, "memory_snapshot", lambda: data)
    assert store.review_local(key, device, True)["state"] == "failed"
    assert store.read_result(token, key)["result"] is None
    assert "SECRET" not in str(store.read_result(token, key))


def test_cli_interactive_exact_request_review_not_remote_boolean(setup, monkeypatch):
    store, device, token, client = setup
    key = store.request_read(token, mod.ACTION)["request_id"]
    monkeypatch.setattr(mod.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(mod.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "SHARE MEMORY")
    mod.main(["review", key])
    assert store.read_result(token, key)["state"] == "completed"


def test_tokens_and_device_capacity(setup):
    store, device, token, client = setup
    for bad in [None, "short", "x" * 257, "x" * 32 + "\n"]:
        with pytest.raises(ValueError):
            store.request_read(bad, mod.ACTION)
    for _ in range(49):
        store.provision_local()
    with pytest.raises(ValueError):
        store.provision_local()


def test_authenticated_pending_cancel_prevents_collection_and_review(setup, monkeypatch):
    store, device, token, client = setup
    key = store.request_read(token, mod.ACTION)["request_id"]
    monkeypatch.setattr(
        mod, "memory_snapshot", lambda: pytest.fail("cancelled pending read must not collect")
    )
    result = client.post(
        "/v1/remote-read/requests/" + key + "/cancel", headers=auth(token), json={}
    )
    assert result.status_code == 200
    assert (
        result.json()["collection_prevented"] and result.json()["state"] == "cancelled_before_read"
    )
    assert not result.json()["running_operation_termination_verified"]
    assert (
        client.get("/v1/remote-read/requests/" + key, headers=auth(token)).json()["result"] is None
    )
    with pytest.raises(ValueError):
        store.review_local(key, device, True)
    assert (
        client.post(
            "/v1/remote-read/requests/" + key + "/cancel", headers=auth(token), json={}
        ).json()["state"]
        == "cancelled_before_read"
    )


def test_cancel_is_owner_bound_and_extra_fields_refused(setup):
    store, device, token, client = setup
    other, other_token = store.provision_local()
    key = store.request_read(token, mod.ACTION)["request_id"]
    for bad in [other_token, "wrong", "legacy-token-" + "a" * 48]:
        assert (
            client.post(
                "/v1/remote-read/requests/" + key + "/cancel", headers=auth(bad), json={}
            ).status_code
            == 409
        )
    assert client.post("/v1/remote-read/requests/" + key + "/cancel", json={}).status_code == 409
    assert (
        client.post(
            "/v1/remote-read/requests/" + key + "/cancel",
            headers=auth(token),
            json={"approved": True},
        ).status_code
        == 422
    )
    assert store.inspect_local(key)["device_id"] == device


def test_running_cancel_suppresses_publication_not_collector_termination(setup, monkeypatch):
    import threading

    store, device, token, client = setup
    key = store.request_read(token, mod.ACTION)["request_id"]
    entered = threading.Event()
    finish = threading.Event()
    calls = []

    def collect():
        calls.append(1)
        entered.set()
        assert finish.wait(3)
        return {"total_bytes": 1000, "available_bytes": 500, "used_percent_reported": 50}

    monkeypatch.setattr(mod, "memory_snapshot", collect)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(store.review_local, key, device, True)
        try:
            assert entered.wait(2)
            result = client.post(
                "/v1/remote-read/requests/" + key + "/cancel", headers=auth(token), json={}
            ).json()
            assert (
                result["state"] == "cancelled_result_suppressed"
                and not result["collection_prevented"]
            )
            assert not result["running_operation_termination_verified"]
        finally:
            finish.set()
        assert running.result()["state"] == "result_unavailable"
    result = store.read_result(token, key)
    assert (
        result["state"] == "cancelled_result_suppressed"
        and result["result"] is None
        and calls == [1]
    )
    with pytest.raises(ValueError):
        store.review_local(key, device, True)


def test_completed_result_clear_no_recall_and_idempotent(setup):
    store, device, token, client = setup
    key = store.request_read(token, mod.ACTION)["request_id"]
    store.review_local(key, device, True)
    old = store.read_result(token, key)
    assert old["result"]["total_bytes"] == 1000
    assert isinstance(old["captured_at_unix"], float)
    cleared = store.cancel_request(token, key)
    assert cleared["state"] == "result_cleared" and not cleared["collection_prevented"]
    assert store.read_result(token, key)["result"] is None
    assert store.cancel_request(token, key)["state"] == "result_cleared"
    assert old["result"]["total_bytes"] == 1000  # an already returned copy cannot be recalled
    with store.connect() as db:
        assert (
            db.execute("SELECT result FROM remote_read_requests WHERE id=?", (key,)).fetchone()[0]
            is None
        )


def test_cancel_during_local_stop_and_revoked_device_refusal(setup):
    store, device, token, client = setup
    key = store.request_read(token, mod.ACTION)["request_id"]
    store.set_stop(True)
    assert store.cancel_request(token, key)["state"] == "stopped"
    store.set_stop(False)
    assert store.read_result(token, key)["result"] is None
    store.revoke_local(device)
    with pytest.raises(ValueError):
        store.cancel_request(token, key)


def test_concurrent_cancel_review_never_republishes_cancelled_result(setup, monkeypatch):
    store, device, token, client = setup
    for _ in range(10):
        key = store.request_read(token, mod.ACTION)["request_id"]

        def review_once():
            try:
                return store.review_local(key, device, True)
            except ValueError:
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(review_once)
            b = pool.submit(store.cancel_request, token, key)
            a.result()
            b.result()
        result = store.read_result(token, key)
        assert result["result"] is None
        assert result["state"] in {
            "cancelled_before_read",
            "cancelled_result_suppressed",
            "result_cleared",
        }


def test_result_schema_and_owner_action_tamper_fail_closed(setup):
    store, device, token, client = setup
    key = store.request_read(token, mod.ACTION)["request_id"]
    store.review_local(key, device, True)
    with store.connect() as db:
        db.execute(
            "UPDATE remote_read_requests SET result=? WHERE id=?",
            (json.dumps({"private": "DO_NOT_LEAK"}), key),
        )
    response = client.get("/v1/remote-read/requests/" + key, headers=auth(token))
    assert response.status_code == 409 and "DO_NOT_LEAK" not in response.text
    assert store.cancel_request(token, key)["state"] == "result_cleared"
    with store.connect() as db:
        db.execute("UPDATE remote_read_requests SET action=? WHERE id=?", ("run_shell", key))
    with pytest.raises(ValueError):
        store.cancel_request(token, key)
    with pytest.raises(ValueError):
        store.read_result(token, key)
