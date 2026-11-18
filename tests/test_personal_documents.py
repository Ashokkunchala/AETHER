"""Local document boundaries and content-preserving reviewed downloads."""
import io
import zipfile

import pytest
from docx import Document
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app import integrations, personal_documents

TOKEN = 'aether-documents-test-token-at-least-32-characters'
AUTH = {'Authorization': 'Bearer ' + TOKEN}


@pytest.fixture
def environment(monkeypatch, tmp_path):
    root = tmp_path / 'authorized'
    root.mkdir()
    monkeypatch.setenv('AETHER_API_TOKEN', TOKEN)
    monkeypatch.setattr(integrations.settings, 'document_allowed_roots', str(root))
    app = FastAPI()
    app.include_router(personal_documents.router)
    with TestClient(app) as client:
        yield client, root


def preview(client, path):
    return client.post('/api/documents/preview', headers=AUTH, json={'path': str(path)})


def test_auth_roots_and_excluded_paths(environment, monkeypatch):
    client, root = environment
    (root / 'notes.txt').write_text('Allowed text')
    assert client.get('/api/documents/library').status_code == 401
    outside = root.parent / 'outside.txt'
    outside.write_text('Not authorized')
    assert preview(client, outside).status_code == 403
    assert preview(client, root / '..' / 'outside.txt').status_code == 403
    assert preview(client, 'relative.txt').status_code == 422
    monkeypatch.setattr(integrations.settings, 'document_allowed_roots', '')
    assert client.get('/api/documents/library', headers=AUTH).status_code == 503
    monkeypatch.setattr(integrations.settings, 'document_allowed_roots', 'relative-folder')
    assert client.get('/api/documents/library', headers=AUTH).status_code == 503


def test_library_skips_secret_names_symlinks_and_noisy_folders(environment):
    client, root = environment
    (root / 'notes.txt').write_text('Allowed text')
    (root / 'credentials.txt').write_text('Excluded filename')
    (root / 'node_modules').mkdir()
    (root / 'node_modules' / 'noise.md').write_text('Not indexed')
    outside = root.parent / 'outside.txt'
    outside.write_text('Outside')
    (root / 'alias.txt').symlink_to(outside)
    data = client.get('/api/documents/library', headers=AUTH).json()
    assert [r['name'] for r in data['items']] == ['notes.txt']
    assert preview(client, root / 'credentials.txt').status_code == 403
    assert preview(client, root / 'alias.txt').status_code == 403
    assert preview(client, root / 'node_modules' / 'noise.md').status_code == 403


def test_preview_exact_text_partial_notice_and_no_source_changes(environment):
    client, root = environment
    path = root / 'notes.md'
    text = '<script>untrusted text</script>\n' + ('A' * 60001)
    path.write_text(text)
    response = preview(client, path)
    assert response.status_code == 200
    data = response.json()
    assert data['text'] == text[:60000]
    assert data['partial'] is True and data['saved'] is False
    assert path.read_text() == text


def test_private_key_shaped_content_rejected(environment):
    client, root = environment
    path = root / 'ordinary.txt'
    path.write_text('Synthetic marker only: -----BEGIN OPENSSH PRIVATE KEY-----')
    assert preview(client, path).status_code == 403


def test_pdf_and_docx_paragraph_and_table_preview(environment):
    client, root = environment
    path = root / 'draft.docx'
    doc = Document()
    doc.add_paragraph('Paragraph text')
    doc.add_table(1,1).cell(0,0).text = 'Table text'
    doc.save(path)
    assert 'Paragraph text\nTable text' == preview(client, path).json()['text']
    pdf = PdfWriter()
    pdf.add_blank_page(width=300, height=300)
    path = root / 'blank.pdf'
    pdf.write(path)
    assert preview(client, path).status_code == 200
    assert 'without OCR' in preview(client, path).json()['notice']


def test_corrupt_archive_or_oversize_decompression_fails_closed(environment):
    client, root = environment
    path = root / 'bad.docx'
    path.write_bytes(b'not a docx')
    assert preview(client, path).status_code == 422
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('large.txt', b'x' * 40000001)
    assert preview(client, path).status_code == 413


@pytest.mark.parametrize('format', ['txt','md','docx'])
def test_reviewed_download_preserves_content_and_never_saves_server_file(environment, format):
    client, root = environment
    body = 'Exact user-reviewed text.\nSecond paragraph, no invented claims.'
    response = client.post('/api/documents/download', headers=AUTH,
                           json={'title':'Test document', 'body':body, 'filename':'reviewed-draft', 'format':format})
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert 'reviewed-draft.' + format in response.headers['content-disposition']
    if format == 'docx':
        doc = Document(io.BytesIO(response.content))
        assert [p.text for p in doc.paragraphs] == ['Test document'] + body.split('\n')
    else:
        assert body in response.text
    assert list(root.iterdir()) == []


@pytest.mark.parametrize('changes', [{'filename':'../../bad'}, {'body':'\x01'}, {'title':' '}, {'format':'exe'}])
def test_bad_download_fields_rejected(environment, changes):
    client, _ = environment
    payload = {'title':'Test', 'body':'Reviewed text', **changes}
    assert client.post('/api/documents/download', headers=AUTH, json=payload).status_code == 422
