# detached.ps1 - start a PowerShell process outside the caller's process tree.
#
# BP12 item 6. On 2026-09-28 the Claude desktop app restarted at 15:12 and took
# the BP11 orchestrator with it, because the orchestrator was a child of a shell
# the app had opened. Win32_Process.Create starts the process through the WMI
# service instead, so it outlives the app, the shell and the arming script.
#
# Two things do not cross over, so the caller hands them in:
#   * $env: edits made in this shell. The new process starts from the user's
#     stored environment; -Environment sets variables inside it before -Command.
#   * Stream redirection. -LogPath sends every output stream to one file.
# The returned pid is the PowerShell process that runs -Command itself, so a
# pid file can stop it later. Dot-source this file; it only defines functions.

function Format-PSLiteral([string]$Text) {
    # A single-quoted PowerShell literal for $Text; an apostrophe is doubled.
    return "'" + ($Text -replace "'", "''") + "'"
}

function Start-Detached {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [System.Collections.IDictionary]$Environment = @{},
        [string]$LogPath = ''
    )
    $prefix = ''
    foreach ($name in $Environment.Keys) {
        if ($name -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
            throw "Start-Detached: '$name' is not an environment variable name"
        }
        $prefix += '$env:' + $name + ' = ' + (Format-PSLiteral ([string]$Environment[$name])) + '; '
    }
    $body = $prefix + $Command
    if ($LogPath) { $body = '& { ' + $body + ' } *> ' + (Format-PSLiteral $LogPath) }
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($body))
    $startup = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ ShowWindow = [uint16]0 }
    $result = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine               = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -EncodedCommand ' + $encoded
        CurrentDirectory          = $WorkingDirectory
        ProcessStartupInformation = $startup
    }
    if ($result.ReturnValue -ne 0) {
        throw "Start-Detached: Win32_Process.Create returned $($result.ReturnValue)"
    }
    return [int]$result.ProcessId
}
