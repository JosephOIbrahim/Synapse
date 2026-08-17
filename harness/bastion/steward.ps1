# steward.ps1 - BASTION harness v2 detached ops steward. READS harness state;
# NEVER touches gates. FORK of harness/notes/h22/steward.ps1 (traced 2026-08-17,
# W8-SMITH). Automates: /rc delivery to new leg windows, crash-loop detection,
# FAILED/stale toasts. The P4 seam (merge/push-word/drop/ratified) stays human.
#
# v2 DELTAS (W8-SMITH target 4):
#   * $DeadlineHours is a PARAM (default 12h, past a typical wave horizon) so the
#     arm template can refresh liveness as a property of arming, not a manual act
#     (PROGRAM.md /rc doctrine).
#   * Log paths are params so a bastion wave is not pinned to the w5l file names.
#   * /rc DELIVERY is preserved VERBATIM: SendKeys('/rc') + '~' to windowed legs,
#     matched by window title, once each. This is the RESOLVED half of the /rc
#     question (delivery mechanism). What '/rc' RESOLVES TO inside Claude Code is
#     UNKNOWN (W8-SMITH task 1 verdict) - that gap belongs to the arm template's
#     headless bake-in slot, not here: a windowed leg simply receives the literal
#     keystroke exactly as the shipped steward sent it.
param(
    [double]$DeadlineHours = 12,
    [string]$LegLog  = 'C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-bastion.log',
    [string]$StewardLog = 'C:\Users\User\SYNAPSE\harness\notes\h22\steward-bastion.log',
    # Legs already handed /rc (pre-seed to skip). Hashtable of legId -> $true.
    [hashtable]$RcDone = @{}
)
$ErrorActionPreference = 'Stop'
$deadline = (Get-Date).AddHours($DeadlineHours)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName Microsoft.VisualBasic
$wsh = New-Object -ComObject WScript.Shell
$rcDone = $RcDone
$toasted = @{}
$lastLine = 0
function Toast($title, $msg) {
    [System.Windows.Forms.MessageBox]::Show($msg, $title,
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Warning,
        [System.Windows.Forms.MessageBoxDefaultButton]::Button1,
        [System.Windows.Forms.MessageBoxOptions]::DefaultDesktopOnly) | Out-Null
}
while ((Get-Date) -lt $deadline) {
    # 1) /rc to any new leg window, once each (delivery VERBATIM from the shipped
    #    steward, steward.ps1:22-31). Definition of /rc is UNKNOWN; the keystroke
    #    is what the windowed leg receives.
    $wins = Get-Process | Where-Object { $_.MainWindowTitle -match 'SYNAPSE (W[A-Z0-9]+-[A-Z0-9]+)' }
    foreach ($p in $wins) {
        if ($p.MainWindowTitle -match 'SYNAPSE (W[A-Z0-9]+-[A-Z0-9]+)') {
            $leg = $Matches[1]
            if (-not $rcDone[$leg]) {
                [Microsoft.VisualBasic.Interaction]::AppActivate($p.Id); Start-Sleep -Milliseconds 700
                $wsh.SendKeys('/rc'); Start-Sleep -Milliseconds 300; $wsh.SendKeys('~')
                $rcDone[$leg] = $true
                Add-Content $StewardLog ((Get-Date -Format 'HH:mm:ss') + "  /rc -> " + $leg)
            }
        }
    }
    # 2+3) scan new orchestrator lines for FAILED / stale / crash signals
    $lines = @(Get-Content $LegLog -ErrorAction SilentlyContinue)
    if ($lines.Count -gt $lastLine) {
        foreach ($l in $lines[$lastLine..($lines.Count - 1)]) {
            if ($l -match 'FAILED|STALE|NOT dispatched|crash') {
                $key = ($l -replace '\d', '').Substring(0, [Math]::Min(60, $l.Length))
                if (-not $toasted[$key]) {
                    $toasted[$key] = $true
                    Add-Content $StewardLog ((Get-Date -Format 'HH:mm:ss') + "  ALERT " + $l)
                    Toast 'SYNAPSE steward (bastion)' ("Attention: " + $l + "`n`nSteward detected this; gates untouched.")
                }
            }
        }
        $lastLine = $lines.Count
    }
    Start-Sleep -Seconds 60
}
Add-Content $StewardLog ((Get-Date -Format 'HH:mm:ss') + '  steward deadline reached, exiting')
