"""Explicit screenshot scope preview. No capture until registry confirmation."""
from pathlib import Path


def preview_screenshot(scope, path, left=None, top=None, width=None, height=None):
    if scope not in ('full_screen', 'region'):
        raise ValueError('Explicitly choose full_screen or region for this single capture.')
    coords = (left, top, width, height)
    if scope == 'full_screen' and any(value is not None for value in coords):
        raise ValueError('Full-screen scope cannot include region coordinates.')
    if scope == 'region' and (any(type(value) is not int for value in coords) or
                              not -100000 <= left <= 100000 or not -100000 <= top <= 100000 or
                              not 1 <= width <= 16000 or not 1 <= height <= 16000 or width*height > 40_000_000):
        raise ValueError('Region requires explicit bounded integer left/top/width/height, positive dimensions and at most 40 million pixels.')
    if not isinstance(path, str) or not 1 <= len(path) <= 2000 or '\x00' in path or path.startswith(('\\\\', '//')):
        raise ValueError('Choose a non-network absolute local destination path.')
    destination = Path(path).expanduser()
    if not destination.is_absolute() or destination.suffix.lower() != '.png' or ':' in destination.name:
        raise ValueError('Choose an absolute local .png destination without alternate streams.')
    parent = destination.parent
    if not parent.is_dir() or parent.resolve() != parent or destination.exists() or destination.is_symlink():
        raise ValueError('Choose a new file in an existing non-symlink canonical local directory. No overwrite.')
    return {'success': True, 'scope': scope, 'destination': str(destination),
            'region': dict(zip(('left', 'top', 'width', 'height'), coords)) if scope == 'region' else None,
            'effect': 'One local screenshot to the exact new PNG path. Full-screen includes all monitors. No image upload, sharing or terminal capture.',
            'privacy': 'The selected screen region can contain credentials, messages and other private data. Confirm only if you explicitly want this exact capture now.',
            'approval': 'Fresh confirmation for this capture only; no standing/auto approval. Cancel means no capture.',
            'limits': 'Local path checks are not a sandbox against hostile concurrent parent-directory changes or mapped remote drives. No redaction or disclosure permission created.'}


def capture_requested_screenshot(scope, path, left=None, top=None, width=None, height=None):
    """Internal registry handler; its trusted confirmation boundary owns authority."""
    preview = preview_screenshot(scope, path, left, top, width, height)
    from jarvis.control.screen import _capture_screenshot
    return _capture_screenshot(preview['destination'], preview['region'])
