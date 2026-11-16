import ctypes
import logging
import os
from ctypes import POINTER, cast
from typing import Any

import psutil
import pyautogui
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

logger = logging.getLogger("jarvis.control")


class SystemController:
    def __init__(self):
        pyautogui.FAILSAFE = False
        self._setup_audio()

    def _setup_audio(self):
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(
                IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self.volume = cast(interface, POINTER(IAudioEndpointVolume))
        except Exception as e:
            logger.warning(f"Audio control unavailable: {e}")
            self.volume = None

    def open_app(self, app_name: str) -> dict[str, Any]:
        return {"success": False, "error": "Legacy app launch disabled. Use exact local approved-app registry launch with fresh confirmation."}

    def close_app(self, app_name: str) -> dict[str, Any]:
        return {"success": False, "error": "Legacy name-based process stop disabled. Use exact process identity with fresh confirmation."}

    def set_volume(self, level: int) -> dict[str, Any]:
        try:
            if self.volume:
                level = max(0, min(100, level))
                self.volume.SetMasterVolumeLevelScalar(level / 100, None)
                return {"success": True, "volume": level}
            return {"success": False, "error": "Audio control unavailable"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_volume(self) -> dict[str, Any]:
        try:
            if self.volume:
                vol = self.volume.GetMasterVolumeLevelScalar()
                return {"success": True, "volume": int(vol * 100)}
            return {"success": False}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def mute(self, mute: bool = True) -> dict[str, Any]:
        try:
            if self.volume:
                self.volume.SetMute(1 if mute else 0, None)
                return {"success": True, "muted": mute}
            return {"success": False}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def screenshot(self, filename: str = None) -> dict[str, Any]:
        return {"success": False, "error": "Direct screenshot disabled. Use the desktop registry with explicit scope, path and fresh confirmation."}

    def shutdown(self, delay: int = 0) -> dict[str, Any]:
        try:
            os.system(f"shutdown /s /t {delay}")
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def restart(self, delay: int = 0) -> dict[str, Any]:
        try:
            os.system(f"shutdown /r /t {delay}")
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def lock(self) -> dict[str, Any]:
        try:
            ctypes.windll.user32.LockWorkStation()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
