"""synapse.cognitive.tools — host-agnostic cognitive tool implementations.

Every module here exports ONE pure Python function per tool, with the
Dispatcher contract:

    def <tool_name>(**kwargs) -> Dict[str, Any]

Tools are JSON-serializable at the boundary (Invariant 3): kwargs are
URIs / dicts / numbers / booleans / lists; returns are dicts. No
``hou.Node`` objects, no file handles, no live cursors.

Registration is the caller's responsibility. Example:

    from synapse.cognitive.dispatcher import Dispatcher
    from synapse.cognitive.tools.inspect_stage import inspect_stage

    dispatcher = Dispatcher(
        tools={"synapse_inspect_stage": inspect_stage},
        main_thread_executor=synapse.host.main_thread_exec,
    )
"""

from __future__ import annotations

from synapse.cognitive.tools.inspect_stage import inspect_stage

__all__ = ["inspect_stage"]
