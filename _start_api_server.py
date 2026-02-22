"""
Start Synapse apiFunction server inside Houdini.

Run in Houdini Python Shell:
    import runpy; runpy.run_path(r"C:\\Users\\User\\Synapse\\_start_api_server.py")

Then test:
    curl -X POST http://localhost:8008/api -d "json=[\"synapse.ping\",[],{}]"
"""

import sys
sys.path.insert(0, r"C:\Users\User\Synapse\python")

from synapse.server.api_adapter import start_api_server

start_api_server(port=8008)
