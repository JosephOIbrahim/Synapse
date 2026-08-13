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
        from ..memory.scene_memory import resolve_hip_dir, resolve_job_dir

        def _on_main():
            hip_path = hou.hipFile.path()
            # Must match the writer's resolution (ensure_scene_structure) so
            # reads land on the same claude/ dirs writes use -- critical for
            # unsaved/untitled scenes, where dirname(hip) != the writer's dir
            # AND $JOB points at Houdini's own install bin, which this process
            # may not write to (WinError 5). Both resolvers are idempotent.
            #
            # TWO keys, two meanings (G1a crucible, SEV 3):
            #   job_path -- the RESOLVED memory ADDRESS. Where memory is
            #               written and read back. May relocate to temp.
            #   job_root -- the RAW project ROOT ($JOB as configured). Where
            #               DISCOVERY looks: cross-scene search and show.json.
            #               A show root is routinely readable-not-writable;
            #               relocating it silently empties discovery.
            hip_dir = resolve_hip_dir(hip_path)
            job_root = hou.getenv("JOB", hip_dir)
            job_path = resolve_job_dir(job_root)
            return {"hip_path": hip_path, "hip_dir": hip_dir,
                    "job_path": job_path, "job_root": job_root}

        return run_on_main(_on_main)

    def _handle_memory_context(self, payload: Dict) -> Dict:
        """Handle context/engram_context command."""
        bridge = self._get_bridge()  # type: ignore[attr-defined]
        return bridge.handle_memory_context(payload)

    def _augment_with_knowledge(self, query: str, result: Dict) -> Dict:
        """Unify Moneta and RAG corpus results into a single result set.

        The recall/search handlers only see Moneta/project memory; the VEX
        corpus and other reference docs live in the RAG ``KnowledgeIndex`` on a
        separate retrieval path (``synapse_knowledge_lookup``). Mid-session VEX
        recall therefore returned nothing. This bridges the seam: after the
        memory lookup, consult the RAG and merge the top hit into the main
        result list, deduped by content hash and labeled by source.

        Best-effort: never raises, and only attaches when the RAG actually
        found something. The separate ``knowledge`` key is preserved for
        backward compatibility.
        """
        if not query:
            return result
        try:
            knowledge = self._get_knowledge_index()  # type: ignore[attr-defined]
            if knowledge is None:
                return result
            hit = knowledge.lookup(query)
            if not hit.found:
                return result

            import hashlib

            # Determine which list to merge into (recall uses "matches",
            # search uses "results")
            target_key = "matches" if "matches" in result else (
                "results" if "results" in result else None
            )

            # Build content hash for dedup
            content_hash = hashlib.sha256(
                (hit.answer or "").encode("utf-8")
            ).hexdigest()[:16]

            # Check for existing entries with same content hash
            existing_hashes = set()
            for entry in result.get(target_key, []) if target_key else []:
                entry_content = entry.get("content") or entry.get("answer") or ""
                existing_hashes.add(
                    hashlib.sha256(entry_content.encode("utf-8")).hexdigest()[:16]
                )

            if target_key and content_hash not in existing_hashes:
                # Shape the knowledge entry to match the target list
                if target_key == "matches":
                    knowledge_entry = {
                        "id": f"knowledge_{content_hash}",
                        "summary": hit.summary or hit.answer[:200],
                        "content": hit.answer,
                        "date": "",
                        "source": "knowledge",
                    }
                else:
                    knowledge_entry = {
                        "id": f"knowledge_{content_hash}",
                        "type": "knowledge",
                        "summary": hit.summary or hit.answer[:200],
                        "content": hit.answer,
                        "score": hit.confidence,
                        "tags": hit.sources,
                        "created_at": "",
                        "source": "knowledge",
                    }

                result.setdefault(target_key, []).append(knowledge_entry)
                result["count"] = result.get("count", 0) + 1
                if target_key == "matches":
                    result["found"] = True

            # Preserve the separate knowledge key for backward compat
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
        # show.json is DISCOVERY, not memory: read it from the raw project
        # root. A readable-but-unwritable show root must still serve its
        # config -- resolving here silently swapped a real show.json for
        # defaults (G1a crucible, proven fps 48.0 -> None).
        cfg = get_show_config(hip_dir=sp["hip_dir"],
                              job_dir=sp.get("job_root", job_path))

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

        # Cross-scene search walks the RAW project root ($JOB), not the
        # resolved memory address: on a studio layout the show root is
        # readable-not-writable, so resolving it points the glob at temp and
        # every sibling scene's memory silently vanishes from results
        # (G1a crucible, proven 2 hits -> 0).
        job_root = sp.get("job_root") or sp["job_path"]
        if scope == "all" and HOU_AVAILABLE and job_root:
            import glob as glob_mod
            current_scene_md = os.path.join(sp["hip_dir"], "claude", "memory.md")
            for scene_md in sorted(glob_mod.glob(
                os.path.join(job_root, "**", "claude", "memory.md"),
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
        """Manually trigger memory evolution (charmander -> charmeleon).

        CI0: this handler used to `from ..memory.evolution import ...`. That
        module was RETIRED in 7f7bbc39 (renamed `evolution.py.deprecated` when
        the Moneta backend superseded it) and the import was never updated, so
        every call to this handler raised ImportError -- a dead MCP tool that
        no test covered. The surviving implementation is
        `shared/evolution.py::LosslessEvolution`, a strict superset of the
        retired evolver: same markdown -> USD conversion, plus lossless
        verification with rollback, an immutable pre-evolution archive, and the
        R10 Solaris viewport sync.

        Stage names are identical on both sides -- shared/constants.py defines
        EVOLUTION_STAGE_FLAT = "charmander" / _STRUCTURED = "charmeleon" -- so
        the reply keys (`current`, `target`, `should_evolve`, `triggers_met`)
        keep the shape the retired path returned.

        W3-EVOLVE -- charizard stage: when ``target_stage == "charizard"`` this
        routes to the store-consolidation path (dry-run prune audit + a
        structural approval token; protected memories never pruned). That path
        drives the live store's public surface and does NOT depend on
        ``shared/evolution.py``, so it runs BEFORE that import guard. The default
        markdown->USD charmander->charmeleon path below is untouched.
        """
        if resolve_param_with_default(payload, "target_stage", None) == "charizard":
            return self._handle_evolve_consolidate(payload)

        try:
            from shared.constants import EVOLUTION_STAGE_STRUCTURED
            from shared.evolution import LosslessEvolution, check_evolution_triggers
        except ImportError as exc:
            # Law 3: a path that did nothing does not report success. `shared/`
            # sits at the repo root and is not part of the installed `synapse`
            # package, so a partial install can legitimately lack it.
            return {
                "status": "unavailable",
                "evolved": False,
                "error": "memory evolution unavailable: shared/evolution.py not "
                         f"importable ({type(exc).__name__}: {exc})",
            }

        sp = self._scene_paths()
        scope = resolve_param_with_default(payload, "scope", "scene")
        dry_run = resolve_param_with_default(payload, "dry_run", True)

        claude_dir = os.path.join(sp["hip_dir"], "claude")
        md_path = os.path.join(claude_dir, "memory.md")
        usd_path = os.path.join(claude_dir, "memory.usd")

        check = check_evolution_triggers(md_path)
        status = {
            "should_evolve": check.should_evolve,
            "triggers_met": check.triggers_met,
            "triggers_pending": check.triggers_pending,
            "current": check.current_stage,
            "target": check.target_stage if check.should_evolve else None,
        }

        if dry_run:
            return {"dry_run": True, **status}

        if check.should_evolve and check.target_stage == EVOLUTION_STAGE_STRUCTURED:
            result = LosslessEvolution().evolve_to_structured(md_path, usd_path)
            # `evolved` reports what HAPPENED, not what was attempted: the
            # lossless verify can refuse and roll back, and that must not read
            # as a success.
            return {
                "dry_run": False,
                "evolved": result.evolved,
                "stage": result.stage,
                "fidelity": result.fidelity,
                "archive": result.archive_path,
                "reason": result.reason,
                **status,
            }

        return {"dry_run": False, "evolved": False, "reason": "No evolution needed",
                **status}

    def _handle_evolve_consolidate(self, payload: Dict) -> Dict:
        """charmeleon->charizard store consolidation (W3-EVOLVE, S6 Phase 4).

        Dry-run (the default) returns the full prune audit -- merge list, prune
        list with ids, before/after counts -- and mutates NOTHING. Apply
        (``dry_run=False``) requires an explicit ``approval_token`` (obtained from
        a prior dry-run) and refuses loudly without it. Protected memories are
        structurally excluded from pruning. Reaches the live store the same way
        ``_handle_sleep_pass`` does.
        """
        from ..memory.consolidation import (
            apply_consolidation, plan_consolidation,
            ConsolidationNotApproved, ConsolidationUnsupported,
        )

        bridge = self._get_bridge()  # type: ignore[attr-defined]
        synapse_mem = getattr(bridge, "_synapse", None)
        store = getattr(synapse_mem, "store", None) if synapse_mem is not None else None
        if store is None or not hasattr(store, "all"):
            return {"stage": "charizard", "ran": False, "applied": False,
                    "reason": "no active memory store"}

        dry_run = resolve_param_with_default(payload, "dry_run", True)
        approval_token = resolve_param_with_default(payload, "approval_token", None)

        if dry_run:
            # Pure preview over the live corpus -- no mutation, no backup.
            audit = plan_consolidation(store.all())
            return {"stage": "charizard", "ran": True, **audit.to_dict()}

        try:
            audit = apply_consolidation(store, approval_token=approval_token)
        except ConsolidationNotApproved as exc:
            # Preview-then-approve is structural: an unapproved apply never mutates.
            return {"stage": "charizard", "ran": True, "dry_run": False,
                    "applied": False, "refused": True, "error": str(exc)}
        except ConsolidationUnsupported as exc:
            # Honest UNKNOWN on the append/consolidate Moneta backend (W3-HARDEN).
            return {"stage": "charizard", "ran": True, "dry_run": False,
                    "applied": False, "supported": False, "error": str(exc)}
        return {"stage": "charizard", "ran": True, **audit.to_dict()}

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

        # Wrap the prune in an Operation so the APPROVE gate fires before
        # execution.  The LosslessExecutionBridge handles consent, undo
        # grouping, and integrity verification.
        def _do_prune() -> Dict:
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

        try:
            from shared.bridge import Operation, get_process_bridge
            from shared.types import AgentID
            exec_bridge = get_process_bridge()
            op = Operation(
                agent_id=AgentID.CONDUCTOR,
                operation_type="sleep_pass",
                summary="Moneta sleep pass: consolidate/decay unprotected memories",
                fn=_do_prune,
            )
            result = exec_bridge.execute(op)
            if result.success and result.result is not None:
                return result.result
            return {"ran": False, "error": result.error or "Bridge execution failed"}
        except ImportError:
            # Fallback: direct execution (standalone/test mode, no bridge)
            return _do_prune()
        except Exception as exc:
            logger.warning(
                "Bridge unavailable for sleep pass (%s: %s); "
                "falling back to direct execution",
                type(exc).__name__, exc,
            )
            return _do_prune()
