"""Owner-run fixed scanner adapters. No install, cleanup, quarantine or shell.

Only plans are model-visible. CLI requires an exact interactive owner review.
Dependency audit discloses package names/versions to PyPI and is never automatic.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def scan_plan(kind: str, target: str, root: str):
    if kind not in ('malware', 'dependencies'):
        raise ValueError('Choose malware or dependencies.')
    raw, base = Path(target), Path(root)
    if not raw.is_absolute() or not base.is_absolute():
        raise ValueError('Exact absolute target and root required.')
    if any(p.is_symlink() for p in (raw, *raw.parents, base, *base.parents)):
        raise ValueError('Linked scan paths are refused.')
    actual, allowed = raw.resolve(strict=True), base.resolve(strict=True)
    if not allowed.is_dir() or not actual.is_file() or not actual.is_relative_to(allowed):
        raise ValueError('Scan one existing regular file inside the selected root.')
    import hashlib
    if actual.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('Single-file scans are limited to64MiB.')
    with actual.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    packages = []
    if kind == 'malware':
        binary = shutil.which('clamscan')
        if not binary:
            raise ValueError('ClamAV is not installed; no automatic install/update.')
        command = [binary, '--no-summary', '--', str(actual)]
        disclosure = 'Local single-file ClamAV signature scan only. Database freshness is not established. No upload, delete, move, quarantine or signature update is requested.'
    else:
        if actual.stat().st_size > 65536:
            raise ValueError('Pinned requirements file too large.')
        lines = actual.read_text().splitlines()
        entries = [x.strip() for x in lines if x.strip() and not x.strip().startswith('#')]
        if not entries or len(entries) > 500 or any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*==[A-Za-z0-9][A-Za-z0-9_.+!-]*', x) for x in entries):
            raise ValueError('Only exact package==version lines and whole-line comments supported. No URLs, options, editable installs, includes, unpinned dependencies or markers.')
        packages = entries
        command = [sys.executable, '-m', 'pip_audit', '--disable-pip', '--no-deps', '--progress-spinner', 'off', '--format', 'json', '--vulnerability-service', 'pypi', '-r', str(actual)]
        disclosure = 'Dependency audit sends these package names/versions to the PyPI vulnerability service over HTTPS. It does not scan malware or prove code safe. No dependency resolver, installation or fix requested. pip-audit must already be installed by the owner.'
    return {'kind': kind, 'target': str(actual), 'root': str(allowed), 'command': command, 'disclosure': disclosure, 'executed': False, 'input_sha256': digest, 'reviewed_packages': packages}


def _run_reviewed(plan):
    # Not registered as an AI tool; called only by this module's interactive CLI.
    # Revalidate exact plan before invoking a fixed argument list without a shell.
    if scan_plan(plan['kind'], plan['target'], plan['root']) != plan:
        raise ValueError('Scanner plan changed; request fresh review.')
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        try:
            result = subprocess.run(plan['command'], stdin=subprocess.DEVNULL, stdout=out, stderr=err, timeout=120, shell=False, check=False)
        except OSError:
            return {'status': 'scan_error', 'notice': 'Scanner unavailable or invocation failed. Nothing installed; no clean result.'}
        except subprocess.TimeoutExpired:
            return {'status': 'unknown_timeout', 'notice': 'Scanner timed out. No clean result; child-process termination is not guaranteed.'}
        out.seek(0, 2); count = out.tell(); out.seek(0); content = out.read(min(count, 1048576)).decode('utf-8', errors='replace')
    if plan['kind'] == 'dependencies':
        try:
            from aether.devops.dependency_audit import review_audit
            report = review_audit(json.loads(content))
            expected = {re.sub(r'[-_.]+', '-', x.split('==')[0]).lower() for x in plan['reviewed_packages']}
            actual = {item['name'] for item in report['packages']}
            complete = not report['skipped_packages'] and expected == actual
            # Keep scanner completion distinct from vulnerability findings.
            status = 'dependency_report_review_required'
            if not complete or count > 1048576 or result.returncode not in (0, 1):
                status = 'unknown_incomplete_audit'
            return {'status': status, 'exit_code': result.returncode, 'report': report,
                    'notice': 'A supplied pip-audit result, not malware scanning or proof of safety. Review package coverage and findings; no auto-fix or automatic provider send.'}
        except Exception:
            return {'status': 'unknown_invalid_audit', 'exit_code': result.returncode,
                    'notice': 'No complete validated dependency report. Inspect the scanner locally; no clean claim.'}
    # Raw scanner output may contain file paths or content. Keep local terminal only.
    status = 'no_findings_reported' if result.returncode == 0 else 'findings_reported' if result.returncode == 1 else 'scan_error'
    if count > 1048576:
        status = 'unknown_truncated_output'
    return {'status': status, 'exit_code': result.returncode, 'output': content, 'output_truncated': count > 1048576,
            'notice': 'No scanner proves safety. Read the full local result; errors/unknown never mean clean. No cleanup/fix or provider/device action by AETHER.'}


def main():
    import argparse
    parser = argparse.ArgumentParser(description='AETHER optional owner-reviewed scanners')
    parser.add_argument('kind', choices=['malware', 'dependencies'])
    parser.add_argument('target')
    parser.add_argument('--root', required=True)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    plan = scan_plan(args.kind, args.target, args.root)
    print(json.dumps(plan, indent=2))
    if not args.run:
        return
    if not sys.stdin.isatty() or input('Type RUN REVIEWED SCAN after reading the disclosure: ') != 'RUN REVIEWED SCAN':
        raise SystemExit('Not approved; nothing scanned.')
    print(json.dumps(_run_reviewed(plan), indent=2))


if __name__ == '__main__':
    main()
