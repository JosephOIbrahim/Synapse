"""
Synapse hwebserver Startup Script

Run this inside Houdini to start the native C++ WebSocket server.

Usage from Houdini Python Shell:
    exec(open("path/to/start_hwebserver.py").read())

Usage from shelf tool:
    import synapse.server.start_hwebserver

Usage from 456.py or pythonrc.py (auto-start):
    try:
        from synapse.server.hwebserver_adapter import start_hwebserver
        start_hwebserver(port=9999)
    except ImportError:
        pass
"""

import logging
import os

logger = logging.getLogger("synapse.hwebserver")


def main():
    port = int(os.environ.get("SYNAPSE_PORT", "9999"))
    enable_rate_limiter = os.environ.get("SYNAPSE_RATE_LIMITER", "1") == "1"

    try:
        from synapse.server.hwebserver_adapter import start_hwebserver
        start_hwebserver(
            port=port,
            enable_rate_limiter=enable_rate_limiter,
        )
    except ImportError as e:
        logger.warning("Cannot start hwebserver: %s", e)
        logger.info("Falling back to websocket server...")
        from synapse.server.websocket import SynapseServer
        server = SynapseServer(
            port=port,
            enable_resilience=False,
        )
        server.start()


if __name__ == "__main__":
    main()
else:
    # When imported as module, auto-start
    main()
