#!/usr/bin/env python3
"""
AETHER Real-Time Assistant Daemon
Iron Man style - Always listening, voice-first, system-aware
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from aether.config.settings import config
from aether.core.agent.aether_agent import AETHERAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('aether.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("aether.daemon")


async def main():
    logger.info("=" * 60)
    logger.info("AETHER REAL-TIME ASSISTANT - INITIALIZING")
    logger.info("=" * 60)
    logger.info(f"Wake word: {'Enabled' if config.wakeword_enabled else 'Disabled'}")
    logger.info(f"Gemini Live: {'Enabled' if config.use_gemini_live else 'Disabled'}")
    logger.info(f"System Control: {'Enabled' if config.system_control_enabled else 'Disabled'}")
    logger.info(f"Memory: {'Enabled' if config.memory_enabled else 'Disabled'}")
    logger.info("=" * 60)

    try:
        agent = AETHERAgent()
        await agent.initialize()
        logger.info("AETHER is now online. Say 'Hey AETHER' to activate.")
        await agent.start()
    except KeyboardInterrupt:
        logger.info("\nShutting down AETHER...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
