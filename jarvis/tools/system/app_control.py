import logging


logger = logging.getLogger("jarvis.tools.app")


def open_app(app_name: str):
    """Legacy substring allowlist path fails closed."""
    return {"success": False, "error": "Use the exact local approved-app registry with fresh confirmation. Legacy broad launch disabled."}


def close_app(app_name: str):
    """Close an application"""
    try:
        import psutil
        app_name_lower = app_name.lower()
        closed = []
        for proc in psutil.process_iter(['name']):
            try:
                if app_name_lower in proc.info['name'].lower():
                    proc.terminate()
                    closed.append(proc.info['name'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if closed:
            return f"Closed {', '.join(closed)}"
        else:
            return f"No processes found matching {app_name}"
    except Exception as e:
        logger.error(f"Failed to close app {app_name}: {e}")
        raise
