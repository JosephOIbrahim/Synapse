# AUTORESEARCH live terminal v3 - flicker-free in-place repaint.
# One progress bar per agent. Clear-Host runs ONCE; every frame after homes
# the cursor and overwrites padded lines - no blank flash. Safe to close
# anytime; workers run detached. ASCII only - PS 5.1 reads this file raw.

$RefreshSeconds = 2   # raise to 3-5 for an even calmer window

$ar = Split-Path -Parent $MyInvocation.MyCommand.Path
$runs = Join-Path $ar 'runs'
$host.UI.RawUI.WindowTitle = 'AUTORESEARCH - live'
try { [Console]::CursorVisible = $false } catch { }
Clear-Host
$tick = 0
$prevCount = 0
$frame = New-Object System.Collections.Generic.List[object]

function Bar([int]$pct, [int]$width) {
    if ($pct -lt 0) { $pct = 0 }
    if ($pct -gt 100) { $pct = 100 }
    $n = [int][math]::Round($width * $pct / 100.0)
    return ('[' + ('#' * $n) + ('-' * ($width - $n)) + ']')
}

function BootBar([int]$width, [int]$t) {
    $p = $t % $width
    return ('[' + ('.' * $p) + '>' + ('.' * ($width - 1 - $p)) + ']')
}

function AddLine([string]$text, [string]$color) {
    $script:frame.Add(@{ t = $text; c = $color })
}

function PaintFrame {
    $w = 78
    try { $w = $host.UI.RawUI.WindowSize.Width - 1 } catch { }
    if ($w -lt 40) { $w = 40 }
    try {
        $home = New-Object System.Management.Automation.Host.Coordinates 0, 0
        $host.UI.RawUI.CursorPosition = $home
    } catch { Clear-Host }
    foreach ($ln in $script:frame) {
        $t = [string]$ln.t
        if ($t.Length -gt $w) { $t = $t.Substring(0, $w) }
        Write-Host ($t.PadRight($w)) -ForegroundColor $ln.c
    }
    $extra = $script:prevCount - $script:frame.Count
    for ($i = 0; $i -lt $extra; $i++) { Write-Host (' ' * $w) }
    $script:prevCount = $script:frame.Count
    $script:frame.Clear()
}

while ($true) {
    $tick++
    AddLine 'AUTORESEARCH  live terminal   (safe to close - workers run detached)' 'Cyan'
    AddLine ('-' * 78) 'Gray'

    if (-not (Test-Path $runs)) {
        AddLine 'no runs yet' 'Gray'
        PaintFrame
        Start-Sleep $RefreshSeconds
        continue
    }
    $dirs = Get-ChildItem $runs -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending
    if (-not $dirs) {
        AddLine 'no runs yet' 'Gray'
        PaintFrame
        Start-Sleep $RefreshSeconds
        continue
    }

    $active = @()
    $recent = @()
    foreach ($d in $dirs) {
        $st = 'LIVE'
        if (Test-Path (Join-Path $d.FullName 'DONE')) { $st = 'DONE' }
        elseif (Test-Path (Join-Path $d.FullName 'FAILED')) { $st = 'FAILED' }
        elseif (Test-Path (Join-Path $d.FullName 'ABANDONED')) { $st = 'ABANDONED' }
        if ($st -eq 'LIVE') { $active += ,@($d, $st) }
        elseif ($recent.Count -lt 6) { $recent += ,@($d, $st) }
    }

    AddLine ('ACTIVE (' + $active.Count + ')') 'White'
    if ($active.Count -eq 0) { AddLine '  none - all agents idle' 'DarkGray' }
    foreach ($pair in $active) {
        $d = $pair[0]
        $stateP = Join-Path $d.FullName 'state.json'
        $kind = 'PROBE'
        if ($d.Name -like 'scout_*') { $kind = 'SCOUT' }
        $s = $null
        if (Test-Path $stateP) {
            try { $s = Get-Content -Raw $stateP | ConvertFrom-Json } catch { $s = $null }
        }
        if ($null -ne $s) {
            if ([string]$s.mission -eq 'scout') { $kind = 'SCOUT' }
            $age = -1
            try { $age = [int]((Get-Date).ToUniversalTime() - ([datetime]::Parse([string]$s.ts).ToUniversalTime())).TotalSeconds } catch { }
            $alive = $false
            try { $alive = ($null -ne (Get-Process -Id ([int]$s.pid) -ErrorAction SilentlyContinue)) } catch { }
            $head = ($kind.PadRight(7) + $d.Name + '   pid ' + $s.pid + '   beat ' + $age + 's')
            if ((-not $alive) -and ($age -gt 15)) {
                AddLine ('  ' + $head) 'Red'
                AddLine ('  ' + (Bar $s.pct 24) + '  ' + $s.pct + '%  STALLED - pid dead, no sentinel') 'Red'
            } else {
                AddLine ('  ' + $head) 'Cyan'
                AddLine ('  ' + (Bar $s.pct 24) + '  ' + ([string]$s.pct).PadLeft(3) + '%  [' + $s.done + '/' + $s.total + ']') 'Cyan'
                AddLine ('  phase ' + $s.phase + '   q ' + $s.question) 'DarkCyan'
            }
        } else {
            AddLine ('  ' + $kind.PadRight(7) + $d.Name) 'Yellow'
            AddLine ('  ' + (BootBar 24 $tick) + '  boot  (hython can take ~60s)') 'Yellow'
        }
    }

    AddLine ('-' * 78) 'Gray'
    AddLine 'RECENT' 'White'
    foreach ($pair in $recent) {
        $d = $pair[0]
        $st = $pair[1]
        $kind = 'PROBE'
        if ($d.Name -like 'scout_*') { $kind = 'SCOUT' }
        if ($st -eq 'DONE') {
            $info = ''
            try {
                $dd = Get-Content -Raw (Join-Path $d.FullName 'DONE') | ConvertFrom-Json
                $info = ('  entries=' + $dd.entries + ' failures=' + $dd.failures)
            } catch { }
            AddLine ('  ' + $kind.PadRight(7) + (Bar 100 12) + ' DONE   ' + $d.Name + $info) 'Green'
        } elseif ($st -eq 'FAILED') {
            AddLine ('  ' + $kind.PadRight(7) + (Bar 100 12) + ' FAILED ' + $d.Name) 'Red'
        } else {
            AddLine ('  ' + $kind.PadRight(7) + (Bar 0 12) + ' ABAND  ' + $d.Name) 'DarkYellow'
        }
    }

    $tailDir = $null
    if ($active.Count -gt 0) { $tailDir = $active[0][0].FullName }
    elseif ($dirs.Count -gt 0) { $tailDir = $dirs[0].FullName }
    if ($tailDir) {
        AddLine ('-' * 78) 'Gray'
        foreach ($log in @('run.out.log', 'run.err.log')) {
            $lp = Join-Path $tailDir $log
            if ((Test-Path $lp) -and ((Get-Item $lp).Length -gt 0)) {
                AddLine ('--- ' + (Split-Path -Leaf $tailDir) + ' : ' + $log + ' (tail) ---') 'DarkGray'
                Get-Content $lp -Tail 8 -ErrorAction SilentlyContinue | ForEach-Object { AddLine ([string]$_) 'Gray' }
            }
        }
    }

    PaintFrame
    Start-Sleep $RefreshSeconds
}
