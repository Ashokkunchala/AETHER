import logging
import os

logger = logging.getLogger("jarvis.tools.files")


def open_file(path: str):
    """Legacy default-handler route fails closed without resolving or launching."""
    from jarvis.control.files import open_path
    return open_path(path)


def list_files(directory: str = "."):
    """List files in directory"""
    try:
        files = os.listdir(directory)
        return files
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        raise
