import logging


logger = logging.getLogger("jarvis.tools.app")


def open_app(app_name: str):
    """Legacy substring allowlist path fails closed."""
    return {"success": False, "error": "Use the exact local approved-app registry with fresh confirmation. Legacy broad launch disabled."}


def close_app(app_name: str):
    """Legacy broad process stop fails closed."""
    return {"success": False, "error": "Name-based process stop disabled. Use exact process identity with fresh confirmation."}
