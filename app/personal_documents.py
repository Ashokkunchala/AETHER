"""Private local document previews and user-reviewed downloads, not file control."""
from __future__ import annotations

import io
import os
import stat
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.personal_data import require_device_token
from jarvis.memory.doc_memory import SECRET_CONTENT_MARKERS, SKIP_DIRS, _looks_secret

router = APIRouter(prefix='/api/documents', tags=['AETHER documents'], dependencies=[Depends(require_device_token)])
SUFFIXES = {'.txt', '.md', '.log', '.pdf', '.docx'}
MAX_BYTES = 10_000_000
MAX_TEXT = 60000


def _roots():
    from app.integrations import settings
    roots = []
    for value in settings.document_allowed_roots.split(';'):
        if not value.strip():
            continue
        path = Path(value.strip()).expanduser()
        if not path.is_absolute():
            raise HTTPException(503, 'DOCUMENT_ALLOWED_ROOTS must contain absolute folder paths.')
        roots.append(path.resolve())
    if not roots:
        raise HTTPException(503, 'Set DOCUMENT_ALLOWED_ROOTS to explicit authorized folders first.')
    return roots


def _allowed(path, roots):
    if path.suffix.lower() not in SUFFIXES or _looks_secret(path):
        return False
    for root in roots:
        if path.is_relative_to(root) and not any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            return True
    return False


@router.get('/library')
def document_library():
    roots = _roots()
    items = []
    scanned = 0
    for root in roots:
        if not root.is_dir():
            continue
        for folder, directories, files in os.walk(root, followlinks=False):
            scanned += 1
            if scanned > 10000:
                break
            directories[:] = sorted(d for d in directories if d not in SKIP_DIRS and not Path(folder, d).is_symlink())
            for name in sorted(files):
                scanned += 1
                if scanned > 10000 or len(items) >= 500:
                    break
                path = Path(folder, name)
                try:
                    resolved = path.resolve()
                    if path.is_symlink() or not _allowed(resolved, roots):
                        continue
                    info = resolved.stat()
                    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
                        continue
                    items.append({'path': str(resolved), 'name': name, 'bytes': info.st_size,
                                  'modified_at': datetime.fromtimestamp(info.st_mtime, UTC).isoformat()})
                except OSError:
                    continue
            if scanned > 10000 or len(items) >= 500:
                break
        if scanned > 10000 or len(items) >= 500:
            break
    items.sort(key=lambda row: (row['modified_at'], row['path']), reverse=True)
    return {'items': items, 'partial': scanned > 10000 or len(items) >= 500,
            'notice': 'At most 500 supported files from a bounded scan, ordered by filesystem modification time, not document version or resume correctness. Secret-shaped files, symlinks and noisy folders are skipped. Source files are never changed.'}


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    path: str = Field(min_length=1, max_length=2000)


@router.post('/preview')
def preview_document(item: PreviewRequest):
    roots = _roots()
    path = Path(item.path).expanduser()
    if not path.is_absolute():
        raise HTTPException(422, 'Choose an absolute path from the authorized library.')
    resolved = path.resolve()
    if not _allowed(resolved, roots) or path.is_symlink():
        raise HTTPException(403, 'File is outside authorized roots or excluded by document safety rules.')
    try:
        # Refuse a last-component symlink; check the opened file is regular and
        # bounded before reading. This is a private local app, not an OS sandbox.
        fd = os.open(resolved, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        with os.fdopen(fd, 'rb') as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
                raise HTTPException(413, 'Choose a regular file no larger than 10 MB.')
            data = source.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, 'File grew beyond the 10 MB preview limit.')
        suffix = resolved.suffix.lower()
        partial = False
        if suffix == '.pdf':
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            partial = len(reader.pages) > 80
            text = '\n'.join((page.extract_text() or '') for page in reader.pages[:80])
        elif suffix == '.docx':
            # Bound decompression before handing the archive to python-docx.
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if sum(part.file_size for part in archive.infolist()) > 40_000_000:
                    raise HTTPException(413, 'DOCX expands beyond the preview limit.')
            from docx import Document
            document = Document(io.BytesIO(data))
            text = '\n'.join([p.text for p in document.paragraphs] + [cell.text for table in document.tables for row in table.rows for cell in row.cells])
        else:
            text = data.decode('utf-8', errors='replace')
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, 'This document could not be read. It may be encrypted, corrupt, missing or unsupported.') from None
    if any(marker in text for marker in SECRET_CONTENT_MARKERS):
        raise HTTPException(403, 'Private-key-shaped document content is excluded.')
    return {'path': str(resolved), 'text': text[:MAX_TEXT], 'partial': partial or len(text) > MAX_TEXT,
            'characters_extracted': len(text), 'saved': False,
            'notice': 'Text preview only, not a semantic summary or verified resume version. At most 80 PDF pages and 60000 characters. Images, scanned text without OCR, comments, headers and embedded objects may be missing. No AI provider used and no source file changed.'}


class DocumentDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=50000)
    filename: str = Field(default='aether-document', pattern=r'^[A-Za-z0-9_-]{1,80}$')
    format: Literal['txt', 'md', 'docx'] = 'docx'

    @field_validator('title', 'body')
    @classmethod
    def valid_text(cls, value):
        if not value.strip() or any((ord(char) < 32 and char not in '\t\r\n') or 0xD800 <= ord(char) <= 0xDFFF or ord(char) in (0xFFFE, 0xFFFF) for char in value):
            raise ValueError('Use nonblank text without unsupported control characters.')
        return value


@router.post('/download')
def create_document_download(item: DocumentDraft):
    if item.format == 'docx':
        from docx import Document
        from docx.shared import Inches, Pt
        document = Document()
        section = document.sections[0]
        section.top_margin = section.bottom_margin = Inches(.8)
        section.left_margin = section.right_margin = Inches(.85)
        document.styles['Normal'].font.name = 'Calibri'
        document.styles['Normal'].font.size = Pt(11)
        document.add_heading(item.title, 0)
        for paragraph in item.body.split('\n'):
            document.add_paragraph(paragraph)
        output = io.BytesIO()
        document.save(output)
        content = output.getvalue()
        media = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    else:
        prefix = '# ' if item.format == 'md' else ''
        content = (prefix + item.title + '\n\n' + item.body).encode('utf-8')
        media = 'text/markdown' if item.format == 'md' else 'text/plain'
    return Response(content, media_type=media, headers={'Cache-Control': 'no-store',
                    'Content-Disposition': f'attachment; filename="{item.filename}.{item.format}"'})
