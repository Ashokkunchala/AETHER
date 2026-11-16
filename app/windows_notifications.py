"""Native Windows toast delivery for AETHER's authenticated notification inbox."""
from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx

from app.config import get_settings

logger = logging.getLogger("aether.notifications")


def main() -> None:
    try:
        from winotify import Notification
    except ImportError as exc:
        raise SystemExit("Install the Windows extra: pip install -e '.[windows]'") from exc
    cfg = get_settings()
    if len(cfg.jarvis_api_token) < 32 or cfg.jarvis_api_token.startswith("replace_"):
        raise SystemExit("Configure JARVIS_API_TOKEN in .env before starting notifications.")
    base = f"http://{cfg.host}:{cfg.port}".rstrip("/")
    cursor_file = Path(cfg.jarvis_db_path).parent / "windows-notification-cursor.txt"
    try:
        cursor = int(cursor_file.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        cursor = 0
    logger.info("AETHER Windows notification agent started.")
    with httpx.Client(timeout=15) as client:
        while True:
            try:
                response = client.get(
                    f"{base}/api/integrations/notifications",
                    params={"after_id": cursor, "limit": 50},
                    headers={"Authorization": f"Bearer {cfg.jarvis_api_token}"},
                )
                if response.status_code in (401, 403):
                    logger.error("AETHER notification authentication failed; stopping.")
                    return
                response.raise_for_status()
                for item in response.json().get("items", []):
                    notification_id = int(item["id"])
                    if notification_id <= cursor:
                        continue
                    toast = Notification(
                        app_id="AETHER Personal Assistant",
                        title=str(item.get("title", "AETHER"))[:180],
                        msg=str(item.get("body", ""))[:500],
                    )
                    toast.show()
                    cursor = notification_id
                    cursor_file.parent.mkdir(parents=True, exist_ok=True)
                    cursor_file.write_text(str(cursor), encoding="ascii")
            except httpx.HTTPError:
                logger.warning("AETHER notification service is temporarily unavailable.")
            except Exception:
                logger.exception("AETHER notification delivery failed.")
            time.sleep(30)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
