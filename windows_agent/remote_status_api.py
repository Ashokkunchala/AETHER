"""Authenticated remote status request/status only. No remote approval/execution route."""

from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict

from windows_agent.remote_status import RemoteStatusStore

router = APIRouter(prefix="/v1/remote-status")


class StatusRequest(BaseModel):
    action: Literal["system_snapshot"]
    model_config = ConfigDict(extra="forbid")


def _token(authorization):
    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        raise ValueError("Dedicated device authentication required.")
    return authorization[7:]


@router.post("/requests", status_code=201)
def request_status(body: StatusRequest, authorization: str | None = Header(default=None)):
    try:
        return RemoteStatusStore().request_status(_token(authorization), body.action)
    except (ValueError, OSError):
        raise HTTPException(
            409, "Device authentication, local stop, scope or request capacity refused."
        ) from None


@router.get("/requests/{request_id}")
def read_result(request_id: str, authorization: str | None = Header(default=None)):
    try:
        return RemoteStatusStore().read_result(_token(authorization), request_id)
    except (ValueError, OSError):
        raise HTTPException(
            409, "Device authentication, local stop or request scope refused."
        ) from None


class CancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


@router.post("/requests/{request_id}/cancel")
def cancel_request(
    request_id: str, body: CancelRequest, authorization: str | None = Header(default=None)
):
    try:
        return RemoteStatusStore().cancel_request(_token(authorization), request_id)
    except (ValueError, OSError):
        raise HTTPException(409, "Device authentication or cancellation scope refused.") from None
