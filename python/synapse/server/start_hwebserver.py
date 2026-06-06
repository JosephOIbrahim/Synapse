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

# Durable, module-level hard reference to the fallback websocket server.
#
# The websocket SynapseServer runs ``serve_forever()`` on a ``daemon=True``
# background thread. If the only reference to the server is the local in
# ``main()``, Python is free to garbage-collect the server object the moment
# main() returns — the daemon thread alone is not a guaranteed-durable owner,
# and once the server object is reaped the bridge on :9999 dies silently.
# This bit us repeatedly (hand-worked-around with
# ``builtins._synapse_manual_srv = srv``). Pinning the server here gives GC a
# hard root it can never reap for the process lifetime.
_fallback_server = None


def get_running_server():
    """Return the durably-retained fallback websocket server, or None.

    Exposed so the panel / host layer can recover the server object without
    scanning ``gc.get_objects()`` for a zombie instance.
    """
    return _fallback_server


def main():
    global _fallback_server

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
        # Retain a hard reference so GC cannot reap the live server while
        # its daemon thread is blocked in serve_forever().
        _fallback_server = server


if __name__ == "__main__":
    main()
else:
    # When imported as module, auto-start
    main()
