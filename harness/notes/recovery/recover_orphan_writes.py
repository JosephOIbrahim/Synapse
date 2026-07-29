"""Recover unlanded work from worktree transcripts - the producer for every file it writes.

    python harness/notes/recovery/recover_orphan_writes.py            # dry run (default)
    python harness/notes/recovery/recover_orphan_writes.py --apply    # write into the main tree

WHY
---
14 orphaned directories under .claude/worktrees/ turned out to be mostly empty
shells - but the work dispatched into them was not lost, because Claude Code
transcripts record every Write and Edit. A forensic pass over
~/.claude/projects/C--Users-User-SYNAPSE--claude-worktrees-*/*.jsonl found 51
unlanded files (~481 KB), including the three receipts
harness/orchestrate.ps1:148 declares lost ("The receipts are lost"). They are
not. C0.json, H9.json and S1.json all reconstruct and parse.

METHOD (proven 3/3 on the lost receipts before this script existed)
------
For each target path: take the LAST Write tool_use whose file_path ends with
the worktree-relative path as the base content, then apply every LATER Edit
tool_use for that path in order (old_string -> new_string, respecting
replace_all). Transcript files are walked in mtime order so cross-session
edits land in sequence.

RULES
-----
- NEVER overwrites. A target that already exists in the main tree is reported
  (with both lengths, so a newer-in-worktree copy stays visible as an open
  question) and skipped. Law 4: recovery is additive; adjudication is human.
- Scope is the six RECOVERABLE orphans only. h1-schemas is excluded because it
  is classified UNCLEAR and its one real artifact is safe on
  origin/repair/h1-schemas-b (commit 0929d56); c1-token-bench is excluded as
  DUPLICATE-OF-MAIN with scratch-only unlanded writes.
- Emits recovery_manifest.json beside this script: source transcript, replay
  counts, sha256 and length per file. That manifest is the provenance record.

Law 1 - how this fails: --apply on a tree where a target exists with different
content reports SKIPPED-EXISTS and touches nothing; a transcript chain that
does not end in parseable JSON for a *.json target aborts that file with
status=replay_error rather than writing a broken receipt.
"""
import argparse, glob, hashlib, json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
PROJ = os.path.expanduser("~/.claude/projects")
MANIFEST_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recovery_manifest.json")

# orphan name -> transcript project slug
SCOPE = [
    "c0-census", "h9-doc-grounding", "s1-forensic",
    "v1-capture-probe", "rsi0-surface-audit", "s0-forensic",
]
SLUG = "C--Users-User-SYNAPSE--claude-worktrees-%s"


def norm(p):
    return p.replace("\\", "/")


def events_for(orphan):
    """Every Write/Edit tool_use across the orphan's transcripts, in order."""
    d = os.path.join(PROJ, SLUG % orphan)
    out = []
    for f in sorted(glob.glob(os.path.join(d, "*.jsonl")), key=os.path.getmtime):
        try:
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    msg = rec.get("message") or {}
                    for c in (msg.get("content") or []):
                        if not isinstance(c, dict) or c.get("type") != "tool_use":
                            continue
                        name = c.get("name")
                        if name not in ("Write", "Edit"):
                            continue
                        inp = c.get("input") or {}
                        fp = norm(str(inp.get("file_path", "")))
                        if not fp:
                            continue
                        out.append((name, fp, inp, os.path.basename(f)))
        except OSError:
            continue
    return out


def worktree_rel(fp, orphan):
    """The path relative to the worktree root, or None if outside it."""
    marker = ".claude/worktrees/%s/" % orphan
    i = norm(fp).lower().find(marker.lower())
    return norm(fp)[i + len(marker):] if i >= 0 else None


def replay(events, rel):
    """Last Write for rel + every later Edit, in order. (content, n_edits) or error."""
    base_i, content = None, None
    for i, (name, fp, inp, _src) in enumerate(events):
        if name == "Write" and norm(fp).lower().endswith(rel.lower()):
            base_i, content = i, inp.get("content", "")
    if content is None:
        return None, 0, "no Write found"
    edits = 0
    for name, fp, inp, _src in events[base_i + 1:]:
        if name != "Edit" or not norm(fp).lower().endswith(rel.lower()):
            continue
        old, new = inp.get("old_string", ""), inp.get("new_string", "")
        if old not in content:
            return None, edits, "edit old_string not found (chain broken)"
        content = content.replace(old, new) if inp.get("replace_all") else content.replace(old, new, 1)
        edits += 1
    return content, edits, None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write files (default: dry run)")
    ns = ap.parse_args(argv)

    manifest, recovered, skipped, errors = [], 0, 0, 0
    for orphan in SCOPE:
        events = events_for(orphan)
        if not events:
            manifest.append({"orphan": orphan, "status": "no_transcripts"})
            continue
        # every distinct worktree-relative path this orphan ever wrote
        rels = []
        for name, fp, _inp, _src in events:
            if name != "Write":
                continue
            rel = worktree_rel(fp, orphan)
            if rel and rel not in rels:
                rels.append(rel)
        for rel in rels:
            target = os.path.join(ROOT, rel)
            entry = {"orphan": orphan, "path": rel}
            content, edits, err = replay(events, rel)
            if err:
                entry.update(status="replay_error", error=err)
                errors += 1
            elif os.path.exists(target):
                entry.update(status="SKIPPED-EXISTS",
                             main_bytes=os.path.getsize(target),
                             worktree_chars=len(content))
                skipped += 1
            else:
                if rel.endswith(".json"):
                    try:
                        json.loads(content)
                    except Exception as e:
                        entry.update(status="replay_error",
                                     error="recovered json does not parse: %s" % str(e)[:80])
                        errors += 1
                        manifest.append(entry)
                        continue
                entry.update(status="recovered" if ns.apply else "would_recover",
                             chars=len(content), edits_replayed=edits,
                             sha256=hashlib.sha256(content.encode("utf-8")).hexdigest()[:16])
                if ns.apply:
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with open(target, "w", encoding="utf-8", newline="\n") as fh:
                        fh.write(content)
                recovered += 1
            manifest.append(entry)

    with open(MANIFEST_OUT, "w", encoding="utf-8") as fh:
        json.dump({"producer": "harness/notes/recovery/recover_orphan_writes.py",
                   "applied": ns.apply, "scope": SCOPE,
                   "excluded": {"h1-schemas": "UNCLEAR; real artifact safe at origin/repair/h1-schemas-b (0929d56)",
                                "c1-token-bench": "DUPLICATE-OF-MAIN; unlanded items are scratch"},
                   "entries": manifest}, fh, indent=1)

    mode = "APPLIED" if ns.apply else "DRY RUN"
    print("%s: %d recovered, %d skipped-exists, %d errors -> %s"
          % (mode, recovered, skipped, errors, os.path.relpath(MANIFEST_OUT, ROOT)))
    for e in manifest:
        if e.get("status") in ("replay_error", "no_transcripts"):
            print("  !! %-18s %s: %s" % (e["orphan"], e.get("path", "-"), e.get("error", e["status"])))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
