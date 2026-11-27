"""Tests for template-backed file creation.

No filesystem mutation outside pytest tmp_path: writes go to temporary
directories or an injected writer.
"""

from __future__ import annotations

import pytest

from aether.file_templates import (
    _TEMPLATES,
    create_file,
    list_templates,
    preview_create_file,
    register_file_creation,
)


class TestListTemplates:
    def test_lists_every_template_with_description(self):
        result = list_templates()
        assert result['success'] is True
        kinds = {t['kind'] for t in result['templates']}
        assert kinds == set(_TEMPLATES)
        assert all(t['description'] for t in result['templates'])
        assert 'starter' in result['note'].lower()


class TestPreview:
    def test_create_preview_shows_exact_change(self, tmp_path):
        target = tmp_path / 'Dockerfile'
        preview = preview_create_file(str(target), kind='dockerfile-python')
        assert preview['success'] is True
        assert preview['action'] == 'create'
        assert preview['source'] == 'template:dockerfile-python'
        assert preview['incoming_bytes'] > 0
        assert preview['content_head'].startswith('# Starter Dockerfile')

    def test_existing_file_requires_overwrite_flag(self, tmp_path):
        target = tmp_path / 'Dockerfile'
        target.write_text('FROM scratch\n')
        preview = preview_create_file(str(target), kind='dockerfile-python')
        assert preview['success'] is False
        assert 'overwrite=true' in preview['error']

    def test_overwrite_preview_marks_action(self, tmp_path):
        target = tmp_path / 'x.txt'
        target.write_text('old')
        preview = preview_create_file(str(target), content='new text', overwrite=True)
        assert preview['success'] is True
        assert preview['action'] == 'overwrite'
        assert preview['existing_bytes'] == 3

    def test_refuses_directory_target(self, tmp_path):
        preview = preview_create_file(str(tmp_path), content='x')
        assert preview['success'] is False
        assert 'Not a file' in preview['error']

    def test_kind_and_content_are_mutually_exclusive(self, tmp_path):
        preview = preview_create_file(str(tmp_path / 'f'), kind='gitignore-python', content='x')
        assert preview['success'] is False
        assert 'exactly one' in preview['error']

    def test_neither_kind_nor_content(self, tmp_path):
        preview = preview_create_file(str(tmp_path / 'f'))
        assert preview['success'] is False
        assert 'exactly one' in preview['error']

    def test_unknown_kind_lists_available(self, tmp_path):
        preview = preview_create_file(str(tmp_path / 'f'), kind='dockerfile-cobol')
        assert preview['success'] is False
        assert 'dockerfile-python' in preview['error']

    @pytest.mark.parametrize('bad', ['', 'x' * 64001])
    def test_content_bounds(self, tmp_path, bad):
        preview = preview_create_file(str(tmp_path / 'f'), content=bad)
        assert preview['success'] is False

    def test_protected_location_refused(self, tmp_path, monkeypatch):
        from aether.control import files as file_control
        guarded = tmp_path / 'guarded'
        guarded.mkdir()
        monkeypatch.setattr(file_control, 'PROTECTED_PREFIXES', [str(guarded)])
        preview = preview_create_file(str(guarded / 'evil.txt'), content='x')
        assert preview['success'] is False
        assert 'protected' in preview['error'].lower()


class TestCreateFile:
    def test_template_file_written_to_disk(self, tmp_path):
        target = tmp_path / 'Dockerfile'
        result = create_file(str(target), kind='dockerfile-python')
        assert result['success'] is True
        written = target.read_text()
        assert written == _TEMPLATES['dockerfile-python'][1]
        assert result['action'] == 'create'
        assert 'starter' in result['note'].lower()

    def test_explicit_content_written_verbatim(self, tmp_path):
        target = tmp_path / 'notes.txt'
        result = create_file(str(target), content='line one\nline two\n')
        assert result['success'] is True
        assert target.read_text() == 'line one\nline two\n'
        assert result['source'] == 'explicit content'

    def test_existing_file_never_overwritten_without_flag(self, tmp_path):
        target = tmp_path / 'Dockerfile'
        target.write_text('ORIGINAL')
        result = create_file(str(target), kind='dockerfile-python')
        assert result['success'] is False
        assert target.read_text() == 'ORIGINAL'

    def test_overwrite_flag_replaces(self, tmp_path):
        target = tmp_path / 'x.txt'
        target.write_text('old')
        result = create_file(str(target), content='new', overwrite=True)
        assert result['success'] is True
        assert result['action'] == 'overwrite'
        assert target.read_text() == 'new'

    def test_writer_failure_is_reported(self, tmp_path):
        def boom(path, content, append):
            return {'success': False, 'error': 'disk full'}
        result = create_file(str(tmp_path / 'f'), content='x', writer=boom)
        assert result['success'] is False
        assert 'disk full' in result['error']

    def test_every_template_renders_nonempty(self, tmp_path):
        for index, kind in enumerate(sorted(_TEMPLATES)):
            target = tmp_path / f'f{index}'
            result = create_file(str(target), kind=kind)
            assert result['success'] is True, kind
            assert target.stat().st_size > 0


class TestRegistryIntegration:
    def test_tools_registered_with_confirmation_and_preview(self):
        from aether.tools.builtin_tools import build_registry, reset_controllers
        from aether.tools.registry import Risk
        reset_controllers()
        registry = build_registry(force=True)
        create = registry.get('create_file')
        listing = registry.get('list_file_templates')
        assert listing is not None and listing.risk == Risk.SAFE
        assert create is not None and create.risk == Risk.MEDIUM
        assert create.requires_confirmation is True
        assert create.confirmation_preview is not None
        assert create.allow_auto_approve is False
        assert create.allow_always is False

    def test_confirmed_execute_writes_file(self, tmp_path):
        import asyncio
        from aether.tools.builtin_tools import build_registry, reset_controllers
        reset_controllers()
        registry = build_registry(force=True)

        async def approve(*args, **kwargs):
            return True

        target = tmp_path / '.gitignore'
        result = asyncio.run(
            registry.execute('create_file', {'path': str(target), 'kind': 'gitignore-python'}, confirm=approve)
        )
        assert result.ok, result.error
        assert '__pycache__' in target.read_text()

    def test_unconfirmed_execute_never_writes(self, tmp_path):
        import asyncio
        from aether.tools.builtin_tools import build_registry, reset_controllers
        reset_controllers()
        registry = build_registry(force=True)
        target = tmp_path / 'Dockerfile'
        result = asyncio.run(registry.execute('create_file', {'path': str(target), 'kind': 'dockerfile-python'}))
        assert not result.ok
        assert not target.exists()
