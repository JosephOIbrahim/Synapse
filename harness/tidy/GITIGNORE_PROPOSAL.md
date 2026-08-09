# GITIGNORE PROPOSAL — models/ and shot_layers/

> TIDY dispatch · data directories · 2026-08-07
> Proposal only. **`.gitignore` is NOT edited by this dispatch.** A human applies the
> entries below (or the harness's data-dirs gate approves them).

## Disposition: GITIGNORE (both)

Both directories are **data / generated-asset dirs**, not source. Neither should be
committed. The tidy STATE.json already classifies both as `GITIGNORE`; this proposal
records the evidence and the exact entries to add.

---

## 1. `models/` — 90MB downloaded ONNX embedder

**Contents:** `models/minilm-l6-v2.onnx` (90,405,214 bytes) — the MiniLM-L6-v2 semantic
embedder, a downloaded model binary.

**Why gitignore (not commit):**
- It is a **downloaded model asset**, not source. 90MB binary in git bloats the repo
  and is not reproducible from the tree.
- `docs/DEBUT_READINESS.md` is explicit: *"No model ships with the repo. Once present,
  the embedder produces 384-dim semantic vectors…"* and the model is expected at
  `~/.synapse/models/minilm-l6-v2/model.onnx` — i.e. **outside the repo**, under the
  user's `.synapse` dir, not in the working tree.
- `SemanticEmbedder` degrades gracefully to `HashEmbedder` when the model file is
  missing (per `docs/DEBUT_READINESS.md`), so ignoring it breaks nothing.

**Proposed entry:**
```
# Downloaded ONNX embedder (MiniLM-L6-v2) — model asset, not source.
# Docs: "No model ships with the repo." Expected at ~/.synapse/models/, not in-tree.
models/
```

---

## 2. `shot_layers/` — recurring solaris-live-test artifact (RES-F11 / R57)

**Contents:** 5 tiny USDC files — `animation.usd`, `fx.usd`, `layout.usd`,
`lighting.usd`, `render.usd` (492 bytes each).

**Why gitignore (not commit):** This is **not a real fixture**. It is the documented,
recurring **RES-F11 / R57** artifact: the solaris live tests write USD department
layers into the **repo root** via the no-`hou`/fake-hou fallback of
`solaris_compose_tools.py:133-136`:

```python
os.makedirs(hou.expandString('$HIP/' + shot + '_layers'))
```

When `$HIP` is empty (no-`hou` test path), `expandString` resolves relative to the
process CWD, so the layers land in the repo root as `shot_layers/`. Every hython
suite run dirties the working tree with it.

Evidence trail (all classify it as test litter, not work):
- `harness/notes/CTO_RULINGS_01.md:1469` — R57: *"`shot_layers/` written to repo root
  by the solaris live tests (RES-F11). Redirect to tmp_path, or gitignore it."*
- `harness/notes/forensic/S2_PREMORTEM.md:1039` — production writes
  `$HIP/<shot>_layers` beside the `.hip`; the repo-root artefact is the no-`hou`
  fallback.
- `harness/notes/receipts/RES.json:308-331` — RES-F11: *"The solaris live tests write
  USD layers into the REPO ROOT (shot_layers/), untracked and not gitignored, so every
  hython suite run dirties the working tree."* Question: *"Gitignore it, redirect the
  tests to tmp_path, or leave it?"*
- `harness/notes/receipts/S2.json:161-162` — five USDC department layers written by
  `solaris_compose_tools.py:133-136`; disposition "LEFT IN PLACE, NOT DELETED … it is
  evidence."

**Proposed entry:**
```
# Solaris live-test artifact (RES-F11 / R57): no-hou fallback of
# solaris_compose_tools.py writes $HIP/<shot>_layers to CWD when $HIP is empty.
# Test litter, not a fixture. (Root cause: missing absolute-path guard at :133-136.)
shot_layers/
```

---

## Recommended combined block (for the human to append to `.gitignore`)

```gitignore
# --- TIDY 2026-08-07: data / generated-asset dirs ---
# Downloaded ONNX embedder (MiniLM-L6-v2) — model asset, not source.
# Docs: "No model ships with the repo." Expected at ~/.synapse/models/, not in-tree.
models/

# Solaris live-test artifact (RES-F11 / R57): no-hou fallback of
# solaris_compose_tools.py writes $HIP/<shot>_layers to CWD when $HIP is empty.
# Test litter, not a fixture. (Root cause: missing absolute-path guard at :133-136.)
shot_layers/
```

---

## Notes / follow-up

- **Root-cause fix (separate, not this dispatch):** the real remedy for `shot_layers/`
  is the missing absolute-path guard at `solaris_compose_tools.py:133-136` (redirect
  to `tmp_path` or guard `$HIP`). Gitignoring stops the tree-dirtying; it does not fix
  the write site. That is a `src/` change and is out of scope for this data-dirs
  dispatch (per the safety model, `src/` is not modified here).
- **`models/`** is a legitimately downloaded dependency; if a future decision wants it
  vendored, it should move to a proper assets location with a documented download
  path — not be committed at the repo root.
- Neither directory is deleted by this dispatch. Both remain on disk, untracked.
