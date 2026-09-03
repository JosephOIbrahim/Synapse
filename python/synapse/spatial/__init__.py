"""World Labs spatial lane — read-only stage queries (Intent 3, D3.3/D3.4).

Three ``pxr`` tools over a ``Usd.Stage``. Read-only: no prim authored, no file
written. See ``queries.py`` for the full contract and PROBE anchors.

    from synapse.spatial import (
        synapse_spatial_describe,
        synapse_spatial_classify,
        synapse_spatial_frustum,
    )

UNREGISTERED BY DESIGN (rule D-1).  The World Labs lane is ``ratified:false``
(``docs/intake/world_manifest.schema.json`` → provenance.ratified), so these
tools are deliberately NOT wired into ``mcp_server`` or any tool registry —
importing this package registers nothing and has no side effects.

When the lane is ratified and the house style calls for a registry entry, gate
it behind an env flag that defaults OFF, e.g. in ``mcp_server`` registration::

    import os
    if os.environ.get("SYNAPSE_SPATIAL_LANE") == "1":
        from synapse.spatial import (synapse_spatial_describe,
                                     synapse_spatial_classify,
                                     synapse_spatial_frustum)
        # ... register the three tools here ...

Until then the flag is unread anywhere in the tree (grep ``SYNAPSE_SPATIAL_LANE``)
— the lane is import-only.
"""
from .queries import (  # noqa: F401
    SCATTER_MAX_ANGLE_DEFAULT_DEG,
    synapse_spatial_classify,
    synapse_spatial_describe,
    synapse_spatial_frustum,
)

__all__ = [
    "synapse_spatial_describe",
    "synapse_spatial_classify",
    "synapse_spatial_frustum",
    "SCATTER_MAX_ANGLE_DEFAULT_DEG",
]
