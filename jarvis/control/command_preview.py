"""Exact-command review text for the existing local shell/process registry paths.

This is not an allowlist or shell sandbox. Nothing is executed during preview.
"""
from __future__ import annotations


def command_preview(command: str, timeout: int = 60, cwd: str | None = None):
    from jarvis.control.shell import classify
    if not isinstance(command, str) or not command.strip() or len(command) > 8000 or '\x00' in command:
        return {'success': False, 'error': 'An explicit nonempty command of at most 8000 characters is required.'}
    if type(timeout) is not int or not 5 <= timeout <= 300:
        return {'success': False, 'error': 'Timeout must be an integer from 5 to 300 seconds.'}
    if cwd is not None and (not isinstance(cwd, str) or not cwd.strip() or len(cwd) > 4096 or '\x00' in cwd):
        return {'success': False, 'error': 'Working directory must be explicit nonempty text when supplied.'}
    classification = classify(command)
    if classification == 'blocked':
        return {'success': False, 'error': 'Command blocked by existing shell policy.'}
    return {'success': True, 'command': command, 'cwd': cwd,
            'cwd_policy': 'explicit supplied path' if cwd is not None else 'inherit launcher process working directory at execution time',
            'timeout_seconds': timeout, 'shell': True,
            'notice': 'Review this exact command and working-directory policy. Shell syntax, scripts, aliases, executable lookup and child processes can execute arbitrary code, disclose files, use the network, spend money or change systems. This is not approved-app launch, an allowlist, a sandbox or authority for deployment, destructive actions or spending. Captured output may reach the configured model provider. Timeout does not guarantee child-process cancellation or rollback.'}


def process_start_preview(command: str, elevated: bool = False):
    if type(elevated) is not bool or elevated:
        return {'success': False, 'error': 'Legacy process elevation is disabled. Use a separately reviewed exact command through an authorized local workflow.'}
    result = command_preview(command)
    if result.get('success'):
        result.pop('timeout_seconds')
        result['background'] = True
        result['notice'] += ' This starts a background shell with no captured output or bounded completion wait. A PID is not readiness or completion; the emergency stop does not terminate an already-running process.'
    return result
