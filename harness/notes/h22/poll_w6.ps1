Write-Host ("now " + (Get-Date -Format 'HH:mm:ss'))
Get-Content C:\Users\User\SYNAPSE\harness\notes\h22\orchestrator-w5l.log -Tail 3
Get-ChildItem C:\Users\User\SYNAPSE\harness\notes\h22\*-landed.flag -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty Name
$hits = Get-Process | Where-Object { $_.MainWindowTitle -match 'W6-FORGE|W5-(SEAT|MEASURES)' }
if ($hits) {
    Add-Type -AssemblyName Microsoft.VisualBasic
    $wsh = New-Object -ComObject WScript.Shell
    foreach ($p in $hits) {
        [Microsoft.VisualBasic.Interaction]::AppActivate($p.Id); Start-Sleep -Milliseconds 700
        $wsh.SendKeys('/rc'); Start-Sleep -Milliseconds 300; $wsh.SendKeys('~'); Start-Sleep -Milliseconds 400
        Write-Host ("sent /rc -> " + $p.MainWindowTitle.Substring(0,[Math]::Min(55,$p.MainWindowTitle.Length)))
    }
} else { Write-Host 'rc-watch: no new target windows' }
