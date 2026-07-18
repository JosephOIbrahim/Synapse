<#
  SYNAPSE render watcher — out-of-band observer for the render-freeze harness.

  WHY THIS EXISTS
  ---------------
  An in-process Karma render captures Houdini's main thread, so the panel AND
  the bridge freeze with it — every in-process instrument goes dark exactly
  when you need it. This watcher runs in a SEPARATE PowerShell process and reads
  Houdini from OUTSIDE, so it keeps seeing everything while the UI is frozen.

  It answers the capsule's core question — is a slow render actually WORKING
  (Karma XPU cold-compile) or truly HUNG (deadlock / device-init / license /
  modal)? — from three cheap, validated signals sampled ~1 Hz:

    * (Get-Process).Responding   -> True while the Qt loop pumps; False = frozen
    * process CPU delta          -> cores-busy (1 core = single-thread; many = render)
    * nvidia-smi GPU util        -> GPU busy = XPU actually rendering on the 4090
    * husk.exe present?          -> the render went OUT OF PROCESS (good / the fix working)

  SIGNATURE TABLE (printed live, one line per tick):
    LIVE .................. Responding=True. Not frozen.
    FROZEN / GPU-BUSY ..... not responding, GPU util high  -> XPU rendering on device (working)
    FROZEN / CPU-BUSY ..... not responding, many cores hot -> CPU render in progress (working)
    FROZEN / 1-CORE ....... not responding, ~one core hot  -> single-thread busy (shader compile / SOHO)
    FROZEN / IDLE ......... not responding, CPU~0 + GPU~0   -> TRUE HANG: deadlock/device-init/license/modal

  USAGE (run BEFORE you trigger a render):
    pwsh -File scripts\render_watch.ps1
    # or target a specific pid / faster tick:
    pwsh -File scripts\render_watch.ps1 -HoudiniPid 59300 -IntervalSec 0.5

  Ctrl+C to stop. A timestamped CSV log is written under <repo>\.synapse\ and is
  flushed every tick, so it survives a force-kill of Houdini during the freeze.
#>

param(
    [int]    $HoudiniPid       = 0,        # 0 = auto-detect houdini.exe
    [double] $IntervalSec      = 1.0,      # sample cadence
    [string] $LogDir           = "",       # default <repo>\.synapse
    [int]    $SustainedFreezeSec = 5,      # how long before we shout "capture + relaunch"
    [int]    $GpuBusyPct       = 20,       # GPU util >= this = "GPU busy"
    [double] $ManyCoresBusy    = 4.0,      # cores-busy >= this = "many cores"
    [double] $OneCoreBusy      = 0.5,      # cores-busy >= this (and < many) = "~one core"
    [int]    $MaxSamples       = 0         # 0 = run until Ctrl+C; >0 = take N samples then exit (baseline mode)
)

$ErrorActionPreference = 'Continue'

# ---- resolve target process --------------------------------------------------
if ($HoudiniPid -eq 0) {
    $cands = Get-Process -Name houdini* -ErrorAction SilentlyContinue
    if (-not $cands) { Write-Host "No houdini.exe running. Launch Houdini first, then re-run." -ForegroundColor Red; exit 1 }
    $HoudiniPid = ($cands | Sort-Object CPU -Descending | Select-Object -First 1).Id
}
$proc = Get-Process -Id $HoudiniPid -ErrorAction SilentlyContinue
if (-not $proc) { Write-Host "No process with PID $HoudiniPid." -ForegroundColor Red; exit 1 }

# ---- resolve log dir (repo = parent of this script's dir) --------------------
if ([string]::IsNullOrWhiteSpace($LogDir)) {
    $repo   = Split-Path -Parent $PSScriptRoot
    $LogDir = Join-Path $repo ".synapse"
}
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
$stamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
$log   = Join-Path $LogDir "render_watch_$stamp.log"
"# SYNAPSE render_watch  pid=$HoudiniPid  cores=$([Environment]::ProcessorCount)  start=$(Get-Date -Format o)" | Out-File $log -Encoding utf8
"iso,elapsed_s,responding,cores_busy,cpu_pct_all,gpu_util,gpu_mem_mb,gpu_temp,husk_procs,state" | Out-File $log -Append -Encoding utf8

$hasNvidia = $null -ne (Get-Command nvidia-smi -ErrorAction SilentlyContinue)
$numCores  = [Environment]::ProcessorCount

Write-Host ""
Write-Host "SYNAPSE render watcher armed." -ForegroundColor Cyan
Write-Host "  pid=$HoudiniPid  cores=$numCores  interval=${IntervalSec}s  nvidia-smi=$hasNvidia"
Write-Host "  log: $log"
Write-Host "  Trigger ONE render now. Ctrl+C to stop." -ForegroundColor Cyan
Write-Host ""

# ---- prime CPU delta ---------------------------------------------------------
$lastCpu  = $proc.CPU
$lastTime = Get-Date
$t0       = $lastTime
$freezeStart = $null
$shouted     = $false
$sampleCount = 0

function Get-GpuSample {
    if (-not $hasNvidia) { return @{ util = -1; mem = -1; temp = -1 } }
    try {
        $csv = (& nvidia-smi --query-gpu=utilization.gpu,memory.used,temperature.gpu --format=csv,noheader,nounits 2>$null | Select-Object -First 1)
        $p = $csv -split ','
        return @{ util = [int]($p[0].Trim()); mem = [int]($p[1].Trim()); temp = [int]($p[2].Trim()) }
    } catch { return @{ util = -1; mem = -1; temp = -1 } }
}

while ($true) {
    Start-Sleep -Seconds $IntervalSec
    $now  = Get-Date
    $proc = Get-Process -Id $HoudiniPid -ErrorAction SilentlyContinue
    if (-not $proc) {
        $line = "$($now.ToString('o')),$([math]::Round(($now-$t0).TotalSeconds,1)),EXITED,,,,,,,HOUDINI_EXITED"
        $line | Out-File $log -Append -Encoding utf8
        Write-Host "[$($now.ToString('HH:mm:ss'))] HOUDINI PROCESS GONE (exited or was force-killed)." -ForegroundColor Magenta
        break
    }

    $wall      = [math]::Max(($now - $lastTime).TotalSeconds, 0.001)
    $coresBusy = ($proc.CPU - $lastCpu) / $wall           # 1.0 = one core-second per wall-second
    $cpuPctAll = [math]::Round(($coresBusy / $numCores) * 100, 1)
    $coresBusy = [math]::Round($coresBusy, 2)
    $lastCpu   = $proc.CPU
    $lastTime  = $now

    $gpu       = Get-GpuSample
    $husk      = @(Get-Process -Name husk -ErrorAction SilentlyContinue).Count
    $mantra    = @(Get-Process -Name mantra -ErrorAction SilentlyContinue).Count
    $responding = $proc.Responding

    # ---- classify ------------------------------------------------------------
    if ($responding) {
        $state = "LIVE"; $color = "Green"; $freezeStart = $null; $shouted = $false
    }
    else {
        if ($freezeStart -eq $null) { $freezeStart = $now }
        if ($gpu.util -ge $GpuBusyPct) {
            $state = "FROZEN/GPU-BUSY (XPU rendering on device -- working)"; $color = "Yellow"
        }
        elseif ($coresBusy -ge $ManyCoresBusy) {
            $state = "FROZEN/CPU-BUSY (CPU render in progress -- working)"; $color = "Yellow"
        }
        elseif ($coresBusy -ge $OneCoreBusy) {
            $state = "FROZEN/1-CORE (single-thread busy -- shader compile / SOHO)"; $color = "Yellow"
        }
        else {
            $state = "FROZEN/IDLE (no CPU, no GPU -- TRUE HANG: deadlock/device-init/license/modal)"; $color = "Red"
        }
    }

    $subProc = @(); if ($husk -gt 0) { $subProc += "husk=$husk" }; if ($mantra -gt 0) { $subProc += "mantra=$mantra" }
    $huskTag = if ($subProc.Count -gt 0) { "  [" + ($subProc -join ' ') + " OUT-OF-PROCESS]" } else { "" }
    $elapsed = [math]::Round(($now - $t0).TotalSeconds, 1)
    Write-Host ("[{0}] {1,-6} cores={2,5} ({3,4}%)  GPU={4,3}% {5,5}MB {6}C{7}  | {8}" -f `
        $now.ToString('HH:mm:ss'), $(if($responding){'LIVE'}else{'FROZEN'}), $coresBusy, $cpuPctAll, `
        $gpu.util, $gpu.mem, $gpu.temp, $huskTag, $state) -ForegroundColor $color

    "$($now.ToString('o')),$elapsed,$responding,$coresBusy,$cpuPctAll,$($gpu.util),$($gpu.mem),$($gpu.temp),$husk,`"$state`"" |
        Out-File $log -Append -Encoding utf8

    # ---- sustained-freeze shout (once) --------------------------------------
    if ($freezeStart -ne $null -and -not $shouted) {
        $frozenFor = ($now - $freezeStart).TotalSeconds
        if ($frozenFor -ge $SustainedFreezeSec) {
            $shouted = $true
            Write-Host ""
            Write-Host "  >>> SUSTAINED FREEZE ($([math]::Round($frozenFor))s). Snapshot captured to log." -ForegroundColor Magenta
            Write-Host "  >>> Verdict signal: $state" -ForegroundColor Magenta
            if ($husk -gt 0) {
                Write-Host "  >>> husk.exe IS running -> render is out-of-process; you can kill husk without killing Houdini:" -ForegroundColor Magenta
                Write-Host "      Get-Process husk | Stop-Process -Force" -ForegroundColor DarkGray
            } else {
                Write-Host "  >>> No husk subprocess -> render is IN-PROCESS; only a Houdini relaunch clears it." -ForegroundColor Magenta
            }
            # rich one-shot snapshot for the log
            "# --- SUSTAINED FREEZE SNAPSHOT $($now.ToString('o')) ---" | Out-File $log -Append -Encoding utf8
            "# houdini threads=$($proc.Threads.Count)  ws_gb=$([math]::Round($proc.WorkingSet64/1GB,2))" | Out-File $log -Append -Encoding utf8
            if ($hasNvidia) {
                "# gpu compute apps:" | Out-File $log -Append -Encoding utf8
                (& nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>$null) | Out-File $log -Append -Encoding utf8
            }
            Write-Host ""
        }
    }

    $sampleCount++
    if ($MaxSamples -gt 0 -and $sampleCount -ge $MaxSamples) {
        Write-Host "  (reached -MaxSamples $MaxSamples -- exiting baseline run)" -ForegroundColor DarkGray
        break
    }
}

Write-Host ""
Write-Host "Watcher stopped. Log: $log" -ForegroundColor Cyan
