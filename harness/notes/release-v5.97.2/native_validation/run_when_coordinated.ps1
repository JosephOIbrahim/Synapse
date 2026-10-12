param(
 [Parameter(Mandatory=$true)][string]$SlotReceipt,
 [Parameter(Mandatory=$true)][string]$SlotSha256,
 [switch]$ValidateOnly
)
$ErrorActionPreference='Stop'
$prepRoot=$PSScriptRoot
function Require($value,[string]$message){if(-not $value){throw $message}}
function Hash([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
$pinPath=Join-Path $prepRoot 'prepared-pins.json'
$pinHash=Hash $pinPath
$pins=Get-Content -LiteralPath $pinPath -Raw | ConvertFrom-Json
$receiptPath=[IO.Path]::GetFullPath($SlotReceipt)
Require ((Hash $receiptPath) -ceq $SlotSha256) 'Receipt hash differs'
$receipt=Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
Require ($receipt.commit -ceq 'b7301f3f985d1c0a9876b8ee629472392422bc26') 'Wrong candidate'
Require ($receipt.prepared_pins_sha256 -ceq $pinHash) 'Unapproved test pins'
Require ($receipt.native_clearance -eq $true -and $receipt.indie_clearance -eq $true -and $receipt.resource_owner_clearance -eq $true -and $receipt.live_gui_preserved_clearance -eq $true) 'Coordinated native/Indie/resource-owner/live-GUI preservation clearance absent'
Require (@($receipt.phases).Count -eq 2 -and 'build' -cin $receipt.phases -and 'reopen' -cin $receipt.phases) 'Need precisely two phases'
Require ($receipt.run_id -match '^[a-z0-9][a-z0-9-]{0,48}$') 'Unsafe run identifier'
Require ($receipt.limits.processes -eq 2 -and $receipt.limits.threads -eq 2 -and $receipt.limits.child_seconds -eq 120 -and $receipt.limits.aggregate_seconds -eq 300 -and $receipt.limits.memory_bytes -eq 4GB -and $receipt.limits.artifact_bytes -eq 64MB) 'Receipt limit mismatch'
Require ($receipt.resource_snapshot.free_memory_bytes -ge 8GB -and $receipt.resource_snapshot.cpu_load_percent -le 50 -and $receipt.resource_snapshot.cpu_load_percent -ge 0 -and $receipt.resource_snapshot.artifact_free_bytes -ge 256MB) 'Insufficient supplied resource headroom'
$now=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
Require ($receipt.resource_snapshot.checked_unix -le $now -and $now-$receipt.resource_snapshot.checked_unix -le 60) 'Parent resource snapshot older than sixty seconds'
Require ($receipt.not_before_unix -le $now -and $receipt.expires_unix-$now -ge 300) 'Need fresh five-minute slot'
Require ($receipt.handoff_launch_by_unix -ge $now) 'Owner launch deadline absent/missed'
function Assert-Pins{
 Require ((Hash $pinPath) -ceq $pinHash -and (Hash $receiptPath) -ceq $SlotSha256) 'Pins/slot revoked or changed'
 foreach($row in $pins.files){Require ((Hash (Join-Path $prepRoot $row.path)) -ceq $row.sha256) ('Changed preparation pin: '+$row.path)}
 foreach($row in $pins.runtime_files){Require ((Hash $row.path) -ceq $row.sha256) 'Changed runtime file'}
}
Assert-Pins
if($ValidateOnly){[pscustomobject]@{status='STATIC_RECEIPT_PINS_ONLY';native_processes=0;prepared_pins_sha256=$pinHash}|ConvertTo-Json;exit 0}
$runRoot=Join-Path $prepRoot ('runs/'+$receipt.run_id)
Require (-not (Test-Path -LiteralPath $runRoot)) 'Run root already exists; no automatic retries'
New-Item -ItemType Directory -Path $runRoot | Out-Null
$nativePython='C:\Program Files\Side Effects Software\Houdini 22.0.400\python313\python.exe'
$hfs='C:\Program Files\Side Effects Software\Houdini 22.0.400'
$clock=[Diagnostics.Stopwatch]::StartNew()
$active=$null;$records=@();$status='FAILED_OR_BLOCKED';$failure=$null
function Read-LicenseReachability{
 $client=[Net.Sockets.TcpClient]::new()
 $timer=[Diagnostics.Stopwatch]::StartNew()
 $observation=[ordered]@{utc=[DateTimeOffset]::UtcNow.ToString('o');endpoint='127.0.0.1:1714';connected=$false;error=$null;elapsed_seconds=0;scope='TCP connect only; no licensing request, native import or service start'}
 try{
  $task=$client.ConnectAsync('127.0.0.1',1714)
  if(-not $task.Wait(2000)){throw 'Existing licence service reachability timed out'}
  $observation.connected=$client.Connected
 }catch{$observation.error=$_.Exception.ToString()}
 finally{$observation.elapsed_seconds=$timer.Elapsed.TotalSeconds;$client.Dispose()}
 return [pscustomobject]$observation
}
try{
 foreach($phase in @('build','reopen')){
  Assert-Pins
  Require (-not (Test-Path -LiteralPath (Join-Path $runRoot 'CANCEL'))) 'Coordinator cancelled'
  Require ($clock.Elapsed.TotalSeconds -le 160 -and $receipt.expires_unix-[DateTimeOffset]::UtcNow.ToUnixTimeSeconds() -ge 140) 'No remaining child/cleanup window'
  $reachability=Read-LicenseReachability
  [IO.File]::WriteAllText((Join-Path $runRoot ($phase+'-license-reachability.json')), ($reachability|ConvertTo-Json), [Text.UTF8Encoding]::new($false))
  Require ($reachability.connected -eq $true) 'Existing licence-service access unavailable; no native process may start'
  if($phase -ceq 'build'){Require ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() -le $receipt.handoff_launch_by_unix) 'Owner launch deadline elapsed before child creation'}
  $phaseDir=Join-Path $runRoot ($phase+'-environment');New-Item -ItemType Directory -Path $phaseDir | Out-Null
  $start=[Diagnostics.ProcessStartInfo]::new($nativePython)
  $start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.WorkingDirectory=$phaseDir
  $start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
  foreach($arg in @('-I','-S','-B',(Join-Path $prepRoot 'native_probe.py'),'--phase',$phase,'--slot',$receiptPath,'--slot-sha256',$SlotSha256,'--run-root',$runRoot)){$start.ArgumentList.Add($arg)}
  if($pins.execution_mode -ceq 'focused-state-diagnostics'){$start.ArgumentList.Add('--diagnostic')}
  foreach($key in @('PYTHONPATH','PYTHONHOME','HSITE','HOUDINI_PACKAGE_DIR','HOUDINI_DSO_PATH','HOUDINI_OTLSCAN_PATH','HOUDINI_SCRIPT_PATH','PXR_PLUGINPATH_NAME','SYNAPSE_MEMORY_BACKEND','HOUDINI_LIC_OPT','HOUDINI_CORE_LIC_OPT','HOUDINI_FX_LIC_OPT','HOUDINI_INDIE_LIC_OPT','HOUDINI_NC_LIC_OPT','HOUDINI_EXPER_LIC_OPT')){$start.Environment.Remove($key)|Out-Null}
  $values=@{HFS=$hfs;HOUDINI_PATH=($hfs+'\houdini');HOUDINI_PACKAGE_SKIP='1';HOUDINI_NO_ENV_FILE='1';HOUDINI_MAXTHREADS='2';OMP_NUM_THREADS='2';TBB_NUM_THREADS='2';HOUDINI_NOHKEY='1';HOUDINI_SCRIPT_LICENSE='hbatch';HOUDINI_HYTHON_LIC_OPT='--skip-license-modes=commercial,education,apprentice';HOUDINI_ANONYMOUS_STATISTICS='0';HOUDINI_PROMPT_ON_CRASHES='0';HOUDINI_DISABLE_PDG='1';HOUDINI_DISABLE_CONSOLE='1';HOUDINI_NO_START_PAGE_SPLASH='1';HOUDINI_USER_PREF_DIR=($phaseDir+'\prefs__HVER__');HOUDINI_TEMP_DIR=$phaseDir;HOUDINI_BACKUP_DIR=$phaseDir;TEMP=$phaseDir;TMP=$phaseDir;SYNAPSE_LOG_DIR=($phaseDir+'\logs');SYNAPSE_BRIDGE_FILE=($phaseDir+'\unused-bridge.json')}
  foreach($key in $values.Keys){$start.Environment[$key]=$values[$key]}
  # Child-local vendor startup requirements. Parent process/system environment unchanged.
  $start.Environment['PATH']=(Join-Path $hfs 'bin')+';'+$start.Environment['PATH']
  $start.Environment['HB']=Join-Path $hfs 'bin'
  $start.Environment['HHP']=Join-Path $hfs 'houdini/python3.13libs'
  $phaseClock=[Diagnostics.Stopwatch]::StartNew()
  $active=[Diagnostics.Process]::Start($start)
  $active.PriorityClass=[Diagnostics.ProcessPriorityClass]::BelowNormal
  $stdout=$active.StandardOutput.ReadToEndAsync();$stderr=$active.StandardError.ReadToEndAsync()
  $maxPrivate=0L;$maxWorking=0L;$limitReason=$null
  while(-not $active.WaitForExit(500)){
   $active.Refresh();$maxPrivate=[Math]::Max($maxPrivate,$active.PrivateMemorySize64);$maxWorking=[Math]::Max($maxWorking,$active.WorkingSet64)
   $bytes=(Get-ChildItem -LiteralPath $runRoot -File -Recurse | Measure-Object -Property Length -Sum).Sum
   if($phaseClock.Elapsed.TotalSeconds -gt 120 -or $clock.Elapsed.TotalSeconds -gt 280){$limitReason='time ceiling'}
   elseif($maxPrivate -gt 4GB -or $maxWorking -gt 4GB){$limitReason='sampled memory ceiling'}
   elseif($bytes -gt 64MB){$limitReason='artifact ceiling'}
   elseif((Test-Path -LiteralPath (Join-Path $runRoot 'CANCEL')) -or (Hash $receiptPath) -cne $SlotSha256){$limitReason='slot revoked'}
   if($limitReason){$active.Kill();Require ($active.WaitForExit(5000)) 'Owned worker termination unconfirmed';break}
  }
  [IO.File]::WriteAllText((Join-Path $runRoot ($phase+'-stdout.log')),$stdout.GetAwaiter().GetResult())
  [IO.File]::WriteAllText((Join-Path $runRoot ($phase+'-stderr.log')),$stderr.GetAwaiter().GetResult())
  $records+=[pscustomobject]@{phase=$phase;pid=$active.Id;exit_code=$active.ExitCode;wall_seconds=$phaseClock.Elapsed.TotalSeconds;max_private_bytes=$maxPrivate;max_working_bytes=$maxWorking;limit_reason=$limitReason}
  Require (-not $limitReason -and $active.ExitCode -eq 0) ('Native phase failed: '+$phase)
  $result=Get-Content -LiteralPath (Join-Path $runRoot ($phase+'.json')) -Raw | ConvertFrom-Json
  $expectedStatus=if($pins.execution_mode -ceq 'focused-state-diagnostics'){'DIAGNOSTIC_OBSERVATIONS_COMPLETE'}else{'ASSERTIONS_PASSED'}
  Require ($result.status -ceq $expectedStatus) 'Missing expected native assertion/diagnostic receipt'
  if($pins.execution_mode -ceq 'full-qualification'){
   if($phase -ceq 'build'){Require ($result.product_rollback_gate -ceq 'PASS' -and @($result.recovery).Count -eq 3 -and @($result.cases).Count -eq 7 -and @($result.controls).Count -eq 21) 'Full native recovery/case/control gate incomplete'}
   else{Require (@($result.reopened).Count -eq 7 -and @($result.reopened|Where-Object {$_.reopen -cne 'PASS' -or $_.replay -cne 'PASS'}).Count -eq 0) 'Full fresh-process reopen/replay gate incomplete'}
  }
  $gatePath=Join-Path $runRoot ($phase+'-native-gate.json')
  $gate=Get-Content -LiteralPath $gatePath -Raw | ConvertFrom-Json
  Require ($gate.status -ceq 'PASSED' -and $gate.actual_build -ceq '22.0.400' -and $gate.actual_license_category -ceq 'licenseCategoryType.Indie' -and $gate.candidate_imported -eq $false -and $result.early_native_gate_sha256 -ceq (Hash $gatePath)) 'Missing/unexpected persisted early native identity gate'
  $active=$null
 }
 $status=if($pins.execution_mode -ceq 'focused-state-diagnostics'){'DIAGNOSTIC_OBSERVATIONS_COMPLETE'}else{'NATIVE_ASSERTIONS_COMPLETE'}
}catch{$failure=$_.Exception.Message}
finally{
 if($null -ne $active -and -not $active.HasExited){$active.Kill();$active.WaitForExit(5000)|Out-Null}
 $scope=if($pins.execution_mode -ceq 'focused-state-diagnostics'){'Focused state diagnostics collected; strict equality outcomes remain explicit; no qualification PASS'}else{'candidate native assertions; separate product rollback gate and release gaps remain'}
 $result=[ordered]@{status=$status;commit=$receipt.commit;prepared_pins_sha256=$pinHash;slot_sha256=$SlotSha256;children=$records;wall_seconds=$clock.Elapsed.TotalSeconds;failure=$failure;scope=$scope;limits='sampled watchdog limits, not kernel resource caps; own root process only'}
 [IO.File]::WriteAllText((Join-Path $runRoot 'controller.json'), ($result|ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
}
if($status -notin @('NATIVE_ASSERTIONS_COMPLETE','DIAGNOSTIC_OBSERVATIONS_COMPLETE')){exit 2}
