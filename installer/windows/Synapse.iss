; Inno Setup owns Windows integration; setup_cli owns every Houdini/runtime file.
#ifndef StageDir
  #error StageDir is required; use installer/build_windows.py
#endif
#ifndef AppVersion
  #error AppVersion is required
#endif
#ifdef TestBuild
  #define ProductName "SYNAPSE (isolated test)"
  #define ProductId "SYNAPSE-Isolated-Installer-Test"
  #define OutputName "SYNAPSE-" + AppVersion + "-TestSetup"
#else
  #define ProductName "SYNAPSE"
  #define ProductId "SYNAPSE-Houdini-PerUser"
  #define OutputName "SYNAPSE-" + AppVersion + "-Setup"
#endif

[Setup]
AppId={#ProductId}
AppName={#ProductName}
AppVersion={#AppVersion}
AppVerName={#ProductName} {#AppVersion}
AppPublisher=SYNAPSE
DefaultDirName={localappdata}\Programs\SYNAPSE
DefaultGroupName={#ProductName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
DisableWelcomePage=no
DisableDirPage=no
DisableProgramGroupPage=yes
CloseApplications=no
RestartApplications=no
SetupMutex=SynapsePerUserSetup
UninstallDisplayName={#ProductName} {#AppVersion}
OutputDir={#StageDir}\..\output
OutputBaseFilename={#OutputName}
Compression=lzma2
SolidCompression=yes
SetupLogging=yes
LicenseFile={#StageDir}\license.txt
InfoBeforeFile={#StageDir}\before.txt
Uninstallable=yes
UsePreviousAppDir=yes

[Files]
Source: "{#StageDir}\maintenance\*"; DestDir: "{tmp}\boot"; Flags: dontcopy recursesubdirs
Source: "{#StageDir}\payload.zip"; DestDir: "{tmp}"; Flags: dontcopy
; Retain ownership metadata so reinstall recognizes leftover Python caches.
Source: "{#StageDir}\maintenance\maintenance-manifest.json"; DestDir: "{app}\maintenance"; Flags: ignoreversion uninsneveruninstall
Source: "{#StageDir}\maintenance\*"; DestDir: "{app}\maintenance"; Excludes: "maintenance-manifest.json"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\Getting started with SYNAPSE"; Filename: "{app}\maintenance\getting-started.html"
Name: "{group}\Verify SYNAPSE installation"; Filename: "{app}\maintenance\python\pythonw.exe"; Parameters: "-I ""{app}\maintenance\setup_cli.py"" verify --app ""{app}"" --show"; WorkingDir: "{app}\maintenance"
Name: "{group}\Uninstall SYNAPSE"; Filename: "{uninstallexe}"

[Code]
var
  HoudiniPage, PrefsPage: TInputDirWizardPage;
  Builds, PrefChoices: TNewComboBox;
  Compatibility, Migration: TNewCheckBox;
  SourceLabel: TNewStaticText;
  Boot, DiscoveryIni, ReportFile, TestRoot: String;
  DiscoveryCount: Integer;

function ReadNumber(Section, Key: String; Default: Integer; Filename: String): Integer;
begin
  Result := StrToIntDef(GetIniString(Section, Key, IntToStr(Default), Filename), Default);
end;

function Quoted(Value: String): String;
begin
  { Windows paths cannot contain quotes. The engine also validates paths. }
  Result := '"' + Value + '"';
end;

function SandboxArgs: String;
begin
  Result := '';
#ifdef TestBuild
  if TestRoot <> '' then Result := ' --sandbox ' + Quoted(TestRoot);
#endif
end;

function UserHome: String;
begin
  Result := GetEnv('USERPROFILE');
#ifdef TestBuild
  Result := AddBackslash(TestRoot) + 'home';
#endif
end;

function RunEngine(Base, Arguments: String): Boolean;
var Code: Integer;
begin
  Result := Exec(AddBackslash(Base) + 'python\python.exe',
    '-I ' + Quoted(AddBackslash(Base) + 'setup_cli.py') + ' ' + Arguments,
    Base, SW_HIDE, ewWaitUntilTerminated, Code);
  if Result then Result := Code = 0;
end;

function EngineError: String;
var Raw: AnsiString;
begin
  Result := 'Setup could not complete its checks. See the setup log and retry.';
  if LoadStringFromFile(ChangeFileExt(ReportFile, '.txt'), Raw) then
    Result := UTF8Decode(Raw);
end;

procedure PreferenceChanged(Sender: TObject);
begin
  if (Builds.ItemIndex >= 0) and (PrefChoices.ItemIndex >= 0) then begin
    PrefsPage.Values[0] := GetIniString(IntToStr(Builds.ItemIndex),
      'pref_' + IntToStr(PrefChoices.ItemIndex), '', DiscoveryIni);
    SourceLabel.Caption := GetIniString(IntToStr(Builds.ItemIndex),
      'source_' + IntToStr(PrefChoices.ItemIndex), '', DiscoveryIni);
  end;
end;

procedure BuildChanged(Sender: TObject);
var I, Count: Integer; Section, Value: String;
begin
  if Builds.ItemIndex < 0 then exit;
  Section := IntToStr(Builds.ItemIndex);
  HoudiniPage.Values[0] := GetIniString(Section, 'hfs', '', DiscoveryIni);
  Compatibility.Checked := False;
  PrefChoices.Items.Clear;
  Count := ReadNumber(Section, 'pref_count', 0, DiscoveryIni);
  for I := 0 to Count - 1 do begin
    Value := GetIniString(Section, 'pref_' + IntToStr(I), '', DiscoveryIni);
    PrefChoices.Items.Add(Value);
  end;
  if Count > 0 then begin
    PrefChoices.ItemIndex := 0;
    PreferenceChanged(nil);
  end;
#ifdef TestBuild
  PrefsPage.Values[0] := AddBackslash(TestRoot) + 'preferences\houdini22.0';
  SourceLabel.Caption := 'Isolated test preferences; artist settings will not be used.';
#endif
end;

procedure InitializeWizard;
var I: Integer; Title, Section: String; Progress: TOutputProgressWizardPage;
begin
  TestRoot := ExpandConstant('{param:TESTROOT|}');
#ifdef TestBuild
  if TestRoot = '' then RaiseException('The isolated test build requires /TESTROOT=<empty test folder>.');
  if ExpandConstant('{param:DIR|}') <> '' then
    WizardForm.DirEdit.Text := ExpandConstant('{param:DIR|}')
  else WizardForm.DirEdit.Text := AddBackslash(TestRoot) + 'application';
#endif
  Boot := ExpandConstant('{tmp}\boot');
  DiscoveryIni := ExpandConstant('{tmp}\discovery.ini');
  ReportFile := ExpandConstant('{tmp}\synapse-check.json');
  Progress := CreateOutputProgressPage('Preparing SYNAPSE {#AppVersion}', 'Finding Houdini installations and preference folders.');
  Progress.Show;
  try
    ExtractTemporaryFiles('{tmp}\boot\*');
    ExtractTemporaryFile('payload.zip');
    if not RunEngine(Boot, 'discover --ini ' + Quoted(DiscoveryIni) + ' --report ' + Quoted(ReportFile)) then
      RaiseException(EngineError);
  finally
    Progress.Hide;
  end;

  HoudiniPage := CreateInputDirPage(wpInfoBefore, 'Choose Houdini',
    'SYNAPSE {#AppVersion} - Windows',
    'Validation target: Houdini 22.0.400 with Python 3.13. Other builds require a compatibility acknowledgement.', False, '');
  HoudiniPage.Add('Houdini application folder:');
  Builds := TNewComboBox.Create(WizardForm);
  Builds.Parent := HoudiniPage.Surface;
  Builds.Top := ScaleY(100);
  Builds.Width := HoudiniPage.SurfaceWidth;
  Builds.Style := csDropDownList;
  Builds.OnChange := @BuildChanged;
  Compatibility := TNewCheckBox.Create(WizardForm);
  Compatibility.Parent := HoudiniPage.Surface;
  Compatibility.Top := ScaleY(148);
  Compatibility.Width := HoudiniPage.SurfaceWidth;
  Compatibility.Height := ScaleY(48);
  Compatibility.Caption := 'Allow a Houdini build with unverified compatibility';

  PrefsPage := CreateInputDirPage(HoudiniPage.ID, 'Choose Houdini preferences',
    'Register SYNAPSE for this Houdini preference folder',
    'Confirm the folder used by your Houdini launcher. You can browse to a custom or OneDrive location. Other preference folders are left alone.', False, '');
  PrefsPage.Add('Houdini preference folder:');
  PrefChoices := TNewComboBox.Create(WizardForm);
  PrefChoices.Parent := PrefsPage.Surface;
  PrefChoices.Top := ScaleY(100);
  PrefChoices.Width := PrefsPage.SurfaceWidth;
  PrefChoices.Style := csDropDownList;
  PrefChoices.OnChange := @PreferenceChanged;
  SourceLabel := TNewStaticText.Create(WizardForm);
  SourceLabel.Parent := PrefsPage.Surface;
  SourceLabel.Top := ScaleY(130);
  SourceLabel.Width := PrefsPage.SurfaceWidth;
  SourceLabel.Height := ScaleY(35);
  SourceLabel.WordWrap := True;
  Migration := TNewCheckBox.Create(WizardForm);
  Migration.Parent := PrefsPage.Surface;
  Migration.Top := ScaleY(177);
  Migration.Width := PrefsPage.SurfaceWidth;
  Migration.Height := ScaleY(50);
  Migration.Caption := 'Back up and replace existing SYNAPSE registration and interface files';
  DiscoveryCount := ReadNumber('discovery', 'count', 0, DiscoveryIni);
  for I := 0 to DiscoveryCount - 1 do begin
    Section := IntToStr(I);
    Title := 'Houdini ' + GetIniString(Section, 'version', '?', DiscoveryIni) +
      ' / Python ' + GetIniString(Section, 'python', '?', DiscoveryIni);
    if ReadNumber(Section, 'tested', 0, DiscoveryIni) = 1 then
      Title := Title + ' - tested target'
    else Title := Title + ' - compatibility unverified';
    Builds.Items.Add(Title);
  end;
  if DiscoveryCount > 0 then begin
    Builds.ItemIndex := 0;
    BuildChanged(nil);
  end;
  if ExpandConstant('{param:HFS|}') <> '' then HoudiniPage.Values[0] := ExpandConstant('{param:HFS|}');
  if ExpandConstant('{param:PREFS|}') <> '' then PrefsPage.Values[0] := ExpandConstant('{param:PREFS|}');
  Migration.Checked := ExpandConstant('{param:MIGRATE|0}') = '1';
  Compatibility.Checked := ExpandConstant('{param:ALLOWUNVERIFIED|0}') = '1';
end;

function InstallArguments(Action: String): String;
begin
  Result := Action + ' --app ' + Quoted(WizardDirValue) + ' --pref ' + Quoted(PrefsPage.Values[0]) +
    ' --home ' + Quoted(UserHome) + ' --hfs ' + Quoted(HoudiniPage.Values[0]) +
    ' --payload ' + Quoted(ExpandConstant('{tmp}\payload.zip')) + ' --report ' + Quoted(ReportFile) + SandboxArgs;
  if Migration.Checked then Result := Result + ' --migrate';
  if Compatibility.Checked then Result := Result + ' --allow-unverified';
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if WizardSilent and ((ExpandConstant('{param:HFS|}') = '') or (ExpandConstant('{param:PREFS|}') = '')) then begin
    Result := 'Silent installation requires explicit /HFS and /PREFS paths.';
    exit;
  end;
  if not RunEngine(Boot, InstallArguments('preflight')) then Result := EngineError;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    WizardForm.StatusLabel.Caption := 'Installing runtime and verifying every file and Houdini registration...';
#ifdef TestBuild
    SetIniString('Test', 'Root', TestRoot, ExpandConstant('{app}\maintenance\test-root.ini'));
#endif
    if not RunEngine(Boot, InstallArguments('install')) then RaiseException(EngineError);
    WizardForm.FinishedLabel.Caption := 'SYNAPSE {#AppVersion} files and registration passed verification.' + #13#10#13#10 +
      'Open Houdini, then New Pane Tab > Synapse. Use Doctor to check the running components.' + #13#10#13#10 +
      'Choose Connect models to select a model and check its connection. This is a separate setup step.' + #13#10#13#10 +
      'Package loading, panel opening and model access still require a check inside Houdini.';
  end;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo,
  MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
begin
  Result := 'SYNAPSE {#AppVersion}' + NewLine + NewLine + MemoDirInfo + NewLine + NewLine +
    'Houdini: ' + HoudiniPage.Values[0] + NewLine + 'Preferences: ' + PrefsPage.Values[0] + NewLine + NewLine +
    'Save and close Houdini before continuing. Setup will never close it for you.' + NewLine +
    'Projects, memory stores, credentials and unrelated settings are preserved.';
  if Migration.Checked then Result := Result + NewLine + 'Existing SYNAPSE registrations/interfaces will be backed up and replaced.';
end;

function InitializeUninstall: Boolean;
var Base: String;
begin
  Base := ExpandConstant('{app}\maintenance');
  ReportFile := ExpandConstant('{tmp}\synapse-uninstall-check.json');
  TestRoot := '';
#ifdef TestBuild
  TestRoot := GetIniString('Test', 'Root', '', Base + '\test-root.ini');
  if TestRoot = '' then begin
    SuppressibleMsgBox('Missing isolated-test root. Rerun the matching test setup with /TESTROOT before uninstalling.', mbError, MB_OK, IDOK);
    Result := False;
    exit;
  end;
#endif
  Result := RunEngine(Base, 'uninstall-check --app ' + Quoted(ExpandConstant('{app}')) + ' --report ' + Quoted(ReportFile) + SandboxArgs);
  if not Result then begin
    Log(EngineError);
    SuppressibleMsgBox(EngineError, mbError, MB_OK, IDOK);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    if not RunEngine(ExpandConstant('{app}\maintenance'), 'uninstall --app ' + Quoted(ExpandConstant('{app}')) +
      ' --report ' + Quoted(ReportFile) + SandboxArgs) then RaiseException(EngineError);
end;
