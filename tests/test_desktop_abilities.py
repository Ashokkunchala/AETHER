from __future__ import annotations

import base64
import json
import time

import pytest

from aether import desktop_abilities as da
from aether.core.agent.voice_tools import _HANDLERS, TOOL_DECLARATIONS, build_tool_executor


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("AETHER_APPROVED_APPS_FILE", str(tmp_path / ".aether" / "approved_apps.json"))
    monkeypatch.setenv("AETHER_HOME", str(tmp_path / ".aether"))
    monkeypatch.setattr(da.Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


def test_tools_declared_and_handled():
    assert {t["name"] for t in TOOL_DECLARATIONS} == set(_HANDLERS)
    for name in ("play_youtube", "create_file", "list_emails", "read_email"):
        assert name in _HANDLERS


def test_open_app_needs_setup_then_works(home, monkeypatch):
    out = da.open_approved_app("chrome")
    assert out["success"] is False and out["needs_setup"] and "aether setup-apps" in out["error"]
    exe = home / "Prog" / "Google" / "Chrome" / "Application" / "chrome.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"MZ-fake")
    monkeypatch.setenv("ProgramFiles", str(home / "Prog"))
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("SystemRoot", raising=False)
    asked = []
    result = da.setup_apps(lambda app, info: asked.append(app) or True)
    assert result["newly_approved"] == ["chrome"] and asked == ["chrome"]
    launched = []

    class P:
        pid = 42

    monkeypatch.setattr("subprocess.Popen", lambda cmd, **kw: launched.append(cmd) or P())
    out = da.open_approved_app("Google Chrome")
    assert out["success"] and launched == [[str(exe.resolve())]]
    # the voice tool path uses the same flow
    assert build_tool_executor(None)("open_app", {"name": "chrome"})["success"]
    # declined apps are not approved
    assert da.open_approved_app("edge")["success"] is False
    # content change is refused
    exe.write_bytes(b"MZ-tampered")
    assert da.open_approved_app("chrome")["success"] is False


def test_setup_decline_writes_nothing(home, monkeypatch):
    exe = home / "Prog" / "Mozilla Firefox" / "firefox.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"x")
    monkeypatch.setenv("ProgramFiles", str(home / "Prog"))
    monkeypatch.delenv("SystemRoot", raising=False)
    result = da.setup_apps(lambda a, i: False)
    assert result["newly_approved"] == [] and result["approved"] == []


def test_youtube_opens_video_or_search():
    opened = []
    html = 'x"videoRenderer":{"videoId":"abcdefghijk","y"'
    out = da.play_on_youtube("new song", opener=lambda u: opened.append(u) or True, fetch=lambda u: html)
    assert out["success"] and opened == ["https://www.youtube.com/watch?v=abcdefghijk"]
    out = da.play_on_youtube("a b&c", opener=lambda u: opened.append(u) or True, fetch=lambda u: "nothing")
    assert opened[-1] == "https://www.youtube.com/results?search_query=a+b%26c"
    assert da.play_on_youtube("  ")["success"] is False


def test_create_file_preview_confirm_no_overwrite(home):
    pre = da.create_new_file("Documents", "Dockerfile", "FROM alpine\n")
    assert pre["needs_confirmation"] and not (home / "Documents" / "Dockerfile").exists()
    tok = pre["confirmation_token"]
    # changed content invalidates the token
    assert da.create_new_file("Documents", "Dockerfile", "FROM evil\n", tok)["success"] is False
    pre = da.create_new_file("Documents", "Dockerfile", "FROM alpine\n")
    done = da.create_new_file("Documents", "Dockerfile", "FROM alpine\n", pre["confirmation_token"])
    assert done["success"] and (home / "Documents" / "Dockerfile").read_text() == "FROM alpine\n"
    again = da.create_new_file("Documents", "Dockerfile", "FROM other\n")
    assert again["success"] is False and "already exists" in again["error"]
    assert (home / "Documents" / "Dockerfile").read_text() == "FROM alpine\n"


@pytest.mark.parametrize("folder,name", [
    ("/etc", "x.txt"), ("Documents", "../x.txt"), ("Documents", "run.ps1"), ("Documents", "a.exe"),
    (".ssh", "config"), ("AppData/Roaming", "x.txt"), ("//server/share", "x.txt"), ("", "x.txt"),
])
def test_create_file_refusals(folder, name):
    assert da.create_new_file(folder, name, "hi")["success"] is False


def test_create_file_token_expires(home, monkeypatch):
    pre = da.create_new_file("Desktop", "n.txt", "hi")
    real = time.monotonic()
    monkeypatch.setattr(da.time, "monotonic", lambda: real + 1000)
    assert da.create_new_file("Desktop", "n.txt", "hi", pre["confirmation_token"])["success"] is False
    assert not (home / "Desktop" / "n.txt").exists()


def test_gmail_not_signed_in():
    out = da.list_recent_emails()
    assert out["success"] is False and "gmail-signin" in out["error"]
    assert da.read_email("abc")["success"] is False


def _signed_in(home):
    da.token_path().parent.mkdir(parents=True, exist_ok=True)
    da.token_path().write_text(json.dumps({"refresh_token": "r", "access_token": "a", "expires_at": time.time() + 1000}))


def test_gmail_list_and_read(home):
    _signed_in(home)
    seen = []

    def get(url, token):
        seen.append(url)
        assert token == "a" and "gmail.googleapis.com" in url
        if url.split("?")[0].endswith("/messages"):
            return {"messages": [{"id": "m1abcdef"}]}
        if "format=full" in url:
            body = base64.urlsafe_b64encode(b"hello body").decode().rstrip("=")
            return {"payload": {"mimeType": "multipart/alternative", "headers": [
                {"name": "Subject", "value": "Hi"}], "parts": [{"mimeType": "text/plain", "body": {"data": body}}]}}
        return {"snippet": "snip &amp; more", "payload": {"headers": [
            {"name": "From", "value": "a@b.c"}, {"name": "Subject", "value": "Hi"}]}}

    out = da.list_recent_emails(3, "is:unread", get=get)
    assert out["emails"][0]["subject"] == "Hi" and out["emails"][0]["snippet"] == "snip & more"
    assert da.read_email("m1abcdef", get=get)["body"] == "hello body"
    assert da.read_email("../x")["success"] is False
    assert all("send" not in u and "modify" not in u for u in seen)


def test_gmail_sign_in_flow(home):
    da.client_secret_path().parent.mkdir(parents=True, exist_ok=True)
    da.client_secret_path().write_text(json.dumps({"installed": {"client_id": "cid", "client_secret": "sec"}}))
    import urllib.parse
    import urllib.request

    def opener(url):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        assert q["scope"] == [da.GMAIL_SCOPE] and q["code_challenge_method"] == ["S256"]
        redirect = q["redirect_uri"][0]
        urllib.request.urlopen(f"{redirect}/?code=abc&state={q['state'][0]}", timeout=5).read()
        return True

    def post(url, data):
        assert data["code"] == "abc" and data["code_verifier"]
        return {"refresh_token": "rt", "access_token": "at", "expires_in": 3600, "scope": da.GMAIL_SCOPE}

    out = da.gmail_sign_in(post=post, opener=opener, timeout=10)
    assert out["success"], out
    assert json.loads(da.token_path().read_text())["scope"] == da.GMAIL_SCOPE
    assert da.gmail_sign_out()["success"] and not da.token_path().exists()


def test_gmail_sign_in_rejects_wrong_state_and_broad_scope(home):
    da.client_secret_path().parent.mkdir(parents=True, exist_ok=True)
    da.client_secret_path().write_text(json.dumps({"installed": {"client_id": "cid", "client_secret": "sec"}}))
    import urllib.parse
    import urllib.request

    def opener(url):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        urllib.request.urlopen(f"{q['redirect_uri'][0]}/?code=abc&state=wrong", timeout=5).read()
        return True

    # wrong state: the handler records an error, the loop keeps waiting until timeout
    out = da.gmail_sign_in(post=lambda *a: {}, opener=opener, timeout=2)
    assert out["success"] is False and not da.token_path().exists()

    def opener2(url):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        urllib.request.urlopen(f"{q['redirect_uri'][0]}/?code=abc&state={q['state'][0]}", timeout=5).read()
        return True

    broad = {"refresh_token": "r", "scope": da.GMAIL_SCOPE + " https://mail.google.com/"}
    out = da.gmail_sign_in(post=lambda *a: broad, opener=opener2, timeout=5)
    assert out["success"] is False and not da.token_path().exists()
