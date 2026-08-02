"""H2 probe (R302 rank 7) — cost of the R7 dependents() forward trace.

QUESTION (harness/latency/REGISTRY.json H2): _infer_stage_touch
(shared/bridge.py) runs once per mutating bridge op ON the main thread and
walks list(n.dependents()) + list(n.outputs()) recursively (max depth 3).
Its dominant term was hypothesized to scale with the NODE COUNT of the
op's target container — a different axis from the prim-count regime.
C4 carried an EXPLICIT BRACKET (1-10 us/descendant), not a measurement.
This probe measures it.

METHOD. Build a WIRED chain of N nulls inside one geo (deep network — the
lane's shape), plus the same N as FLAT siblings, and time:

  a. container.dependents()  — the depth-0 call C4 flagged as dominant
  b. head.dependents() + head.outputs() — the per-node step cost
  c. a full _infer_stage_touch-shaped recursive trace (depth 3) from the
     chain head — what one bridge op actually pays

Run for N in (100, 500) in ONE hython process (fresh nodes per N).

RUN (hython, any H22 build — record the build with the numbers):
  & "C:/Program Files/Side Effects Software/Houdini 22.0.397/bin/hython.exe" \
      scripts/probe_h2_dependents_trace.py

Zero SYNAPSE imports — the trace loop is inlined verbatim from
shared/bridge.py:_infer_stage_touch_impl (minus the LopNode hit, absent
here by construction: worst case, the full walk).
"""
import time

import hou

print("build:", hou.applicationVersionString())


def trace_like_bridge(node):
    """Verbatim shape of _infer_stage_touch_impl's walk (no LOP present)."""
    visited = set()

    def _trace(n, depth=0):
        if depth > 3 or n.path() in visited:
            return False
        visited.add(n.path())
        for dep in list(n.dependents()) + list(n.outputs()):
            if isinstance(dep, hou.LopNode):
                return True
            if _trace(dep, depth + 1):
                return True
        return False

    return _trace(node), len(visited)


for n_nodes in (100, 500):
    # Wired chain (deep network)
    chain_geo = hou.node("/obj").createNode("geo", f"h2_chain_{n_nodes}")
    prev = None
    head = None
    for i in range(n_nodes):
        node = chain_geo.createNode("null", f"n{i}")
        if prev is not None:
            node.setInput(0, prev)
        else:
            head = node
        prev = node

    t0 = time.perf_counter()
    deps_c = chain_geo.dependents()
    t1 = time.perf_counter()
    print(f"N={n_nodes} chain | a. container.dependents(): "
          f"{(t1-t0)*1000:.3f} ms ({len(deps_c)} deps)")

    t2 = time.perf_counter()
    d = head.dependents()
    o = head.outputs()
    t3 = time.perf_counter()
    print(f"N={n_nodes} chain | b. head dependents+outputs: "
          f"{(t3-t2)*1000:.3f} ms ({len(d)} deps, {len(o)} outputs)")

    t4 = time.perf_counter()
    hit, visited = trace_like_bridge(head)
    t5 = time.perf_counter()
    print(f"N={n_nodes} chain | c. bridge-shaped trace (depth 3): "
          f"{(t5-t4)*1000:.3f} ms (visited {visited} nodes, lop_hit={hit})")

    # Flat container (the C4 depth-0 shape)
    flat_geo = hou.node("/obj").createNode("geo", f"h2_flat_{n_nodes}")
    for i in range(n_nodes):
        flat_geo.createNode("null", f"f{i}")

    t6 = time.perf_counter()
    deps_f = flat_geo.dependents()
    t7 = time.perf_counter()
    t8 = time.perf_counter()
    hit_f, visited_f = trace_like_bridge(flat_geo)
    t9 = time.perf_counter()
    print(f"N={n_nodes} flat  | a. container.dependents(): "
          f"{(t7-t6)*1000:.3f} ms ({len(deps_f)} deps) | "
          f"c. trace: {(t9-t8)*1000:.3f} ms (visited {visited_f})")
