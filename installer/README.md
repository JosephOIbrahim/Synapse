# Build the Windows installer

This directory builds a conventional per-user Inno Setup wizard. Users run the
resulting EXE; the commands below are for builders. Builds use the canonical root
`VERSION`. Final artifact validation, release tags, uploads and signing are
separate release steps.

Published builds and their qualification notes are available in
[SYNAPSE releases](https://github.com/JosephOIbrahim/Synapse/releases).
Artists can follow the [installation guide](../docs/getting-started/installation.md);
the commands below reproduce a build.

## Inputs and build

Start in a reviewed Git checkout containing this directory. Use Windows x64,
Git, Python 3.11 or newer, and Inno Setup **7.1.0**. The local build was made
with stock Python 3.14; the embedded maintenance runtime is **3.13.15** and
Houdini's tested runtime is **3.13.10**, supplied by Houdini 22.0.400.

All fetched inputs have SHA-256 pins in [toolchain.lock.json](toolchain.lock.json).
For a new build workspace, fetch the compiler and maintenance runtime:

```powershell
$buildRoot = 'C:\path\to\build-staging'
$downloads = Join-Path $buildRoot 'downloads'
New-Item -ItemType Directory -Force -Path $downloads | Out-Null
$lock = Get-Content -LiteralPath installer/toolchain.lock.json -Raw | ConvertFrom-Json
foreach ($item in @($lock.inno, $lock.python)) {
    $name = [System.IO.Path]::GetFileName(([Uri]$item.url).AbsolutePath)
    $target = Join-Path $downloads $name
    Invoke-WebRequest -Uri $item.url -OutFile $target
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLower() -ne $item.sha256) {
        throw ('Download checksum mismatch: ' + $name)
    }
}
$compilerInstaller = Join-Path $downloads 'innosetup-7.1.0-x64.exe'
$signature = Get-AuthenticodeSignature -LiteralPath $compilerInstaller
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Pyrsys B.V.') {
    throw 'Compiler publisher could not be verified'
}
```

Install that verified compiler into a chosen tools directory using its standard
installer, then set `$iscc` to the resulting `ISCC.exe`. Alternatively, for a
hidden per-user builder setup:

```powershell
$innoDirectory = Join-Path $buildRoot 'tools\inno'
$compilerArgs = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CURRENTUSER', ('/DIR="' + $innoDirectory + '"'))
$process = Start-Process -FilePath $compilerInstaller -ArgumentList $compilerArgs -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw 'Compiler installation failed' }
$iscc = Join-Path $innoDirectory 'ISCC.exe'
```

Fetch only the two explicit wheels; no dependency resolution runs during Setup:

```powershell
python -m pip download --only-binary=:all: --no-deps --platform win_amd64 --implementation cp --python-version 3.13 --abi cp313 --dest $downloads filelock==3.20.0 websockets==15.0.1
foreach ($item in $lock.wheels.PSObject.Properties) {
    $target = Join-Path $downloads $item.Name
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLower() -ne $item.Value) {
        throw ('Wheel checksum mismatch: ' + $item.Name)
    }
}
```

The source already contains the Anthropic SDK and its transitive dependencies,
including Windows native SDK files for Python 3.11 and 3.13. Qt and OpenUSD come
from Houdini. No developer virtual environment is copied into the product.

### Explicit Moneta artifact

The 5.97.6 bundle uses Moneta 1.3.0 at commit
`4f7afc73736aecce6d55d5e03f28fb3137d474d3`, under the MIT License by its
copyright holder's written grant of 2026-10-19. The upstream metadata still
declares "Proprietary"; the bundle preserves that metadata and includes the
grant notice and full MIT text. `installer/moneta_license.json` binds the grant
to the exact source content. The builder never probes for or quietly includes
a sibling checkout.

Export an explicitly selected source into a portable archive:

```powershell
$monetaArchive = Join-Path $buildRoot 'moneta-local.zip'
python -B installer/build_payload.py --export-moneta 'C:\approved-source\Moneta' --output $monetaArchive
$monetaHash = (Get-FileHash -LiteralPath $monetaArchive -Algorithm SHA256).Hash.ToLower()
```

The exporter includes only `src/moneta/*.py` (recursively), the three schema
resources, generated distribution metadata, and provenance/license notices.
For the provided local archive, the expected SHA-256 is
`a0ac38e10abc62ef6cc26118d7c80ad206be6393014f6b38b76ba8d88327daba`
for `moneta-1.3.0-4f7afc73-canonical.zip`.
Record the digest of any independently approved archive rather than substituting
unreviewed contents under this digest.

Build the real installer:

```powershell
python -B installer/build_windows.py --downloads $downloads --iscc $iscc --output $buildRoot --moneta-bundle $monetaArchive --moneta-sha256 $monetaHash
```

Output: `C:\path\to\build-staging\output\SYNAPSE-<version>-Setup.exe` and its
`.build.json` report with installer hash, payload hash, maintenance file hashes,
component identity and toolchain pins. Each invocation creates a fresh staging
directory; the builder never deletes an earlier stage. The output EXE is unsigned.
The payload ZIP is deterministic for identical tracked inputs, revision and
builder Python; the EXE contains build-time metadata, so it is not advertised as
byte-identical across times or machines.

Omit both Moneta options to build the explicit JSONL-only variant. That variant
has not received the native Moneta-enabled probe reported for this review.
Different native Houdini/Python builds need their own qualification.

## Optional native artifact

The public 5.97.6 build adds the reviewed `moneta-native-0.1.0-win64-clean.zip`.
Its SHA-256 is `f0c67e0642305ce9db5f71d355712b6af9eb7d5db05e0d72c65d44403e47bb1e`,
independently bound in [native_artifact.json](native_artifact.json). Pass both
`--native-bundle <archive>` and `--native-sha256 <digest>` to the build command.
The builder refuses a different artifact, inventory, compatible Moneta identity
or missing hash. Omitting native options produces a separate native-OFF variant.

The native bundle retains upstream metadata and includes the owner's MIT grant,
four exact Rust source files, portable SBOM and third-party notices. Native source
Git HEAD is UNKNOWN; source-file hashes and tested binary identity are recorded
instead of inventing a commit. Known private paths were removed by a remapped
offline build; this is not a complete reproducible-build or universal secret scan.

Activation is restricted to Windows x64 / H22.0.400 / Python 3.13.10 and actual
disposable primary-Moneta/native write/reopen checks. Explicit OFF and existing
default-OFF remain OFF. Failed/unsupported explicit ON, including inherited ON, refuses activation. The
installer snapshots registrations and package namespace and checks them again
before switching. Uninstall restores exact supported migration backups.

## Payload and ownership

[build_payload.py](build_payload.py) uses `git ls-files` plus an explicit runtime
allowlist, then consolidates panel, shelf, callback and icon assets using
[synapse_setup/registration.py](synapse_setup/registration.py). It excludes test
folders, caches, credentials, local `.synapse` data, logs, HIP scenes and pip
provenance files. Every runtime file has a hash. Missing required dependencies,
changed wheels, invalid archive paths and inconsistent product versions fail.
The helper Python is isolated with a `_pth` file and needs no system packages.

Inno owns the wizard, maintenance files, Start menu shortcuts and per-user Windows
uninstall registration. The engine owns runtime versions and the single
`packages/synapse.json` in each selected preference folder. Registration uses
`hpath`; UI files do not have a second copy in user preferences. Legacy source
scripts share the same package/UI definitions but remain source-development tools.

Install stages a complete version directory, validates it, then switches
registration and diagnostic stamp with a write-ahead journal. Recovery validates
all destinations and prior contents. Upgrades keep older runtime directories;
no obsolete code is copied into the newly active one. Uninstall first deactivates
registration, then deletes only unchanged manifest-owned runtime files. A
completion receipt allows Windows cleanup to resume after an interruption. The maintenance manifest is retained so a later Setup can identify leftover helper caches and reinstall safely.

Edited runtime and added files are retained. Edited maintenance files block
upgrade/uninstall before Inno can overwrite or delete them; save the edits and
restore the original helper files before continuing. Unrelated preferences and
project/user memory are not recursively removed. Legacy migration backups are
restored on uninstall, which can reactivate the original source installation.

## Tests

Run the isolated engine regressions and existing source-installer tests:

```powershell
python -B -m unittest discover -s installer/tests -v
$legacyTemp = Join-Path $buildRoot ('legacy-tests-' + [Guid]::NewGuid().ToString('N'))
python -m pytest tests/test_install_package.py tests/test_install_package_parity.py tests/test_install_verify.py -q --basetemp $legacyTemp
```

The
[verification record](../docs/getting-started/windows-installer-verification.md)
records historical test-build commands. Release-specific qualification must bind
the actual final EXE, extracted payload and maintenance files to their hashes.

Build a separate TestSetup with `--test-build` added to the build command. It has
a distinct Windows AppId and requires `/TESTROOT`. Engine destinations must be
inside that root. Its running-Houdini guard is bypassed only for this isolated
mode; production Setup still refuses maintenance while Houdini is running.
Test shortcuts and its Windows uninstall entry use the isolated test name.
Only one compiled test installation can be registered at a time.

Create intentionally synthetic previous/missing-dependency installers:

```powershell
$version = (Get-Content -LiteralPath VERSION -Raw).Trim()
$testReport = Join-Path $buildRoot ("output\SYNAPSE-" + $version + "-TestSetup.build.json")
python -B installer/create_test_fixture.py --build-report $testReport --iscc $iscc --kind previous
python -B installer/create_test_fixture.py --build-report $testReport --iscc $iscc --kind missing-dependency
```

The 0.0.1 fixture is **not a historical release**. It changes only generated
payload bytes to exercise upgrade and retirement of old files.

Run the compiled sequence using a new, empty test root:

```powershell
python -B installer/test_executable.py --expected-version $version --setup "$buildRoot\output\SYNAPSE-$version-TestSetup.exe" --previous-setup "$buildRoot\output\SYNAPSE-fixture-previous.exe" --broken-setup "$buildRoot\output\SYNAPSE-fixture-missing-dependency.exe" --root "$buildRoot\test-seat-01" --hfs 'C:\Program Files\Side Effects Software\Houdini 22.0.400'
```

This runs compiled fresh/repeat/upgrade/uninstall/reinstall, failures, Windows
registration/shortcut cleanup and data-preservation checks. The write-denied
fixture changes only its new subfolder's ACL and restores that explicit deny in
`finally`. Logs and `executable-report.json` remain in the test root. A failed run
can leave the isolated installation registered for inspection; use its generated
uninstaller before another run. Never point this harness at an artist directory.

For a native check, first install into an isolated root using `setup_cli.py
install --sandbox ... --home ... --pref ... --app ... --hfs ... --payload ...`.
Use the payload path in the build report. Then:

```powershell
python -B installer/run_houdini_probe.py --app "$buildRoot\native-seat\application" --sandbox "$buildRoot\native-seat" --hfs 'C:\Program Files\Side Effects Software\Houdini 22.0.400' --report "$buildRoot\houdini-native.json"
```

The runner launches a separate bounded `hython` process with isolated preferences,
home, temp and project paths, strips provider credentials/launch overrides, and
uses offscreen Qt. It verifies actual installed import paths, Moneta USD schema,
panel construction and Doctor execution. Doctor rows are retained separately;
they are never converted to blanket PASS. No artist GUI or model request is used.

## Release follow-through

The separate TestSetup does not certify a production Setup. Extract and verify
the actual final EXE without executing its Windows integration on an artist seat,
and exercise its exact embedded maintenance engine/payload in disposable folders.
Wizard visuals, Windows registration/shortcuts, a clean Windows machine/VM, a full
artist GUI session and model access require their own measured qualification.
Signing requires an approved publisher certificate/process; no key is embedded.
Publication of another build, version changes, merge/push/tag and redistribution
of a different Moneta bundle require their own authorization.

References: [Inno Setup](https://jrsoftware.org/isinfo.php),
[Houdini packages](https://www.sidefx.com/docs/houdini/ref/plugins.html), and
[CPython 3.13.15](https://www.python.org/downloads/release/python-31315/).
