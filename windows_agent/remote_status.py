"""Per-device read-only laptop status request/result path; collection only after laptop-local review."""

from __future__ import annotations

import json
import math
import platform
import re
import sys
import time
import uuid

from windows_agent.local_approval import LocalApprovalStore
from windows_agent.remote_read import _digest, _id

ACTION = "system_snapshot"
REQUEST_TTL = 120
RESULT_TTL = 120
MAX_DISKS = 8
MAX_RESULT_BYTES = 4096


def system_snapshot():
    if platform.system() != "Windows":
        raise ValueError("Laptop status snapshot is supported on Windows only.")
    import psutil

    cpu = psutil.cpu_percent(interval=0.2)
    cores = psutil.cpu_count(logical=True)
    vm = psutil.virtual_memory()
    disks = []
    for part in psutil.disk_partitions(all=False)[:MAX_DISKS]:
        mount = part.mountpoint or ""
        if not re.fullmatch(r"[A-Za-z]:[\\/]?", mount):
            continue  # Simple local drive-letter mounts only; never UNC/network paths.
        usage = psutil.disk_usage(mount)
        disks.append(
            {
                "mount": mount.rstrip("\\/").upper() + ":\\",
                "total_bytes": usage.total,
                "free_bytes": usage.free,
                "used_percent_reported": round(usage.percent, 1),
            }
        )
    battery = None
    raw_battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
    if raw_battery is not None and type(raw_battery.percent) in (int, float):
        battery = {
            "percent_reported": round(raw_battery.percent, 1),
            "plugged": bool(raw_battery.power_plugged),
        }
    links_up = None
    try:
        stats = psutil.net_if_stats()
        links_up = sum(1 for item in stats.values() if item.isup)
    except Exception:
        links_up = None
    return {
        "cpu_percent_reported": round(cpu, 1),
        "cpu_cores_logical": cores,
        "memory_total_bytes": vm.total,
        "memory_available_bytes": vm.available,
        "disks": disks,
        "battery": battery,
        "network_links_up": links_up,
    }


def _finite_percent(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 100


def _closed_status(data):
    if not isinstance(data, dict) or set(data) != {
        "cpu_percent_reported",
        "cpu_cores_logical",
        "memory_total_bytes",
        "memory_available_bytes",
        "disks",
        "battery",
        "network_links_up",
    }:
        raise ValueError("Unsupported status result schema.")
    if not _finite_percent(data["cpu_percent_reported"]):
        raise ValueError("Unsupported CPU percentage.")
    cores = data["cpu_cores_logical"]
    if type(cores) is not int or not 1 <= cores <= 1024:
        raise ValueError("Unsupported core count.")
    total, available = data["memory_total_bytes"], data["memory_available_bytes"]
    if (
        type(total) is not int
        or type(available) is not int
        or not 0 < total <= 2**60
        or not 0 <= available <= total
    ):
        raise ValueError("Unsupported memory values.")
    disks = data["disks"]
    if not isinstance(disks, list) or len(disks) > MAX_DISKS:
        raise ValueError("Unsupported disk list.")
    closed_disks = []
    for disk in disks:
        if not isinstance(disk, dict) or set(disk) != {
            "mount",
            "total_bytes",
            "free_bytes",
            "used_percent_reported",
        }:
            raise ValueError("Unsupported disk entry schema.")
        if not isinstance(disk["mount"], str) or re.fullmatch(r"[A-Z]:\\", disk["mount"]) is None:
            raise ValueError("Unsupported disk mount label.")
        dtotal, dfree = disk["total_bytes"], disk["free_bytes"]
        if (
            type(dtotal) is not int
            or type(dfree) is not int
            or not 0 < dtotal <= 2**60
            or not 0 <= dfree <= dtotal
        ):
            raise ValueError("Unsupported disk values.")
        if not _finite_percent(disk["used_percent_reported"]):
            raise ValueError("Unsupported disk percentage.")
        closed_disks.append(
            {
                "mount": disk["mount"],
                "total_bytes": dtotal,
                "free_bytes": dfree,
                "used_percent_reported": disk["used_percent_reported"],
            }
        )
    battery = data["battery"]
    if battery is not None:
        if not isinstance(battery, dict) or set(battery) != {"percent_reported", "plugged"}:
            raise ValueError("Unsupported battery schema.")
        if not _finite_percent(battery["percent_reported"]) or type(battery["plugged"]) is not bool:
            raise ValueError("Unsupported battery values.")
        battery = {"percent_reported": battery["percent_reported"], "plugged": battery["plugged"]}
    links = data["network_links_up"]
    if links is not None and (type(links) is not int or not 0 <= links <= 1000):
        raise ValueError("Unsupported link count.")
    return {
        "cpu_percent_reported": data["cpu_percent_reported"],
        "cpu_cores_logical": cores,
        "memory_total_bytes": total,
        "memory_available_bytes": available,
        "disks": closed_disks,
        "battery": battery,
        "network_links_up": links,
    }


class RemoteStatusStore(LocalApprovalStore):
    def __init__(self):
        super().__init__()
        with self.connect() as db:
            db.executescript(
                """CREATE TABLE IF NOT EXISTS remote_read_devices (
                id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE, revoked INTEGER NOT NULL DEFAULT0);
                CREATE TABLE IF NOT EXISTS remote_status_requests (
                id TEXT PRIMARY KEY, device_id TEXT NOT NULL, action TEXT NOT NULL,
                expires REAL NOT NULL, state TEXT NOT NULL, result TEXT, result_expires REAL);
            """.replace("DEFAULT0", "DEFAULT 0")
            )

    @staticmethod
    def _device(db, token):
        digest = _digest(token)
        row = db.execute(
            "SELECT id FROM remote_read_devices WHERE token_hash=? AND revoked=0", (digest,)
        ).fetchone()
        if not row:
            raise ValueError("Device token invalid/revoked; no request/result access.")
        return row[0]

    def request_status(self, token, action):
        if action != ACTION:
            raise ValueError(
                "Only the fixed system_snapshot action is supported; no command arguments."
            )
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._active(db)
            device = self._device(db, token)
            db.execute(
                "DELETE FROM remote_status_requests WHERE expires<=? AND (result_expires IS NULL OR result_expires<=?)",
                (time.time(), time.time()),
            )
            if db.execute("SELECT count(*) FROM remote_status_requests").fetchone()[0] >= 100:
                raise ValueError("Local request capacity reached.")
            if (
                db.execute(
                    "SELECT count(*) FROM remote_status_requests WHERE device_id=? AND state IN ('pending_local_review','running_local_read')",
                    (device,),
                ).fetchone()[0]
                >= 5
            ):
                raise ValueError("Device pending request limit reached.")
            key = uuid.uuid4().hex
            db.execute(
                "INSERT INTO remote_status_requests(id,device_id,action,expires,state) VALUES(?,?,?,?,?)",
                (key, device, ACTION, time.time() + REQUEST_TTL, "pending_local_review"),
            )
        return {
            "request_id": key,
            "action": ACTION,
            "state": "pending_local_review",
            "expires_in_seconds": REQUEST_TTL,
            "executed": False,
        }

    def inspect_local(self, request_id):
        _id(request_id)
        with self.connect() as db:
            self._active(db)
            row = db.execute(
                "SELECT r.device_id,r.action,r.expires,r.state,d.revoked FROM remote_status_requests r JOIN remote_read_devices d ON d.id=r.device_id WHERE r.id=?",
                (request_id,),
            ).fetchone()
        if (
            not row
            or row[2] <= time.time()
            or row[3] != "pending_local_review"
            or row[4]
            or row[1] != ACTION
        ):
            raise ValueError("Request missing/expired/decided/revoked or unsupported.")
        return {"request_id": request_id, "device_id": row[0], "action": ACTION}

    def review_local(self, request_id, expected_device, approved):
        _id(request_id)
        _id(expected_device)
        if type(approved) is not bool:
            raise ValueError("Explicit local boolean decision required.")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._active(db)
            row = db.execute(
                "SELECT r.action,r.expires,r.state,d.revoked FROM remote_status_requests r JOIN remote_read_devices d ON d.id=r.device_id WHERE r.id=? AND r.device_id=?",
                (request_id, expected_device),
            ).fetchone()
            if (
                not row
                or row[0] != ACTION
                or row[1] <= time.time()
                or row[2] != "pending_local_review"
                or row[3]
            ):
                raise ValueError("Request changed/expired/replayed/revoked.")
            db.execute(
                "UPDATE remote_status_requests SET state=? WHERE id=?",
                ("running_local_read" if approved else "denied", request_id),
            )
        if not approved:
            return {"state": "denied", "executed": False}
        # Consumed before collecting. No queue-retry after failure. Only fixed code, no registry lookup/shell.
        try:
            data = _closed_status(system_snapshot())
            encoded = json.dumps(data, allow_nan=False, separators=(",", ":"))
            if len(encoded) > MAX_RESULT_BYTES:
                raise ValueError("Unexpected output size.")
            state = "completed"
        except Exception:
            encoded, state = None, "failed"
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self._active(db)
            except ValueError:
                state, encoded = "stopped", None
            revoked = db.execute(
                "SELECT revoked FROM remote_read_devices WHERE id=?", (expected_device,)
            ).fetchone()
            if not revoked or revoked[0]:
                state, encoded = "revoked", None
            changed = db.execute(
                "UPDATE remote_status_requests SET state=?,result=?,result_expires=? WHERE id=? AND state='running_local_read'",
                (state, encoded, time.time() + RESULT_TTL, request_id),
            ).rowcount
            if changed != 1:
                state = "result_unavailable"
        return {"state": state, "executed": True, "result_disclosed_locally": False}

    def cancel_request(self, token, request_id):
        _id(request_id)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            # Stop blocks reads/new work, but authenticated privacy cancellation remains available.
            device = self._device(db, token)
            row = db.execute(
                "SELECT action,state,expires,result_expires FROM remote_status_requests WHERE id=? AND device_id=?",
                (request_id, device),
            ).fetchone()
            if not row or row[0] != ACTION:
                raise ValueError("Request unavailable for this device.")
            previous, expires, result_expires = row[1:]
            known = {
                "pending_local_review",
                "running_local_read",
                "completed",
                "denied",
                "failed",
                "stopped",
                "revoked",
                "cancelled_before_read",
                "cancelled_result_suppressed",
                "result_cleared",
            }
            if previous not in known:
                raise ValueError("Unsupported stored request state.")
            if previous == "pending_local_review":
                state = "cancelled_before_read"
            elif previous == "running_local_read":
                state = "cancelled_result_suppressed"
            elif previous == "completed":
                state = "result_cleared"
            else:
                state = previous
            # Idempotent, owner-bound and irreversible for this request. Never dispatch a collector.
            db.execute(
                "UPDATE remote_status_requests SET state=?,result=NULL,result_expires=? WHERE id=? AND device_id=?",
                (
                    state,
                    result_expires if result_expires is not None else expires,
                    request_id,
                    device,
                ),
            )
        return {
            "request_id": request_id,
            "action": ACTION,
            "state": state,
            "result": None,
            "cancel_acknowledged": True,
            "collection_prevented": state == "cancelled_before_read",
            "running_operation_termination_verified": False,
            "notice": "Pending cancellation prevents this request from starting; if already dispatched, only result publication/access is suppressed. A read may already have happened. No OS/process kill, undo, secure erasure or recall of an already returned/displayed copy. No retry or approval is created.",
        }

    def read_result(self, token, request_id):
        _id(request_id)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._active(db)
            device = self._device(db, token)
            row = db.execute(
                "SELECT action,expires,state,result,result_expires FROM remote_status_requests WHERE id=? AND device_id=?",
                (request_id, device),
            ).fetchone()
        if not row:
            raise ValueError("Request unavailable for this device.")
        action, expires, state, raw, result_expires = row
        if action != ACTION:
            raise ValueError("Unsupported stored action.")
        if state in ("pending_local_review", "running_local_read") and expires <= time.time():
            return {"request_id": request_id, "action": ACTION, "state": "expired", "result": None}
        if result_expires is not None and result_expires <= time.time():
            return {
                "request_id": request_id,
                "action": ACTION,
                "state": "result_expired",
                "result": None,
            }
        return {
            "request_id": request_id,
            "action": ACTION,
            "state": state,
            "result": _closed_status(json.loads(raw)) if raw and state == "completed" else None,
            "source": "Fixed laptop-local CPU/memory/drive/battery/link read after local review, not complete system health, utilization history, GPU usage or temperature",
            "result_ttl_seconds": RESULT_TTL,
            "captured_at_unix": result_expires - RESULT_TTL
            if result_expires is not None and state == "completed"
            else None,
            "device_display_verified": False,
        }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="AETHER laptop-local paired status review")
    parser.add_argument("action", choices=["review"])
    parser.add_argument("identifier", nargs="?")
    args = parser.parse_args(argv)
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error("Use an interactive terminal on the trusted laptop; no piped approval.")
    store = RemoteStatusStore()
    item = store.inspect_local(args.identifier)
    print("Exact request ID:", item["request_id"])
    print("Requesting opaque device ID:", item["device_id"])
    print(
        "Action: system_snapshot. Reads reported CPU percent, logical core count, RAM total/available bytes, drive-letter capacity/free bytes, battery percent/plug state and up-link count only. No machine/user/file/process names, GPU usage, temperature, addresses or SSIDs. A short-lived result is released to this device token over the configured connection. Queueing/phone confirmation is not approval. Expires120seconds after creation. No shell or fallback. Pairing uses python -m windows_agent.remote_read pair; devices are shared."
    )
    answer = input(
        "Type SHARE STATUS to approve this one exact read/result disclosure; anything else denies: "
    )
    result = store.review_local(item["request_id"], item["device_id"], answer == "SHARE STATUS")
    print("State:", result["state"])


if __name__ == "__main__":
    main()
