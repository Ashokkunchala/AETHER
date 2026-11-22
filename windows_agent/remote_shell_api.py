"""Authenticated remote command request/status only. No remote approval/execution route."""

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from windows_agent.remote_shell import RemoteShellStore

router = APIRouter(prefix="/v1/remote-shell")


class CommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=300)
    model_config = ConfigDict(extra="forbid")


def _token(authorization):
    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        raise ValueError("Dedicated device authentication required.")
    return authorization[7:]


@router.post("/requests", status_code=201)
def request_command(body: CommandRequest, authorization: str | None = Header(default=None)):
    try:
        return RemoteShellStore().request_command(_token(authorization), body.command)
    except (ValueError, OSError):
        raise HTTPException(
            409, "Device authentication, local stop, blocked policy, scope or capacity refused."
        ) from None


@router.get("/requests/{request_id}")
def read_result(request_id: str, authorization: str | None = Header(default=None)):
    try:
        return RemoteShellStore().read_result(_token(authorization), request_id)
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
        return RemoteShellStore().cancel_request(_token(authorization), request_id)
    except (ValueError, OSError):
        raise HTTPException(409, "Device authentication or cancellation scope refused.") from None
