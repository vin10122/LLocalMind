; Compile through tools/build_windows_installer.py with Inno Setup 6.3+.
; Keep this AppId stable: new releases upgrade the same per-user installation.
#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef SourceDir
  #error SourceDir is required
#endif
#ifndef ReleaseDir
  #error ReleaseDir is required
#endif

[Setup]
AppId={{B644D036-5385-40F5-9D76-B6A08E0527EC}
AppName=LLocalMind
AppVersion={#AppVersion}
AppPublisher=LLocalMind
AppPublisherURL=https://github.com/vin10122/Intel-optimized-MoE-streaming
DefaultDirName={localappdata}\Programs\LLocalMind
DefaultGroupName=LLocalMind
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#ReleaseDir}
OutputBaseFilename=LLocalMind-Setup-{#AppVersion}-windows-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\LLocalMind.exe
UsePreviousAppDir=yes

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Excludes: "*.gguf,*.log,data\*,models\*,updates\*"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\LLocalMind"; Filename: "{app}\LLocalMind.exe"
Name: "{autodesktop}\LLocalMind"; Filename: "{app}\LLocalMind.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crea un collegamento sul desktop"; Flags: unchecked

[Run]
Filename: "{app}\LLocalMind.exe"; Description: "Avvia LLocalMind"; Flags: nowait postinstall skipifsilent
Filename: "{app}\LLocalMind.exe"; Flags: nowait; Check: ShouldRelaunch

[Code]
function ShouldRelaunch: Boolean;
begin
  Result := WizardSilent and (ExpandConstant('{param:RELAUNCH|0}') = '1');
end;

; No [InstallDelete] or [UninstallDelete]: user data and external GGUFs
; are never deleted. All releases retain the same per-user AppId.
