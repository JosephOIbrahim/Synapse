"""Background-render stop via the hscript ``rps`` / ``rkill`` pair (H3b, R73).

WHY THIS MODULE EXISTS
----------------------
``hou.RopNode`` carries no cancel/abort/interrupt verb on 22.0.368 (H3a-F1,
re-confirmed this leg by ``dir()`` sweep). ``hou.ActiveRender`` — the documented
HOM replacement for ``rkill``/``rps`` — is ``#status: ni`` and absent at runtime.
R48 concluded from that that a render could not be stopped at all; **R73 refuted
it**. The hscript commands ``rps`` (list background render processes) and
``rkill`` (stop one) both exist and work.

This module is the SYNAPSE-side use of that pair. It is deliberately narrow:
it stops *background* renders, which is the only thing ``rps`` can see.

WHAT WAS MEASURED (VERIFIED-RUNTIME, Houdini Indie 22.0.368, 2026-07-28)
------------------------------------------------------------------------
Producer: ``harness/notes/h3b/rkill_probe_evidence.json``.

1. ``rkill <pid>`` is **PID-selective**. Two concurrent husk renders, killed one
   by mapped PID: target dead inside 0.5 s, the other alive across a 5 s watch.

2. ``rkill`` is **SILENT**. Empty stdout *and* empty stderr whether it killed a
   real process or matched nothing at all. It therefore cannot be trusted as its
   own receipt — every stop in here is verified by re-reading ``rps``. This is
   Law 3: ``status`` describes what happened, never what was attempted.

3. The **RopNode -> process mapping is renderer-dependent**, and this is the
   central finding of the leg:

   * ``usdrender_rop`` (Karma/husk) — MAPPABLE. ``rps`` reports husk's full
     command line, which contains a per-invocation temp scene at
     ``usd_renders/usdrender_<houdiniPID>_<node.sessionId()>_<counter>/``.
     ``sessionId`` pins the exact ROP; ``houdiniPID`` scopes it to *this*
     Houdini, so a stop can never reach another session's render.
   * ``ifd`` (mantra) — **NOT MAPPABLE**. ``rps`` reports the bare string
     ``"mantra"`` with no arguments (Houdini pipes the IFD over stdin, so the
     OS command line is bare too — checked via Win32_Process). Two concurrent
     mantra renders are indistinguishable by every field available.

   Consequence, and it is a refusal rather than a guess: a stop addressed to a
   mantra ROP resolves to nothing and returns ``unmappable``. It does not fall
   back to "kill the only render running" — that is how you kill the wrong one.

4. ``rps`` retains **completed** renders as rows with PID ``-1``. They are not
   killable and are excluded from every mapping.

PARTIAL-FRAME BEHAVIOUR — the mandatory finding (brief PART B.3)
----------------------------------------------------------------
Stopping a render is process-level and blunt. What it leaves on disk differs
per renderer, and one of the two is genuinely hazardous:

* **husk / Karma — SAFE.** husk writes progressive snapshots to a *separate*
  file ``<stem>_part.exr`` (the ROP invokes ``--snapshot 300``) and writes the
  real output path only on completion, removing ``_part`` as it goes. Killing
  husk mid-render therefore CANNOT corrupt the declared output: the file simply
  never appears. Residue is at most ``<stem>_part.exr``.

* **mantra — HAZARDOUS, and quietly so.** mantra writes the real output file's
  EXR *header* immediately and accumulates pixels in a sidecar
  ``<output>.mantra_checkpoint``. A killed mantra render leaves a 1,015-byte
  EXR at the declared output path that is **structurally valid** — correct
  magic, full resolution header, ``iinfo`` exits 0 — and contains **no pixels**.
  It is not corrupt; it is valid-and-empty, so any "does the file exist and
  parse?" check passes it. Two independent detectors, both measured:
    - the orphaned ``<output>.mantra_checkpoint`` (removed on clean completion)
    - the EXR header lacks ``renderTime`` / ``renderMemory`` / ``date``, which a
      completed mantra frame always carries

``partial_output_risk()`` returns that advisory as data so a caller cannot
"succeed" without being handed the residue it must check.

NOT COVERED, stated rather than implied
---------------------------------------
* A **foreground** render (``soho_foreground=1``, or any in-process
  ``RopNode.render()`` that blocks the main thread) never becomes a background
  process, never appears in ``rps``, and cannot be reached from here.
* ``hou.IPRViewer.killRender`` exists and is a DIFFERENT case — interactive
  preview, not a ROP render. It is not wrapped here.
* ``rkill *`` kills every background render on the host including renders this
  session did not start. It is deliberately unreachable from this module.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised only inside Houdini
    import hou
    HOU_AVAILABLE = True
except ImportError:
    hou = None
    HOU_AVAILABLE = False


# ``rps`` marks finished renders with this sentinel PID.
DEAD_PID = -1

# husk's per-invocation temp scene directory, observed verbatim in rps:
#   .../usd_renders/usdrender_<houdiniPID>_<sessionId>_<counter>/__render__.usd
_USDRENDER_DIR_RE = re.compile(r"usdrender_(\d+)_(\d+)_(\d+)")

RENDERER_HUSK = "husk"
RENDERER_MANTRA = "mantra"
RENDERER_UNKNOWN = "unknown"


# --------------------------------------------------------------------------
# Pure parsing / mapping.  No hou.  These are the READER, and reader blindness
# is its own defect class (R60) — tests/test_h3b_render_stop.py calibrates them
# against real captured rps text before any pin trusts them.
# --------------------------------------------------------------------------

def parse_rps(text: str) -> List[Dict[str, Any]]:
    """Parse ``rps`` stdout into structured rows.

    Returns one dict per render slot: ``pid`` (int), ``command`` (str, may be a
    bare renderer name), ``alive`` (bool — False for the ``-1`` sentinel) and
    ``renderer``.

    The idle form is ``"No background renders currently running"``, which
    yields ``[]``. A header line beginning ``PID`` is skipped. Any line whose
    first token is not an integer is skipped rather than guessed at.
    """
    rows: List[Dict[str, Any]] = []
    if not text:
        return rows
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("PID"):
            continue
        if line.lower().startswith("no background renders"):
            continue
        parts = line.split(None, 1)
        try:
            pid = int(parts[0])
        except (ValueError, IndexError):
            continue
        command = parts[1].strip() if len(parts) > 1 else ""
        rows.append({
            "pid": pid,
            "command": command,
            "alive": pid != DEAD_PID,
            "renderer": classify_renderer(command),
        })
    return rows


def classify_renderer(command: str) -> str:
    """Name the renderer behind an ``rps`` command string.

    husk reports a full command line; mantra reports the bare word ``mantra``.
    Anything else is ``unknown`` and is never treated as mappable.
    """
    if not command:
        return RENDERER_UNKNOWN
    head = command.split()[0].lower()
    head = os.path.basename(head)
    if head.startswith("husk"):
        return RENDERER_HUSK
    if head.startswith("mantra"):
        return RENDERER_MANTRA
    return RENDERER_UNKNOWN


def rop_token(houdini_pid: int, session_id: int) -> str:
    """The substring that identifies one ROP's husk invocation in ``rps``.

    Scoped by ``houdini_pid`` on purpose: it makes a cross-session kill
    structurally impossible rather than merely unlikely.
    """
    return "usdrender_%d_%d_" % (int(houdini_pid), int(session_id))


def resolve_rop_pids(rows: List[Dict[str, Any]], houdini_pid: int,
                     session_id: int) -> List[int]:
    """Live PIDs whose command line belongs to this ROP. Dead rows excluded.

    Returns ``[]`` when the ROP is not rendering — the reader's negative case,
    and the reason this function can fail (Law 1).
    """
    token = rop_token(houdini_pid, session_id)
    return [r["pid"] for r in rows
            if r.get("alive") and token in (r.get("command") or "")]


def describe_usdrender_command(command: str) -> Optional[Dict[str, int]]:
    """Decode ``usdrender_<hpid>_<sessionId>_<n>`` out of a husk command line.

    ``None`` when the command carries no such token — which is every mantra row
    and any husk invocation not spawned by a ``usdrender_rop``.
    """
    m = _USDRENDER_DIR_RE.search(command or "")
    if not m:
        return None
    return {
        "houdini_pid": int(m.group(1)),
        "session_id": int(m.group(2)),
        "invocation": int(m.group(3)),
    }


def partial_output_risk(renderer: str) -> Dict[str, Any]:
    """What a stop leaves on disk, per renderer. Measured, not assumed.

    Returned as data with every stop so a caller is handed the residue it must
    check instead of a clean-looking success.
    """
    if renderer == RENDERER_HUSK:
        return {
            "renderer": RENDERER_HUSK,
            "declared_output_safe": True,
            "summary": (
                "husk writes progress snapshots to a separate <stem>_part.exr "
                "and only writes the declared output path on completion, so a "
                "stopped Karma render leaves no partial file at the real "
                "output. The output simply never appears."
            ),
            "residue": ["<output_stem>_part.exr (if --snapshot elapsed)"],
            "detect_incomplete": "declared output path is absent",
        }
    if renderer == RENDERER_MANTRA:
        return {
            "renderer": RENDERER_MANTRA,
            "declared_output_safe": False,
            "summary": (
                "mantra writes the EXR header to the declared output path "
                "immediately and accumulates pixels in a .mantra_checkpoint "
                "sidecar. A stopped mantra render leaves a STRUCTURALLY VALID "
                "but PIXEL-EMPTY EXR at the real output path (~1KB, iinfo exits "
                "0). A file-exists or file-parses check will pass it."
            ),
            "residue": ["<output>.mantra_checkpoint",
                        "<output>.exr (valid header, no pixels)"],
            "detect_incomplete": (
                "an orphaned <output>.mantra_checkpoint beside the frame, OR an "
                "EXR header missing renderTime/renderMemory/date (a completed "
                "mantra frame always carries all three)"
            ),
        }
    return {
        "renderer": renderer,
        "declared_output_safe": None,
        "summary": (
            "Unrecognised renderer — partial-output behaviour was not measured "
            "for it and is not asserted in either direction."
        ),
        "residue": [],
        "detect_incomplete": "unknown; verify the frame before trusting it",
    }


# --------------------------------------------------------------------------
# Live surface.  Everything below needs hou and must run on the main thread;
# the callers in handlers_render.py marshal via server.main_thread.run_on_main.
# --------------------------------------------------------------------------

def _hscript(cmd: str):
    out, err = hou.hscript(cmd)
    return out or "", err or ""


def read_render_processes() -> List[Dict[str, Any]]:
    """Structured ``rps`` snapshot, husk rows annotated with their ROP."""
    out, _err = _hscript("rps")
    rows = parse_rps(out)
    hpid = os.getpid()
    for r in rows:
        decoded = describe_usdrender_command(r.get("command") or "")
        if decoded:
            r["usdrender"] = decoded
            r["this_session"] = (decoded["houdini_pid"] == hpid)
            r["rop_path"] = _rop_path_for_session_id(decoded["session_id"]) \
                if decoded["houdini_pid"] == hpid else None
        else:
            r["usdrender"] = None
            r["this_session"] = None
            r["rop_path"] = None
        r["mappable_to_rop"] = bool(r.get("rop_path"))
    return rows


def _rop_path_for_session_id(session_id: int) -> Optional[str]:
    """Resolve a node sessionId back to a path, or None if it no longer exists."""
    try:
        node = hou.nodeBySessionId(int(session_id))
    except Exception:
        return None
    return node.path() if node is not None else None


def _pid_is_live(pid: int) -> bool:
    return any(r["pid"] == pid and r["alive"] for r in parse_rps(_hscript("rps")[0]))


def stop_render(node_path: Optional[str] = None,
                pid: Optional[int] = None) -> Dict[str, Any]:
    """Stop ONE background render, identified by ROP path or explicit PID.

    ``status`` is one of — and every one of these describes an observed
    outcome, never an attempt (Law 3):

    ``stopped``            the PID was live, was killed, and is verified gone
    ``noop_not_rendering`` the ROP resolved but no live render belongs to it
    ``noop_no_such_pid``   the PID is not a live row in ``rps``
    ``unmappable``         the ROP is rendering under a renderer whose rps row
                           carries no identity (mantra) — refused, not guessed
    ``ambiguous``          more than one live PID matched — refused
    ``kill_unconfirmed``   rkill was issued and the PID is STILL live afterwards

    Raises ``ValueError`` when neither or both selectors are supplied.
    """
    if (node_path is None) == (pid is None):
        raise ValueError(
            "Pass exactly one of node_path or pid -- a stop that cannot say "
            "WHAT it is stopping is not a stop."
        )

    rows = read_render_processes()
    live_rows = [r for r in rows if r["alive"]]

    if pid is not None:
        pid = int(pid)
        match = [r for r in live_rows if r["pid"] == pid]
        if not match:
            return {
                "status": "noop_no_such_pid",
                "pid": pid,
                "killed": False,
                "live_renders": live_rows,
                "note": "No live rps row carries that PID; nothing was signalled.",
            }
        target, renderer = pid, match[0]["renderer"]
        resolved_from = "pid"
        rop_out = match[0].get("rop_path")
    else:
        node = hou.node(node_path)
        if node is None:
            raise ValueError(
                "Couldn't find a node at %s -- double-check the path exists"
                % node_path
            )
        session_id = node.sessionId()
        mine = resolve_rop_pids(rows, os.getpid(), session_id)
        if not mine:
            # Distinguish "not rendering" from "rendering but unidentifiable".
            unmappable = [r for r in live_rows if not r["mappable_to_rop"]]
            if unmappable:
                return {
                    "status": "unmappable",
                    "node": node_path,
                    "killed": False,
                    "renderers_in_flight": sorted(
                        {r["renderer"] for r in unmappable}),
                    "live_renders": live_rows,
                    "note": (
                        "There ARE background renders in flight, but none can be "
                        "attributed to this ROP: their rps rows carry no node "
                        "identity (mantra reports the bare command 'mantra'). "
                        "Refusing rather than killing the only render running, "
                        "which could be the wrong one. Stop it by explicit pid "
                        "if you can confirm which it is."
                    ),
                }
            return {
                "status": "noop_not_rendering",
                "node": node_path,
                "killed": False,
                "live_renders": live_rows,
                "note": "No background render is attributable to this ROP.",
            }
        if len(mine) > 1:
            return {
                "status": "ambiguous",
                "node": node_path,
                "killed": False,
                "candidate_pids": mine,
                "note": (
                    "More than one live render maps to this ROP. Refusing; "
                    "stop the intended one by explicit pid."
                ),
            }
        target = mine[0]
        renderer = next((r["renderer"] for r in live_rows if r["pid"] == target),
                        RENDERER_UNKNOWN)
        resolved_from = "node"
        rop_out = node_path

    # rkill is silent on both success and no-match, so it is never its own
    # receipt: issue it, then re-read rps and report what is actually true.
    kout, kerr = _hscript("rkill %d" % target)
    still_live = _pid_is_live(target)

    result = {
        "status": "kill_unconfirmed" if still_live else "stopped",
        "killed": not still_live,
        "pid": target,
        "node": rop_out,
        "resolved_from": resolved_from,
        "renderer": renderer,
        "verified_by": "rps re-read after rkill (rkill itself reports nothing)",
        "rkill_stdout": kout.strip(),
        "rkill_stderr": kerr.strip(),
        "partial_output": partial_output_risk(renderer),
    }
    if still_live:
        result["note"] = (
            "rkill was issued but the PID is still listed as live. The render "
            "was NOT confirmed stopped -- do not treat the output as final."
        )
    return result
