# Windows installer verification

Local review of SYNAPSE 5.67.4, Windows x64, 2026-09-09. This is not a public
release qualification. The implementation is isolated on branch
`feature/windows-installer-20260909`; the artist installation and source master
checkout were not installed over.

The evidence board is the parent of this checkout:
`checks/windows-installer-20260909`. Paths below are relative to that board.
Earlier build and test directories are retained as evidence; the delivery
artifacts are specifically in `build-delivery/output`.

## Delivery identity

Both installers were built from implementation commit
`15ad0eb2974dd0263a8af5915acfdfc2a1416aef`. Subsequent verification documentation
does not change their implementation. No `VERSION` surface was changed.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `build-delivery/output/SYNAPSE-5.67.4-Setup.exe` | 31,824,451 | `92935703f934b2d7d2ccde377f6e4195da7ad44e44f5ac804c108da011971845` |
| `build-delivery/output/SYNAPSE-5.67.4-TestSetup.exe` | 31,824,840 | `64dc68b9acc03cd176529c630e1ce691d602013ad261d9cc145e55bd21849978` |

Windows Authenticode reports **NotSigned** for both files. The adjacent
`.build.json` reports record the toolchain, payload and maintenance file hashes.
Both carry the same 1,817-file runtime and 41 maintenance files. The payload ID is
`5.67.4-53b476b278b143f6`; payload ZIP SHA-256 is
`057e307fcf06eb6ae7908b9f960f34136696d6a3318c19b6ca4817300e8d2726`.
TestSetup uses a separate Windows AppId and confines engine destinations to its
test root. The production EXE was built and hash checked; only TestSetup was
executed through the compiled lifecycle.

`artifacts/delivery-artifact-inventory.json` records the artifact sizes/hashes,
test counts and qualification limits. Independent final review is **PASS** for
source/artifact consistency and the bounded evidence below, in
`bus/INTEGRATOR-review.jsonl` under leg
`windows-installer-20260909:delivery-qualified:INTEGRATOR`. Earlier failed receipts
remain intact.

## Verified scope

- **All 19 compiled lifecycle checks passed** in
  `executable-seat-delivery/executable-report.json`, with individual Windows logs
  under that seat's `logs` directory. This covers fresh/repeat install, upgrade
  from an explicitly synthetic 0.0.1 payload, installed registration and helper
  verification, normal Windows uninstall, reinstall with retained data, and
  resuming Windows cleanup after the runtime uninstall has already completed.
  Failures exercised a missing dependency, readable error text, a real Windows
  write-denied directory, an edited registration and an edited maintenance file.
  Project, credential, settings, memory and custom-file fixture hashes survived
  upgrade and uninstall. A final Windows check confirmed that the test AppId and
  shortcut group were absent. No historical installer compatibility is inferred
  from the synthetic prior payload.
- **37 installer unit tests passed**: 26 independent adversarial checks and 11
  lifecycle checks. The regressions exercise journal crash boundaries, path escapes,
  manifest checks, migrations, competing changes, downgrade rejection,
  unavailable dependencies, discovery, and preservation. Independent hostile
  tests exposed actual failures before fixes. Detailed review receipts, including
  failed intermediate runs, are in `bus/INTEGRATOR-review.jsonl`. Full test output
  is in `artifacts/installer-tests-final.txt`.
- **34 existing source-installer tests passed**; see
  `artifacts/legacy-tests-final.txt`. These ran under stock Python 3.14.2, which
  correctly warns that the vendored native SDK targets Python 3.11/3.13. The
  separate native probe below verifies the actual Python 3.13 dependencies.
- `artifacts/delivery-native/engine-install.json` verifies every installed runtime
  file and the XML/package registration from the exact delivery payload.
- `artifacts/delivery-native/houdini-native.json` records a separate Houdini 22.0.400 process with
  Python 3.13.10. Actual import paths for SYNAPSE, Anthropic, pydantic/native core,
  jiter, websockets, filelock, shared, retina, the host cache helper, MCP tool
  definitions and Moneta were all inside the installed runtime. The probe
  registered the bundled Moneta USD schema and constructed SynapsePanel offscreen.
- Doctor executed; its rows are retained in
  `artifacts/delivery-native/houdini-doctor.json` (9 ok, 1 fail, 4 skipped).
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
- Crash boundaries use deterministic interruption tests, and reparse-path tests
  simulate filesystem metadata. Actual power loss, native junction creation and
  simultaneous-process stress were not exercised.
- Optional semantic models, external MCP server environments and external
  substrates are not bundled. Doctor may observe machine-provided optional
  components; those rows are not evidence that the installer supplies them.
- The native probe emitted an OpenSSL legacy-provider warning and reported that
  no Anthropic key was configured. No provider credentials were supplied.

## Reproduce

From the isolated code checkout:

```powershell
python -B -m unittest discover -s installer/tests -v
$freshTestTemp = Join-Path (Resolve-Path '..').Path ('pytest-legacy-' + [Guid]::NewGuid().ToString('N'))
python -m pytest tests/test_install_package.py tests/test_install_package_parity.py tests/test_install_verify.py -q --basetemp $freshTestTemp
```

The recorded legacy run used `--basetemp ../pytest-legacy-final-01`. Use a fresh
path when repeating it so pytest does not clear prior evidence. The default
system pytest temporary directory was inaccessible in this session.

See [installer/README.md](../../installer/README.md) for pinned inputs, complete
build instructions, synthetic fixture creation, compiled lifecycle and bounded
native probe commands. Build logs are `artifacts/build-delivery-production.txt`
and `artifacts/build-delivery-test.txt`. The [filming walkthrough](windows-installer-demo.md)
identifies the additional live checks.

The exact final compiled run used these board-relative artifacts (all arguments
were passed as absolute paths):

```powershell
$reviewBoard = (Resolve-Path '..').Path
$delivery = Join-Path $reviewBoard 'build-delivery'
python -B installer/test_executable.py --setup "$delivery\output\SYNAPSE-5.67.4-TestSetup.exe" --previous-setup "$delivery\output\SYNAPSE-fixture-previous.exe" --broken-setup "$delivery\output\SYNAPSE-fixture-missing-dependency.exe" --root "$reviewBoard\executable-seat-delivery" --hfs 'C:\Program Files\Side Effects Software\Houdini 22.0.400'
python -B installer/run_houdini_probe.py --app '../native-seat-delivery/application' --sandbox '../native-seat-delivery' --hfs 'C:\Program Files\Side Effects Software\Houdini 22.0.400' --report '../artifacts/delivery-native/houdini-native.json'
```

These paths identify the completed evidence, not disposable scratch folders. Use
new test/native roots for another run and first install that native payload as
described in the build guide.
