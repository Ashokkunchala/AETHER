"""WebSocket bridge for the browser UI and any remote client.

Speaks the same event vocabulary as ``AETHERBrain.ask`` so a browser gets the
realtime experience the terminal gets: streamed text, tool lifecycle events,
and an interactive confirmation dialog before anything risky runs.

Protocol (JSON text frames)
---------------------------
client → server
    {"type": "chat", "message": "...", "auto_approve": false}
    {"type": "approve", "id": "<confirm-id>", "approved": true}
    {"type": "cancel",  "id": "<turn-id>"}
    {"type": "status"}
    {"type": "tools"}
    {"type": "ping"}

server → client
    {"type": "ready", "model": ..., "tools": ...}
    {"type": "status", "message": ...}            # thinking / model fallback
    {"type": "text_delta", "text": ...}
    {"type": "tool_start" | "tool_end" | "tool_error" | "tool_cancelled", ...}
    {"type": "confirm", "id": ..., "tool": ..., "args": ..., "risk": ...}
    {"type": "done", "text": ..., "tools_used": [...], "elapsed": ...}
    {"type": "error", "error": ...}
    {"type": "status_snapshot", ...}
    {"type": "tools_list", ...}
    {"type": "pong"}

Auth: POST to ``/api/ws-ticket`` with the bearer token, then pass the
short-lived, single-use ticket as ``?ticket=...`` on the WebSocket handshake.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextvars import ContextVar
from dataclasses import replace
from typing import Annotated, Any, Literal, TypeAlias

from fastapi import APIRouter, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, RootModel, StrictBool, ValidationError
from starlette.websockets import WebSocketState

from app.core.ws_sessions import SessionIdentity, TicketStore
from aether.core.brain import AETHERBrain

logger = logging.getLogger("aether.ws")

router = APIRouter()

_WS_TICKET_TTL_SECONDS = 60
_APPROVAL_TIMEOUT_SECONDS = 60
_tickets = TicketStore(ttl=_WS_TICKET_TTL_SECONDS)


class _Frame(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ChatFrame(_Frame):
    type: Literal["chat"]
    message: str = Field(min_length=1, max_length=16000)
    # Backward-compatible but never used to grant authority.
    auto_approve: StrictBool = False


class ApprovalFrame(_Frame):
    type: Literal["approve"]
    id: str = Field(min_length=1, max_length=64)
    approved: StrictBool


class ControlFrame(_Frame):
    type: Literal["ping", "status", "tools", "cancel"]
    id: str | None = Field(default=None, max_length=64)


FrameType: TypeAlias = Annotated[ChatFrame | ApprovalFrame | ControlFrame, Field(discriminator="type")]


class IncomingFrame(RootModel[FrameType]):
    """Strict discriminated wire message; no implicit approval defaults."""


@router.post("/api/ws-ticket")
async def create_ws_ticket(request: Request, profile: Literal["legacy", "personal-readonly", "personal-local"] = "legacy") -> dict[str, int | str]:
    """Exchange a bearer credential for a short-lived, one-use WebSocket ticket."""
    identity = SessionIdentity.authenticate(request.headers.get("authorization"))
    ticket = _tickets.issue(replace(identity, profile=profile))
    from app.core.auth import token_auth
    token_auth._log_audit("ws_session_issued", device_id=identity.device_id, success=True)
    return {"ticket": ticket, "expires_in": _WS_TICKET_TTL_SECONDS}


# Free-tier Gemini quotas are tiny; never let one browser melt them.
MAX_CONCURRENT_TURNS = 2
_turn_gate = asyncio.Semaphore(MAX_CONCURRENT_TURNS)


def _sendable(event: dict[str, Any]) -> dict[str, Any]:
    """Make a brain event JSON-safe (Args/Path objects etc.)."""
    clean: dict[str, Any] = {}
    for key, value in event.items():
        try:
            json.dumps(value)
            clean[key] = value
        except (TypeError, ValueError):
            clean[key] = str(value)
    return clean


async def _emit(websocket: WebSocket, payload: dict[str, Any]) -> bool:
    """Send one frame; returns False when the socket is gone."""
    if websocket.client_state != WebSocketState.CONNECTED:
        return False
    try:
        await websocket.send_text(json.dumps(_sendable(payload), ensure_ascii=False, default=str))
        return True
    except (WebSocketDisconnect, RuntimeError):
        return False
    except Exception:  # pragma: no cover - defensive
        logger.debug("WebSocket send failed", exc_info=True)
        return False


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket, ticket: str = Query(default="")):
    """Streaming AETHER session authenticated with a one-use ticket."""
    identity = _tickets.consume(ticket)
    if identity is None:
        await websocket.close(code=4401, reason="unauthorized")
        logger.debug("WS handshake rejected: invalid or expired ticket")
        return

    await websocket.accept()
    turn_cancel = asyncio.Event()
    local_turn: ContextVar[asyncio.Event | None] = ContextVar("local_turn", default=None)
    if identity.profile == "personal-readonly":
        from app.personal_tool_chat import PERSONAL_PROMPT, build_personal_registry

        registry = build_personal_registry()
        if not len(registry):
            await websocket.close(code=1011, reason="personal tools unavailable")
            return
        brain = AETHERBrain(registry=registry, system_prompt=PERSONAL_PROMPT)
    elif identity.profile == "personal-local":
        from app.personal_local_tools import LOCAL_PROMPT, build_local_registry

        def local_session_active():
            context = local_turn.get()
            return context is not None and not context.is_set() and identity.is_active()

        registry = build_local_registry(local_session_active)
        brain = AETHERBrain(registry=registry, system_prompt=LOCAL_PROMPT)
    else:
        brain = AETHERBrain()
    pending_confirm: dict[str, asyncio.Future[bool]] = {}
    turn_task: asyncio.Task | None = None

    await _emit(websocket, {
        "type": "ready",
        "model": brain.active_model,
        "providers": brain.provider_candidates(),
        "tools": len(brain.registry),
        "configured": brain.configured,
        "profile": identity.profile,
    })

    async def confirm(tool, args: dict[str, Any]) -> bool:
        if turn_cancel.is_set() or not identity.is_active():
            return False
        confirm_id = uuid.uuid4().hex
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        pending_confirm[confirm_id] = future
        try:
            await _emit(websocket, {
                "type": "confirm",
                "id": confirm_id,
                "tool": tool.name,
                "description": tool.description,
                "category": tool.category,
                "risk": tool.risk.name,
                "args": args,
            })
            try:
                approved = await asyncio.wait_for(future, _APPROVAL_TIMEOUT_SECONDS)
            except TimeoutError:
                return False
            return approved and not turn_cancel.is_set() and identity.is_active()
        finally:
            pending_confirm.pop(confirm_id, None)

    async def run_turn(message: str) -> None:
        nonlocal turn_task, turn_cancel
        turn_cancel = asyncio.Event()
        turn_context = local_turn.set(turn_cancel)
        if not identity.is_active():
            await websocket.close(code=4401, reason="session revoked")
            turn_task = None
            local_turn.reset(turn_context)
            return
        try:
            async with _turn_gate:
                # Remote clients cannot self-grant approval. Sensitive tools always
                # flow through the explicit confirmation callback for this socket.
                async for event in brain.ask(message, confirm=confirm, auto_approve=False):
                    if turn_cancel.is_set():
                        await _emit(websocket, {"type": "status", "message": "stopped by user"})
                        break
                    if not await _emit(websocket, event):
                        turn_cancel.set()
                        break
        except asyncio.CancelledError:
            await _emit(websocket, {"type": "error", "error": "turn cancelled"})
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("WS turn failed")
            await _emit(websocket, {"type": "error", "error": str(exc)})
        finally:
            local_turn.reset(turn_context)
            turn_task = None

    try:
        while True:
            raw = await websocket.receive_text()
            if not identity.is_active():
                await websocket.close(code=4401, reason="session revoked")
                break
            try:
                if len(raw) > 20000:
                    raise ValueError("frame too large")
                frame = IncomingFrame.model_validate_json(raw).root
            except (ValueError, ValidationError):
                await _emit(websocket, {"type": "error", "error": "invalid frame"})
                continue
            message = frame.model_dump()
            kind = frame.type

            if kind == "ping":
                await _emit(websocket, {"type": "pong"})

            elif kind == "status":
                snapshot = await asyncio.to_thread(brain.snapshot)
                await _emit(websocket, {"type": "status_snapshot", **snapshot})

            elif kind == "tools":
                await _emit(websocket, {"type": "tools_list", "tools": brain.registry.get_tool_schemas()})

            elif kind == "approve":
                confirm_id = str(message.get("id", ""))
                future = pending_confirm.get(confirm_id)
                if future and not future.done():
                    future.set_result(message["approved"])
                else:
                    await _emit(websocket, {"type": "error", "error": "unknown or expired approval"})

            elif kind == "cancel":
                turn_cancel.set()
                if turn_task and not turn_task.done():
                    turn_task.cancel()

            elif kind == "chat":
                text = str(message.get("message", "")).strip()
                if not text:
                    await _emit(websocket, {"type": "error", "error": "empty message"})
                    continue
                if turn_task and not turn_task.done():
                    await _emit(websocket, {"type": "error", "error": "a turn is already running"})
                    continue
                turn_task = asyncio.create_task(run_turn(text))

            else:
                await _emit(websocket, {"type": "error", "error": f"unknown frame type {kind!r}"})

    except WebSocketDisconnect:
        logger.debug("WS client disconnected")
    finally:
        turn_cancel.set()
        for future in pending_confirm.values():
            if not future.done():
                future.set_result(False)
        pending_confirm.clear()
        if turn_task and not turn_task.done():
            turn_task.cancel()
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
        except Exception:  # pragma: no cover - defensive
            pass
