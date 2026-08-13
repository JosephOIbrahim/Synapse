# SYNAPSE Production-Readiness Report — Mid-Size NYC Studio, 2026

**Prepared from live diagnostics** (synapse_doctor, synapse_health, synapse_metrics, synapse_context, synapse_memory_status)
**Date:** 2026-08-12
**Scope:** Usability and production-readiness of SYNAPSE as an AI co-pilot embedded in Houdini, evaluated against the operating reality of a mid-size (30–150 artist) NYC studio in 2026.

---

## 0. Executive Summary

SYNAPSE is a genuinely capable tool — the tool surface (SOP/LOP/TOPS/COPs, USD authoring, render orchestration, memory) is broad and the voice/UX philosophy is right. But the current build is **not production-safe for a mid-size studio**. The problems are not feature gaps; they are **architecture and trust problems** that will surface on day one of a real show and erode confidence fast.

The single most damaging issue is that **all project memory lives in a per-machine temp directory** (`%LOCALAPPDATA%\Temp\houdini_temp\<hip>\\.synapse`). In a studio, that means every artist's memory is isolated, ephemeral, and lost on reboot — the exact opposite of what a shared production memory should be.

The report is organized from first principles: **where the data lives, how the tool behaves under load, how it fails, and how artists experience it.** Each section ends with concrete recommendations.

---

## 1. Data Persistence & Memory — The Critical Failure

### 1.1 Memory is stored in a temp directory
Observed storage path:
```
C:\Users\User\AppData\Local\Temp\houdini_temp\untitled\.synapse
```
This is a **per-machine, per-HIP-file temp location**. Consequences for a studio:

- **No shared memory.** Artist A's learned recipes, decisions, and scene context never reach Artist B. The "project memory" is not a project memory — it's a local scratch file.
- **Ephemeral.** Temp dirs are cleaned by the OS and by Houdini session teardown. A reboot or a new session can wipe 403 accumulated memories.
- **No per-show isolation.** Two shows on the same machine collide in the same temp namespace.
- **No backup, no versioning, no audit.** For a studio under NDA, this is a compliance risk — there is no record of what the AI was told or did.

### 1.2 The memory backend is silently degraded
`synapse_health` reports:
```
write_plane: degraded
reason: memory backend 'moneta' was selected but this process fell back to jsonl
  (init failed: ValueError: embedding dim mismatch: expected 384, got 256)
```
The doctor confirms the cascade:
- `moneta_substrate`: **fail** (schema registered but no typed prim demonstrable)
- `moneta_consolidation`: **skipped** (store not Moneta-backed)
- `vector_recall`: **skipped** (store not Moneta-backed)
- `use_real_usd`: **skipped** (store not Moneta-backed)

**What this means:** The system *intends* to use a Moneta/USD-backed memory with vector recall and consolidation, but a **model embedding-dimension mismatch (384 vs 256)** silently dropped it to a flat JSONL file. Every feature that depends on the richer backend — semantic recall, consolidation, USD authoring — is **disabled without a loud warning**. The doctor flags it, but the artist-facing panel does not. This is a silent-capability-loss failure: the tool looks healthy and quietly does less.

### 1.3 Memory evolution is stuck at the lowest stage
`evolution_stage: charmander` (the first of three stages). 403 entries accumulated but never evolved. The consolidation/decay machinery (`synapse_sleep_pass`) is a no-op under the jsonl backend. So memory grows unbounded and never prunes or consolidates — a slow-burn quality problem.

### 1.4 Recommendations
1. **Move memory to a shared, versioned store** — a studio SAN path or a git-backed store per show, not `%TEMP%`. This is the #1 fix.
2. **Fail loudly on backend fallback.** If Moneta init fails, the panel must show a red banner: "Memory degraded — vector recall disabled." Silent fallback is unacceptable in production.
3. **Fix the embedding-dim mismatch** (384 vs 256) at the source, or make the model choice explicit and validated at startup.
4. **Enable consolidation** so memory prunes and evolves instead of accumulating 400+ flat entries.
5. **Per-show namespacing** so two shows never share memory.

---

## 2. Trust & Failure Transparency

### 2.1 The doctor is honest, the panel is not
The doctor output is excellent — it distinguishes `ok` / `fail` / `skipped`, explains *why* (e.g. "stale stamp bookkeeping, not tree drift"), and gives plain-language detail. This is the right tone. **But the artist-facing panel does not surface this.** An artist mid-show has no idea the memory backend fell back, that recall is off, or that their memory is in a temp dir. The gap between what the tool knows and what the artist is told is a trust problem.

### 2.2 Stale install stamp causes confusion
```
install stamp says 5.23.0 but the running package IS the stamped tree (5.45.1)
— repo-direct install, stale stamp bookkeeping, not tree drift
```
The doctor correctly identifies this as benign. But a TD doing a studio-wide rollout will see a version mismatch and burn hours chasing a ghost. **Version reporting must be unambiguous** — the running version and the install stamp should agree, or the stamp should be removed.

### 2.3 Recommendations
- Surface doctor/health status in the panel with a **health indicator** (green/amber/red) and a one-line "what's degraded and why."
- Make version reporting single-source-of-truth.
- Add a **"what changed / what's disabled"** summary after every session start.

---

## 3. Performance Under Load — Panel Result Path

### 3.1 The panel result path is slow
From `synapse_metrics`:
```
panel_result_ms_sum{phase="append"}   648.6ms   (slow: 1)
panel_result_ms_sum{phase="finalize"} 780.2ms   (slow: 1)
main_thread_hold_slowest_ms{synapse_doctor} 648.3ms
dispatch_wait_ms_max 306ms
```
The **append** and **finalize** phases of the panel result path exceed the slow threshold. The slowest main-thread hold is 648ms (the doctor call itself). For an artist in a flow state, a ~0.6–0.8s stall on the main thread is **perceptible and disruptive** — it can freeze the viewport mid-interaction.

### 3.2 Dispatch waits
91 samples, max 306ms enqueue-to-start. Not catastrophic, but on a busy scene with heavy cooks, this compounds.

### 3.3 Recommendations
- **Move panel result append/finalize off the main thread** where possible, or make them incremental/streaming so a large result doesn't block.
- **Profile the 648ms doctor hold** — a diagnostic call should not stall the main thread for 0.6s.
- Add a **main-thread budget** and a visible "working" indicator so artists know a stall is the tool, not a hang.

---

## 4. Panel Design Improvements

The panel is the artist's entire interface to SYNAPSE. Current design gaps, from a first-principles UX view:

### 4.1 No persistent health/status strip
There is no always-visible indicator of: connection state, memory backend health, current show/project, or degraded features. Artists should never have to run a doctor to learn the tool is degraded.

**Recommendation:** A slim status bar (top or bottom) showing: ● connection, ● memory backend (with amber if degraded), ● current project/show, ● active render/job. Click-through to a full health panel.

### 4.2 No undo/redo visibility
SYNAPSE wraps operations in undo groups, but the panel doesn't tell the artist "this action is undoable — press Ctrl+Z." For a tool that mutates a scene, **undo confidence is everything.** Artists need to know their scene is safe.

**Recommendation:** After each mutation, show a subtle "✓ done — undoable" affordance. Add a prominent "Undo last action" button in the panel.

### 4.3 No destructive-action confirmation
The voice guide says to confirm before destructive ops, but the panel has no explicit confirmation gate for delete/overwrite/disk-write. In a studio, an accidental overwrite of a render or a deleted node is a real cost.

**Recommendation:** A confirmation dialog (or at minimum a highlighted "this will overwrite X" line) before any destructive operation.

### 4.4 No session/audit log visible
For a studio under NDA, there's no visible record of what the AI did. The doctor has an audit log, but the artist can't see it.

**Recommendation:** A collapsible "Session Log" tab listing every action taken, with timestamps and undo status. This doubles as a trust and compliance feature.

### 4.5 No recipe library UI
The memory system stores verified recipes ("Create a Solaris Network", "Frame everything in the camera"), but there's no panel surface to browse, search, or re-run them. The knowledge exists but is invisible.

**Recommendation:** A "Recipes" tab that lists verified recipes with one-click re-run. This turns accumulated memory into a reusable asset — huge for a studio.

### 4.6 No multi-user / show context
The panel has no notion of "which show am I on" or "who else is working on this." For a studio, show context should be first-class.

**Recommendation:** A project/show selector at the top, wired to the memory namespace (fixes 1.1 and 1.4 together).

### 4.7 Streaming output is good, but no progress for long ops
Streaming works (142 stream samples, max 164ms — fine). But long operations (renders, cooks, TOPS) have no progress bar in the panel.

**Recommendation:** Progress indicators for render/cook/TOPS jobs, with cancel.

---

## 5. Studio-Specific Production Concerns

### 5.1 Mixed OS fleet
NYC mid-size studios run Windows, macOS, and Linux. The observed paths are Windows (`C:\Users\...`). Path handling, temp locations, and the memory store must be **cross-platform and path-agnostic** — a Windows-authored memory path must not break a Linux artist.

### 5.2 Shared storage & concurrency
If memory moves to shared storage (recommended), it must handle **concurrent writers** (two artists, same show). The current jsonl append model is not concurrency-safe. Needs locking or a proper store.

### 5.3 Render farm integration
SYNAPSE has TOPS/PDG and render orchestration, but the doctor shows no farm scheduler configured (local scheduler only). For a studio with a farm, **Deadline/Tractor/HQueue integration is a hard requirement** — the tool must hand off to the farm, not render locally.

### 5.4 Security / NDA
- Memory in `%TEMP%` is a data-exposure risk (no control over who reads it).
- No audit trail visible to artists.
- No per-show access control.
For NDA-bound commercial work, these are blockers.

### 5.5 Version control of scenes
No integration with the studio's scene versioning (e.g. per-shot HIP versioning, git for HDAs). The tool should respect and integrate with the studio's existing versioning, not fight it.

### 5.6 TD support burden
The stale stamp, silent backend fallback, and temp-dir memory will generate **support tickets** that a small TD team (often 1–3 people) can't afford. Every silent degradation is a future ticket.

---

## 6. Prioritized Roadmap

| Priority | Item | Why |
|---|---|---|
| **P0** | Move memory to shared, versioned, per-show store | Data loss + no collaboration today |
| **P0** | Fail loudly on backend fallback (embedding mismatch) | Silent capability loss erodes trust |
| **P0** | Panel health/status strip | Artists must know the tool's state |
| **P1** | Fix embedding-dim mismatch / validate model at startup | Restores vector recall + consolidation |
| **P1** | Undo/redo visibility + destructive-action confirmation | Scene safety confidence |
| **P1** | Move panel append/finalize off main thread | Kill the 0.6–0.8s stalls |
| **P1** | Session/audit log tab | Trust + NDA compliance |
| **P2** | Recipes library UI | Turn memory into reusable assets |
| **P2** | Cross-platform path handling | Mixed-fleet reality |
| **P2** | Farm scheduler integration (Deadline/Tractor) | Studio render pipeline |
| **P2** | Show/project selector wired to memory namespace | Multi-show isolation |
| **P3** | Concurrency-safe shared store | Two artists, one show |
| **P3** | Scene versioning integration | Respect studio pipeline |

---

## 7. Closing

SYNAPSE has the right bones: a broad, capable tool surface; a genuinely good voice/UX philosophy (lead with what's working, explain don't diagnose, frame as options); and honest diagnostics. The gap between the tool's capability and its production-readiness is **not features — it's architecture and trust**:

1. **Memory must be shared, versioned, and per-show** — not a temp file.
2. **Degradation must be loud** — never silent fallback.
3. **The panel must show health, undo, and audit** — artists need to trust the tool with their scene.
4. **The main thread must not stall** — flow state is the product.

Fix those four and SYNAPSE becomes a credible production co-pilot for a mid-size NYC studio. Leave them and it stays a promising prototype that a TD will quietly uninstall after the first lost memory or frozen viewport.
