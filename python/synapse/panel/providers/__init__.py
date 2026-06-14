"""Panel chat provider abstraction.

A ``StreamProvider`` owns the per-provider transport + request/response
translation for one streamed turn, returning NORMALIZED Anthropic-shaped content
blocks so the worker's conversation loop and tool dispatch stay provider-agnostic.

No Qt, no hou — pure transport.
"""
