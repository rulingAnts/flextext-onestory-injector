; Inno Setup script -- compile on Windows with ISCC.exe after the
; PyInstaller build:
;     ISCC.exe packaging\installer.iss
; Produces: packaging\Output\FlexTextOneStoryInjector-Setup.exe
;
; Per-user install (no admin rights needed -- field machines rarely
; have them), which also keeps SmartScreen friction down.

[Setup]
AppName=FlexText OneStory Injector
AppVersion=0.1.0
AppPublisher=Seth Johnston
DefaultDirName={userpf}\FlexTextOneStoryInjector
DefaultGroupName=FlexText OneStory Injector
PrivilegesRequired=lowest
OutputBaseFilename=FlexTextOneStoryInjector-Setup
Compression=lzma2
SolidCompression=yes
LicenseFile=..\LICENSE

[Files]
Source: "..\dist\FlexTextOneStoryInjector\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\FlexText OneStory Injector"; Filename: "{app}\FlexTextOneStoryInjector.exe"
Name: "{userdesktop}\FlexText OneStory Injector"; Filename: "{app}\FlexTextOneStoryInjector.exe"

[Run]
Filename: "{app}\FlexTextOneStoryInjector.exe"; Description: "Launch now"; Flags: postinstall nowait skipifsilent
