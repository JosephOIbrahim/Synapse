param([string]$Orch, [string]$Repo, [string]$ManifestFile, [string]$OutDir, [string]$OutJson)
# W6-HCRX independent QUOTE attack. Distinct from the builder's ADVERSARIAL_NAMES.
# Drives the REAL orchestrate.ps1 -DryRun, then per generated runner:
#  (1) PowerShell Language Parser: parse-error count + BOM
#  (2) AST CommandAst enumeration: ONLY Set-Location/Write-Host/claude allowed.
#      Any extra command => a payload broke into a code position (real injection).
$env:SYNAPSE_ORCH_LIB = '1'
$env:TEMP = $OutDir
$env:TMP  = $OutDir
. $Orch -Repo $Repo -DryRun *> $null
$manifest = [System.IO.File]::ReadAllText($ManifestFile) | ConvertFrom-Json
$script:DryDispatched = @{}
$ALLOWED = @('Set-Location','Write-Host','claude')
$res = [ordered]@{}
foreach ($leg in @($manifest.legs)) {
    Start-Leg $leg *> $null
    $rp = Join-Path $env:TEMP ("orch_" + $leg.id + ".ps1")
    $entry = [ordered]@{}
    if (Test-Path $rp) {
        $errs = $null; $toks = $null
        $ast = [System.Management.Automation.Language.Parser]::ParseFile($rp, [ref]$toks, [ref]$errs)
        $bytes = [System.IO.File]::ReadAllBytes($rp)
        $entry.exists = $true
        $entry.count  = $errs.Count
        $entry.errors = @($errs | ForEach-Object { $_.Message })
        $entry.bom    = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
        $cmds = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true)
        $names = @($cmds | ForEach-Object { $_.GetCommandName() } | Where-Object { $_ })
        $entry.commands = $names
        $entry.unexpected = @($names | Where-Object { $ALLOWED -notcontains $_ })
    } else {
        $entry.exists = $false; $entry.count = -1; $entry.errors = @('runner not written')
        $entry.bom = $false; $entry.commands = @(); $entry.unexpected = @('<no-runner>')
    }
    $res[[string]$leg.id] = $entry
}
$res | ConvertTo-Json -Depth 8 | Out-File -FilePath $OutJson -Encoding utf8
