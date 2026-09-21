"""Outside-in benchmark arms.

Two arms, each in its OWN process and port, never sharing a scene file:
  - synapse.py       SYNAPSE panel path over ws://localhost:9999/synapse
  - fxhoudinimcp.py  fxhoudinimcp MCP server (stdio) against its hwebserver on :8100

Both arms drive the SAME provider agent loop (``_agent.run_agent``) so the only
difference measured is the tool surface and its transport, not the harness.
"""
