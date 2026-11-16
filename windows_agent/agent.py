"""Opt-in Windows helper: status and allow-listed URL opening only.

Run locally only. This agent intentionally exposes no shell/PowerShell endpoint.
"""
import hmac
import os
import platform
import webbrowser

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from windows_agent.local_approval import LocalApprovalStore, validate_url

app = FastAPI(title="AETHER Windows Companion Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


def authorize(authorization: str | None = Header(default=None)):
    expected = os.getenv("JARVIS_AGENT_TOKEN", "")
    if len(expected) < 32:
        raise HTTPException(status_code=503, detail="Configure JARVIS_AGENT_TOKEN (32+ characters).")
    supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid agent token.")


class OpenUrlRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    model_config = ConfigDict(extra="forbid")


class ApprovedOpenUrlRequest(OpenUrlRequest):
    request_id: str = Field(pattern="^[0-9a-f]{32}$")


@app.get("/health")
def health():
    return {"status": "ok", "agent": "jarvis-windows"}


@app.get("/v1/status")
def status(_=__import__("fastapi").Depends(authorize)):
    return {"platform": platform.platform(), "python": platform.python_version(), "actions": ["request-url", "open-locally-approved-url"], "local_approval_required": True}


@app.post("/v1/request-url")
def request_url(request: OpenUrlRequest, _=__import__("fastapi").Depends(authorize)):
    try:
        key=LocalApprovalStore().request(request.url)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"request_id":key,"state":"pending-local-review","expires_in_seconds":120,"opened":False}


@app.post("/v1/open-url")
def open_url(request: ApprovedOpenUrlRequest, _=__import__("fastapi").Depends(authorize)):
    try:
        host=validate_url(request.url)
        LocalApprovalStore().consume(request.request_id,request.url)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    # Approval is consumed before OS invocation. Failure needs a new request/review.
    opened = webbrowser.open(request.url, new=2)
    if not opened:
        raise HTTPException(status_code=502, detail="The operating system could not open the URL; approval was consumed.")
    return {"opened": True, "host": host,"browser_request_accepted":True,"page_loaded_verified":False}

# This is a separate per-device read-only request/result protocol. No HTTP decision endpoint.
from windows_agent.remote_read_api import router as remote_read_router
app.include_router(remote_read_router)
