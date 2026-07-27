# v5.35.1 — the corpus was five years old

*A patch, not a feature release. Two behavioural fixes and one class of encoding defect. `v5.35.0` shipped this morning; this closes what the day's own audits found in it.*

---

## SYNAPSE was running on Houdini 22 and thinking in Houdini 21

Found because a live agent response cited *"H21.0.671 LOP node parameter names."* SYNAPSE has been on 22.0.368 since 15 July.

`scout.py` selects its symbol table by running Houdini major:

```python
major = str(EXPECTED_HOUDINI_VERSION or "").split(".", 1)[0]
candidate = f"h{major}_symbol_table.json"
```

**`EXPECTED_HOUDINI_VERSION` was declared `None` and nothing in the codebase ever assigned it.** Its docstring said *"mcp_server sets it when hou is importable."* No such injector existed.

So `major` was always `""`, the guard always failed, and every session silently loaded the H21 table. **`h22_symbol_table.json` is 1.2 MB and had never been read once.**

The injector now exists at `synapse/host/version_injector.py` and runs in the daemon boot chain.

**Why it mattered more than a stale filename:** Copernicus barely existed in H21. A model reasoning from an H21 corpus about a COP graph is reasoning about a different product — and it explains why COP grounding measured 6.2%. That figure was never *thin*; it was measured against a corpus predating the subsystem.

**What was NOT broken:** `wiring.py` and `lop_knowledge.py` both probe correctly and were already loading their H22 catalogues. An earlier version of this finding claimed otherwise. Scout was the outlier, not the rule.

---

## Seven version locations, and they disagreed

```
VERSION · __version__ · pyproject.toml · __init__ docstring
CLAUDE.md banner · git tag · install stamp
```

`v5.35.0` bumped `VERSION` and tagged. It did not touch the other four in-repo locations, so the running code reported **5.33.0** while the tag said **5.35.0** — which is what `synapse_doctor` was reading when it flagged a version mismatch.

`harness/verify/version_agreement.py` now enforces all six checkable locations and runs in the release path. `VERSION` is canonical; the rest derive.

---

## A UTF-8 BOM will silently prevent SYNAPSE from loading

**This one is worth reading even if you never hit the others.**

A BOM (`EF BB BF`) on `packages/synapse.json` makes Houdini's package parser reject the file — **with no error, no warning, and no diagnostic.** `import synapse` still works, the version still prints, and the panel simply never appears.

PowerShell's `Set-Content -Encoding utf8` writes one on Windows PowerShell 5.1. SideFX's own packages, and every working third-party package we checked, begin with `7B` — a bare `{`.

```powershell
# writes a BOM - Houdini will not load this
Set-Content synapse.json $text -Encoding utf8

# no BOM
[System.IO.File]::WriteAllText($p, $text, (New-Object System.Text.UTF8Encoding $false))
```

`harness/verify/bom_audit.py` now guards every JSON this project writes, `VERSION` included — which is where it found the next one.

---

## Also in this patch

**The README carries the install traps.** Three ways to get a silent non-install: the BOM, `path` instead of `hpath`, and a `PYTHONPATH` missing the repo root. All three end the same way — no error, no panel.

**`hou.RopNode` render cancellation, corrected.** `v5.35.0` implied no way existed to stop a render. `rkill` works. The narrower and true statement is that `RopNode` carries no cancel method and integrators must drop to hscript.

---

## Known limitations, unchanged from v5.35.0

The PDG rollback still raises `TypeError` on every call. Emergency halt is still unsurfaced in the panel. 41 node types in use are deprecated, 39 of them invisible to a runtime probe. Node grounding remains 18.3% LOP and 6.2% Copernicus.

None of those moved in this patch, and saying so is the point of listing them.

---

## Verifying any of this

```
python harness/verify/version_agreement.py     # seven locations
python harness/verify/bom_audit.py             # every JSON, VERSION included
python harness/heats_status.py                 # leg board
```

Each fails on an unfixed tree. That was demonstrated before any of them was trusted.
