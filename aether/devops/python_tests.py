"""Fresh-approved fixed pytest invocation. Not a code/network/filesystem sandbox."""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

_ENV_KEYS = {'PATH', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'TEMP', 'TMP', 'HOME',
             'USERPROFILE', 'LOCALAPPDATA', 'APPDATA', 'PATHEXT', 'LANG', 'LC_ALL'}
_EXIT = {0: 'pytest reported success', 1: 'pytest reported test failures',
         2: 'pytest reported interruption', 3: 'pytest internal error',
         4: 'pytest command/configuration error', 5: 'pytest collected no tests',
         6: 'pytest warning limit exceeded (where supported by installed version)'}


def _canonical(value: str, directory: bool):
    if not isinstance(value, str) or not value or '\x00' in value or len(value) > 4096:
        raise ValueError('Explicit canonical local absolute paths are required.')
    path = Path(value)
    if value.startswith(('\\\\', '//')) or not path.is_absolute():
        raise ValueError('Network/relative paths are not accepted.')
    if path.resolve(strict=True) != path or path.is_symlink():
        raise ValueError('Symlinked, relative or noncanonical paths are not accepted.')
    if directory and not path.is_dir():
        raise ValueError('Choose an existing project/test directory.')
    if not directory and (not path.is_file() or path.suffix != '.py'):
        raise ValueError('Choose an existing Python test file.')
    return path


def _plan(project: str, selection: str, timeout: int):
    if type(timeout) is not int or not 5 <= timeout <= 300:
        raise ValueError('Timeout must be an integer from 5 through 300 seconds.')
    root = _canonical(project, True)
    tests = _canonical(str(root / 'tests'), True)
    if not isinstance(selection, str) or not selection or '\\' in selection:
        raise ValueError('Select tests or a slash-separated path under tests; no flags.')
    parts = selection.split('/')
    if parts[0] != 'tests' or any(part in {'', '.', '..'} or part.startswith('-') for part in parts):
        raise ValueError('Selection must be tests or a path within tests, without traversal or flags.')
    selected = root.joinpath(*parts)
    selected = _canonical(str(selected), selected.is_dir())
    if selected != tests and not selected.is_relative_to(tests):
        raise ValueError('Selection must stay inside this project tests directory.')
    python = Path(sys.executable)
    if not python.is_absolute() or not python.is_file():
        raise ValueError('Current AETHER Python executable is unavailable.')
    # Use the already-running trusted interpreter, not PATH, user argv or a shell.
    argv = [str(python), '-I', '-B', '-m', 'pytest', '-q', '--tb=no',
            '--disable-warnings', '-p', 'no:cacheprovider', '-o', 'addopts=', str(selected)]
    return root, selected, argv


def preview_python_tests(project: str, selection: str = 'tests', timeout: int = 60):
    try:
        root, selected, argv = _plan(project, selection, timeout)
    except (ValueError, OSError, RuntimeError):
        return {'success': False, 'error': 'Invalid/unavailable canonical project, tests selection, interpreter or timeout. No test process started.'}
    return {'success': True, 'project': str(root), 'selection': str(selected),
            'argv': argv, 'shell': False, 'timeout_seconds': timeout,
            'output_policy': 'wrapper discards stdout/stderr and retains/uploads no output log; tests/plugins may write their own files/reports',
            'notice': 'This executes trusted project code, conftest/config and installed pytest/plugin dependencies with the current AETHER Python interpreter. Tests/imports/plugins can read/write files, launch programs, use credentials from files, use the network, spend money or change systems. A reduced environment and disabled plugin autoload are not a sandbox. Selected project/command/status can appear in model tool context. Repository/import/config/dependency bytes are not frozen or reviewed by this tool and can change after approval. Review this exact command and project before approval. Timeout terminates only the direct test process, not guaranteed children/remote effects; stop cannot undo work. Exit code is not independent proof of tests run or product readiness. No install, repair, retry, deploy or elevation is performed.'}


def run_python_tests(project: str, selection: str = 'tests', timeout: int = 60):
    preview = preview_python_tests(project, selection, timeout)
    if not preview.get('success'):
        return preview
    # Revalidate canonical paths immediately before dispatch after the review wait.
    try:
        root, _, argv = _plan(project, selection, timeout)
    except (ValueError, OSError, RuntimeError):
        return {'success': False, 'error': 'Project/test selection changed or became unavailable. No test process started.'}
    env = {key: value for key, value in os.environ.items() if key.upper() in _ENV_KEYS}
    env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONNOUSERSITE='1', PYTHONIOENCODING='utf-8')
    stamp = datetime.now(UTC).isoformat()
    common = {'as_of': stamp, 'argv': argv, 'project': str(root),
              'output_retained': False, 'tests_count_verified': False,
              'child_process_completion_verified': False, 'product_readiness_verified': False,
              'automatic_retry': False}
    try:
        result = subprocess.run(argv, cwd=str(root), env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                shell=False, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {**common, 'success': False, 'timed_out': True,
                'error': 'Direct test process timed out. Its termination does not prove child/remote work stopped or effects were undone.'}
    except Exception:
        return {**common, 'success': False, 'error': 'Test process could not be completed. Output and exception details are not disclosed; no retry performed.'}
    code = result.returncode
    return {**common, 'success': code == 0, 'timed_out': False,
            'exit_code': code, 'outcome': _EXIT.get(code, 'unrecognized exit status; inspect locally'),
            'error': None if code == 0 else f"pytest direct process exited with status {code}: {_EXIT.get(code, 'unrecognized status')}. Output discarded; test counts and child completion unverified. No retry.",
            'notice': 'Only direct process exit status was observed. Output discarded; no test count, independent correctness, sandbox or readiness claim.'}
