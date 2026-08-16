# W6-HCRX independent GATE attack. FRESH scenarios (not the builder's V1/V2/V3 walk),
# reordered so each condition is isolated without cross-contamination:
#   G-B  receipt IS HEAD, only a DECOY release (wrong frm) + a claim(release field) -> closing "no RELEASE line"
#   G-A  valid RELEASE now present, receipt buried 2 commits deep                    -> closing "is not the branch HEAD"
#        (isolates the HEAD check: refusal fires even though a valid RELEASE exists)
#   OK   receipt re-committed as HEAD, valid RELEASE present                         -> done
$ErrorActionPreference = 'Stop'
$ORCH = $args[0]; $BUS = $args[1]
$root = Join-Path ([System.IO.Path]::GetTempPath()) ("w6hcrx_gate_" + [guid]::NewGuid().ToString('N').Substring(0,10))
$fail = 0
function RunGit($wt,[string[]]$a){ $o = & git.exe -C $wt @a 2>&1; if($LASTEXITCODE -ne 0){ throw "git $($a -join ' '): $o" }; return $o }
try {
    $wt = Join-Path $root 'wt'
    New-Item -ItemType Directory -Force -Path $wt | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $root 'harness\autorevise') | Out-Null
    Copy-Item $BUS (Join-Path $root 'harness\autorevise\bus.py') -Force
    $scratchBus = Join-Path $root 'harness\autorevise\bus.py'
    function Bus([string[]]$a){ & python $scratchBus @a *> $null }

    RunGit $wt @('init','-q'); RunGit $wt @('config','user.email','a@b.c'); RunGit $wt @('config','user.name','x')
    RunGit $wt @('checkout','-q','-b','wave99/hcrxgate')
    Set-Content -Path (Join-Path $wt 'product.txt') -Value 'work' -Encoding utf8
    RunGit $wt @('add','product.txt'); RunGit $wt @('commit','-q','-m','product')
    $rcptDir = Join-Path $wt 'harness\notes\receipts'; New-Item -ItemType Directory -Force -Path $rcptDir | Out-Null
    $rcpt = Join-Path $rcptDir 'W99-HCRXGATE.json'; $rcptRel = 'harness/notes/receipts/W99-HCRXGATE.json'

    $env:SYNAPSE_ORCH_LIB = '1'
    . $ORCH -Repo $root -DryRun -Quiet *> $null
    $ErrorActionPreference = 'Stop'
    $leg = [pscustomobject]@{ id='W99-HCRXGATE'; name='hcrx gate attack'; receipt='W99-HCRXGATE.json'
                              branch='wave99/hcrxgate'; worktree='wt'; deps=@() }
    function Scenario([string]$tag,[string]$expState,[string]$expPhrase){
        $script:CloseGateReason['W99-HCRXGATE'] = $null
        $state  = Get-LegState $leg
        $reason = $script:CloseGateReason['W99-HCRXGATE']
        $okS = ($state -eq $expState)
        $okR = ([string]::IsNullOrEmpty($expPhrase)) -or ($reason -and $reason.Contains($expPhrase))
        $v = if($okS -and $okR){'PASS'}else{'FAIL'; $script:fail++}
        Write-Host ("[{0}] {1}  state={2} (want {3})" -f $tag,$v,$state,$expState)
        if($reason){ Write-Host ("     message: {0}" -f $reason) }
        if(-not $okR){ Write-Host ("     WANT PHRASE: {0}" -f $expPhrase) -ForegroundColor Red }
    }
    Write-Host "=== W6-HCRX GATE attack (fresh scenarios, real Get-LegState) ===" -ForegroundColor Cyan

    # G-B FIRST (no valid release yet): receipt IS HEAD, only a decoy release + a claim.
    Set-Content -Path $rcpt -Value '{"leg":"W99-HCRXGATE","status":"green"}' -Encoding utf8
    RunGit $wt @('add',$rcptRel); RunGit $wt @('commit','-q','-m','receipt is HEAD')
    Bus @('post','wave99','W99-DECOY','status','{\"release\":[\"harness/orchestrate.ps1\"]}')    # decoy: WRONG frm
    Bus @('post','wave99','W99-HCRXGATE','claim','{\"release\":[\"harness/orchestrate.ps1\"]}')   # decoy: right frm, type=claim not status
    Scenario 'G-B receipt=HEAD, only DECOY release' 'closing' 'no RELEASE line for W99-HCRXGATE'

    # Now post a VALID release, then bury the receipt 2 commits deep.
    Bus @('post','wave99','W99-HCRXGATE','status','{\"release\":[\"harness/orchestrate.ps1\"]}')  # VALID release present
    Set-Content -Path (Join-Path $wt 'p2.txt') -Value 'more' -Encoding utf8
    RunGit $wt @('add','p2.txt'); RunGit $wt @('commit','-q','-m','later work 1')
    Set-Content -Path (Join-Path $wt 'p3.txt') -Value 'more2' -Encoding utf8
    RunGit $wt @('add','p3.txt'); RunGit $wt @('commit','-q','-m','later work 2')
    Scenario 'G-A receipt-buried-2-deep (+valid RELEASE)' 'closing' 'is not the branch HEAD'

    # OK: re-commit the receipt as HEAD; valid RELEASE already present -> done
    Set-Content -Path $rcpt -Value '{"leg":"W99-HCRXGATE","status":"green","v":2}' -Encoding utf8
    RunGit $wt @('add',$rcptRel); RunGit $wt @('commit','-q','-m','receipt is the closing commit')
    Scenario 'OK receipt=HEAD + valid RELEASE' 'done' ''

    Write-Host ""
    if($fail -eq 0){ Write-Host "=== GATE-ATTACK PASS: both forged closes refused with exact messages; clean close only with receipt=HEAD + RELEASE ===" -ForegroundColor Green }
    else { Write-Host "=== GATE-ATTACK FAIL: $fail scenario(s) off ===" -ForegroundColor Red }
}
finally {
    Remove-Item Env:\SYNAPSE_ORCH_LIB -ErrorAction SilentlyContinue
    if(Test-Path $root){ Remove-Item $root -Recurse -Force -ErrorAction SilentlyContinue }
}
exit $fail
