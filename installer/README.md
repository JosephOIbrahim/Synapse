# Build the Windows installer

This directory builds a conventional per-user Inno Setup wizard. Users run the
resulting EXE; the commands below are for builders. The reviewed product version
remains 5.67.4. No release version, tag, public upload or signing is performed.

## Inputs and build

Start in a reviewed Git checkout containing this directory. Use Windows x64,
Git, Python 3.11 or newer, and Inno Setup **7.1.0**. The local build was made
with stock Python 3.14; the embedded maintenance runtime is **3.13.15** and
Houdini's tested runtime is **3.13.10**, supplied by Houdini 22.0.400.

All fetched inputs have SHA-256 pins in [toolchain.lock.json](toolchain.lock.json).
For a new build workspace, fetch the compiler and maintenance runtime:

```powershell
$buildRoot = 'C:\synapse-build'
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

This review included Moneta 1.2.0rc1 for local evaluation. Moneta declares a
proprietary license; obtain the necessary rights before distributing it. The
builder never probes for or quietly includes a sibling checkout.

Export an explicitly selected source into a portable archive:

```powershell
$monetaArchive = Join-Path $buildRoot 'moneta-local.zip'
python -B installer/build_payload.py --export-moneta 'C:\approved-source\Moneta' --output $monetaArchive
$monetaHash = (Get-FileHash -LiteralPath $monetaArchive -Algorithm SHA256).Hash.ToLower()
```

The exporter includes only `src/moneta/*.py` (recursively), the three schema
resources, generated distribution metadata, and provenance/license notices.
For the provided local archive, the expected SHA-256 is
`81a3d8735c7da49ca81302725acab6a3324311091e850c34afcea92e87ea31f7`.
Record the digest of any independently approved archive rather than substituting
unreviewed contents under this digest.

Build the real installer:

```powershell
python -B installer/build_windows.py --downloads $downloads --iscc $iscc --output $buildRoot --moneta-bundle $monetaArchive --moneta-sha256 $monetaHash
```

Output: `C:\synapse-build\output\SYNAPSE-5.67.4-Setup.exe` and its
`.build.json` report with installer hash, payload hash, maintenance file hashes,
component identity and toolchain pins. Each invocation creates a fresh staging
directory; the builder never deletes an earlier stage. The output EXE is unsigned.
The payload ZIP is deterministic for identical tracked inputs, revision and
builder Python; the EXE contains build-time metadata, so it is not advertised as
byte-identical across times or machines.

Omit both Moneta options to build the explicit JSONL-only variant. That variant
has not received the native Moneta-enabled probe reported for this review.
Different native Houdini/Python builds need their own qualification.

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
completion receipt allows Windows cleanup to resume after an interruption.

Edited runtime and added files are retained. Edited maintenance files block
upgrade/uninstall before Inno can overwrite or delete them; save the edits and
restore the original helper files before continuing. Unrelated preferences and
project/user memory are not recursively removed. Legacy migration backups are
restored on uninstall, which can reactivate the original source installation.

## Tests

Run the isolated engine regressions and existing source-installer tests:

```powershell
python -B -m unittest discover -s installer/tests -v
python -m pytest tests/test_install_package.py tests/test_install_package_parity.py tests/test_install_verify.py -q
```

The
[verification record](../docs/getting-started/windows-installer-verification.md)
records the exact command used for this build.

Build a separate TestSetup with `--test-build` added to the build command. It has
a distinct Windows AppId and requires `/TESTROOT`. Engine destinations must be
inside that root. Its running-Houdini guard is bypassed only for this isolated
mode; production Setup still refuses maintenance while Houdini is running.
Test shortcuts and its Windows uninstall entry use the isolated test name.
Only one compiled test installation can be registered at a time.

Create intentionally synthetic previous/missing-dependency installers:

```powershell
$testReport = Join-Path $buildRoot 'output\SYNAPSE-5.67.4-TestSetup.build.json'
python -B installer/create_test_fixture.py --build-report $testReport --iscc $iscc --kind previous
python -B installer/create_test_fixture.py --build-report $testReport --iscc $iscc --kind missing-dependency
```

The 0.0.1 fixture is **not a historical release**. It changes only generated
payload bytes to exercise upgrade and retirement of old files.

Run the compiled sequence using a new, empty test root:

```powershell
python -B installer/test_executable.py --setup "$buildRoot\output\SYNAPSE-5.67.4-TestSetup.exe" --previous-setup "$buildRoot\output\SYNAPSE-fixture-previous.exe" --broken-setup "$buildRoot\output\SYNAPSE-fixture-missing-dependency.exe" --root "$buildRoot\test-seat-01" --hfs 'C:\Program Files\Side Effects Software\Houdini 22.0.400'
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

This branch provides local build artifacts and evidence. Native wizard visual
inspection, a clean Windows machine/VM, a full artist GUI session, model access,
and genuine historical installer upgrades remain separate qualification work.
Signing requires an approved publisher certificate/process; no key is embedded.
Public release, version changes, merge/push/tag and Moneta redistribution require
their own authorization. No download link to an unpublished release is invented.

References: [Inno Setup](https://jrsoftware.org/isinfo.php),
[Houdini packages](https://www.sidefx.com/docs/houdini/ref/plugins.html), and
[CPython 3.13.15](https://www.python.org/downloads/release/python-31315/).
