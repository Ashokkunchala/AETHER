#!/usr/bin/env python3
"""Headless entry point for the always-on AETHER voice service.

Runs the same AETHERAgent state machine as ``aether start`` (wake word ->
Gemini Live -> local tools -> sleep) but logs only to a rotating file so it can
run invisibly under pythonw.exe from a Windows Scheduled Task.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ENV_PATH = ROOT / ".env"
try:
    from dotenv import load_dotenv

    if ENV_PATH.is_file():
        load_dotenv(ENV_PATH, override=False)
except ImportError:  # pragma: no cover - python-dotenv is a declared dependency
    pass

from aether.config.settings import config  # noqa: E402
from aether.core.agent.aether_agent import AETHERAgent  # noqa: E402

LOG_DIR = ROOT / "data" / "logs"
LOG_FILE = LOG_DIR / "voice-service.log"
STATUS_FILE = LOG_DIR / "voice-service.json"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG = logging.getLogger("aether.voice_service")


def configure_logging() -> None:
    """File-only logging: pythonw.exe has no usable stdout/stderr."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root.addHandler(handler)
    logging.getLogger("openwakeword").setLevel(logging.WARNING)


def write_status(**fields: object) -> None:
    payload: dict[str, object] = {
        "pid": os.getpid(),
        "updated_at": datetime.now(UTC).isoformat(),
        "wake_word": config.wakeword_model,
        "threshold": config.wakeword_threshold,
        "call_mode": False,
        "state": "starting",
    }
    payload.update(fields)
    tmp = STATUS_FILE.parent / (STATUS_FILE.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATUS_FILE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AETHER always-on voice service")
    parser.add_argument(
        "--wake-word",
        default=config.wakeword_model,
        help="openWakeWord model key, e.g. hey_jarvis, alexa, hey_mycroft",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=config.wakeword_threshold,
        help="wake-word confidence threshold (0.02-0.95)",
    )
    parser.add_argument(
        "--wakeword-models-dir",
        default=str(config.wakeword_models_dir),
        help="optional directory containing custom <name>.onnx wake models",
    )
    parser.add_argument(
        "--call-mode",
        action="store_true",
        help="skip the wake word and stream the microphone immediately",
    )
    args = parser.parse_args()
    if not 0.02 <= args.threshold <= 0.95:
        parser.error("--threshold must be between 0.02 and 0.95")
    return args


async def refresh_live_status(agent: AETHERAgent) -> None:
    """Keep voice-service.json honest about the Live session while sleeping."""
    while True:
        await asyncio.sleep(10)
        try:
            current = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if current.get("state") != "running":
            continue
        write_status(
            state="running",
            call_mode=agent.call_mode,
            gemini_live=bool(agent.live_client and agent.live_client.connected),
        )


async def run(args: argparse.Namespace) -> int:
    config.wakeword_model = args.wake_word
    config.wakeword_threshold = args.threshold
    config.wakeword_models_dir = Path(args.wakeword_models_dir)
    config.wakeword_enabled = not args.call_mode

    if not config.gemini_api_key.strip():
        LOG.error("GEMINI_API_KEY is missing; refusing to open the microphone")
        write_status(state="error", error="GEMINI_API_KEY is missing")
        return 2

    agent = AETHERAgent()
    try:
        await agent.initialize()
    except Exception:
        LOG.exception("AETHER voice agent failed to initialize")
        write_status(state="error", error="initialization failed")
        return 1

    write_status(
        state="running",
        call_mode=bool(args.call_mode),
        gemini_live=bool(config.use_gemini_live),
    )
    LOG.info(
        "AETHER voice service online: wake_word=%s threshold=%.2f call_mode=%s",
        args.wake_word,
        args.threshold,
        args.call_mode,
    )

    status_task = asyncio.create_task(refresh_live_status(agent))
    try:
        await agent.start(call_mode=args.call_mode)
    except asyncio.CancelledError:
        LOG.info("AETHER voice service cancelled")
    except Exception:
        LOG.exception("AETHER voice loop crashed")
        write_status(state="error", error="voice loop crashed")
        return 1
    finally:
        status_task.cancel()
        try:
            await status_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        try:
            await agent.stop()
        except Exception:
            LOG.exception("AETHER voice agent shutdown error")

    write_status(state="stopped")
    LOG.info("AETHER voice service stopped")
    return 0


def main() -> int:
    args = parse_args()
    configure_logging()
    LOG.info("AETHER voice service starting (pid=%s)", os.getpid())
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
