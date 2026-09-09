# Windows installer verification

Local review of SYNAPSE 5.67.4, Windows x64, 2026-09-09. This is not a public
release qualification. The implementation is isolated on branch
`feature/windows-installer-20260909`; the artist installation and source master
checkout were not installed over.

The evidence board is the parent of this checkout:
`checks/windows-installer-20260909`. Its `artifacts`, `build/output`, test-seat
folders and append-only `bus` receipts contain the detailed results.

## Verified scope

- A compiled TestSetup completed fresh install, repeat install, upgrade from an
  explicitly synthetic 0.0.1 payload, and Windows uninstall. Registration pointed
  at installed files, and project data, credentials, settings, memory and custom
  files retained their hashes. See `executable-seat-01/executable-report.json`.
- Isolated unit regressions exercise journal crash boundaries, path escapes,
  manifest checks, migrations, competing changes, downgrade rejection,
  unavailable dependencies, discovery, and preservation. Independent hostile
  tests exposed actual failures before fixes. Detailed review receipts, including
  failed intermediate runs, are in `bus/INTEGRATOR-review.jsonl`.
- `artifacts/houdini-native.json` records a separate Houdini 22.0.400 process with
  Python 3.13.10. Actual import paths for SYNAPSE, Anthropic, pydantic/native core,
  jiter, websockets, filelock, shared, retina, the host cache helper, MCP tool
  definitions and Moneta were all inside the installed runtime. The probe
  registered the bundled Moneta USD schema and constructed SynapsePanel offscreen.
- Doctor executed; its rows are retained in `artifacts/houdini-doctor.json`.
  `moneta_substrate` is **FAIL**: schema registration was true, but schema use was
  UNKNOWN because no active USD root was supplied. No live memory store was
  instantiated. This is not an end-to-end Moneta storage pass.

## Unverified or limited

- The installer EXE is unsigned. Signing and public redistribution were not done.
  Moneta is proprietary and was bundled only for local evaluation.
- Native wizard visual inspection hit a computer-use app approval timeout. No
  successful screenshot review or native click-through is claimed.
- Full live artist GUI, shelf clicks, model access, scene-building behavior,
  a clean Windows machine/VM and genuine historical installer upgrades were not
  exercised. The artist GUI was left untouched.
- Only Houdini 22.0.400 / Python 3.13 was natively probed. Other builds require
  acknowledgement and separate qualification. Python 3.11 payload compatibility
  was not natively exercised here.
- Optional semantic models, external MCP server environments and external
  substrates are not bundled. Doctor may observe machine-provided optional
  components; those rows are not evidence that the installer supplies them.
- The native probe emitted an OpenSSL legacy-provider warning and reported that
  no Anthropic key was configured. No provider credentials were supplied.

## Reproduce

From the isolated code checkout:

```powershell
python -B -m unittest discover -s installer/tests -v
python -m pytest tests/test_install_package.py tests/test_install_package_parity.py tests/test_install_verify.py -q
```

See [installer/README.md](../../installer/README.md) for exact build, compiled
lifecycle and bounded native probe commands. The [filming walkthrough](windows-installer-demo.md)
identifies the additional live checks. Final rebuilt artifact hashes and expanded
compiled checks are recorded in the build/evidence reports.
