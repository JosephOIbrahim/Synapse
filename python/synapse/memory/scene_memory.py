"""
Synapse Scene Memory -- Living Memory System

Persistent, layered memory that lives alongside Houdini scene files.
Memory evolves: Flat (markdown) -> Structured (USD) -> Composed (composed USD).

This module handles all file operations for the scene memory system.
Every function is idempotent, non-destructive, and encoding-safe.
"""

import logging
import os
import tempfile
import threading
import time
from typing import Dict, List, Optional, Any

from .models import Memory, MemoryType

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    hou = None
    HOU_AVAILABLE = False

logger = logging.getLogger("synapse.scene_memory")

# Schema version for memory files
SCHEMA_VERSION = "0.1.0"

# Process-safe file locking for concurrent writes
# Uses filelock (cross-platform) when available, falls back to threading.Lock
try:
    from filelock import FileLock as _FileLock
    _FILELOCK_AVAILABLE = True
except ImportError:
    _FILELOCK_AVAILABLE = False

_thread_locks: Dict[str, threading.Lock] = {}
_thread_locks_lock = threading.Lock()


class _ProcessFileLock:
    """Context manager that combines process-level and thread-level locking.

    Process lock: filelock.FileLock on ``path + '.lock'``
    Thread lock: threading.Lock per path (for in-process concurrency)

    Falls back to thread-only if filelock is unavailable.
    """

    def __init__(self, path: str, timeout: float = 10.0):
        self._path = path
        self._timeout = timeout
        # Thread lock
        with _thread_locks_lock:
            if path not in _thread_locks:
                _thread_locks[path] = threading.Lock()
            self._thread_lock = _thread_locks[path]
        # Process lock (optional)
        self._file_lock = None
        if _FILELOCK_AVAILABLE:
            self._file_lock = _FileLock(path + ".lock", timeout=timeout)

    def __enter__(self):
        self._thread_lock.acquire()
        try:
            if self._file_lock is not None:
                self._file_lock.acquire()
        except Exception:
            self._thread_lock.release()
            raise
        return self

    def __exit__(self, *exc):
        try:
            if self._file_lock is not None:
                self._file_lock.release()
        finally:
            self._thread_lock.release()
        return False


def _get_file_lock(path: str) -> _ProcessFileLock:
    """Get a process-safe file lock for the given path."""
    return _ProcessFileLock(path)


# =============================================================================
# DIRECTORY & FILE MANAGEMENT
# =============================================================================

#: Parents whose ``claude/`` could not be created here, mapped to where the
#: memory actually went. Populated by the writer AND by the read-side probe, so
#: readers follow the writer without re-deriving anything (see the resolver
#: contract in ``resolve_hip_dir``). Process-local: an address is a runtime
#: fact about THIS host, never persisted.
_RELOCATED: Dict[str, str] = {}
_RELOCATED_LOCK = threading.Lock()


def unsaved_memory_base() -> str:
    """Where an UNSAVED scene's memory lives: ``$HOUDINI_TEMP_DIR/untitled``.

    Deliberately the SAME root ``store._resolve_project_path`` routes an
    unsaved scene's ``.synapse`` store to (C-0 / PR #60, commit 19c299b). The
    two memory subsystems must address one scene at one place; divergence
    between them is its own bug.

    Outside Houdini (tests/CI) the ``$HOUDINI_TEMP_DIR`` environment variable
    wins, then the platform temp dir -- always somewhere writable, never the
    process working directory.

    An UNEXPANDED result is rejected: when the variable is undefined
    ``expandString`` hands the token straight back, and joining it would
    create a literal ``$HOUDINI_TEMP_DIR`` directory wherever the process
    happens to be standing -- the same "address nobody can predict" class of
    bug this whole module is fixing.
    """
    _TOKEN = "$HOUDINI_TEMP_DIR"
    if HOU_AVAILABLE:
        try:
            expanded = hou.text.expandString(_TOKEN)
            if expanded and expanded.strip() != _TOKEN:
                return os.path.normpath(os.path.join(expanded, "untitled"))
        except Exception:
            pass
    env = os.environ.get("HOUDINI_TEMP_DIR")
    if env:
        return os.path.normpath(os.path.join(env, "untitled"))
    return os.path.normpath(
        os.path.join(tempfile.gettempdir(), "synapse", "untitled")
    )


def _hip_is_unsaved(hip_path: str) -> bool:
    """Delegate to ``store.hip_is_unsaved`` -- one detector, one verdict.

    Never re-implemented here: a second unsaved-scene detector is how the two
    subsystems would drift apart again. The absolute-import fallback exists
    because ``tests/test_scene_memory.py`` loads this file as a TOP-LEVEL
    module via ``importlib.util.spec_from_file_location``, where the relative
    import has no parent package.
    """
    try:
        from .store import hip_is_unsaved as _impl
    except (ImportError, ValueError):
        try:
            from synapse.memory.store import hip_is_unsaved as _impl
        except ImportError:
            # store unreachable -> assume saved and let the writability probe
            # decide. Guessing "unsaved" here would relocate real project
            # memory on an import accident.
            return False
    return bool(_impl(hip_path, hou))


def _can_create_under(parent: str) -> bool:
    """True when this process may create a directory under *parent*.

    Probes the nearest EXISTING ancestor by creating and deleting a temp file
    there -- exactly the permission ``os.makedirs`` needs, and nothing is left
    behind. ``os.access(path, os.W_OK)`` is deliberately NOT used: on Windows
    it reports the read-only ATTRIBUTE, not the ACL, so an ACL-protected
    directory like ``C:/Program Files/...`` reads writable and the WinError 5
    arrives later, at makedirs, in front of the artist.
    """
    probe = os.path.abspath(parent)
    while not os.path.isdir(probe):
        nxt = os.path.dirname(probe)
        if nxt == probe:
            return False
        probe = nxt
    try:
        fd, tmp = tempfile.mkstemp(prefix=".synapse-probe-", dir=probe)
    except (PermissionError, OSError):
        return False
    try:
        os.close(fd)
    except OSError:
        pass
    try:
        os.unlink(tmp)
    except OSError:
        pass
    return True


def _record_relocation(parent: str, fallback: str, kind: str, reason: str) -> None:
    """Remember (and announce, once per parent) that memory moved.

    LOUDNESS over silence: never write somewhere the caller cannot predict
    without naming the attempted path, the fallback and the reason.
    """
    parent = os.path.normpath(parent)
    with _RELOCATED_LOCK:
        if parent in _RELOCATED:
            return
        _RELOCATED[parent] = fallback
    logger.warning(
        "Scene memory relocated: %s memory cannot live at %s (%s). "
        "Using %s instead. Nothing is carried over from the original path.",
        kind, os.path.join(parent, "claude"), reason, os.path.join(fallback, "claude"),
    )


def _resolve_memory_parent(parent: str, kind: str) -> str:
    """Resolve the directory whose ``claude/`` actually holds memory.

    Order, and why:

    1. ``parent/claude`` already exists -> that IS the address. Never probed,
       so a populated but read-only project dir keeps being read from where it
       is.
    2. A recorded relocation for this parent -> follow it. This is what keeps
       readers on the writer's address after an unpredicted makedirs failure.
    3. Writable -> use it.
    4. Otherwise -> ``unsaved_memory_base()``, recorded + warned.
    """
    parent = os.path.normpath(parent)
    if os.path.isdir(os.path.join(parent, "claude")):
        return parent
    with _RELOCATED_LOCK:
        recorded = _RELOCATED.get(parent)
    if recorded is not None:
        return recorded
    if _can_create_under(parent):
        return parent
    fallback = unsaved_memory_base()
    if os.path.normpath(fallback) == parent:
        return parent  # nowhere left to go; the makedirs guard will raise
    _record_relocation(parent, fallback, kind, "not writable by this process")
    return fallback


def resolve_hip_dir(hip_path: str) -> str:
    """Resolve the directory whose ``claude/`` holds this scene's memory.

    For a SAVED hip (a real file on disk) that is the file's parent directory.
    For an UNSAVED/untitled hip it is ``unsaved_memory_base()`` -- Houdini
    reports a full path under its own install dir for a never-saved scene
    (``C:/Program Files/.../Houdini 22.0.397/bin/untitled.hip``), so the hip
    path itself is not somewhere this process may write. Trusting it raw is
    what made ``synapse_memory_write`` die with
    ``PermissionError WinError 5: '<install>/bin/claude'``.

    Single source of truth: readers (status, context, query, project_setup)
    and the writer (ensure_scene_structure) MUST resolve this identically, or
    they read and write different ``claude/`` dirs. Every branch here is a
    pure function of the hip path plus on-disk facts both sides can observe,
    so both sides land on the same directory. Pinned by
    ``tests/test_g1a_scene_memory_address.py``.

    Idempotent: ``resolve_hip_dir(resolve_hip_dir(p))`` == ``resolve_hip_dir(p)``.
    """
    hip_path = os.path.normpath(hip_path or ".")
    if _hip_is_unsaved(hip_path):
        return unsaved_memory_base()
    base = os.path.dirname(hip_path) if os.path.isfile(hip_path) else hip_path
    return _resolve_memory_parent(base, "scene")


def resolve_job_dir(job_path: str) -> str:
    """Resolve the directory whose ``claude/`` holds PROJECT memory.

    Normally ``$JOB``. For an unsaved scene Houdini leaves ``$JOB`` pointing at
    its own install ``bin`` -- the directory that produced the WinError 5 --
    so the same writability contract applies here as to the scene dir. Readers
    (``load_full_context``, ``get_memory_status``) and the writer
    (``ensure_scene_structure``) all route through this one function.

    Idempotent, same as ``resolve_hip_dir``.
    """
    job_path = os.path.normpath(job_path or ".")
    return _resolve_memory_parent(job_path, "project")


def _makedirs_or_relocate(parent: str, kind: str) -> str:
    """``makedirs(parent/claude)``; on refusal relocate rather than raise.

    ``os.makedirs`` must never be the thing that surfaces to the artist. The
    resolvers above already steer away from unwritable addresses; this is the
    last line for what they could not predict (a race, a revoked ACL, a full
    or read-only volume). The relocation is recorded so every subsequent
    reader resolves to the same place. Only if the fallback ALSO fails does
    this raise.
    """
    target = os.path.join(parent, "claude")
    try:
        os.makedirs(target, exist_ok=True)
        return target
    except OSError as exc:
        fallback_parent = unsaved_memory_base()
        if os.path.normpath(fallback_parent) == os.path.normpath(parent):
            raise
        _record_relocation(parent, fallback_parent, kind, f"{type(exc).__name__}: {exc}")
        fallback = os.path.join(fallback_parent, "claude")
        os.makedirs(fallback, exist_ok=True)
        return fallback


def ensure_scene_structure(hip_path: str, job_path: str) -> Dict[str, str]:
    """
    Create claude/ directories at $JOB and $HIP levels if they don't exist.
    Seed memory.md and agent.usd if they don't exist.

    Returns paths dict:
        {project_dir, scene_dir, project_md, scene_md, agent_usd}

    Idempotent: safe to call repeatedly. Never overwrites existing files.

    Addresses come from ``resolve_hip_dir`` / ``resolve_job_dir`` -- the same
    two functions every reader uses -- so the writer can never land on a
    ``claude/`` the readers do not look in.
    """
    hip_path = os.path.normpath(hip_path)
    job_path = os.path.normpath(job_path)

    hip_dir = resolve_hip_dir(hip_path)
    job_dir = resolve_job_dir(job_path)
    hip_name = os.path.basename(hip_path)
    job_name = os.path.basename(job_path)

    project_dir = _makedirs_or_relocate(job_dir, "project")
    scene_dir = _makedirs_or_relocate(hip_dir, "scene")

    # Seed project.md
    project_md = os.path.join(project_dir, "project.md")
    if not os.path.exists(project_md):
        seed_project_md(project_md, job_name, fps=24.0)

    # Seed scene memory.md
    scene_md = os.path.join(scene_dir, "memory.md")
    if not os.path.exists(scene_md):
        seed_scene_md(scene_md, hip_name, job_name)

    # Seed agent.usd
    agent_usd = os.path.join(scene_dir, "agent.usd")
    if not os.path.exists(agent_usd):
        try:
            from .agent_state import initialize_agent_usd
            initialize_agent_usd(agent_usd)
        except ImportError:
            _seed_agent_usd_stub(agent_usd)

    paths = {
        "project_dir": project_dir,
        "scene_dir": scene_dir,
        "project_md": project_md,
        "scene_md": scene_md,
        "agent_usd": agent_usd,
    }
    logger.info("Scene structure ready: %s", scene_dir)
    return paths


def seed_project_md(path: str, job_name: str, fps: float = 24.0) -> None:
    """Create initial project.md with header and empty sections. Process-safe."""
    now = _now()
    content = (
        f"# Project Memory: {job_name}\n"
        f"# Created: {now}\n"
        f"# Evolution: Flat (markdown)\n"
        f"# Schema: {SCHEMA_VERSION}\n\n---\n\n"
        f"## Pipeline Configuration\n"
        f"- **Frame Rate:** {fps}fps\n\n"
        f"## Key Decisions\n\n"
        f"## Notes\n"
    )
    lock = _get_file_lock(path)
    with lock:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    logger.info("Seeded project.md: %s", path)


def seed_scene_md(path: str, scene_name: str, project_name: str) -> None:
    """Create initial memory.md with header. Process-safe."""
    now = _now()
    content = (
        f"# Scene Memory: {scene_name}\n"
        f"# Project: {project_name}\n"
        f"# Created: {now}\n"
        f"# Evolution: Flat (markdown)\n"
        f"# Schema: {SCHEMA_VERSION}\n\n---\n\n"
    )
    lock = _get_file_lock(path)
    with lock:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    logger.info("Seeded memory.md: %s", path)


def _seed_agent_usd_stub(path: str) -> None:
    """Create a placeholder agent.usd file. Full USD impl in Phase 2."""
    # Write a minimal USDA that can be parsed later
    content = (
        '#usda 1.0\n'
        '(\n'
        f'    customLayerData = {{\n'
        f'        string "synapse:version" = "{SCHEMA_VERSION}"\n'
        f'        string "synapse:type" = "agent_state"\n'
        f'        string "synapse:status" = "idle"\n'
        f'    }}\n'
        ')\n\n'
        'def Xform "SYNAPSE"\n'
        '{\n'
        '    def Xform "agent"\n'
        '    {\n'
        '    }\n'
        '}\n'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("Seeded agent.usd stub: %s", path)


def _now() -> str:
    """UTC timestamp string."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# =============================================================================
# MEMORY READ/WRITE OPERATIONS
# =============================================================================

def load_memory(claude_dir: str, name: str = "memory") -> Dict[str, Any]:
    """
    Load memory from either USD or markdown, preferring USD if evolved.

    Returns: {format: "md"|"usd"|"none", path: str, content: str, evolution: str}
    """
    claude_dir = os.path.normpath(claude_dir)
    usd_path = os.path.join(claude_dir, f"{name}.usd")
    md_path = os.path.join(claude_dir, f"{name}.md")

    if os.path.exists(usd_path) and name != "agent":
        # Check if it's a real evolved USD (not the agent stub)
        try:
            content = _read_file(usd_path)
            if '"synapse:type" = "agent_state"' not in content:
                return {
                    "format": "usd",
                    "path": usd_path,
                    "content": content,
                    "evolution": "charmeleon",
                }
        except Exception as e:
            logger.warning("Could not read USD %s: %s", usd_path, e)

    if os.path.exists(md_path):
        content = _read_file(md_path)
        return {
            "format": "md",
            "path": md_path,
            "content": content,
            "evolution": "charmander",
        }

    return {
        "format": "none",
        "path": "",
        "content": "",
        "evolution": "none",
    }


def write_session_start(scene_dir: str, goal: str = "") -> None:
    """Append session start header to memory.md."""
    md_path = os.path.join(scene_dir, "memory.md")
    if not os.path.exists(md_path):
        return

    now = _now()
    date = now.split("T")[0]
    time_str = now.split("T")[1].rstrip("Z")

    lines = [
        f"\n## Session {date} {time_str}\n",
    ]
    if goal:
        lines.append(f"**Goal:** {goal}\n")
    lines.append("")

    with open(md_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info("Session start written to %s", md_path)


def write_decision(scene_dir: str, decision: Dict[str, str], scope: str = "scene") -> None:
    """
    Write decision to memory.

    decision: {name, choice, reasoning, alternatives}
    scope: "scene" | "project" | "both"
    """
    entry = (
        f"### Decision: {decision.get('name', 'Untitled')}\n"
        f"**Choice:** {decision.get('choice', '')}\n"
        f"**Reasoning:** {decision.get('reasoning', '')}\n"
    )
    alternatives = list(decision.get("alternatives", []))
    if alternatives:
        entry += "**Alternatives:**\n"
        for alt in alternatives:
            entry += f"- {alt}\n"
    entry += "\n"

    if scope in ("scene", "both"):
        _append_to_md(os.path.join(scene_dir, "memory.md"), entry)

    if scope in ("project", "both"):
        # scene_dir is $HIP/claude, project is $JOB/claude
        # Caller provides project_dir explicitly via write_memory_entry
        project_md = _find_project_md(scene_dir)
        if project_md:
            _append_to_md(project_md, entry)


def write_parameter_experiment(scene_dir: str, experiment: Dict[str, Any]) -> None:
    """Write parameter experiment. experiment: {node, parm, before, after, result}"""
    entry = (
        f"### Parameter: {experiment.get('node', '')} / {experiment.get('parm', '')}\n"
        f"- **Before:** {experiment.get('before', '')}\n"
        f"- **After:** {experiment.get('after', '')}\n"
        f"- **Result:** {experiment.get('result', '')}\n\n"
    )
    _append_to_md(os.path.join(scene_dir, "memory.md"), entry)


def write_blocker(scene_dir: str, blocker: Dict[str, Any]) -> None:
    """Write blocker entry. blocker: {description, attempts, status}"""
    status = blocker.get("status", "open")
    prefix = "Blocker" if status == "open" else "Blocker Resolved"
    entry = (
        f"### {prefix}: {blocker.get('description', '')}\n"
        f"- **Attempts:** {blocker.get('attempts', '')}\n"
        f"- **Status:** {status}\n\n"
    )
    _append_to_md(os.path.join(scene_dir, "memory.md"), entry)


def write_session_end(scene_dir: str, summary: Dict[str, Any]) -> None:
    """
    Append a session-end block -- but only when there is something to record.

    A bare timestamp (no accomplishments, next actions, or summary text) is
    NOT written. Those bodyless writes produced the ~200 empty
    '### Session End' stubs that bloated memory.md and slowed session-start
    parsing (Mile 1 / C-2). Skipping them here is what stops the spam from
    regrowing after a one-time prune.

    summary: {stopped_at, summary_text, next_actions, accomplishments}
    """
    accomplishments = summary.get("accomplishments", [])
    next_actions = summary.get("next_actions", [])
    summary_text = (summary.get("summary_text") or "").strip()

    if not accomplishments and not next_actions and not summary_text:
        return  # no body -> don't write a bare stub

    entry = (
        f"### Session End\n"
        f"- **Stopped at:** {summary.get('stopped_at', _now())}\n"
    )
    if summary_text:
        entry += f"\n{summary_text}\n"
    if accomplishments:
        entry += "- **Accomplished:**\n"
        for a in accomplishments:
            entry += f"  - {a}\n"
    if next_actions:
        entry += "- **Next:**\n"
        for n in next_actions:
            entry += f"  - {n}\n"
    entry += "\n---\n\n"

    _append_to_md(os.path.join(scene_dir, "memory.md"), entry)


def _is_bare_session_end(section_lines: List[str]) -> bool:
    """True if a '### ' section is a bodyless Session End (timestamp only)."""
    if not section_lines or section_lines[0].strip() != "### Session End":
        return False
    body = [l for l in section_lines[1:] if l.strip() and l.strip() != "---"]
    return len(body) == 1 and body[0].strip().startswith("- **Stopped at:**")


def compact_memory(scene_dir: str, dry_run: bool = True, backup: bool = True) -> Dict[str, Any]:
    """Strip bodyless '### Session End' stubs from a scene memory.md.

    Idempotent maintenance op. Preserves the preamble and every section that
    carries real content (Notes, decisions, session-ends WITH a body). Backs
    up before writing so the prune is reversible. This is the reusable form of
    the one-time Mile 1 prune -- safe to sweep across many scenes.

    Returns a report: {path, exists, stubs_before, stubs_after, removed,
                       bytes_before, bytes_after, changed, dry_run, backup_path}.
    """
    path = os.path.join(scene_dir, "memory.md")
    report: Dict[str, Any] = {
        "path": path, "exists": False, "stubs_before": 0, "stubs_after": 0,
        "removed": 0, "bytes_before": 0, "bytes_after": 0,
        "changed": False, "dry_run": dry_run, "backup_path": None,
    }
    if not os.path.exists(path):
        return report

    content = _read_file(path)
    report["exists"] = True
    report["stubs_before"] = content.count("### Session End")
    report["bytes_before"] = len(content.encode("utf-8"))

    # Parse into a preamble (everything before the first '### ' header) plus
    # one section per '### ' header. Separator '---' lines are normalised away
    # and re-added on join, so dropping a stub never orphans a separator.
    preamble: List[str] = []
    sections: List[List[str]] = []
    cur: Optional[List[str]] = None
    for ln in content.splitlines():
        if ln.startswith("### "):
            if cur is not None:
                sections.append(cur)
            cur = [ln]
        elif cur is None:
            preamble.append(ln)
        else:
            cur.append(ln)
    if cur is not None:
        sections.append(cur)

    kept: List[str] = []
    removed = 0
    for sec in sections:
        if _is_bare_session_end(sec):
            removed += 1
            continue
        text = "\n".join(l for l in sec if l.strip() != "---").strip()
        if text:
            kept.append(text)

    report["removed"] = removed
    if removed == 0:
        report["stubs_after"] = report["stubs_before"]
        report["bytes_after"] = report["bytes_before"]
        return report

    pre = "\n".join(l for l in preamble if l.strip() != "---").rstrip()
    parts = ([pre] if pre else []) + kept
    new_content = "\n\n---\n\n".join(parts).rstrip() + "\n"
    report["stubs_after"] = new_content.count("### Session End")
    report["bytes_after"] = len(new_content.encode("utf-8"))
    report["changed"] = True

    if not dry_run:
        if backup:
            import shutil
            backup_path = path + ".compact.bak"
            shutil.copy2(path, backup_path)
            report["backup_path"] = backup_path
        with _get_file_lock(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)

    return report


def write_memory_entry(scene_dir: str, entry: Dict[str, Any], entry_type: str) -> None:
    """
    Write a memory entry to the scene's memory file.

    entry_type: session_start, session_end, decision, parameter_experiment,
                blocker, blocker_resolved, asset_reference, wedge_result, note
    """
    writers = {
        "session_start": lambda: write_session_start(scene_dir, entry.get("goal", "")),
        "session_end": lambda: write_session_end(scene_dir, entry),
        "decision": lambda: write_decision(scene_dir, entry, entry.get("scope", "scene")),
        "parameter_experiment": lambda: write_parameter_experiment(scene_dir, entry),
        "blocker": lambda: write_blocker(scene_dir, {**entry, "status": "open"}),
        "blocker_resolved": lambda: write_blocker(scene_dir, {**entry, "status": "resolved"}),
        "asset_reference": lambda: _write_generic_entry(scene_dir, "Asset Reference", entry),
        "wedge_result": lambda: _write_generic_entry(scene_dir, "Wedge Result", entry),
        "note": lambda: _write_generic_entry(scene_dir, "Note", entry),
    }
    writer = writers.get(entry_type)
    if writer:
        writer()

        # Also deposit into the Moneta store for unified recall
        try:
            from .store import get_synapse_memory, MemoryStore
            syn = get_synapse_memory()
            if hasattr(syn.store, 'add') and not isinstance(syn.store, MemoryStore):
                syn.store.add(Memory(
                    content=entry.get("content", ""),
                    memory_type=MemoryType.NOTE,
                    tags=entry.get("tags", []) or [],
                    source="auto",
                ))
                logger.debug(
                    "Moneta deposit from scene_memory succeeded: type=%s, tags=%s",
                    entry_type, entry.get("tags", []),
                )
        except Exception as exc:
            logger.debug("Moneta deposit from scene_memory failed (non-critical): %s", exc)

    else:
        logger.warning("Unknown entry type: %s", entry_type)


def load_full_context(hip_dir: str, job_dir: str) -> Dict[str, Any]:
    """
    Load all memory layers into a single context dict.

    Returns: {project: {...}, scene: {...}, agent: {...}, summary: str}
    Truncates to ~8000 tokens max, prioritizing recent sessions and unresolved blockers.

    Both dirs are re-resolved through the shared resolvers so this reader can
    never look in a different ``claude/`` than ``ensure_scene_structure``
    wrote to. The resolvers are idempotent, so an already-resolved dir passes
    through unchanged -- and a caller that hand-rolled ``dirname(hip)``
    (``houdini/scripts/python/synapse_shelf.py``) is corrected here.
    """
    hip_dir = resolve_hip_dir(os.path.normpath(hip_dir))
    job_dir = resolve_job_dir(os.path.normpath(job_dir))

    project_claude = os.path.join(job_dir, "claude")
    scene_claude = os.path.join(hip_dir, "claude")

    project = load_memory(project_claude, "project") if os.path.isdir(project_claude) else {
        "format": "none", "path": "", "content": "", "evolution": "none"
    }
    scene = load_memory(scene_claude, "memory") if os.path.isdir(scene_claude) else {
        "format": "none", "path": "", "content": "", "evolution": "none"
    }

    # Agent state
    agent = {"status": "idle", "has_suspended_tasks": False, "suspended_count": 0}
    try:
        from .agent_state import load_agent_state
        agent = load_agent_state(scene_claude)
    except ImportError:
        agent_usd = os.path.join(scene_claude, "agent.usd")
        if os.path.exists(agent_usd):
            agent["path"] = agent_usd

    # Build summary text with smart prioritization
    summary_parts = []

    if project["content"]:
        decisions = _extract_decisions(project["content"])
        if decisions:
            summary_parts.append("## Project Decisions\n" + "\n".join(decisions))
        else:
            summary_parts.append("## Project Context\n" + _truncate(project["content"], 2000))

    if scene["content"]:
        blockers = _extract_blockers(scene["content"])
        recent = _extract_recent_sessions(scene["content"], max_sessions=3)
        decisions = _extract_decisions(scene["content"])

        if blockers:
            summary_parts.append("## Active Blockers\n" + "\n".join(blockers))
        if decisions:
            summary_parts.append("## Scene Decisions\n" + "\n".join(decisions))
        if recent:
            summary_parts.append("## Recent Sessions\n" + "\n".join(recent))

        # Fill remaining budget with older content
        budget_used = sum(len(p) for p in summary_parts)
        if budget_used < 6000 and not (blockers or decisions or recent):
            summary_parts.append("## Scene Memory\n" + _truncate(scene["content"], 6000 - budget_used))

    summary = "\n\n".join(summary_parts) if summary_parts else "No memory loaded."

    return {
        "project": project,
        "scene": scene,
        "agent": agent,
        "summary": summary,
    }


# =============================================================================
# HELPERS
# =============================================================================

def _read_file(path: str) -> str:
    """Read a file with UTF-8 encoding."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _append_to_md(md_path: str, text: str) -> None:
    """Append text to a markdown file if it exists. Process-safe."""
    if not os.path.exists(md_path):
        logger.warning("Cannot append to missing file: %s", md_path)
        return
    lock = _get_file_lock(md_path)
    with lock:
        with open(md_path, "a", encoding="utf-8") as f:
            f.write(text)


def _write_generic_entry(scene_dir: str, title: str, entry: Dict[str, Any]) -> None:
    """Write a generic markdown entry."""
    content = entry.get("content", "")
    if isinstance(content, dict):
        import json
        content = json.dumps(content, indent=2, sort_keys=True)
    text = f"### {title}\n{content}\n\n"
    _append_to_md(os.path.join(scene_dir, "memory.md"), text)


def _find_project_md(scene_dir: str) -> Optional[str]:
    """Walk up from scene claude dir to find project.md."""
    # scene_dir is $HIP/claude, project is $JOB/claude
    # Walk up: $HIP/claude -> $HIP -> parent -> parent/claude
    current = os.path.dirname(scene_dir)  # $HIP
    for _ in range(5):  # max depth
        parent = os.path.dirname(current)
        if parent == current:
            break
        candidate = os.path.join(parent, "claude", "project.md")
        if os.path.exists(candidate):
            return candidate
        current = parent
    return None


def _extract_blockers(content: str) -> List[str]:
    """Extract unresolved blocker sections from markdown memory."""
    import re
    blockers = []
    for match in re.finditer(
        r'### Blocker: (.+?)(?=\n###|\n## |\Z)', content, re.DOTALL
    ):
        block = match.group(1)
        if "**Status:** resolved" not in block:
            blockers.append("- " + block.strip()[:200])
    return blockers


def _extract_decisions(content: str) -> List[str]:
    """Extract decision summaries from markdown memory."""
    import re
    decisions = []
    for match in re.finditer(
        r'### Decision: (.+?)\n.*?\*\*Choice:\*\* (.+)', content
    ):
        decisions.append(f"- {match.group(1).strip()}: {match.group(2).strip()}")
    return decisions


def _extract_recent_sessions(content: str, max_sessions: int = 3) -> List[str]:
    """Extract last N session blocks from markdown memory."""
    import re
    sessions = re.findall(
        r'(## Session .+?)(?=\n## Session |\Z)', content, re.DOTALL
    )
    return [s.strip()[:500] for s in sessions[-max_sessions:]]


def _truncate(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, preserving complete lines."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_newline = truncated.rfind("\n")
    if last_newline > max_chars // 2:
        truncated = truncated[:last_newline]
    return truncated + "\n...(truncated)"


def _parse_sections(content: str) -> List[Dict[str, Any]]:
    """Split markdown memory into typed sections.

    Each section has: type, title, text, line.
    Section types: session, decision, parameter, blocker, blocker_resolved,
    note, wedge, session_end, header.
    """
    import re

    sections: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {"type": "header", "title": "", "text": "", "line": 1}

    _SECTION_PATTERNS = [
        ("## Session ", "session"),
        ("### Decision:", "decision"),
        ("### Parameter:", "parameter"),
        ("### Blocker", None),          # special: resolved vs open
        ("### Note", "note"),
        ("### Wedge", "wedge"),
        ("### Session End", "session_end"),
    ]

    for i, line in enumerate(content.split("\n"), 1):
        matched = False
        for prefix, sec_type in _SECTION_PATTERNS:
            if not line.startswith(prefix):
                continue
            if current["text"].strip():
                sections.append(current)

            if prefix == "### Blocker":
                is_resolved = "Resolved" in line
                current = {
                    "type": "blocker_resolved" if is_resolved else "blocker",
                    "title": re.sub(r'^### Blocker\s*(Resolved)?:\s*', '', line).strip(),
                    "text": line + "\n",
                    "line": i,
                }
            elif prefix == "### Decision:":
                current = {
                    "type": "decision",
                    "title": line.replace("### Decision:", "").strip(),
                    "text": line + "\n",
                    "line": i,
                }
            elif prefix == "### Parameter:":
                current = {
                    "type": "parameter",
                    "title": line.replace("### Parameter:", "").strip(),
                    "text": line + "\n",
                    "line": i,
                }
            else:
                current = {
                    "type": sec_type,
                    "title": line.strip("# \n") if sec_type != "session_end" else "Session End",
                    "text": line + "\n",
                    "line": i,
                }
            matched = True
            break
        if not matched:
            current["text"] += line + "\n"

    if current["text"].strip():
        sections.append(current)
    return sections


def search_memory(content: str, query: str, type_filter: str = "") -> List[Dict[str, Any]]:
    """
    Section-aware memory search with TF-IDF scoring.

    Splits markdown into sections, computes TF-IDF for each query term
    across all sections, then ranks by combined score. Rare terms (e.g.
    specific node names) are weighted higher than common ones (e.g. "render").

    Args:
        content: Raw markdown memory content
        query: Search query string
        type_filter: Optional section type filter (decision, parameter, blocker, session, note)

    Returns: Sorted list of {section_type, title, text, score, line}
    """
    import math
    import re

    if not content or not query:
        return []

    # Tokenize query into lowercase words (2+ chars for relevance)
    query_words = [
        w for w in re.findall(r'[a-z0-9_/]+', query.lower()) if len(w) >= 2
    ]
    query_word_set = set(query_words)
    if not query_word_set:
        return []

    # Parse sections
    sections = _parse_sections(content)
    if type_filter:
        sections = [s for s in sections if s["type"] == type_filter]

    # Pre-compute: tokenize each section and build word lists
    scorable = []
    for section in sections:
        if section["type"] == "header":
            continue
        words = re.findall(r'[a-z0-9_/]+', section["text"].lower())
        word_set = set(words)
        if not (query_word_set & word_set):
            continue  # Skip sections with zero overlap
        scorable.append((section, words, word_set))

    if not scorable:
        return []

    # IDF: log(N / df) where N = total scorable sections, df = sections containing term
    n_docs = len(scorable)
    doc_freq: Dict[str, int] = {}
    for _, _, word_set in scorable:
        for w in query_word_set:
            if w in word_set:
                doc_freq[w] = doc_freq.get(w, 0) + 1

    idf: Dict[str, float] = {}
    for w in query_word_set:
        df = doc_freq.get(w, 0)
        # Smoothed IDF: log((N + 1) / (df + 1)) + 1
        idf[w] = math.log((n_docs + 1) / (df + 1)) + 1.0

    # Score each section with TF-IDF
    results = []
    for section, words, word_set in scorable:
        n_words = len(words) or 1  # avoid /0

        # TF-IDF sum for matching query terms
        tfidf_score = 0.0
        for w in query_word_set:
            if w not in word_set:
                continue
            tf = words.count(w) / n_words
            tfidf_score += tf * idf[w]

        # Normalize by number of query terms for comparability
        tfidf_score /= len(query_word_set)

        # Title boost: query terms in title get 2x IDF weight
        title_words = set(re.findall(r'[a-z0-9_/]+', section["title"].lower()))
        title_matches = query_word_set & title_words
        if title_matches:
            for w in title_matches:
                tfidf_score += idf[w] * 0.5 / len(query_word_set)

        # Exact phrase bonus
        if query.lower() in section["text"].lower():
            tfidf_score += 0.5

        results.append({
            "section_type": section["type"],
            "title": section["title"],
            "text": section["text"].strip()[:500],
            "score": round(tfidf_score, 3),
            "line": section["line"],
        })

    # Sort by score descending, then by line ascending for tiebreaker
    results.sort(key=lambda r: (-r["score"], r["line"]))
    return results


def get_evolution_stage(claude_dir: str, name: str = "memory") -> str:
    """Detect current evolution stage: charmander, charmeleon, or charizard.

    Pokémon naming is the canonical convention used across the forge corpus,
    CLAUDE.md §6, the living-memory design plan, and the scene_memory tests.
    Both the legacy ('flat'/'structured'/'composed') and canonical names are
    accepted on read so existing on-disk USD layers do not invalidate.
    """
    claude_dir = os.path.normpath(claude_dir)
    usd_path = os.path.join(claude_dir, f"{name}.usd")
    md_path = os.path.join(claude_dir, f"{name}.md")

    if os.path.exists(usd_path):
        # Try pxr first (works for both binary USDC and text USDA)
        try:
            from pxr import Usd
            stage = Usd.Stage.Open(usd_path)
            layer_data = stage.GetRootLayer().customLayerData
            evo = layer_data.get("synapse:evolution", "")
            if evo in ("charizard", "composed"):
                return "charizard"
            if evo in ("charmeleon", "structured"):
                return "charmeleon"
            # Check sublayers as fallback
            if list(stage.GetRootLayer().subLayerPaths):
                return "charizard"
            return "charmeleon"
        except ImportError:
            pass
        # Fallback: text scan for USDA files
        try:
            content = _read_file(usd_path)
            if '"synapse:evolution" = "charizard"' in content or \
               '"synapse:evolution" = "composed"' in content:
                return "charizard"
            if "subLayers" in content or "references" in content:
                return "charizard"
        except Exception:
            pass
        return "charmeleon"

    if os.path.exists(md_path):
        return "charmander"

    return "none"


def get_memory_status(scene_dir: str, project_dir: str) -> Dict[str, Any]:
    """Get current memory system status.

    Routes both dirs through the shared resolvers (idempotent) so status
    reports on the same ``claude/`` the writer uses -- status reading an empty
    directory while writes landed elsewhere is the exact class of bug the
    resolver contract exists to prevent.
    """
    if not scene_dir.endswith("claude"):
        scene_dir = resolve_hip_dir(scene_dir)
    if not project_dir.endswith("claude"):
        project_dir = resolve_job_dir(project_dir)
    scene_claude = os.path.join(scene_dir, "claude") if not scene_dir.endswith("claude") else scene_dir
    project_claude = os.path.join(project_dir, "claude") if not project_dir.endswith("claude") else project_dir

    def _dir_status(d: str, name: str) -> Dict[str, Any]:
        path = os.path.join(d, f"{name}.md")
        usd_path = os.path.join(d, f"{name}.usd")
        status = {
            "evolution": get_evolution_stage(d, name),
            "size_kb": 0.0,
            "session_count": 0,
        }
        if os.path.exists(usd_path):
            status["size_kb"] = round(os.path.getsize(usd_path) / 1024, 2)
        elif os.path.exists(path):
            status["size_kb"] = round(os.path.getsize(path) / 1024, 2)
            content = _read_file(path)
            status["session_count"] = content.count("## Session ")
        return status

    return {
        "project": _dir_status(project_claude, "project"),
        "scene": _dir_status(scene_claude, "memory"),
        "agent": {
            "status": "idle",
            "task_count": 0,
            "suspended_count": 0,
        },
    }


# =============================================================================
# CORRUPTION RECOVERY
# =============================================================================

def validate_memory(claude_dir: str) -> List[str]:
    """Validate memory files and return list of issues found."""
    issues: List[str] = []
    claude_dir = os.path.normpath(claude_dir)

    # Check markdown files
    for name in ("memory.md", "project.md"):
        path = os.path.join(claude_dir, name)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                if len(content) == 0:
                    issues.append(f"{name}: Empty file")
            except UnicodeDecodeError:
                issues.append(f"{name}: Encoding error")

    # Check USD files
    for name in ("memory.usd", "agent.usd"):
        path = os.path.join(claude_dir, name)
        if os.path.exists(path):
            try:
                from pxr import Usd
                stage = Usd.Stage.Open(path)
                if not stage.GetPrimAtPath("/SYNAPSE"):
                    issues.append(f"{name}: Missing /SYNAPSE root prim")
                # Schema version check
                layer_data = stage.GetRootLayer().customLayerData
                file_version = layer_data.get("synapse:version", "0.0.0")
                if file_version != SCHEMA_VERSION:
                    issues.append(
                        f"{name}: Schema version mismatch "
                        f"(file={file_version}, current={SCHEMA_VERSION})"
                    )
            except ImportError:
                pass  # pxr not available, skip USD validation
            except Exception as e:
                issues.append(f"{name}: Corrupted - {e}")
                # Backup corrupted file
                import shutil
                backup = path + f".corrupted.{int(time.time())}"
                shutil.move(path, backup)
                issues.append(f"{name}: Backed up to {backup}")
                if name == "agent.usd":
                    try:
                        from .agent_state import initialize_agent_usd
                        initialize_agent_usd(path)
                        issues.append(f"{name}: Reinitialized")
                    except Exception:
                        pass

    return issues
