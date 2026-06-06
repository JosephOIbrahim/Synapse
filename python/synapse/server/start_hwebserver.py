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
# background thread. While that thread is actively serving, the running bound
# method roots the server — so a live, serving server is NOT reaped mid-serve.
# Two real gaps this hard ref closes:
#   1. Recoverability — without a named handle, the host/panel layer has no
#      way to reach the running server except scanning ``gc.get_objects()``.
#      This is what bit us repeatedly (hand-worked-around in the Houdini
#      Python Shell with ``builtins._synapse_manual_srv = srv``).
#   2. Post-exit window — the instant the serve thread stops (bind failure,
#      shutdown, exception), a bare-local reference becomes collectible with
#      no handle left for diagnosis or restart.
# Pinning the server here gives a stable, named root for the process lifetime.
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
