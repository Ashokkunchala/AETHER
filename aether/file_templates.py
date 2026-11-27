"""Template-backed file creation ("create a Dockerfile for my app").

``create_file`` writes one local text file either from explicit supplied
content or from a small set of deterministic, locally rendered starter
templates (Dockerfile, .gitignore, compose, CI). Templates are fixed strings
rendered without network, model or environment access, so the bytes are
reviewable before anything is written.

Safety posture matches the existing file tools: MEDIUM risk, fresh
confirmation with an exact preview (action, path, bytes, content head),
never inside protected system locations, and an existing file is never
overwritten unless ``overwrite=true`` is passed explicitly. The preview is a
snapshot and can go stale; the write re-checks existence at apply time.

Honest limits: templates are starting points, not tuned production configs;
the tool writes text only (no chmod, no format/lint validation, no VCS).
"""
from __future__ import annotations

from typing import Any, Callable

from aether.control import files as _files

_MAX_CONTENT_CHARS = 64000
_PREVIEW_HEAD_CHARS = 400

_DOCKERFILE_PYTHON = """# Starter Dockerfile for a Python application. Review base image, port and entry point before use.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python", "app.py"]
"""

_DOCKERFILE_NODE = """# Starter Dockerfile for a Node.js application. Review base image, port and start script before use.
FROM node:20-slim

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev

COPY . .

EXPOSE 3000
CMD ["node", "server.js"]
"""

_DOCKER_COMPOSE = """# Starter compose file with one application service built from the local Dockerfile.
services:
  app:
    build: .
    ports:
      - "8000:8000"
    restart: unless-stopped
"""

_GITIGNORE_PYTHON = """# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.env
.pytest_cache/
.coverage
dist/
build/
"""

_GITIGNORE_NODE = """# Node
node_modules/
npm-debug.log*
.env
dist/
coverage/
"""

_GITHUB_ACTIONS_PYTHON = """# Starter Python CI: install dependencies and run pytest on every push and pull request.
name: Tests

on:
  push:
  pull_request:

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python -m pip install -r requirements-dev.txt
      - run: python -m pytest -q
"""

_TEMPLATES: dict[str, tuple[str, str]] = {
    # kind: (description, content)
    'dockerfile-python': ('Starter Dockerfile for a Python app (python:3.11-slim, port 8000, app.py entry).', _DOCKERFILE_PYTHON),
    'dockerfile-node': ('Starter Dockerfile for a Node.js app (node:20-slim, port 3000, server.js entry).', _DOCKERFILE_NODE),
    'docker-compose': ('Starter compose file with one app service built from the local Dockerfile.', _DOCKER_COMPOSE),
    'gitignore-python': ('Standard Python .gitignore (venv, caches, .env, build output).', _GITIGNORE_PYTHON),
    'gitignore-node': ('Standard Node .gitignore (node_modules, logs, .env, build output).', _GITIGNORE_NODE),
    'github-actions-python': ('Starter GitHub Actions Python CI (pip install + pytest on push/PR).', _GITHUB_ACTIONS_PYTHON),
}

_CONTENT_HEAD = 400


def _err(message: str) -> dict[str, Any]:
    return {'success': False, 'error': message}


def list_templates() -> dict[str, Any]:
    """List the available deterministic starter templates."""
    return {
        'success': True,
        'templates': [
            {'kind': kind, 'description': description}
            for kind, (description, _content) in sorted(_TEMPLATES.items())
        ],
        'note': 'Templates are fixed local starter text, rendered without network or model access. Review and edit after creation; they are not tuned production configs.',
    }


def _resolve_content(kind: str | None, content: str | None) -> tuple[str | None, str | None, str | None]:
    """Return (text, source_label, error). Exactly one of kind/content applies."""
    if kind and content is not None:
        return None, None, 'Pass exactly one of kind (a template) or content (explicit text), not both.'
    if kind:
        entry = _TEMPLATES.get(kind)
        if entry is None:
            known = ', '.join(sorted(_TEMPLATES))
            return None, None, f'Unknown template kind: {kind!r}. Available: {known}.'
        return entry[1], f'template:{kind}', None
    if content is None:
        return None, None, 'Pass exactly one of kind (a template) or content (explicit text).'
    if not isinstance(content, str) or not 1 <= len(content) <= _MAX_CONTENT_CHARS:
        return None, None, f'Explicit content must be text of 1-{_MAX_CONTENT_CHARS} characters.'
    return content, 'explicit content', None


def preview_create_file(path: str, kind: str | None = None, content: str | None = None, overwrite: bool = False) -> dict[str, Any]:
    """Exact preview of what ``create_file`` would write. A snapshot, re-checked at apply time."""
    text, source, error = _resolve_content(kind, content)
    if error:
        return _err(error)
    target = _files.resolve(path)
    if _files._protected(target):
        return _err('Refusing to write into a protected system location')
    exists = target.exists()
    if exists and not target.is_file():
        return _err(f'Not a file: {target}')
    if exists and not overwrite:
        return _err(f'File already exists: {target} (set overwrite=true to replace it)')
    return {
        'success': True,
        'action': 'overwrite' if exists else 'create',
        'path': str(target),
        'source': source,
        'existing_bytes': target.stat().st_size if exists else 0,
        'incoming_bytes': len(text.encode('utf-8')),
        'content_head': text[:_CONTENT_HEAD],
        'truncated_in_preview': len(text) > _CONTENT_HEAD,
        'overwrite_requested': overwrite,
        'warning': 'This preview is a snapshot; existence and size are re-checked when the approved write is applied.',
    }


def create_file(
    path: str,
    kind: str | None = None,
    content: str | None = None,
    overwrite: bool = False,
    writer: Callable[..., dict] | None = None,
) -> dict[str, Any]:
    """Write one local text file from a template or explicit content.

    Never overwrites an existing file unless ``overwrite`` is true; existence
    is re-checked here at apply time, not only in the preview.
    """
    preview = preview_create_file(path, kind=kind, content=content, overwrite=overwrite)
    if not preview.get('success'):
        return preview
    text, source, _error = _resolve_content(kind, content)
    write = writer or _files.write_text
    result = write(preview['path'], text, False)
    if not result.get('success'):
        return result
    return {
        'success': True,
        'action': preview['action'],
        'path': result['path'],
        'bytes': result['bytes'],
        'source': source,
        'note': 'Text file written. Content is starter text: review and edit before relying on it; no format validation, linting or VCS step was performed.',
    }


def register_file_creation(registry) -> None:
    from aether.tools.registry import Risk, Tool
    registry.register(Tool(
        name='list_file_templates',
        description='List the deterministic local starter file templates (Dockerfile, .gitignore, compose, CI) that create_file can render without network or model access.',
        parameters={'type': 'object', 'properties': {}, 'additionalProperties': False},
        handler=list_templates,
        risk=Risk.SAFE, category='files',
    ))
    registry.register(Tool(
        name='create_file',
        description="Create one local text file from a starter template (see list_file_templates, e.g. kind='dockerfile-python' for a Dockerfile) or from explicit supplied content. Fresh confirmation with an exact content preview; never overwrites an existing file unless overwrite=true. Starter text only: review and edit after creation.",
        parameters={'type': 'object', 'properties': {
            'path': {'type': 'string', 'description': 'Target file path.'},
            'kind': {'type': 'string', 'description': 'Template kind from list_file_templates. Mutually exclusive with content.'},
            'content': {'type': 'string', 'description': 'Explicit file text (1-64000 chars). Mutually exclusive with kind.'},
            'overwrite': {'type': 'boolean', 'description': 'Replace an existing file. Default false: existing files are refused.'},
        }, 'required': ['path'], 'additionalProperties': False},
        handler=create_file,
        confirmation_preview=preview_create_file,
        risk=Risk.MEDIUM, category='files', requires_confirmation=True,
        allow_always=False, allow_auto_approve=False,
    ))
