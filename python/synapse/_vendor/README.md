# Vendored Dependencies — `synapse._vendor`

**Sprint 3 Spike 2.2.** Bundled at commit (pending at time of writing).

## Why this exists

Houdini ships a separate Python `site-packages` per point release.
A `pip install anthropic` into `Houdini 21.0.631/python311/Lib/site-packages/`
is **invisible** to `Houdini 21.0.671/python311/Lib/site-packages/` —
the user's daemon boot fails with `DaemonBootError: anthropic SDK is
not installed` the moment they upgrade Houdini.

Vendoring the SDK and its transitive dependencies directly into the
SYNAPSE tree eliminates that failure mode. Every Houdini install that
can see `python/synapse/` automatically gets the full dep stack —
no runtime `pip install`, no per-point-release maintenance, no
cross-install variance.

This mirrors Spike 0 Bootstrap Lock #3:

> No runtime pip — bundle and pin all deps.

## ABI lock

**win_amd64, cp311 + cp313 (dual-ABI as of the H22 drop, 2026-07-15).**
The `pydantic_core` and `jiter` packages each ship native binary
extensions. Both ABIs now live side by side at the SAME package versions
(`pydantic_core` 2.46.3, `jiter` 0.14.0), so the pure-Python layer serves
either binary:

- `_pydantic_core.cp311-win_amd64.pyd` + `jiter.cp311-win_amd64.pyd` — CPython 3.11
- `_pydantic_core.cp313-win_amd64.pyd` + `jiter.cp313-win_amd64.pyd` — CPython 3.13

The running interpreter loads whichever matches its ABI.

Valid for:

- Houdini 20.5.x / 21.0.x (631, 671, …) / 21.5.x — Python **3.11** → cp311
- Houdini 22.0.x — Python **3.13** → cp313

Runs where it doesn't belong:

- Stock Python 3.14 on the same machine will load NEITHER binary (no cp314
  in the tree). The prepend in `synapse/__init__.py` is gated by
  `sys.version_info[:2] in _VENDOR_PYS` (`{(3, 11), (3, 13)}`), so
  stock-Python 3.14 test runs stay passive — system pydantic continues to
  resolve normally, and `_VENDOR_ABI_RISK` flags the fallback.

## Future cliff

**H22 (cp313) was handled this way on 2026-07-15** — see the drop-day
note below. When SideFX ships a Houdini release on a further Python line:

1. Re-vendor with the matching binary. **Match the vendored versions
   EXACTLY** (`pydantic_core` 2.46.3, `jiter` 0.14.0) — a version bump
   breaks the pure-Python layer (`pydantic` pins `pydantic_core` hard:
   2.13.3 requires exactly 2.46.3). Pull the right wheel:
   `pip download pydantic-core==2.46.3 jiter==0.14.0 --python-version <XYZ>
   --platform win_amd64 --only-binary=:all: --no-deps -d <dir>`, then copy
   only the `.pyd`s into `_vendor/pydantic_core/` and `_vendor/jiter/`
   (keep the pure-Python tree unchanged).
2. Widen `_VENDOR_PYS` in `synapse/__init__.py` to include the new line.
3. Update this document with the new supported versions.
4. `tests/conftest.py` `VENDOR_PYS` / `VENDOR_ABI_TAGS` +
   `tests/test_vendored_deps.py::test_native_package_has_all_vendored_abis`
   pin the expected ABIs; update them in lockstep, same commit.

> **Drop-day note (2026-07-15).** H22.0.368 shipped CPython 3.13. Executed
> steps 1–4 above: added cp313 `.pyd`s for pydantic_core 2.46.3 + jiter
> 0.14.0. **Gotcha found:** the pre-staged `harness/state/wheel_cache/cp313/`
> held pydantic_core **2.47.0**, which `pydantic` 2.13.3 rejects
> (`SystemError: incompatible ... requires 2.46.3`). Always pull the
> version-matched wheel, not "latest". Verified under H22 hython:
> `import synapse; import anthropic` clean, vendor active, no ABI warning.

## Refresh procedure

Run from the repo root:

```bash
PYTHONNOUSERSITE=1 "C:/Program Files/Side Effects Software/Houdini 21.0.631/bin/hython.exe" -c "
import sys, os
# Strip RenderMan paths (Spike 0 finding: RenderMan injects a broken
# pip via HOUDINI_PATH that shadows hython's own).
sys.path = [p for p in sys.path if ('pixar' not in p.lower() and 'renderman' not in p.lower())]
sys.path.insert(0, os.path.join(sys.prefix, 'Lib', 'site-packages'))
import runpy
sys.argv = [
    'pip', 'install',
    '--target', r'C:/Users/User/SYNAPSE/python/synapse/_vendor',
    '--cert', r'C:/Users/User/AppData/Roaming/Python/Python311/site-packages/certifi/cacert.pem',
    '--upgrade',
    '--no-compile',
    'anthropic',
]
runpy.run_module('pip', run_name='__main__')
"
```

After refresh:

```bash
# Drop pip entry-point scripts we don't need
rm -rf python/synapse/_vendor/bin/
# Drop any compiled byte-code
find python/synapse/_vendor -name __pycache__ -type d -exec rm -rf {} +
# Verify
pytest tests/test_vendored_deps.py -v
```

Then commit the updated tree.

## Pinned versions (this install)

Taken from the initial vendor run:

| Package | Version |
|---|---|
| anthropic | 0.96.0 |
| anyio | 4.13.0 |
| certifi | 2026.2.25 |
| distro | 1.9.0 |
| docstring-parser | 0.18.0 |
| h11 | 0.16.0 |
| httpcore | 1.0.9 |
| httpx | 0.28.1 |
| idna | 3.11 |
| jiter | 0.14.0 |
| pydantic | 2.13.3 |
| pydantic-core | 2.46.3 |
| sniffio | 1.3.1 |
| typing-extensions | 4.15.0 |
| typing-inspection | 0.4.2 |
| annotated-types | 0.7.0 |

Refreshing pulls whatever is latest and compatible; update this table
in the same commit that refreshes the tree.

## What is NOT vendored

- **`websockets`** — ships in Houdini's own site-packages and in the
  user-site. Not pulled in by anthropic's dep graph. We rely on it
  being present; the MCP server imports it directly.
- **`orjson`** — optional speedup; code falls back to stdlib `json`
  when absent.
- **Houdini's own modules** — `hou`, `hdefereval`, `pxr`. These are
  provided by the DCC at runtime; we never ship them ourselves.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ImportError: No module named 'pydantic_core._pydantic_core'` | Running on an interpreter whose ABI doesn't match the vendored `.pyd`. | Check `sys.version_info[:2]`. If Python 3.14+, ensure the version gate in `synapse/__init__.py` is active (it will be — this is the gated path). If 3.11 but wrong platform, re-vendor on the target platform. |
| `DaemonBootError: anthropic SDK is not installed` on a Houdini upgrade | `_vendor/` isn't being prepended. | Check `synapse._vendor_path` exists. Check `python/synapse/_vendor/anthropic/` is present on disk. Re-run the refresh procedure if missing. |
| Git sees tens of megabytes of "new" files under `_vendor/` | First-time commit of the vendor tree. | Expected — `_vendor/` is committed intentionally per the vendoring strategy. The `.gitignore` rules at the repo root whitelist the tree. |
| `git add` skips `_vendor/pydantic_core/_pydantic_core.cp311-win_amd64.pyd` | `.gitignore` rules above the whitelist block aren't being overridden. | Verify the `!python/synapse/_vendor/**` block in `.gitignore` is at the END of the file (later rules win in gitignore). |
