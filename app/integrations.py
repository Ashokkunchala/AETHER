"""AETHER external-service integration primitives.

OAuth credentials and provider tokens remain server-side. External mutations are
represented as approval requests and are never executed by a draft/create route.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel, Field

from app.config import get_settings
from app.personal_data import require_device_token

router = APIRouter(prefix="/api/integrations", tags=["AETHER integrations"])
settings = get_settings()
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_API = "https://www.googleapis.com"
META_GRAPH = "https://graph.facebook.com/v23.0"
GOOGLE_SCOPES = (
    "openid email profile "
    "https://www.googleapis.com/auth/calendar.events "
    "https://www.googleapis.com/auth/gmail.readonly "
    "https://www.googleapis.com/auth/gmail.send"
)


@contextmanager
def _connect():
    path = Path(settings.jarvis_db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript("""
      CREATE TABLE IF NOT EXISTS integration_secrets (
        provider TEXT PRIMARY KEY, encrypted_value TEXT NOT NULL, updated_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS integration_states (
        nonce_hash TEXT PRIMARY KEY, created_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS approval_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT NOT NULL,
        action TEXT NOT NULL, payload_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending', result_json TEXT,
        created_at TEXT NOT NULL, decided_at TEXT
      );
      CREATE TABLE IF NOT EXISTS aether_notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, body TEXT NOT NULL,
        channel TEXT NOT NULL DEFAULT 'general', due_at TEXT, delivered_at TEXT,
        read_at TEXT, created_at TEXT NOT NULL
      );
    """)
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _fernet() -> Fernet:
    key_material = settings.secret_key or settings.jarvis_api_token
    if len(key_material) < 32:
        raise HTTPException(503, "Configure a 32-character SECRET_KEY to enable integrations.")
    key = __import__("base64").urlsafe_b64encode(hashlib.sha256(key_material.encode()).digest())
    return Fernet(key)


def _seal(value: dict) -> str:
    return _fernet().encrypt(json.dumps(value).encode()).decode()


def _open(value: str) -> dict:
    try:
        return json.loads(_fernet().decrypt(value.encode()))
    except (InvalidToken, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(503, "Stored integration credentials cannot be decrypted.") from exc


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _google_credentials() -> tuple[str, str, str]:
    client_id = settings.google_oauth_client_id
    client_secret = settings.google_oauth_client_secret
    redirect_uri = settings.google_oauth_redirect_uri
    if not client_id or not client_secret or not redirect_uri:
        raise HTTPException(503, "Configure GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET and GOOGLE_OAUTH_REDIRECT_URI.")
    return client_id, client_secret, redirect_uri


def _save_provider(provider: str, data: dict) -> None:
    with _connect() as db:
        db.execute(
            "INSERT INTO integration_secrets(provider,encrypted_value,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(provider) DO UPDATE SET encrypted_value=excluded.encrypted_value,updated_at=excluded.updated_at",
            (provider, _seal(data), _now()),
        )


def _provider(provider: str) -> dict:
    with _connect() as db:
        row = db.execute("SELECT encrypted_value FROM integration_secrets WHERE provider=?", (provider,)).fetchone()
    if not row:
        raise HTTPException(409, f"{provider} is not connected.")
    return _open(row["encrypted_value"])


async def _google_access_token() -> str:
    data = _provider("google")
    expires = datetime.fromisoformat(data["expires_at"])
    if expires > datetime.now(UTC) + timedelta(seconds=90):
        return data["access_token"]
    client_id, client_secret, _ = _google_credentials()
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(GOOGLE_TOKEN, data={
            "client_id": client_id, "client_secret": client_secret,
            "refresh_token": data["refresh_token"], "grant_type": "refresh_token",
        })
    if response.status_code != 200:
        raise HTTPException(502, "Google token refresh failed; reconnect Google.")
    token = response.json()
    data["access_token"] = token["access_token"]
    data["expires_at"] = (datetime.now(UTC) + timedelta(seconds=int(token.get("expires_in", 3600)))).isoformat()
    _save_provider("google", data)
    return data["access_token"]


async def _google(method: str, path: str, *, params: dict | None = None, body: dict | None = None):
    token = await _google_access_token()
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.request(method, GOOGLE_API + path, params=params, json=body,
                                        headers={"Authorization": f"Bearer {token}"})
    if response.status_code >= 400:
        raise HTTPException(502, f"Google API request failed ({response.status_code}).")
    return response.json() if response.content else {}


class CalendarProposal(BaseModel):
    action: Literal["create", "update", "delete"]
    event_id: str | None = None
    title: str | None = Field(default=None, max_length=200)
    description: str = Field(default="", max_length=5000)
    location: str = Field(default="", max_length=500)
    start: str | None = None
    end: str | None = None


class EmailDraft(BaseModel):
    to: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=20000)


class WhatsAppDraft(BaseModel):
    to: str = Field(min_length=8, max_length=20)
    body: str = Field(min_length=1, max_length=4096)


@router.get("/google/connect")
def google_connect(_=Depends(require_device_token)):
    client_id, _, redirect_uri = _google_credentials()
    nonce = secrets.token_urlsafe(32)
    serializer = URLSafeTimedSerializer(settings.secret_key or settings.jarvis_api_token, salt="aether-google-oauth")
    state = serializer.dumps(nonce)
    with _connect() as db:
        db.execute("DELETE FROM integration_states WHERE created_at<?", ((datetime.now(UTC)-timedelta(minutes=15)).isoformat(),))
        db.execute("INSERT INTO integration_states(nonce_hash,created_at) VALUES(?,?)",
                   (hashlib.sha256(nonce.encode()).hexdigest(), _now()))
    params = {"client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
              "scope": GOOGLE_SCOPES, "access_type": "offline", "prompt": "consent",
              "include_granted_scopes": "true", "state": state}
    return {"authorization_url": GOOGLE_AUTH + "?" + urlencode(params)}


@router.get("/google/callback", include_in_schema=False)
async def google_callback(code: str, state: str, error: str | None = None):
    if error:
        raise HTTPException(400, "Google authorization was not completed.")
    try:
        nonce = URLSafeTimedSerializer(settings.secret_key or settings.jarvis_api_token,
                                       salt="aether-google-oauth").loads(state, max_age=600)
    except BadSignature as exc:
        raise HTTPException(400, "Invalid or expired OAuth state.") from exc
    digest = hashlib.sha256(nonce.encode()).hexdigest()
    with _connect() as db:
        row = db.execute("SELECT 1 FROM integration_states WHERE nonce_hash=?", (digest,)).fetchone()
        if not row:
            raise HTTPException(400, "OAuth state was already used or expired.")
        db.execute("DELETE FROM integration_states WHERE nonce_hash=?", (digest,))
    client_id, client_secret, redirect_uri = _google_credentials()
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(GOOGLE_TOKEN, data={
            "code": code, "client_id": client_id, "client_secret": client_secret,
            "redirect_uri": redirect_uri, "grant_type": "authorization_code",
        })
    if response.status_code != 200:
        raise HTTPException(502, "Google token exchange failed.")
    token = response.json()
    if not token.get("refresh_token"):
        raise HTTPException(400, "Google did not return a refresh token. Revoke the app grant and reconnect.")
    _save_provider("google", {
        "access_token": token["access_token"], "refresh_token": token["refresh_token"],
        "expires_at": (datetime.now(UTC)+timedelta(seconds=int(token.get("expires_in",3600)))).isoformat(),
        "scope": token.get("scope", ""),
    })
    return RedirectResponse("/life?google=connected", status_code=303)


@router.get("/status", dependencies=[Depends(require_device_token)])
def integration_status():
    with _connect() as db:
        rows = {row["provider"]: row["updated_at"] for row in db.execute("SELECT provider,updated_at FROM integration_secrets")}
    return {
        "google": {"connected": "google" in rows, "updated_at": rows.get("google")},
        "whatsapp": {"configured": bool(settings.whatsapp_access_token and settings.whatsapp_phone_number_id)},
        "documents": {"configured": bool(settings.document_allowed_roots)},
    }


@router.get("/calendar/events", dependencies=[Depends(require_device_token)])
async def calendar_events(time_min: str | None = None, time_max: str | None = None,
                          max_results: int = Query(default=50, ge=1, le=250)):
    params = {"singleEvents": "true", "orderBy": "startTime", "maxResults": max_results}
    if time_min: params["timeMin"] = time_min
    if time_max: params["timeMax"] = time_max
    return await _google("GET", "/calendar/v3/calendars/primary/events", params=params)


def _approval(provider: str, action: str, payload: dict) -> dict:
    with _connect() as db:
        cur = db.execute("INSERT INTO approval_requests(provider,action,payload_json,created_at) VALUES(?,?,?,?)",
                         (provider, action, json.dumps(payload), _now()))
        return {"id": cur.lastrowid, "provider": provider, "action": action, "status": "pending",
                "payload": payload, "message": "Review and explicitly approve before execution."}


@router.post("/calendar/proposals", status_code=201, dependencies=[Depends(require_device_token)])
def calendar_proposal(item: CalendarProposal):
    if item.action in {"update", "delete"} and not item.event_id:
        raise HTTPException(422, "event_id is required for update/delete.")
    if item.action != "delete" and (not item.title or not item.start or not item.end):
        raise HTTPException(422, "title, start and end are required.")
    if item.start and item.end and item.end <= item.start:
        raise HTTPException(422, "Event end must be after start.")
    return _approval("google_calendar", item.action, item.model_dump())


@router.get("/approvals", dependencies=[Depends(require_device_token)])
def pending_approvals():
    with _connect() as db:
        rows = db.execute("SELECT * FROM approval_requests WHERE status='pending' ORDER BY id DESC LIMIT 100").fetchall()
    return {"items": [{**dict(r), "payload": json.loads(r["payload_json"])} for r in rows]}


@router.post("/approvals/{approval_id}/approve", dependencies=[Depends(require_device_token)])
async def approve_action(approval_id: int):
    with _connect() as db:
        row = db.execute("SELECT * FROM approval_requests WHERE id=?", (approval_id,)).fetchone()
        if not row or row["status"] != "pending":
            raise HTTPException(404, "Pending approval not found.")
        claim = db.execute("UPDATE approval_requests SET status='executing' WHERE id=? AND status='pending'",
                           (approval_id,))
        if not claim.rowcount:
            raise HTTPException(409, "This approval is already being processed.")
        payload = json.loads(row["payload_json"])
        provider, action = row["provider"], row["action"]
    try:
        result = None
        if provider == "google_calendar":
            event_id = payload.get("event_id")
            if action == "delete":
                result = await _google("DELETE", f"/calendar/v3/calendars/primary/events/{event_id}")
            else:
                event = {"summary": payload["title"], "description": payload.get("description", ""),
                         "location": payload.get("location", ""),
                         "start": {"dateTime": payload["start"]}, "end": {"dateTime": payload["end"]}}
                result = await _google("POST" if action == "create" else "PATCH",
                                       "/calendar/v3/calendars/primary/events" if action == "create"
                                       else f"/calendar/v3/calendars/primary/events/{event_id}", body=event)
        elif provider == "gmail":
            result = await _send_gmail(payload)
        elif provider == "whatsapp":
            result = await _send_whatsapp(payload)
        else:
            raise HTTPException(400, "Unknown approval provider.")
        with _connect() as db:
            db.execute("UPDATE approval_requests SET status='approved',result_json=?,decided_at=? WHERE id=? AND status='executing'",
                       (json.dumps({"id": result.get("id") or result.get("message_id")}), _now(), approval_id))
        return {"status": "approved", "result": result}
    except Exception:
        with _connect() as db:
            db.execute("UPDATE approval_requests SET status='failed',decided_at=? WHERE id=? AND status='executing'",
                       (_now(), approval_id))
        raise


@router.post("/approvals/{approval_id}/reject", dependencies=[Depends(require_device_token)])
def reject_action(approval_id: int):
    with _connect() as db:
        cur = db.execute("UPDATE approval_requests SET status='rejected',decided_at=? WHERE id=? AND status='pending'",
                         (_now(), approval_id))
        if not cur.rowcount:
            raise HTTPException(404, "Pending approval not found.")
    return {"status": "rejected"}


@router.get("/gmail/messages", dependencies=[Depends(require_device_token)])
async def gmail_messages(q: str = "newer_than:14d", max_results: int = Query(default=20, ge=1, le=100)):
    listing = await _google("GET", "/gmail/v1/users/me/messages",
                            params={"q": q, "maxResults": max_results})
    messages = []
    for item in listing.get("messages", [])[:max_results]:
        msg = await _google("GET", f"/gmail/v1/users/me/messages/{item['id']}",
                            params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]})
        headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
        messages.append({"id": item["id"], "thread_id": msg.get("threadId"),
                         "from": headers.get("from", ""), "subject": headers.get("subject", ""),
                         "date": headers.get("date", ""), "snippet": msg.get("snippet", ""),
                         "unread": "UNREAD" in msg.get("labelIds", [])})
    return {"items": messages, "result_size_estimate": listing.get("resultSizeEstimate", 0)}


@router.post("/gmail/drafts", status_code=201, dependencies=[Depends(require_device_token)])
def gmail_draft(item: EmailDraft):
    return _approval("gmail", "send", item.model_dump())


async def _send_gmail(payload: dict):
    import base64
    from email.message import EmailMessage
    message = EmailMessage()
    message["To"] = payload["to"]
    message["Subject"] = payload["subject"]
    message.set_content(payload["body"])
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")
    return await _google("POST", "/gmail/v1/users/me/messages/send", body={"raw": raw})


@router.post("/whatsapp/drafts", status_code=201, dependencies=[Depends(require_device_token)])
def whatsapp_draft(item: WhatsAppDraft):
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        raise HTTPException(503, "Configure WhatsApp Cloud API credentials first.")
    return _approval("whatsapp", "send", item.model_dump())


async def _send_whatsapp(payload: dict):
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        raise HTTPException(503, "WhatsApp Cloud API is not configured.")
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(f"{META_GRAPH}/{settings.whatsapp_phone_number_id}/messages",
            headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
            json={"messaging_product": "whatsapp", "recipient_type": "individual",
                  "to": payload["to"], "type": "text", "text": {"preview_url": False, "body": payload["body"]}})
    if response.status_code >= 400:
        raise HTTPException(502, "WhatsApp message delivery failed.")
    return response.json()


@router.get("/documents/search", dependencies=[Depends(require_device_token)])
def search_documents(q: str = Query(min_length=2, max_length=200), limit: int = Query(default=20, ge=1, le=100)):
    roots = [Path(p).expanduser().resolve() for p in settings.document_allowed_roots.split(";") if p.strip()]
    if not roots:
        raise HTTPException(503, "Set DOCUMENT_ALLOWED_ROOTS to explicitly authorize folders.")
    terms = [term.casefold() for term in q.split() if len(term) > 1][:12]
    results = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if len(results) >= limit:
                break
            if not path.is_file() or path.suffix.lower() not in {".txt", ".md", ".log"}:
                continue
            try:
                resolved = path.resolve()
                if not resolved.is_relative_to(root) or path.stat().st_size > 2_000_000:
                    continue
                content = path.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                matches = [(i + 1, line.strip()[:500]) for i, line in enumerate(lines)
                           if all(term in line.casefold() for term in terms)]
                if matches:
                    results.append({"path": str(resolved), "matches": matches[:5]})
            except (OSError, PermissionError):
                continue
    return {"query": q, "items": results}


@router.get("/notifications", dependencies=[Depends(require_device_token)])
def notifications(after_id: int = 0, limit: int = Query(default=50, ge=1, le=100)):
    with _connect() as db:
        rows = db.execute("SELECT * FROM aether_notifications WHERE id>? ORDER BY id LIMIT ?",
                          (after_id, limit)).fetchall()
    return {"items": [dict(r) for r in rows]}


@router.post("/notifications/{notification_id}/read", dependencies=[Depends(require_device_token)])
def notification_read(notification_id: int):
    with _connect() as db:
        db.execute("UPDATE aether_notifications SET read_at=? WHERE id=?", (_now(), notification_id))
    return {"status": "read"}


def dispatch_due_reminders() -> int:
    """Turn due-soon personal reminders into one-shot cross-device notifications."""
    # Ensure the notification table exists before using the shared personal-data DB.
    with _connect():
        pass
    from app.personal_data import _connect as personal_connect
    db = personal_connect()
    try:
        columns = {row[1] for row in db.execute("PRAGMA table_info(reminders)")}
        if "notification_sent_at" not in columns:
            db.execute("ALTER TABLE reminders ADD COLUMN notification_sent_at TEXT")
        now = datetime.now(UTC)
        horizon = (now + timedelta(minutes=15)).isoformat()
        rows = db.execute(
            "SELECT id,title,due_at FROM reminders WHERE completed=0 "
            "AND notification_sent_at IS NULL AND due_at<=? ORDER BY due_at LIMIT 50",
            (horizon,),
        ).fetchall()
        for row in rows:
            db.execute("UPDATE reminders SET notification_sent_at=? WHERE id=? AND notification_sent_at IS NULL",
                       (_now(), row["id"]))
            db.execute(
                "INSERT INTO aether_notifications(title,body,channel,due_at,created_at) VALUES(?,?,?,?,?)",
                ("Reminder: " + row["title"][:160], "Due " + row["due_at"], "reminder",
                 row["due_at"], _now()),
            )
        db.commit()
        return len(rows)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def enqueue_notification(title: str, body: str, channel: str = "general", due_at: str | None = None) -> int:
    with _connect() as db:
        cur = db.execute("INSERT INTO aether_notifications(title,body,channel,due_at,created_at) VALUES(?,?,?,?,?)",
                         (title[:180], body[:1000], channel[:40], due_at, _now()))
        return int(cur.lastrowid)
