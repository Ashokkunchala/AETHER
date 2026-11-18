"""Screen capture: screenshots, region capture, pixel colour and screen recording."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("aether.control.screen")


def screen_size() -> dict[str, Any]:
    try:
        import mss

        with mss.mss() as sct:
            monitor = sct.monitors[0]
            return {"success": True, "width": monitor["width"], "height": monitor["height"]}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def screenshot(path: str | None = None, region: dict[str, int] | None = None) -> dict[str, Any]:
    """Legacy direct entrypoint fails closed; use the scoped confirmed registry tool."""
    return {"success": False, "error": "Explicit scoped screenshot confirmation is required through the desktop registry. Direct capture is disabled."}


def _capture_screenshot(path: str, region: dict[str, int] | None) -> dict[str, Any]:
    """Internal primitive called only after the registry's scoped confirmation."""
    try:
        import os

        import mss
        import mss.tools

        with mss.mss() as sct:
            monitor = region if region is not None else sct.monitors[0]
            image = sct.grab(monitor)
            payload = mss.tools.to_png(image.rgb, image.size)
        # Exclusive creation prevents overwriting a file/symlink introduced after preview.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0), 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
        return {"success": True, "path": path, "absolute": path,
                "captured_scope": "region" if region is not None else "full_screen",
                "uploaded": False, "shared": False, "redacted": False}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def get_pixel_color(x: int, y: int) -> dict[str, Any]:
    try:
        import mss

        with mss.mss() as sct:
            pixel = sct.grab({"left": int(x), "top": int(y), "width": 1, "height": 1})
            r, g, b = pixel.rgb[0], pixel.rgb[1], pixel.rgb[2]
        return {"success": True, "x": int(x), "y": int(y), "rgb": [r, g, b], "hex": f"#{r:02x}{g:02x}{b:02x}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def list_monitors() -> list[dict[str, Any]]:
    try:
        import mss

        with mss.mss() as sct:
            return [
                {
                    "index": i,
                    "left": m["left"],
                    "top": m["top"],
                    "width": m["width"],
                    "height": m["height"],
                }
                for i, m in enumerate(sct.monitors)
            ]
    except Exception as exc:
        logger.warning("Could not list monitors: %s", exc)
        return []


def record_screen(duration: int = 10, path: str | None = None) -> dict[str, Any]:
    """Record the screen to an .avi using OpenCV (optional dependency)."""
    try:
        import cv2
        import mss
        import numpy as np
    except ImportError as exc:
        return {"success": False, "error": f"Screen recording needs opencv-python and numpy: {exc}"}

    duration = max(1, min(int(duration), 120))
    if not path:
        out_dir = Path("data/recordings")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = str(out_dir / f"recording_{int(time.time())}.avi")
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    try:
        with mss.mss() as sct:
            monitor = sct.monitors[0]
            width, height = monitor["width"], monitor["height"]
            # Downscale very large screens to keep file sizes sane
            scale = min(1.0, 1280 / max(width, 1))
            out_w, out_h = int(width * scale), int(height * scale)
            fourcc = cv2.VideoWriter_fourcc(*"XVID")
            writer = cv2.VideoWriter(path, fourcc, 15.0, (out_w, out_h))
            if not writer.isOpened():
                return {"success": False, "error": "Could not open video writer"}
            frames = int(duration * 15)
            for _ in range(frames):
                frame = np.array(sct.grab(monitor))
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                if scale < 1.0:
                    frame = cv2.resize(frame, (out_w, out_h))
                writer.write(frame)
            writer.release()
        return {"success": True, "path": str(path), "duration": duration, "fps": 15}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def ocr_screen(region: dict[str, int] | None = None) -> dict[str, Any]:
    """OCR text on screen via Tesseract (optional dependency)."""
    try:
        import mss
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        return {"success": False, "error": f"OCR needs pillow + pytesseract + tesseract: {exc}"}
    try:
        with mss.mss() as sct:
            monitor = region or sct.monitors[0]
            img = Image.frombytes("RGB", sct.grab(monitor).size, sct.grab(monitor).rgb)
        text = pytesseract.image_to_string(img)
        return {"success": True, "text": text.strip()}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
