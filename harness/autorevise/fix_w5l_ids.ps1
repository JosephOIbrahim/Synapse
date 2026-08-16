$ErrorActionPreference = 'Stop'
$enc = New-Object System.Text.UTF8Encoding($false)
Get-ChildItem C:\Users\User\SYNAPSE\harness\autorevise\missions\w5l_*.json | ForEach-Object {
    $raw = [System.IO.File]::ReadAllText($_.FullName)
    if ($raw[0] -eq [char]0xFEFF) { $raw = $raw.Substring(1) }
    [System.IO.File]::WriteAllText($_.FullName, $raw, $enc)
    Write-Host ("debommed " + $_.Name)
}
Set-Location C:\Users\User\SYNAPSE\harness\autorevise
python compile_wave.py
