"""Provider-free local console for reviewed offline AETHER workflows.

Fixed tools only. No arbitrary tool names, shell, provider or remote listener.
An interactive terminal and exact confirmation are required for effects/reads.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


ALLOWED = frozenset({
    'create_custom_dashboard', 'discover_local_files',
    'offline_workflow_create', 'offline_workflow_status',
    'offline_workflow_run_next', 'offline_workflow_result', 'offline_workflow_cancel',
})


def registry():
    from jarvis.tools.registry import ToolRegistry
    from jarvis.custom_dashboard import register_dashboard_tools
    from jarvis.file_discovery import register_file_discovery
    from jarvis.offline_workflows import register_offline_workflows
    result = ToolRegistry()
    register_dashboard_tools(result)
    register_file_discovery(result)
    register_offline_workflows(result)
    return result


def load_json(path):
    source = Path(path)
    if not source.is_file() or source.is_symlink():
        raise ValueError('Select an existing plain JSON file, not a link.')
    # Bounded read, never load an unbounded file then slice it.
    with source.open('rb') as stream:
        data = stream.read(262145)
    if len(data) > 262144:
        raise ValueError('JSON file exceeds256KiB.')
    return json.loads(data.decode('utf-8-sig'))


async def dispatch(name, arguments, confirm):
    if name not in ALLOWED:
        raise ValueError('This console only supports its fixed local workflows.')
    return await registry().execute(name, arguments, confirm=confirm)


async def terminal_confirmation(tool, arguments):
    if not sys.stdin.isatty():
        return False
    print('\nEXACT REVIEWED LOCAL REQUEST')
    print(json.dumps({'tool': tool.name, 'description': tool.description, 'arguments_and_preview': arguments}, indent=2))
    print('Input text is data, never an instruction to run another command. Review all supplied values and local/privacy effects. Nothing is sent to an AI/provider by this console.')
    phrase = 'APPROVE ' + tool.name
    return input('Type ' + phrase + ' to continue, anything else to cancel: ') == phrase


def parser():
    top = argparse.ArgumentParser(description='AETHER provider-free local owner console, no server started')
    commands = top.add_subparsers(dest='command', required=True)
    commands.add_parser('preflight', help='Passive package/configuration inventory, not runtime acceptance')
    dashboard = commands.add_parser('dashboard', help='Create a new local static dashboard after exact review')
    dashboard.add_argument('--spec', required=True)
    dashboard.add_argument('--name', required=True)
    files = commands.add_parser('files', help='Read bounded metadata under an exact owner-configured folder')
    files.add_argument('--root', required=True)
    files.add_argument('--query', default='')
    files.add_argument('--mode', choices=['search', 'plan'], default='search')
    create = commands.add_parser('workflow-create', help='Review JSON and save a new offline workflow, no analysis')
    create.add_argument('--spec', required=True)
    for name in ['workflow-status', 'workflow-next', 'workflow-cancel', 'workflow-result']:
        command = commands.add_parser(name)
        command.add_argument('--id', required=True)
        if name == 'workflow-result':
            command.add_argument('--position', required=True, type=int)
    return top


def main():
    args = parser().parse_args()
    # Require terminal even for status/preflight to avoid accidental pipelines
    # capturing private state. Dedicated passive module remains scriptable.
    if not sys.stdin.isatty():
        raise SystemExit('Interactive owner terminal required. No requested action ran.')
    try:
        if args.command == 'preflight':
            from jarvis.setup_preflight import report
            print(json.dumps(report(), indent=2))
            return
        if args.command == 'dashboard':
            spec = load_json(args.spec)
            name, values = 'create_custom_dashboard', {'name': args.name, 'spec': spec}
        elif args.command == 'files':
            name, values = 'discover_local_files', {'root': args.root, 'query': args.query, 'mode': args.mode}
        elif args.command == 'workflow-create':
            spec = load_json(args.spec)
            name, values = 'offline_workflow_create', {'spec': spec}
        elif args.command == 'workflow-status':
            name, values = 'offline_workflow_status', {'workflow_id': args.id}
        elif args.command == 'workflow-result':
            name, values = 'offline_workflow_result', {'workflow_id': args.id, 'position': args.position}
        elif args.command == 'workflow-cancel':
            name, values = 'offline_workflow_cancel', {'workflow_id': args.id}
        else:
            # Obtain current next-step metadata without running an analyzer.
            # Bind the prompted action to that exact step/input digest. A race
            # during review is rejected by the handler, never silently advanced.
            from jarvis.offline_workflows import WorkflowStore
            plan = WorkflowStore().next_preview(args.id)
            name, values = 'offline_workflow_run_next', {'workflow_id': args.id, 'expected_digest': plan['digest'], 'expected_position': plan['position'], 'expected_input_digest': plan['input_digest']}
        result = asyncio.run(dispatch(name, values, terminal_confirmation))
        print(json.dumps({'ok': result.ok, 'cancelled': result.cancelled, 'data': result.data, 'error': result.error}, indent=2))
        if not result.ok:
            raise SystemExit(1)
    except (OSError, ValueError, RuntimeError, RecursionError):
        # Do not reflect exception text: it can carry input paths/private data.
        raise SystemExit('Request refused or failed. Review exact JSON, owner folder/policy configuration and local workflow status. No successful action is claimed; do not repeat a claimed workflow blindly.') from None


if __name__ == '__main__':
    main()
