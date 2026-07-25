"""
SYNAPSE MCP tool implementation packages.

Tool modules with real `validate()` / `plan()` / `execute()` bodies live here,
inside the installable `python/synapse/` package tree so both transports can
import them. (Prior to SR1 M1 the Solaris family lived at the repo-root
`synapse/mcp/tools/solaris/` shadow tree and was unreachable — L2 F1.)
"""
