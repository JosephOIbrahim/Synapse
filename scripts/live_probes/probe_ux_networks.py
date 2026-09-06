"""Bounded build/rebuild/relayout regression on real Houdini nodes.

Run only in an isolated hython process (network_hython.py), or call run(parent)
with an explicitly disposable subnet in the authorized GUI trial. Invalid-slot
rejection is an inline negative control. No render or external asset is used.
"""
import json
import os
from pathlib import Path
import sys

REPO = Path(os.environ.get("SYNAPSE_NETWORK_PROBE_SOURCE", Path(__file__).resolve().parents[2]))
sys.path[:0] = [str(REPO / "python"), str(REPO)]
import hou
from synapse.server.handlers_solaris_graph import SolarisGraphMixin
from synapse.server.handlers_solaris_assemble import SolarisAssembleMixin
from synapse.server.handler_helpers import _apply_section_boxes
from synapse.core.errors import SynapseUserError


class Harness(SolarisGraphMixin, SolarisAssembleMixin):
    pass


def run(parent):
    h = Harness()
    results = []
    def check(name, operation):
        try:
            evidence = operation()
            results.append({"name": name, "verdict": "PASS", "evidence": evidence})
        except Exception as exc:
            results.append({"name": name, "verdict": "FAIL", "error": type(exc).__name__ + ": " + str(exc)})

    def container(name):
        return parent.createNode("subnet", name)

    def pair(p, prefix, **options):
        return {"parent": p.path(), "nodes": [{"id": "a", "type": "null", "name": prefix + "_a"},
                {"id": "b", "type": "null", "name": prefix + "_b"}],
                "connections": [{"from": "a", "to": "b", "input": 0}], "display_node": "b", **options}

    def positions(p):
        return {n.name(): list(n.position()) for n in p.children()}

    def stable():
        p = container("stable_rebuild")
        a, b = pair(p, "A"), pair(p, "B")
        h._handle_solaris_build_graph(a)
        h._handle_solaris_build_graph(b)
        before = positions(p)
        response = h._handle_solaris_build_graph(a)
        assert positions(p) == before, (before, positions(p))
        assert response["status"] == "updated", response["status"]  # display B -> A
        assert response["display_node"] == p.node("A_b").path()
        again = h._handle_solaris_build_graph(a)
        assert positions(p) == before and again["status"] == "unchanged"
        return {"display_change_status": response["status"], "repeat_status": again["status"], "positions": positions(p)}
    check("A then B then rebuild A preserves both", stable)

    def orientation():
        p = container("orientation")
        spec = pair(p, "H")
        h._handle_solaris_build_graph(spec)
        a, b = p.node("H_a"), p.node("H_b")
        assert a.position()[1] > b.position()[1]
        response = h._handle_solaris_build_graph({**spec, "layout": "horizontal", "relayout": True})
        assert a.position()[0] < b.position()[0] and a.position()[1] == b.position()[1]
        assert response["status"] == "updated"
        before = positions(p)
        again = h._handle_solaris_build_graph({**spec, "layout": "horizontal", "relayout": True})
        assert positions(p) == before and again["status"] == "unchanged"
        assert b.input(0) == a
        return {"positions": before, "repeat_status": again["status"]}
    check("vertical horizontal repeat preserves wiring", orientation)

    def outputs():
        p = container("source_output")
        spec = {"parent": p.path(), "nodes": [{"id": "s", "type": "splitscene"}, {"id": "t", "type": "null"}],
                "connections": [{"from": "s", "to": "t", "input": 0, "output": 0}]}
        h._handle_solaris_build_graph(spec)
        spec["connections"][0]["output"] = 1
        response = h._handle_solaris_build_graph(spec)
        assert p.node("t").inputConnections()[0].outputIndex() == 1
        assert response["status"] == "updated", response["status"]
        assert response["connections_made"][0]["output"] == 1
        return response["connections_made"]
    check("output changes are observed and reported", outputs)

    def append():
        p = container("existing_append")
        source, target = p.createNode("splitscene", "source"), p.createNode("merge", "target")
        target.setInput(0, source, 0)
        target.setPosition(hou.Vector2(20, -20))
        spec = {"parent": p.path(), "nodes": [{"id": "s", "existing": True, "path": source.path()},
                {"id": "t", "existing": True, "path": target.path()}],
                "connections": [{"from": "s", "to": "t", "output": 1}]}
        response = h._handle_solaris_build_graph(spec)
        ports = [(c.inputIndex(), c.outputIndex()) for c in target.inputConnections()]
        assert ports == [(0, 0), (1, 1)], ports
        again = h._handle_solaris_build_graph(spec)
        assert len(target.inputConnections()) == 2 and again["status"] == "unchanged"
        assert list(target.position()) == [20, -20]
        return {"ports": ports, "repeat_status": again["status"]}
    check("existing append distinguishes outputs and repeats once", append)

    def invalid_slot():
        p = container("invalid_slot")
        spec = {"parent": p.path(), "nodes": [{"id": n, "type": "null"} for n in ("a", "b", "m")],
                "connections": [{"from": "a", "to": "m"}, {"from": "b", "to": "m"}]}
        before = [n.path() for n in p.children()]
        refused = False
        try:
            h._handle_solaris_build_graph(spec)
        except Exception:
            refused = True
        assert refused and [n.path() for n in p.children()] == before
        return "Rejected duplicate input before creating any graph nodes"
    check("negative control duplicate input rejected before mutation", invalid_slot)

    def boxes():
        p = container("section_identity")
        ranks = {"geo": 100, "mat": 200, "cam": 400, "light": 500, "rs": 700, "out": 900}
        groups = []
        for offset, namespace in ((0, "OUT"), (20, "OUT_sceneAlt")):
            nodes = {name: p.createNode("null", namespace + "_" + name) for name in ranks}
            for i, node in enumerate(nodes.values()):
                node.setPosition(hou.Vector2(offset, -i * 2))
            _apply_section_boxes(p, nodes, ranks, namespace=namespace)
            groups.append(nodes)
        before = {b.name() for b in p.networkBoxes()}
        assert len(before) == 6, before
        _apply_section_boxes(p, groups[0], ranks, namespace="OUT")
        assert {b.name() for b in p.networkBoxes()} == before
        for i, node in enumerate(groups[0].values()):
            node.setPosition(hou.Vector2(i * 3.5, -30))
        drawn = _apply_section_boxes(p, groups[0], ranks, namespace="OUT", orientation="horizontal")
        assert len(drawn) == 3
        return {"names": sorted(b.name() for b in p.networkBoxes())}
    check("section ownership and horizontal band safety", boxes)

    def display():
        p = container("existing_display")
        a, b = p.createNode("null", "a"), p.createNode("null", "b")
        a.setDisplayFlag(True)
        response = h._handle_solaris_build_graph({"parent": p.path(), "nodes": [
            {"id": "b", "existing": True, "path": b.path()}], "display_node": "b"})
        assert a.isDisplayFlagSet()
        assert response["display_node"] == a.path(), response["display_node"]
        assert response["requested_display_node"] == b.path()
        return {"observed": response["display_node"], "requested": response["requested_display_node"]}
    check("existing display remains actual in receipt", display)

    def assembly():
        p = container("assembly")
        a, b = p.createNode("null", "a"), p.createNode("null", "b")
        refused = False
        try:
            h._handle_solaris_assemble_chain({"parent": p.path(), "mode": "nodes", "nodes": [a.path(), a.path()], "dry_run": True})
        except (ValueError, RuntimeError, SynapseUserError):
            refused = True
        assert refused and not a.inputs()
        response = h._handle_solaris_assemble_chain({"parent": p.path(), "mode": "nodes", "nodes": [a.path(), b.path()], "sort": False, "layout": "horizontal"})
        assert a.position()[0] < b.position()[0] and a.position()[1] == b.position()[1]
        return {"chain": response["chain"], "positions": positions(p)}
    check("assembly refuses duplicates and supports horizontal", assembly)

    def mixed_preview():
        p = container("mixed_preview")
        artist = p.createNode("null", "artist")
        reused = p.createNode("null", "reused")
        target = p.createNode("merge", "target")
        target.setInput(0, artist)
        target.setPosition(hou.Vector2(25, -15))
        reused.setPosition(hou.Vector2(-12, 8))
        spec = {"parent": p.path(), "nodes": [
            {"id": "fresh", "type": "null"}, {"id": "reuse", "type": "null", "name": "reused"},
            {"id": "target", "existing": True, "path": target.path()}],
            "connections": [{"from": "fresh", "to": "target"},
                            {"from": "reuse", "to": "target", "input": 1}],
            "display_node": "target", "layout": "horizontal"}
        before = positions(p)
        preview = h._handle_solaris_build_graph({**spec, "dry_run": True})
        assert positions(p) == before and len(target.inputConnections()) == 1
        assert not preview["layout"]["applied"]
        planned = preview["planned_connections"]
        assert [wire["input"] for wire in planned] == [2, 1]
        actual = h._handle_solaris_build_graph(spec)
        assert actual["connections_made"] == planned
        assert list(target.position()) == before["target"] and list(reused.position()) == before["reused"]
        assert target.input(0) == artist
        again = h._handle_solaris_build_graph(spec)
        assert again["status"] == "unchanged" and len(target.inputConnections()) == 3
        return {"plan_matches_readback": True, "ports": planned, "repeat": again["status"]}
    check("mixed ownership preview reserves explicit ports and matches apply", mixed_preview)

    def aliases():
        p = container("aliased_nodes")
        artist = p.createNode("null", "artist")
        before = positions(p)
        refused = False
        try:
            h._handle_solaris_build_graph({"parent": p.path(), "dry_run": True, "nodes": [
                {"id": "one", "existing": True, "path": artist.path()},
                {"id": "two", "existing": True, "path": p.path() + "/../" + p.name() + "/artist"}]})
        except (ValueError, RuntimeError, SynapseUserError):
            refused = True
        assert refused and positions(p) == before
        return "Two spellings of one actual node rejected without mutation"
    check("negative control aliases cannot duplicate an actual node", aliases)

    def protected_output():
        p = container("protected_output")
        source, target = p.createNode("splitscene", "s"), p.createNode("null", "t")
        target.setInput(0, source, 0)
        before = positions(p)
        refused = False
        try:
            h._handle_solaris_build_graph({"parent": p.path(), "nodes": [
                {"id": "fresh", "type": "null"},
                {"id": "s", "existing": True, "path": source.path()},
                {"id": "t", "existing": True, "path": target.path()}],
                "connections": [{"from": "s", "to": "t", "input": 0, "output": 1}]})
        except (ValueError, RuntimeError, SynapseUserError):
            refused = True
        assert refused and positions(p) == before
        assert target.inputConnections()[0].outputIndex() == 0
        return "Occupied artist input preserved, including its source output port"
    check("negative control protected output conflict rejected before mutation", protected_output)

    def failed_readback():
        import synapse.server.handlers_solaris_graph as graph
        p = container("failed_readback")
        original = graph.observed_inputs
        reads = []
        def unreadable_after_write(node):
            actual = original(node)
            reads.append(node.path())
            return {} if actual else actual
        graph.observed_inputs = unreadable_after_write
        try:
            refused = False
            try:
                h._handle_solaris_build_graph(pair(p, "fault"))
            except SynapseUserError as exc:
                refused = "readback" in str(exc).lower()
            assert refused and len(reads) >= 2
        finally:
            graph.observed_inputs = original
        return "Injected unavailable readback cannot return a verified connection"
    check("negative control failed readback cannot claim verification", failed_readback)

    def assembly_noop():
        p = container("assembly_noop")
        a, b = p.createNode("null", "a"), p.createNode("null", "b")
        b.setInput(0, a)
        before = positions(p)
        response = h._handle_solaris_assemble_chain({"parent": p.path(), "mode": "nodes", "nodes": [b.path()], "layout": "horizontal"})
        assert not response["wired"] and positions(p) == before
        assert response["layout"] == {"requested": "horizontal", "applied": False}
        return response["layout"]
    check("assembly no-op distinguishes requested from applied layout", assembly_noop)

    def versioned_rebuild():
        p = container("versioned_rebuild")
        spec = {"parent": p.path(), "nodes": [{"id": "dome", "type": "domelight"}]}
        h._handle_solaris_build_graph(spec)
        again = h._handle_solaris_build_graph(spec)
        assert again["status"] == "unchanged"
        return {"actual_type": p.node("dome").type().name(), "repeat": again["status"]}
    check("bare versioned type rebuild recognizes the created type", versioned_rebuild)

    def existing_cycle():
        p = container("existing_cycle")
        a, b = p.createNode("null", "a"), p.createNode("null", "b")
        b.setInput(0, a)
        before = positions(p)
        refused = False
        try:
            h._handle_solaris_build_graph({"parent": p.path(), "nodes": [
                {"id": "a", "existing": True, "path": a.path()},
                {"id": "b", "existing": True, "path": b.path()}],
                "connections": [{"from": "b", "to": "a"}]})
        except SynapseUserError:
            refused = True
        assert refused and not a.inputs() and b.input(0) == a and positions(p) == before
        return "Requested edge that would cycle through live wiring rejected"
    check("negative control cycle through live network rejected", existing_cycle)

    def indirect_input():
        p = container("indirect_input")
        artist = p.createNode("null", "artist")
        artist.setInput(0, p.indirectInputs()[0])
        response = h._handle_solaris_build_graph({"parent": p.path(), "nodes": [
            {"id": "artist", "existing": True, "path": artist.path()}, {"id": "out", "type": "null"}],
            "connections": [{"from": "artist", "to": "out"}]})
        assert p.node("out").input(0) == artist
        return response["connections_made"]
    check("valid subnet indirect input remains a usable boundary", indirect_input)

    def unordered_boundary():
        p = container("unordered_boundary")
        spec = {"parent": p.path(), "nodes": [{"id": "a", "type": "null"}, {"id": "s", "type": "sublayer"}],
                "connections": [{"from": "a", "to": "s", "input": 1}]}
        preview = h._handle_solaris_build_graph({**spec, "dry_run": True})
        actual = h._handle_solaris_build_graph(spec)
        assert p.node("s").input(0) is None and p.node("s").input(1) == p.node("a")
        assert actual["connections_made"] == preview["planned_connections"]
        before = positions(p)
        refused = False
        try:
            h._handle_solaris_build_graph({"parent": p.path(), "nodes": [
                {"id": "fresh", "type": "null"}, {"id": "m", "type": "merge"}],
                "connections": [{"from": "fresh", "to": "m", "input": 2}]})
        except SynapseUserError:
            refused = True
        assert refused and positions(p) == before
        return "Sublayer dedicated input may be empty; a merge gap is rejected before creation"
    check("negative control uses measured unordered boundary", unordered_boundary)

    def implicit_layout():
        p = container("implicit_layout")
        artist, merge = p.createNode("null", "artist"), p.createNode("merge", "m")
        merge.setInput(0, artist)
        spec = {"parent": p.path(), "nodes": [{"id": "a", "type": "null"}, {"id": "b", "type": "null"},
                {"id": "m", "existing": True, "path": merge.path()}],
                "connections": [{"from": "b", "to": "m"}, {"from": "a", "to": "m"}]}
        h._handle_solaris_build_graph(spec)
        assert merge.input(1) == p.node("b") and merge.input(2) == p.node("a")
        assert p.node("b").position()[0] < p.node("a").position()[0]
        return "New siblings follow resolved merge input order"
    check("implicit append layout follows actual ports", implicit_layout)

    def assembly_arity():
        p = container("assembly_arity")
        a, rop, b = [p.createNode(t, n) for t, n in (("null", "a"), ("usdrender_rop", "rop"), ("null", "b"))]
        before = positions(p)
        for dry_run in (True, False):
            refused = False
            try:
                h._handle_solaris_assemble_chain({"parent": p.path(), "mode": "nodes", "sort": False,
                    "nodes": [a.path(), rop.path(), b.path()], "dry_run": dry_run})
            except ValueError:
                refused = True
            assert refused and positions(p) == before and not b.inputs()
        return "Preview and execution both reject a render node with no output"
    check("negative control assembly arity is rejected before mutation", assembly_arity)
    return {"version": hou.applicationVersionString(), "pid": os.getpid(), "results": results,
            "verdict": "PASS" if all(r["verdict"] == "PASS" for r in results) else "FAIL"}


if __name__ == "__main__":
    assert not hou.isUIAvailable(), "Use run(disposable_parent) explicitly for an authorized GUI trial"
    parent = hou.node("/stage").createNode("subnet", "UX_network_milestone")
    record = run(parent)
    print(json.dumps(record, indent=2, sort_keys=True))
    print(record["verdict"] + ": network milestone composed live checks")
    raise SystemExit(0 if record["verdict"] == "PASS" else 1)
