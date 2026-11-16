"""Laptop-local exact URL approval. No HTTP endpoint can make this decision."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

TTL_SECONDS=120


def validate_url(url):
    if not isinstance(url,str) or not 8<=len(url)<=2048 or any(ord(c)<=32 or ord(c)==127 for c in url) or '\\' in url:
        raise ValueError('Use an exact HTTPS URL without controls, whitespace or backslashes.')
    try:
        parsed=urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):raise ValueError()
        host=parsed.hostname.lower()
    except ValueError as exc:raise ValueError('Only credential-free HTTPS URLs on port443 are allowed.') from exc
    allowed={v.strip().lower() for v in os.getenv('JARVIS_ALLOWED_URL_HOSTS','').replace(',',';').split(';') if v.strip()}
    if host not in allowed:raise ValueError('Exact host is not in JARVIS_ALLOWED_URL_HOSTS. No subdomain wildcard or default allowlist.')
    return host


def token_digest():
    token=os.getenv('JARVIS_AGENT_TOKEN','')
    if len(token)<32:raise ValueError('Configure the local agent token first.')
    return hashlib.sha256(token.encode()).hexdigest()


class LocalApprovalStore:
    def __init__(self):
        self.path=Path(os.environ.get('JARVIS_AGENT_APPROVAL_DB',str(Path.home()/'.jarvis'/'companion-approvals.db')))
        if str(self.path).startswith(('\\\\','//')) or not self.path.is_absolute() or self.path.resolve()!=self.path or self.path.is_symlink():raise ValueError('Use a canonical absolute local approval database path.')
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd=os.open(self.path,os.O_CREAT|os.O_WRONLY,0o600);os.close(fd)
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS url_requests(id TEXT PRIMARY KEY,url TEXT NOT NULL,token_hash TEXT NOT NULL,expires REAL NOT NULL,state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS local_settings(key TEXT PRIMARY KEY,value INTEGER NOT NULL);''')

    def connect(self):return sqlite3.connect(self.path,timeout=5)

    @staticmethod
    def _active(db):
        row=db.execute('SELECT value FROM local_settings WHERE key=?',('stopped',)).fetchone()
        if row and row[0]:raise ValueError('Laptop-local companion stop is enabled.')

    def request(self,url):
        validate_url(url);digest=token_digest();key=uuid.uuid4().hex
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE');self._active(db)
            db.execute('DELETE FROM url_requests WHERE expires<=?',(time.time(),))
            if db.execute('SELECT count(*) FROM url_requests').fetchone()[0]>=100:raise ValueError('Local request limit reached. Wait for expiry or review requests locally.')
            db.execute('INSERT INTO url_requests VALUES(?,?,?,?,?)',(key,url,digest,time.time()+TTL_SECONDS,'pending'))
        return key

    def inspect(self,key):
        if not isinstance(key,str) or re.fullmatch('[0-9a-f]{32}',key) is None:raise ValueError('Invalid request ID.')
        with self.connect() as db:
            self._active(db)
            row=db.execute('SELECT url,token_hash,expires,state FROM url_requests WHERE id=?',(key,)).fetchone()
        if not row or row[2]<=time.time() or row[3]!='pending' or not hmac.compare_digest(row[1],token_digest()):raise ValueError('Request is missing, expired, already decided or from a different token.')
        validate_url(row[0]);return row[0]

    def decide_local(self,key,url,approved):
        # Internal local boundary. Never register this as an HTTP route.
        validate_url(url)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE');self._active(db)
            n=db.execute('UPDATE url_requests SET state=? WHERE id=? AND url=? AND token_hash=? AND state=? AND expires>?',('approved' if approved else 'rejected',key,url,token_digest(),'pending',time.time())).rowcount
            if n!=1:raise ValueError('Request expired, changed or was already decided.')

    def consume(self,key,url):
        validate_url(url)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE');self._active(db)
            n=db.execute('UPDATE url_requests SET state=? WHERE id=? AND url=? AND token_hash=? AND state=? AND expires>?',('consumed',key,url,token_digest(),'approved',time.time())).rowcount
            if n!=1:raise ValueError('Laptop-local approval missing, expired, replayed or target/token mismatched.')

    def set_stop(self,enabled):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO local_settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('stopped',int(enabled)))
            if enabled:db.execute("UPDATE url_requests SET state='revoked' WHERE state IN ('pending','approved')")


def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description='AETHER laptop-local companion URL approval')
    p.add_argument('action',choices=['review','stop','resume']);p.add_argument('request_id',nargs='?')
    args=p.parse_args(argv)
    if not sys.stdin.isatty() or not sys.stdout.isatty():p.error('Use an interactive terminal on the trusted laptop. Piped/caller booleans cannot approve requests.')
    store=LocalApprovalStore()
    if args.action=='stop':store.set_stop(True);print('Companion stopped; pending approvals revoked.');return
    if args.action=='resume':
        if input('Type RESUME to allow new local URL requests: ')=='RESUME':store.set_stop(False)
        return
    url=store.inspect(args.request_id)
    print('Exact URL:',url)
    print('This opens one browser tab on this laptop, may contact that site and use browser cookies. It does not approve downloads, commands or future tabs. Expires120seconds after request creation.')
    answer=input('Type OPEN to approve this exact URL once; anything else denies: ')
    store.decide_local(args.request_id,url,answer=='OPEN')
    print('Approved once.' if answer=='OPEN' else 'Denied.')


if __name__=='__main__':main()
