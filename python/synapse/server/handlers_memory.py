"""
Synapse Memory Handler Mixin

Extracted from handlers.py -- contains memory bridge handlers and Living Memory
(scene memory) handlers for the SynapseHandler class.
"""

import os
from typing import Dict

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.aliases import resolve_param, resolve_param_with_default
from ..core.show_config import get_show_config, reload_show_config
from .handler_helpers import _HOUDINI_UNAVAILABLE


class MemoryHandlerMixin:
    """Mixin providing memory bridge and Living Memory (scene memory) handlers."""

    @staticmethod
    def _scene_paths() -> Dict:
        """Common boilerplate for Living Memory handlers.

        Returns: {hip_path, hip_dir, job_path}
        Raises RuntimeError if Houdini is not available.

        Thread-safe: dispatches hou.* calls to the main thread via
        run_on_main() to avoid crashes when called from the MCP async loop.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        from .main_thread import run_on_main
        from ..memory.scene_memory import resolve_hip_dir

        def _on_main():
            hip_path = hou.hipFile.path()
            # Must match the writer's scene-dir resolution (ensure_scene_structure)
            # so reads land on the same claude/ dir writes use -- critical for
            # unsaved/untitled scenes where dirname(hip) != the writer's dir.
            hip_dir = resolve_hip_dir(hip_path)
            job_path = hou.getenv("JOB", hip_dir)
            return {"hip_path": hip_path, "hip_dir": hip_dir, "job_path": job_path}

        return run_on_main(_on_main)

    def _handle_memory_context(self, payload: Dict) -> Dict:
        """Handle context/engram_context command."""
        bridge = self._get_bridge()  # type: ignore[attr-defined]
        return bridge.handle_memory_context(payload)

    def _augment_with_knowledge(self, query: str, result: Dict) -> Dict:
        """Additively attach a RAG corpus hit to a memory result.

        The recall/search handlers only see Moneta/project memory; the VEX
        corpus and other reference docs live in the RAG ``KnowledgeIndex`` on a
        separate retrieval path (``synapse_knowledge_lookup``). Mid-session VEX
        recall therefore returned nothing. This bridges the seam: after the
        memory lookup, consult the RAG and attach the top hit under a
        ``knowledge`` key.

        Purely additive -- existing result keys are never modified, so callers
        that ignore ``knowledge`` see no behavior change. Best-effort: never
        raises, and only attaches when the RAG actually found something.
        """
        if not query:
            return result
        try:
            knowledge = self._get_knowledge_index()  # type: ignore[attr-defined]
            if knowledge is None:
                return result
            hit = knowledge.lookup(query)
            if hit.found:
                result["knowledge_found"] = True
                result["knowledge"] = {
                    "answer": hit.answer,
                    "confidence": hit.confidence,
                    "topic": hit.topic,
                    "sources": hit.sources,
                    "reference_file": hit.reference_file,
                    "summary": hit.summary,
                }
        except Exception:
            pass
        return result

    def _handle_memory_search(self, payload: Dict) -> Dict:
        """Handle search/engram_search command.

        Augmented to also reach the RAG corpus (VEX/reference docs) so the
        memory-search path is no longer blind to the knowledge index.
        """
        bridge = self._get_bridge()  # type: ignore[attr-defined]
        result = bridge.handle_memory_search(payload)
        return self._augment_with_knowledge(payload.get("query", ""), result)

    def _handle_memory_add(self, payload: Dict) -> Dict:
        """Handle add_memory/engram_add command."""
        bridge = self._get_bridge()  # type: ignore[attr-defined]
        return bridge.handle_memory_add(payload)

    def _handle_memory_decide(self, payload: Dict) -> Dict:
        """Handle decide/engram_decide command."""
        bridge = self._get_bridge()  # type: ignore[attr-defined]
        return bridge.handle_memory_decide(payload)

    def _handle_memory_recall(self, payload: Dict) -> Dict:
        """Handle recall/engram_recall command.

        The bridge recall only matches prior DECISION memories. We additively
        bridge in the RAG corpus so a mid-session question like
        "vex @attrib promote" surfaces the VEX reference, not just decisions.
        """
        bridge = self._get_bridge()  # type: ignore[attr-defined]
        result = bridge.handle_memory_recall(payload)
        return self._augment_with_knowledge(payload.get("query", ""), result)

    def _handle_project_setup(self, payload: Dict) -> Dict:
        """Initialize or load SYNAPSE project structure for current scene."""
        from ..memory.scene_memory import ensure_scene_structure, load_full_context

        sp = self._scene_paths()
        hip_path, job_path = sp["hip_path"], sp["job_path"]

        paths = ensure_scene_structure(hip_path, job_path)
        ctx = load_full_context(sp["hip_dir"], job_path)

        # M2-I: session start is the explicit show-config reload touchpoint
        # (mcp/server.py instructs project_setup at every session start).
        # Dirs were already resolved on the main thread by _scene_paths --
        # no new hou surface here. Result keys are purely additive.
        reload_show_config()
        cfg = get_show_config(hip_dir=sp["hip_dir"], job_dir=job_path)

        return {
            "paths": paths,
            "project_memory": ctx["project"].get("content", "")[:2000],
            "scene_memory": ctx["scene"].get("content", "")[:3000],
            "agent_state": ctx["agent"],
            "evolution_stage": ctx["scene"].get("evolution", "none"),
            "suspended_tasks": [],
            "show_config": cfg.as_dict(),
            "show_config_sources": cfg.source_files,
        }

    def _handle_memory_write(self, payload: Dict) -> Dict:
        """Write a memory entry to scene or project memory."""
        from ..memory.scene_memory import write_memory_entry, ensure_scene_structure

        sp = self._scene_paths()
        paths = ensure_scene_structure(sp["hip_path"], sp["job_path"])

        entry_type = resolve_param(payload, "entry_type")
        content = resolve_param(payload, "content")
        scope = resolve_param_with_default(payload, "scope", "scene")

        if isinstance(content, str):
            content = {"content": content}
        content["scope"] = scope

        write_memory_entry(paths["scene_dir"], content, entry_type)
        return {"written": True, "entry_type": entry_type, "scope": scope}

    def _handle_memory_query(self, payload: Dict) -> Dict:
        """Query scene or project memory with section-aware ranked search."""
        from ..memory.scene_memory import load_full_context, search_memory

        sp = self._scene_paths()

        query = resolve_param(payload, "query")
        scope = resolve_param_with_default(payload, "scope", "all")
        type_filter = resolve_param_with_default(payload, "type_filter", "")

        ctx = load_full_context(sp["hip_dir"], sp["job_path"])
        results = []

        # Section-aware search with word-level scoring
        for layer_name in ("project", "scene"):
            if scope not in ("all", layer_name):
                continue
            content = ctx[layer_name].get("content", "")
            for hit in search_memory(content, query, type_filter):
                hit["layer"] = layer_name
                results.append(hit)

        # Cross-scene search
        if scope == "all" and HOU_AVAILABLE and sp["job_path"]:
            import glob as glob_mod
            current_scene_md = os.path.join(sp["hip_dir"], "claude", "memory.md")
            for scene_md in sorted(glob_mod.glob(
                os.path.join(sp["job_path"], "**", "claude", "memory.md"),
                recursive=True,
            )):
                if scene_md == current_scene_md:
                    continue
                try:
                    with open(scene_md, "r", encoding="utf-8") as f:
                        scene_content = f.read()
                except Exception:
                    continue
                scene_name = os.path.basename(
                    os.path.dirname(os.path.dirname(scene_md))
                )
                for hit in search_memory(scene_content, query, type_filter):
                    hit["layer"] = f"scene:{scene_name}"
                    results.append(hit)

        # Sort all results by score descending, stable tiebreak on layer+line
        results.sort(key=lambda r: (-r["score"], r["layer"], r["line"]))

        return {
            "query": query,
            "scope": scope,
            "type_filter": type_filter,
            "count": len(results),
            "results": results[:50],
        }

    def _handle_memory_status(self, payload: Dict) -> Dict:
        """Get memory system status."""
        from ..memory.scene_memory import get_memory_status

        sp = self._scene_paths()
        status = get_memory_status(sp["hip_dir"], sp["job_path"])

        # Single source of truth (Contract 1): the live entry store (Store A,
        # the JSONL-backed SynapseMemory) is the authority for "how many
        # entries", not the markdown file stats. Surface it here so status no
        # longer contradicts synapse_context -- which read 176 from the live
        # store while status reported 0 from a near-empty markdown file.
        try:
            bridge = self._get_bridge()  # type: ignore[attr-defined]
            synapse_mem = getattr(bridge, "_synapse", None)
            if synapse_mem is not None:
                status["entries_total"] = synapse_mem.store.count()
        except Exception:
            pass

        return status

    def _handle_evolve_memory(self, payload: Dict) -> Dict:
        """Manually trigger memory evolution."""
        from ..memory.evolution import check_evolution, evolve_to_charmeleon

        sp = self._scene_paths()
        scope = resolve_param_with_default(payload, "scope", "scene")
        dry_run = resolve_param_with_default(payload, "dry_run", True)

        claude_dir = os.path.join(sp["hip_dir"], "claude")
        status = check_evolution(claude_dir)

        if dry_run:
            return {"dry_run": True, **status}

        if status["should_evolve"] and status["target"] == "charmeleon":
            md_path = os.path.join(claude_dir, "memory.md")
            usd_path = os.path.join(claude_dir, "memory.usd")
            result = evolve_to_charmeleon(md_path, usd_path)
            return {"dry_run": False, "evolved": True, **result}

        return {"dry_run": False, "evolved": False, "reason": "No evolution needed"}

    def _handle_sleep_pass(self, payload: Dict) -> Dict:
        """Trigger Moneta consolidation/decay. DESTRUCTIVE — permanently prunes
        unprotected memories, so this command is gated APPROVE via the bridge
        (operation 'sleep_pass'; the gate fires in execute_through_bridge before
        this handler runs). Returns the prune audit so any data loss is visible.

        No-op (with a clear reason) when the active store isn't Moneta-backed,
        so it is safe under the default jsonl backend.
        """
        bridge = self._get_bridge()  # type: ignore[attr-defined]
        synapse_mem = getattr(bridge, "_synapse", None)
        store = getattr(synapse_mem, "store", None) if synapse_mem is not None else None
        if store is None or not hasattr(store, "run_sleep_pass"):
            return {"ran": False, "reason": "active memory backend is not Moneta-backed"}
        before = store.count()
        audit = store.run_sleep_pass()
        after = store.count()
        return {
            "ran": True,
            "pruned": getattr(audit, "pruned", before - after),
            "pruned_ids": list(getattr(audit, "pruned_ids", [])),
            "staged": getattr(audit, "staged", 0),
            "before": before,
            "after": after,
        }
